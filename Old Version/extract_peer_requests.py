import re
from pathlib import Path

root = Path(".")

ip_port_regex = re.compile(
    r"^(\d+\.\d+\.\d+\.\d+:\d+)\s+had a run\. Requests: \d+, Duplicates: \d+, Inserts: \d+, Adj\. Requests: \d+, Passes Levine: Yes, Levine Downloader probability: [\d\.]+"
)

found_filefolders = list(root.glob("File*"))
if not found_filefolders:
    print("No File* folders found in current directory.")
    exit(1)

for file_folder in found_filefolders:
    relayer_folders = list(file_folder.glob("Relayer*"))
    if not relayer_folders:
        print(f"No Relayer* folders found in {file_folder}")
        continue

    for relayer_folder in relayer_folders:
        prob_report = relayer_folder / "probabilityReport.txt"
        req_file = relayer_folder / "downloadRequests.txt"

        if not prob_report.exists():
            print(f"Missing {prob_report}")
            continue
        if not req_file.exists():
            print(f"Missing {req_file}")
            continue

        # Get all IP:ports with Passes Levine: Yes
        ip_ports = []
        with prob_report.open("r", encoding="utf-8") as f:
            for line in f:
                m = ip_port_regex.match(line.strip())
                if m:
                    ip_ports.append(m.group(1))
        if not ip_ports:
            print(f"No IP:ports matched regex in {prob_report}")
            continue

        # For each IP:port, find matching lines in downloadRequests.txt and write output
        with req_file.open("r", encoding="utf-8") as reqf:
            all_req_lines = reqf.readlines()

        for ip_port in ip_ports:
            matches = [l for l in all_req_lines if ip_port in l]
            if not matches:
                print(f"No matches for {ip_port} in {req_file}")
                continue
            safe_ip_port = ip_port.replace('.', '_').replace(':', '_')
            out_file = relayer_folder / f"requests_{safe_ip_port}.txt"
            with out_file.open('w', encoding='utf-8') as outf:
                outf.writelines(matches)
            print(f"Wrote {len(matches)} lines for {ip_port} to {out_file}")

print("Script complete.")
