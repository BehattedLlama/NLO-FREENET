#!/usr/bin/env python3
import os
import math
import shutil
import re
import argparse
import json
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import time

# ---- Globals controlled by CLI ----
FORCE_REPROCESS = False

# ---- Constants matching Levine 2017 Whitepaper constants ----
RUN_MIN_REQUESTS = 20
PROB_THRESHOLD = 0.98

# ---- Regexes for postprocessing ----
PASS_RUN_RE = re.compile(
    r'^(\d+\.\d+\.\d+\.\d+:\d+)\s+had a run\. Requests: \d+, Duplicates: \d+, Inserts: \d+, Adj\. Requests: \d+, Passes Levine: Yes, Levine Downloader probability: ([\d\.]+)',
    re.IGNORECASE
)
FP_LINE_RE = re.compile(r'Number of False Positive Runs:\s*(\d+)', re.IGNORECASE)

# ---- Numeric helpers (Levine method) ----

def log_binomial_pmf(k, n, p):
    if p <= 0 or p >= 1:
        if p == 0:
            return 0.0 if k == 0 else float('-inf')
        if p == 1:
            return 0.0 if k == n else float('-inf')
    if k < 0 or k > n:
        return float('-inf')
    log_comb = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    return log_comb + k * math.log(p) + (n - k) * math.log(1 - p)

def binomial_pmf(k, n, p):
    lp = log_binomial_pmf(k, n, p)
    if lp == float('-inf'):
        return 0.0
    return math.exp(lp)

def calc_even_share_probability(g, T, r):
    if g <= 0 or T < 0 or r < 0:
        return 0.0
    inv_g = 1.0 / g
    inv_g8 = 1.0 / (g * 8.0)
    numerator = (1.0 / (g + 1.0)) * binomial_pmf(r, T, inv_g)
    alternate = (g / (g + 1.0)) * binomial_pmf(r, T, inv_g8)
    denom = numerator + alternate
    if denom == 0:
        return 0.0
    return numerator / denom

# ---- Parsing helpers ----

def parse_request_line(line):
    parts = line.rstrip("\n").split(',')
    if len(parts) < 9:
        raise ValueError("Malformed request line")
    timestamp = parts[0]
    req_type = parts[1]
    key = parts[2]
    request_loc = parts[3]
    htl = parts[4]
    ip = parts[5]
    try:
        num_peers = float(parts[8])
    except Exception:
        num_peers = 0.0
    time_seconds = None
    if 'T' in timestamp:
        try:
            time_part = timestamp.split('T', 1)[1]
            h, m, s = time_part.split(':')
            time_seconds = int(h) * 3600 + int(m) * 60 + int(float(s))
        except Exception:
            time_seconds = None
    return {
        'timestamp_raw': timestamp,
        'req_type': req_type,
        'key': key,
        'request_loc': request_loc,
        'htl': htl,
        'ip': ip,
        'num_peers': num_peers,
        'time_seconds': time_seconds,
    }

def read_and_split(path: Path):
    try:
        return path.read_text(encoding='utf-8').splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding='utf-16', errors='ignore').splitlines()

def iso_to_excel(iso_str):
    iso_str = iso_str.strip().split(',')[0]
    fmt = "%Y-%m-%dT%H:%M:%S.%f" if '.' in iso_str else "%Y-%m-%dT%H:%M:%S"
    try:
        dt = datetime.strptime(iso_str, fmt)
    except ValueError:
        try:
            dt = datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return ""
    epoch = datetime(1899, 12, 30)
    delta = dt - epoch
    serial = delta.days + (delta.seconds + delta.microseconds / 1e6) / 86400
    return f"{serial:.4f}"

# ---- Excel safety escaping ----

def escape_for_excel(cell: str) -> str:
    if not cell:
        return cell
    if cell[0] in ('-', '+', '=', '@'):
        return "'" + cell
    return cell

# ---- Directory helpers to mitigate transient Windows race conditions ----

def ensure_dir(path: Path):
    for attempt in range(5):
        try:
            path.mkdir(parents=True, exist_ok=True)
            return
        except PermissionError:
            time.sleep(0.1 * (attempt + 1))
    path.mkdir(parents=True, exist_ok=True)

# ---- Log location helper ----

