import sys
from pathlib import Path
import re

def main(args):
    base = Path.cwd()
    if not (base / 'gcloud').is_dir():
        print("Script must be run from directory containing the gcloud folder.")
        sys.exit(1)

    files = [f'File{num}' for num in args]
    output_path = base / 'gcloud' / 'false_positives_report.txt'

    for_report_line = re.compile(r'Number of False Positive Runs:\s*(\d+)')

    with output_path.open('w', encoding='utf-8') as outf:
        for file in files:
            filedir = base / 'gcloud' / file
            outf.write(f"{file}:\n")
            found_any = False
            for i in range(1, 36):
                relayer_dir = filedir / f'Relayer{i}'
                prob_file = relayer_dir / 'probabilityReport.txt'
                if prob_file.is_file():
                    with prob_file.open('r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            m = for_report_line.search(line)
                            if m:
                                num_fp = int(m.group(1))
                                if num_fp > 0:
                                    found_any = True
                                    outf.write(f"  Relayer{i}: Number of False Positive Runs: {num_fp}\n")
                                break
            # Add fullDownloadReport.txt (indented)
            full_download_path = filedir / 'fullDownloadReport.txt'
            if full_download_path.is_file():
                outf.write("\n")
                # Try reading as utf-8 first, then fallback to utf-16
                try:
                    with full_download_path.open('r', encoding='utf-8') as f:
                        lines = f.readlines()
                except UnicodeDecodeError:
                    with full_download_path.open('r', encoding='utf-16') as f:
                        lines = f.readlines()
                for line in lines:
                    outf.write(f"  {line.rstrip()}\n")
            outf.write("\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python false_positive_report.py 1 2 3 ... 11")
        sys.exit(1)
    main(sys.argv[1:])
