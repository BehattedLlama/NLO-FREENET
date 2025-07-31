import os
from pathlib import Path
from datetime import datetime

def iso_to_excel(iso_str):
    # Converts ISO 8601 to Excel serial date (days since 1899-12-30)
    dt = datetime.strptime(iso_str.split(',')[0], "%Y-%m-%dT%H:%M:%S.%f")
    excel_epoch = datetime(1899, 12, 30)
    delta = dt - excel_epoch
    return f"{delta.days + delta.seconds / 86400 + delta.microseconds / 86400 / 1e6:.4f}"

root = Path(".")

for file_folder in root.glob("File*"):
    downloader_dir = file_folder / "Downloader"
    prob_report = downloader_dir / "probabilityReport.txt"
    # Read total blocks and unique requests (data blocks)
    total_blocks = data_blocks = None
    if prob_report.exists():
        with prob_report.open("r", encoding="utf-8") as pr:
            for line in pr:
                # Robust, case-insensitive, space-insensitive matching
                lcline = line.lower().strip()
                if "total number of blocks for file:" in lcline:
                    total_blocks = line.strip().split(":")[1].strip()
                if "unique requests sent:" in lcline:
                    data_blocks = line.strip().split(":")[1].strip()
    if not total_blocks or not data_blocks:
        # Uncomment for troubleshooting:
        # print(f"Skipping {prob_report} (total_blocks={total_blocks}, data_blocks={data_blocks})")
        continue  # Skip this file if missing info

    for relayer_folder in file_folder.glob("Relayer*"):
        for reqs_file in relayer_folder.glob("requests_*.txt"):
            out_file = reqs_file.parent / ("summary_ready_" + reqs_file.name[len("requests_"):])
            with reqs_file.open("r", encoding="utf-8") as infile, out_file.open("w", encoding="utf-8") as outfile:
                for line in infile:
                    fields = line.strip().split(',')
                    if len(fields) < 9:
                        continue
                    excel_date = iso_to_excel(fields[0])
                    blank_port = ""
                    req_type = "R" if fields[1] == "FNPCHKDataRequest" else ("I" if fields[1] == "FNPInsertRequest" else "?")
                    htl = fields[4]
                    split_key = fields[2]
                    peers = fields[8]
                    le_id = fields[5]  # IP:Port
                    # Tab-delimited: Date/Time, Port(blank), Type, HTL, Total Blocks, Data Blocks, Peers, LE ID, Split Keys
                    output_line = f"{excel_date}\t{blank_port}\t{req_type}\t{htl}\t{total_blocks}\t{data_blocks}\t{peers}\t{le_id}\t{split_key}\n"
                    outfile.write(output_line)