def locate_requests_log(instance_name: str, start_dir: Path) -> Path | None:
    filename = f"requests_{instance_name}.log"
    cur = start_dir
    for _ in range(5):
        candidate = cur / filename
        if candidate.exists():
            return candidate
        cur = cur.parent
    return None

# ---- Override loader ----

def load_overrides():
    overrides_path = Path("overrides.json")
    if not overrides_path.exists():
        return {}
    try:
        return json.loads(overrides_path.read_text(encoding='utf-8'))
    except Exception:
        return {}

# ---- Derive relayer IP via key overlap (tightened) ----

def derive_relayer_ip_from_overlap(inst: Path) -> str:
    MIN_OVERLAP = 3
    MIN_RATIO = 0.5  # at least 50% of relayer forwarded keys must align with a single downloader dest

    parent_file_dir = inst.parent  # FileN/
    downloader_requests = parent_file_dir / "downloader" / "downloadRequests.txt"
    if not downloader_requests.exists():
        return ""

    dest_to_keys = defaultdict(set)
    with downloader_requests.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                rec = parse_request_line(line)
            except Exception:
                continue
            dest_ipport = rec['ip']
            key = rec['key']
            dest_to_keys[dest_ipport].add(key)

    relayer_keys = set()
    download_reqs_path = inst / "downloadRequests.txt"
    if not download_reqs_path.exists():
        return ""
    with download_reqs_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                rec = parse_request_line(line)
            except Exception:
                continue
            if 'insert' in rec['req_type'].lower():
                continue
            relayer_keys.add(rec['key'])

    if not relayer_keys:
        return ""

    best_ip = ""
    best_overlap = 0
    best_ratio = 0.0
    for cand_ip, keys in dest_to_keys.items():
        overlap = len(relayer_keys & keys)
        if overlap == 0:
            continue
        ratio = overlap / len(relayer_keys)
        if overlap > best_overlap or (overlap == best_overlap and ratio > best_ratio):
            best_overlap = overlap
            best_ratio = ratio
            best_ip = cand_ip

    if best_overlap >= MIN_OVERLAP and best_ratio >= MIN_RATIO:
        return best_ip
    return ""

# ---- FTS block writer (corrected) ----

def write_fts_block_final(out_path: Path, relayer_name: str, overrides: dict, le_ipport: str,
                          run_start_excel: str, run_end_excel: str,
                          detail_rows: list[str], manifest_key: str, subject_ip: str):
    le_ip, le_port = (le_ipport.split(':', 1) + [""])[:2]
    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"{relayer_name}\t\n")
        f.write(f"My Status\t{overrides.get('My Status','')}\n")
        f.write(f"Iccacops Status\t{overrides.get('Iccacops Status','')}\n")
        f.write(f"ISP:\t{overrides.get('ISP','')}\n")
        f.write(f"Location\t{overrides.get('Location','')}\n")
        f.write(f"IP Address\t{subject_ip}\n")  # relayer's IP
        f.write(f"Location ID\t{overrides.get('Location ID','')}\n")
        f.write(f"LE ID\t{le_port}\n")
        f.write(f"Filename\t{overrides.get('Filename','')}\n")
        f.write(f"SHA1 hex\t{overrides.get('SHA1 hex','')}\n")
        f.write(f"SHA1 base32\t{overrides.get('SHA1 base32','')}\n")
        f.write(f"SHA256\t{overrides.get('SHA256','')}\n")
        f.write(f"Manifest key\t{manifest_key}\n")
        f.write(f"Run Start\t{run_start_excel}\n")
        f.write(f"Run End\t{run_end_excel}\n")
        f.write("\n")
        f.write("Date/Time\tPort\tType\tHTL\tTotal Blocks\tData Blocks\tPeers\tLE ID\tSplit Keys\n")
        for row in detail_rows:
            f.write(row.rstrip("\n") + "\n")

# ---- Core logic for a single (manifest, instance) pair ----

def process_instance_pair(manifest_name, instance_name):
    base = Path.cwd()
    manifest_path = base / manifest_name
    if not manifest_path.exists():
        print(f"[WARN] manifest missing: {manifest_name}")
        return
    if not manifest_name.startswith("downloadKeys_File") or not manifest_name.endswith(".txt"):
        return
    file_number = manifest_name[len("downloadKeys_File"):-4]
    file_dir = base / f"File{file_number}"
    inst_dir = file_dir / instance_name
    ensure_dir(inst_dir)

    prob_report_path = inst_dir / "probabilityReport.txt"
    if prob_report_path.exists() and not FORCE_REPROCESS:
        return

    shutil.copy2(manifest_path, inst_dir / "downloadKeys.txt")
    process_instance(inst_dir, is_downloader=(instance_name == "downloader"))

