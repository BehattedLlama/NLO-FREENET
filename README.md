# Levine Method Pipeline

## Overview

`LevineMethod.py` is a unified, parallel, resumable forensics-grade pipeline that replaces the previous multi-script toolchain. It ingests Freenet request logs and download key manifests, applies the Levine Method algorithm to detect runs and compute false/true positive statistics, and emits all intermediate and summary artifacts needed for audit, discovery, and direct ingestion into the FTS Excel tool (via `FTS-<ipport>.txt` files). The script assumes that the user can independently create the required Freenet nodes, connect them, log requests for test file downloads, and collect the relevant logs to a working folder with names matching the user's instanceNames.txt (default instance names are downloader, relayer1, relayer2 . . . relayerN).

## Required inputs (working directory)

The script must be run from a directory containing:

1. **`instancesNames.txt`**

   * Plain-text list of node roles, one per line (e.g., `downloader`, `relayer1`, ..., `relayer35`).

2. **`requests_<instance>.log`**

   * Raw outgoing block request logs for each controlled node. Example filenames: `requests_downloader.log`, `requests_relayer7.log`, etc.

3. **`downloadKeys_File<N>.txt`**

   * Manifest files for each file being downloaded, e.g., `downloadKeys_File1.txt`, containing the key hashes relevant to that file.
     
## Output structure

For each manifest and instance pair (e.g., `File1/downloader`, `File1/Relayer29`) the pipeline generates:

* Filtered request data: `downloadRequests.txt`, `requestLocs.txt`, `avgPeers.txt`, `sentToPeer.txt`.
* Per-peer breakdowns: `keys<N>.txt`, `requests<N>.txt`, `requestTimestamps<N>.txt`, `requestIntervals<N>.txt`, `dataRequestsOnly<N>.txt`.
* Metrics: `duplicates.txt`, `inserts.txt`, `avgIntervals.txt`, `HTL.txt`, `dataRequestsNum.txt`.
* Levine Method summary: `probabilityReport.txt`.
* Extraction for passes: `requests_<safe_ipport>.txt` and `FTS-<safe_ipport>.txt` (formatted for direct paste into the FTS Excel tool).
* Per-file aggregate reports under `File<N>/`: `false_positives_report.txt`, `fullDownloadReport.txt`, `duplicatesReport.txt`, `insertsReport.txt`, `avgTimingReport.txt`, `Metadata.txt`, and `File<N>_summary.csv`.

Directory example after run:

```
./downloadKeys_File1.txt
./instancesNames.txt
./requests_downloader.log
./requests_relayerX.log
./File1/
  downloader/
    probabilityReport.txt
    FTS-<ipport>.txt
    ...
  Relayer29/
    ...
  fullDownloadReport.txt
  duplicatesReport.txt
  ...
```

## Dependencies

* **Python 3.9+** (recommended 3.11+). Only standard library modules are used; no external packages required.

## Usage

```sh
python LevineMethod.py [--files 1 2 3 ...] [--force] [--no-parallel]
```

### Arguments

* `--files`: List of file numbers to process (e.g., `1 2 3`). If omitted, the script autodiscovers all `downloadKeys_File*.txt` in the current directory and processes them.
* `--force`: Recompute everything for the specified file(s) regardless of existing outputs (overrides resume checkpoints).
* `--no-parallel`: Disable parallel execution and run serially.

## Parallelism

By default the script detects available logical CPUs and uses `(cores - 1)` workers, reserving one core for system responsiveness. It scales down automatically on lower-core systems; no manual tuning is required unless you explicitly disable it with `--no-parallel`.

## Resume behavior

On reruns the pipeline skips instance-level work if the corresponding `probabilityReport.txt` already exists unless `--force` is provided. Aggregate per-file reports (false positives index, full download summary, CSVs, etc.) are regenerated every execution for the targeted files.

## Examples

Process all discovered files with fresh computations:

```sh
python LevineMethod.py --force
```

Process only File1 through File3:

```sh
python LevineMethod.py --files 1 2 3
```

Run a single file serially for inspection:

```sh
python LevineMethod.py --files 5 --no-parallel --force
```

## Forensic intent

All intermediate artifacts are preserved to establish a full audit trail: filtered requests, per-peer breakdowns, run decisions, and FTS-ready summaries. This makes the output suitable for discovery and independent validation by third parties.