def process_instance(instance_folder: Path, is_downloader=False):
    cwd = os.getcwd()
    os.chdir(instance_folder)
    try:
        with open("downloadKeys.txt", 'r', encoding='utf-8', errors='ignore') as f:
            keys = [l.strip() for l in f if l.strip()]

        instance_name = instance_folder.name
        logpath = locate_requests_log(instance_name, instance_folder)
        if logpath is None:
            print(f"[ERROR] no requests_{instance_name}.log found in {instance_folder} or upward")
            return

        filtered_lines = []
        parsed_records = []
        ip_add = []
        num_peers_vals = []
        request_locs = []
        with open(logpath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if not line.strip():
                    continue
                if any(k in line for k in keys):
                    filtered_lines.append(line.rstrip("\n"))
                    try:
                        rec = parse_request_line(line)
                    except ValueError:
                        continue
                    parsed_records.append(rec)
                    ip_add.append(rec['ip'])
                    num_peers_vals.append(rec['num_peers'])
                    request_locs.append(rec['request_loc'])

        with open("downloadRequests.txt", "w") as f:
            for l in filtered_lines:
                f.write(l + "\n")
        with open("requestLocs.txt", "w") as f:
            for loc in request_locs:
                f.write(loc + "\n")
        avg_peers = sum(num_peers_vals) / len(num_peers_vals) if num_peers_vals else 0.0
        with open("avgPeers.txt", "w") as f:
            f.write(f"{avg_peers}\n")
        ip_counts = Counter(ip_add)
        with open("sentToPeer.txt", "w") as f:
            for ip, cnt in ip_counts.items():
                f.write(f"{ip}   was sent {cnt} requests\n")

        per_peer = defaultdict(lambda: {
            'raw_requests': [],
            'non_insert_requests': [],
            'key_freq': Counter(),
            'insert_count': 0,
            'htl_counts': {'16':0, '17':0, '18':0},
            'timestamps': [],
            'request_locs': [],
        })
        for rec in parsed_records:
            peer = rec['ip']
            entry = per_peer[peer]
            line_repr = ",".join([
                rec['timestamp_raw'],
                rec['req_type'],
                rec['key'],
                rec['request_loc'],
                rec['htl'],
                rec['ip'],
                "", "",
            ])
            entry['raw_requests'].append(line_repr)
            entry['request_locs'].append(rec['request_loc'])

            if 'insert' in rec['req_type'].lower():
                entry['insert_count'] += 1
            else:
                entry['non_insert_requests'].append(line_repr)
                entry['key_freq'][rec['key']] += 1

            if rec['htl'] in ('16','17','18'):
                entry['htl_counts'][rec['htl']] += 1
            if rec['time_seconds'] is not None:
                entry['timestamps'].append(rec['time_seconds'])

        for entry in per_peer.values():
            entry['timestamps'].sort()

        peer_order = []
        with open("sentToPeer.txt", "r") as f:
            for ln in f:
                if not ln.strip():
                    continue
                peer_order.append(ln.strip().split()[0])

        duplicates_list = []
        inserts_list = []
        data_requests_num_list = []
        htl_lines = []
        avg_intervals = []

        for idx, peer in enumerate(peer_order, start=1):
            entry = per_peer.get(peer, {
                'raw_requests': [],
                'non_insert_requests': [],
                'key_freq': Counter(),
                'insert_count': 0,
                'htl_counts': {'16':0, '17':0, '18':0},
                'timestamps': [],
                'request_locs': [],
            })

            keys_file = f"keys{idx}.txt"
            requests_file = f"requests{idx}.txt"
            timestamps_file = f"requestTimestamps{idx}.txt"
            intervals_file = f"requestIntervals{idx}.txt"
            data_only_file = f"dataRequestsOnly{idx}.txt"

            with open(keys_file, "w") as f:
                for line in entry['raw_requests']:
                    try:
                        parsed = parse_request_line(line)
                    except Exception:
                        continue
                    f.write(parsed['key'] + "\n")

            with open(requests_file, "w") as f:
                for line in entry['raw_requests']:
                    f.write(line + "\n")

            with open(timestamps_file, "w") as f:
                for ts in entry['timestamps']:
                    f.write(f"{ts}\n")

            intervals = []
            for i in range(1, len(entry['timestamps'])):
                intervals.append(entry['timestamps'][i] - entry['timestamps'][i-1])
            with open(intervals_file, "w") as f:
                for iv in intervals:
                    f.write(f"{iv}\n")
            if intervals:
                avg_intervals.append(sum(intervals)/len(intervals))
            else:
                avg_intervals.append(float('nan'))

            with open(data_only_file, "w") as f:
                for line in entry['non_insert_requests']:
                    f.write(line + "\n")

            duplicates = sum(c*(c-1)//2 for c in entry['key_freq'].values())
            inserts = entry['insert_count']
            data_requests_num = len(entry['non_insert_requests'])
            htl_line = f"HTL 18: {entry['htl_counts'].get('18',0)}, HTL 17: {entry['htl_counts'].get('17',0)}, HTL 16: {entry['htl_counts'].get('16',0)}"

            duplicates_list.append(str(duplicates))
            inserts_list.append(str(inserts))
            data_requests_num_list.append(str(data_requests_num))
            htl_lines.append(htl_line)

        with open("avgIntervals.txt", "w") as f:
            for v in avg_intervals:
                if isinstance(v, float) and math.isnan(v):
                    f.write("nan\n")
                else:
                    f.write(f"{v}\n")
        with open("duplicates.txt", "w") as f:
            for l in duplicates_list:
                f.write(l + "\n")
        with open("inserts.txt", "w") as f:
            for l in inserts_list:
                f.write(l + "\n")
        with open("dataRequestsNum.txt", "w") as f:
            for l in data_requests_num_list:
                f.write(l + "\n")
        with open("HTL.txt", "w") as f:
            for l in htl_lines:
                f.write(l + "\n")

        peer_list_for_report = peer_order
        adj_requests_sent = sum(int(x) for x in data_requests_num_list if x.isdigit())
        try:
            with open("avgPeers.txt", "r") as f:
                avg_peers = float(f.read().strip())
        except Exception:
            avg_peers = 0.0
        with open("downloadKeys.txt", "r") as f:
            blocks = [l for l in (x.rstrip("\n") for x in f) if l != ""]
        total_blocks = len(blocks)
        T = int(0.8 * total_blocks)

        report_lines = []
        num_runs = 0
        false_positive = 0
        true_positive = 0
        unique_peers_count = len(per_peer)

        for idx, peer in enumerate(peer_list_for_report):
            # Match Excel behavior: "requests" is unique non-insert requests (Total Unique Requests)
            requests = int(data_requests_num_list[idx]) if idx < len(data_requests_num_list) and data_requests_num_list[idx].isdigit() else 0
            inserts_cnt = int(inserts_list[idx]) if idx < len(inserts_list) and inserts_list[idx].isdigit() else 0
            duplicates_cnt = int(duplicates_list[idx]) if idx < len(duplicates_list) and duplicates_list[idx].isdigit() else 0

            adj_requests = requests - inserts_cnt - 3 * duplicates_cnt
            if adj_requests < 0:
                adj_requests = 0

            if requests >= RUN_MIN_REQUESTS:
                num_runs += 1
                prob = calc_even_share_probability(avg_peers, T, adj_requests)
                passes = prob > PROB_THRESHOLD
                if passes:
                    if is_downloader:
                        true_positive += 1
                    else:
                        false_positive += 1
                decision = "Yes" if passes else "No"
                report_lines.append(
                    f"{peer} had a run. Requests: {requests}, Duplicates: {duplicates_cnt}, Inserts: {inserts_cnt}, "
                    f"Adj. Requests: {adj_requests}, Passes Levine: {decision}, Levine Downloader probability: {prob:.6f}"
                )
            else:
                report_lines.append(
                    f"{peer} did not see a run. Requests: {requests}, Duplicates: {duplicates_cnt}, Inserts: {inserts_cnt}, "
                    f"Adj. Requests: {adj_requests}"
                )

        report_lines.append("")
        report_lines.append(f"Average Peers: {avg_peers}")
        report_lines.append(f"Number of Unique Peers Requests were Sent To: {unique_peers_count}")
        if unique_peers_count > 0:
            report_lines.append(f"Percent of Runs out of Peers Requests were Sent To: {100.0 * (num_runs / unique_peers_count):.2f} %")
        else:
            report_lines.append("Percent of Runs out of Peers Requests were Sent To:  0 %")
        report_lines.append(f"Number of Runs: {num_runs}")
        if not is_downloader:
            report_lines.append(f"Number of False Positive Runs: {false_positive}")
            if num_runs > 0:
                report_lines.append(f"Local Rate of False Positive Runs: {100.0 * (false_positive / num_runs):.2f} %")
            else:
                report_lines.append("Local Rate of False Positive Runs: Not Applicable")
        else:
            report_lines.append(f"Number of True Positive Runs: {true_positive}")
            if num_runs > 0:
                report_lines.append(f"Local Rate of True Positive Runs: {100.0 * (true_positive / num_runs):.2f} %")
            else:
                report_lines.append("Local Rate of True Positive Runs: Not Applicable")
            report_lines.append(f"Total Number of Blocks for File: {total_blocks}")
            report_lines.append(f"Unique Requests sent: {adj_requests_sent}")
            if total_blocks > 0:
                report_lines.append(f"Percent of File Requested: {100.0 * adj_requests_sent / total_blocks:.2f} %")
            else:
                report_lines.append("Percent of File Requested: 0 %")

        with open("probabilityReport.txt", "w") as f:
            for l in report_lines:
                f.write(l + "\n")

        extract_peer_requests_for_instance(is_downloader)

    finally:
        os.chdir(cwd)

# ---- Post-processing helpers ----

def extract_peer_requests_for_instance(is_downloader_flag):
    inst = Path.cwd()
    relayer_name = inst.name
    prob_report = inst / "probabilityReport.txt"
    download_requests = inst / "downloadRequests.txt"
    if not prob_report.exists() or not download_requests.exists():
        return

    ip_ports = []
    for line in read_and_split(prob_report):
        m = PASS_RUN_RE.match(line.strip())
        if m:
            ip_ports.append(m.group(1))
    if not ip_ports:
        return

    req_lines = download_requests.read_text(encoding='utf-8', errors='ignore').splitlines()
    overrides_all = load_overrides()

    total_blocks = ""
    data_blocks = ""
    for line in read_and_split(prob_report):
        low = line.lower()
        if "total number of blocks for file:" in low:
            parts = line.split(":", 1)
            if len(parts) > 1:
                total_blocks = parts[1].strip()
        if "unique requests sent:" in low:
            parts = line.split(":", 1)
            if len(parts) > 1:
                data_blocks = parts[1].strip()

    avg_peers = 0.0
    if (inst / "avgPeers.txt").exists():
        try:
            with open("avgPeers.txt", "r") as f:
                avg_peers = float(f.read().strip())
        except:
            avg_peers = 0.0

    percent_file_requested = ""
    if is_downloader_flag:
        for line in read_and_split(prob_report):
            if line.lower().startswith("percent of file requested:"):
                pct = line.split(":", 1)[1].strip()
                percent_file_requested = pct

    manifest_key = ""
    dk_path = inst / "downloadKeys.txt"
    if dk_path.exists():
        try:
            manifest_key = dk_path.read_text(encoding='utf-8', errors='ignore').splitlines()[0].strip()
        except Exception:
            manifest_key = ""

    for ip_port in ip_ports:
        matches = [l for l in req_lines if ip_port in l]
        if not matches:
            continue
        safe = ip_port.replace('.', '_').replace(':', '_')
        out_req = inst / f"requests_{safe}.txt"
        with out_req.open('w', encoding='utf-8') as f:
            for l in matches:
                f.write(l + "\n")

        detail_rows = []
        total_blocks_for_detail = total_blocks
        data_blocks_for_detail = data_blocks
        for line in matches:
            parts = line.strip().split(',')
            if len(parts) < 9:
                continue
            excel_date = iso_to_excel(parts[0])
            port = ip_port.split(':', 1)[1]
            req_type = "R" if parts[1].strip() == "FNPCHKDataRequest" else ("I" if parts[1].strip() == "FNPInsertRequest" else "?")
            htl = parts[4].strip()
            peers = parts[8].strip()
            le_ip = escape_for_excel(parts[5].strip())
            split_key = escape_for_excel(parts[2].strip())
            detail_line = "\t".join([
                excel_date,
                port,
                req_type,
                htl,
                total_blocks_for_detail,
                data_blocks_for_detail,
                peers,
                le_ip,
                split_key
            ])
            detail_rows.append(detail_line)

        run_start_excel = ""
        run_end_excel = ""
        if matches:
            excels = []
            for line in matches:
                p = line.strip().split(',')
                if p:
                    excel = iso_to_excel(p[0])
                    excels.append(excel)
            if excels:
                run_start_excel = excels[0]
                run_end_excel = excels[-1]

        key_name = f"{relayer_name}_{ip_port.replace(':', '_')}"
        overrides = overrides_all.get(key_name, {})

        subject_ip = derive_relayer_ip_from_overlap(inst)

        fts_path = inst / f"FTS-{safe}.txt"
        write_fts_block_final(
            out_path=fts_path,
            relayer_name=relayer_name,
            overrides=overrides,
            le_ipport=ip_port,
            run_start_excel=run_start_excel,
            run_end_excel=run_end_excel,
            detail_rows=detail_rows,
            manifest_key=manifest_key,
            subject_ip=subject_ip or overrides.get("IP Address", "")
        )

def generate_false_positive_index(file_numbers):
    base = Path.cwd()
    out_path = base / "false_positives_report.txt"
    with out_path.open("w", encoding="utf-8") as outf:
        for num in file_numbers:
            folder = base / f"File{num}"
            if not folder.exists():
                continue
            outf.write(f"File{num}:\n")
            for i in range(1, 36):
                relayer_dir = folder / f"Relayer{i}"
                prob_file = relayer_dir / "probabilityReport.txt"
                if not prob_file.exists():
                    continue
                for line in read_and_split(prob_file):
                    m = FP_LINE_RE.search(line)
                    if m:
                        num_fp = int(m.group(1))
                        if num_fp > 0:
                            outf.write(f"  Relayer{i}: Number of False Positive Runs: {num_fp}\n")
                        break
            full_download = folder / "fullDownloadReport.txt"
            if full_download.exists():
                outf.write("\n")
                for line in read_and_split(full_download):
                    outf.write(f"  {line}\n")
            outf.write("\n")

def generate_per_file_reports(file_numbers):
    base = Path.cwd()
    for num in file_numbers:
        folder = base / f"File{num}"
        if not folder.exists():
            continue

        full_dl_path = folder / "fullDownloadReport.txt"
        with full_dl_path.open("w", encoding="utf-8") as f_full:
            f_full.write(f"File{num} Summary:\n")
            dl_dir = folder / "downloader"
            if dl_dir.exists():
                pr = dl_dir / "probabilityReport.txt"
                if pr.exists():
                    f_full.write("Downloader:\n")
                    for line in read_and_split(pr):
                        f_full.write(f"  {line}\n")
            for i in range(1, 36):
                rel_dir = folder / f"Relayer{i}"
                pr = rel_dir / "probabilityReport.txt"
                if not pr.exists():
                    continue
                f_full.write(f"\nRelayer{i}:\n")
                for line in read_and_split(pr):
                    f_full.write(f"  {line}\n")

        dup_report = folder / "duplicatesReport.txt"
        with dup_report.open("w", encoding="utf-8") as f_dup:
            f_dup.write(f"Duplicates report for File{num}\n")
            for i in range(1, 36):
                rel_dir = folder / f"Relayer{i}"
                dups = rel_dir / "duplicates.txt"
                if dups.exists():
                    vals = [l.strip() for l in read_and_split(dups) if l.strip()]
                    f_dup.write(f"Relayer{i}: {' '.join(vals)}\n")

        ins_report = folder / "insertsReport.txt"
        with ins_report.open("w", encoding="utf-8") as f_ins:
            f_ins.write(f"Inserts report for File{num}\n")
            for i in range(1, 36):
                rel_dir = folder / f"Relayer{i}"
                ins = rel_dir / "inserts.txt"
                if ins.exists():
                    vals = [l.strip() for l in read_and_split(ins) if l.strip()]
                    f_ins.write(f"Relayer{i}: {' '.join(vals)}\n")

        avg_timing = folder / "avgTimingReport.txt"
        with avg_timing.open("w", encoding="utf-8") as f_avg:
            f_avg.write(f"Average timing (intervals) for File{num}\n")
            for i in range(1, 36):
                rel_dir = folder / f"Relayer{i}"
                avg_int = rel_dir / "avgIntervals.txt"
                if avg_int.exists():
                    vals = [l.strip() for l in read_and_split(avg_int) if l.strip()]
                    f_avg.write(f"Relayer{i}: {' '.join(vals)}\n")

        requests_txt = folder / "Requests.txt"
        with requests_txt.open("w", encoding="utf-8") as f_req:
            f_req.write(f"Relayers with pass runs for File{num}\n")
            for i in range(1, 36):
                rel_dir = folder / f"Relayer{i}"
                pr = rel_dir / "probabilityReport.txt"
                if not pr.exists():
                    continue
                for line in read_and_split(pr):
                    if "Passes Levine: Yes" in line:
                        f_req.write(f"Relayer{i}: {line}\n")
                        break

        meta_txt = folder / "Metadata.txt"
        with meta_txt.open("w", encoding="utf-8") as f_meta:
            f_meta.write(f"File{num} Metadata\n")
            if (folder / "downloader").exists():
                pr = folder / "downloader" / "probabilityReport.txt"
                if pr.exists():
                    for line in read_and_split(pr):
                        low = line.lower()
                        if "total number of blocks for file" in low or "unique requests sent:" in low:
                            f_meta.write(f"{line}\n")

        csv_path = folder / f"File{num}_summary.csv"
        headers = [
            "ExcelDate", "Port", "Type", "HTL", "TotalBlocks", "DataBlocks",
            "Peers", "LE_IP", "SplitKey", "SourceRelayer", "IPPortRun"
        ]
        with csv_path.open("w", encoding="utf-8") as f_csv:
            f_csv.write(",".join(headers) + "\n")
            for i in range(1, 36):
                rel_dir = folder / f"Relayer{i}"
                if not rel_dir.exists():
                    continue
                for fts in rel_dir.glob("FTS-*.txt"):
                    ipport = fts.name[len("FTS-"):]
                    with fts.open("r", encoding='utf-8', errors='ignore') as fin:
                        lines = fin.read().splitlines()
                        try:
                            idx = lines.index("Date/Time\tPort\tType\tHTL\tTotal Blocks\tData Blocks\tPeers\tLE ID\tSplit Keys")
                        except ValueError:
                            continue
                        for detail in lines[idx+1:]:
                            parts = detail.split("\t")
                            if len(parts) < 9:
                                continue
                            excel_date, port, req_type, htl, total_blocks, data_blocks, peers, le_ip, split_key = parts[:9]
                            row = [
                                excel_date, port, req_type, htl, total_blocks, data_blocks,
                                peers, le_ip, split_key, f"Relayer{i}", ipport
                            ]
                            f_csv.write(",".join(row) + "\n")

# ---- Entry point with parallelization, resume, and progress summary ----

def main():
    global FORCE_REPROCESS
    parser = argparse.ArgumentParser(description="Parallelized, resumable Freenet Levine pipeline")
    parser.add_argument("--files", nargs="*", help="File numbers to process (e.g., 1 2 3). If omitted, auto-discovers all downloadKeys_File*.txt.")
    parser.add_argument("--no-parallel", action="store_true", help="Disable parallel execution (run serially).")
    parser.add_argument("--force", action="store_true", help="Re-run even if output already exists (overrides resume checkpoint).")
    args = parser.parse_args()

    if args.force:
        FORCE_REPROCESS = True

    inst_file = Path("instancesNames.txt")
    if not inst_file.exists():
        print("[FATAL] missing instancesNames.txt")
        return
    instances = [l.strip() for l in inst_file.read_text().splitlines() if l.strip()]

    if args.files and len(args.files) > 0:
        file_nums = args.files
    else:
        file_nums = []
        for path in sorted(Path(".").glob("downloadKeys_File*.txt")):
            name = path.name
            if name.startswith("downloadKeys_File") and name.endswith(".txt"):
                num = name[len("downloadKeys_File"):-4]
                file_nums.append(num)
    if not file_nums:
        print("[FATAL] no downloadKeys_File*.txt manifests found")
        return

    jobs = []
    for num in file_nums:
        manifest = f"downloadKeys_File{num}.txt"
        for inst in instances:
            jobs.append((manifest, inst))

    failed_jobs = []
    total_jobs = len(jobs)

    def format_duration(seconds):
        if seconds < 0:
            return "unknown"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h{m:02d}m{s:02d}s"
        if m:
            return f"{m}m{s:02d}s"
        return f"{s}s"

    completed = 0
    start_time = time.time()
    avg_duration = None
    alpha = 0.2

    if args.no_parallel:
        for manifest, inst in jobs:
            job_start = time.time()
            try:
                process_instance_pair(manifest, inst)
                job_status = "OK"
            except Exception as e:
                failed_jobs.append((manifest, inst, str(e)))
                print(f"[ERROR] {manifest}/{inst} failed: {e}")
                job_status = "FAIL"
            job_elapsed = time.time() - job_start

            if avg_duration is None:
                avg_duration = job_elapsed
            else:
                avg_duration = alpha * job_elapsed + (1 - alpha) * avg_duration

            completed += 1
            total_elapsed = time.time() - start_time
            remaining = total_jobs - completed
            rate = 1.0 / avg_duration if avg_duration > 0 else 0
            eta = remaining * avg_duration

            slow_marker = " (slow)" if job_elapsed > 2 * avg_duration else ""
            pct = (completed / total_jobs) * 100
            eta_str = format_duration(eta) if completed >= 5 else "estimating..."
            print(f"[JOB DONE] {manifest}/{inst} took {format_duration(job_elapsed)}{slow_marker} [{job_status}]")
            print(f"[PROGRESS] {completed}/{total_jobs} ({pct:.1f}%) done. Failures: {len(failed_jobs)}. Elapsed: {format_duration(total_elapsed)}, ETA: {eta_str}, rate: {rate:.2f} jobs/sec.")
    else:
        max_workers = max(1, (os.cpu_count() or 1) - 1)
        print(f"[START] parallel execution using {max_workers} workers, force={'yes' if FORCE_REPROCESS else 'no'}")
        with ProcessPoolExecutor(max_workers=max_workers) as exe:
            future_to_job = {}
            submit_times = {}
            for m, i in jobs:
                fut = exe.submit(process_instance_pair, m, i)
                future_to_job[fut] = (m, i)
                submit_times[fut] = time.time()

            for fut in as_completed(future_to_job):
                manifest, inst = future_to_job[fut]
                real_start = submit_times.get(fut, time.time())
                job_elapsed = time.time() - real_start
                try:
                    fut.result()
                    job_status = "OK"
                except Exception as e:
                    failed_jobs.append((manifest, inst, str(e)))
                    print(f"[ERROR] {manifest}/{inst} failed: {e}")
                    job_status = "FAIL"

                if avg_duration is None:
                    avg_duration = job_elapsed
                else:
                    avg_duration = alpha * job_elapsed + (1 - alpha) * avg_duration

                completed += 1
                total_elapsed = time.time() - start_time
                remaining = total_jobs - completed
                rate = 1.0 / avg_duration if avg_duration > 0 else 0
                eta = remaining * avg_duration

                slow_marker = " (slow)" if job_elapsed > 2 * avg_duration else ""
                pct = (completed / total_jobs) * 100
                eta_str = format_duration(eta) if completed >= 5 else "estimating..."
                print(f"[JOB DONE] {manifest}/{inst} took {format_duration(job_elapsed)}{slow_marker} [{job_status}]")
                print(f"[PROGRESS] {completed}/{total_jobs} ({pct:.1f}%) done. Failures: {len(failed_jobs)}. Elapsed: {format_duration(total_elapsed)}, ETA: {eta_str}, rate: {rate:.2f} jobs/sec.")

    generate_false_positive_index(file_nums)
    generate_per_file_reports(file_nums)

    if failed_jobs:
        summary_path = Path("failed_jobs_summary.txt")
        with summary_path.open("w", encoding="utf-8") as sf:
            sf.write(f"Total jobs: {total_jobs}\n")
            sf.write(f"Failed jobs: {len(failed_jobs)}\n\n")
            for manifest, inst, err in failed_jobs:
                sf.write(f"{manifest}/{inst}: {err}\n")
        print(f"[DONE] pipeline complete with failures. See false_positives_report.txt and {summary_path} for details.")
    else:
        print("[DONE] pipeline complete. No failed jobs. See false_positives_report.txt for summary.")

if __name__ == "__main__":
    main()
