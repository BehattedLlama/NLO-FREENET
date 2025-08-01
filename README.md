# Freenet/Hyphanet Outgoing Request Log Analysis

> **Scripts and tooling for parsing, organizing, and applying the Levine Method to Freenet/Hyphanet outgoing request logs.**

---

## Overview

This repository contains scripts designed to analyze outgoing request logs from downloader and relayer nodes within Freenet/Hyphanet. Logs are parsed, organized per test file, and evaluated using the **Levine Method** to detect anomalous request patterns and estimate false positive rates.

---

## Directory Structure (Example)

After processing logs, your working directory structure will look similar to this:  
Working/
├──File1/  
| ├── avgTimingReport.txt  
| ├── duplicatesReport.txt  
| ├── fullDownloadReport.txt  
| ├── generateCSV2.ps1  
| ├── insertsReport.txt  
| ├── instanceNames.txt  
| ├── Metadata.txt  
| ├── Requests.txt  
| ├── downloader/  
| │ ├── downloadRequests.txt  
│ │ ├── requestsLocs.txt  
│ │ ├── avgPeers.txt  
│ │ ├── sentToPeer.txt  
│ │ ├── probabilityReport.txt  
│ │ ├── requestTimestamps*.txt  
│ │ ├── keys*.txt  
│ │ ├── requests*.txt  
│ │ ├── requestIntervals*.txt  
│ │ ├── avgIntervals*.txt  
│ │ ├── duplicates.txt  
│ │ ├── inserts.txt  
│ │ ├── dataRequestsOnly*.txt  
│ │ ├── dataRequestsNum.txt  
│ │ └── HTL.txt  
│ ├── Relayer1/  
│ │ └── [similar structure as downloader/]  
└─└── Relayer.../  
└──File2/  
  [similar structure as File1/]  
  
---

## Scripts & Functions

| **Script** | **Invoked By** | **Purpose** | **Primary Outputs** |
|------------|----------------|-------------|---------------------|
| **`analyzeAllRequests.ps1`** | User (entry point) | Organizes logs, invokes parsing and analysis scripts, and sets up directories for results. | Directories (`File*/downloader`, `File*/Relayer*`), populated with structured results |
| **`filterRequests.pl`** | `analyzeAllRequests.ps1` | Filters logs by download keys, extracts request locations, peer statistics, and peer distributions. | `downloadRequests.txt`, `requestsLocs.txt`, `avgPeers.txt`, `sentToPeer.txt` |
| **`requestTimingDuplicatesInserts.pl`** | `analyzeAllRequests.ps1` | Detects duplicate requests, separates inserts from data requests, calculates request timing intervals, and summarizes key metrics. | `requestTimestamps*.txt`, `keys*.txt`, `requests*.txt`, `requestIntervals*.txt`, `avgIntervals*.txt`, `duplicates.txt`, `inserts.txt`, `dataRequestsOnly*.txt`, `dataRequestsNum.txt`, `HTL.txt` |
| **`calcProbabilities.pl`** | After above scripts | Implements the Levine Method to identify anomalous runs of requests and calculate false positive rates. | `probabilityReport.txt` |

---

## Quick Start

To begin processing logs, navigate to the main directory and execute:

```powershell
.\analyzeAllRequests.ps1
```
This will automatically:

1. Read and parse keys from each downloadKeys_File*.txt.

2. Invoke filterRequests.pl to organize requests.

3. Execute requestTimingDuplicatesInserts.pl to perform detailed request timing and content analysis.

4. Run calcProbabilities.pl to evaluate logs using the Levine Method.

Output Details & Interpretation

Core files:

   - downloadRequests.txt: 
    Filtered requests matching the specified keys.

   - requestsLocs.txt: 
    Locations extracted from each matching request.

   - avgPeers.txt: 
    Average peer count observed during downloads.

   - sentToPeer.txt: 
    Distribution of requests per peer IP address.

Detailed analysis (per relayer):

   - Timing and duplicate files: 
    Provide granular insight into timing, duplicates, and inserts vs. data requests.

   - probabilityReport.txt: 
    Contains Levine Method analysis results, identifying anomalous request patterns and calculating false positive rates.

# Post-processing and Formatting Workflow

After the initial log parsing and Levine Method analysis, additional steps are taken to identify and isolate relevant false-positive request runs and prepare data for input into the FTS Tool spreadsheet.

This secondary workflow involves three scripts executed in the following order:  
## false_positive_report.py

Purpose: Scans each File*/Relayer* folder's probabilityReport.txt to detect relayers that recorded one or more false-positive request runs. The identified relayers and their false-positive counts are summarized into a single report (false_positives_report.txt).

Usage: Arg is file number(s) to analyze
```
python false_positive_report.py 1 2 3 ... 12
```
  Generates false_positives_report.txt containing a list of relayers with false-positive runs.  
  Manually review this report to determine which File*/Relayer* folders are relevant for further analysis.  

## Manual Step: Copy Relevant Relayer Folders

Based on the output from false_positive_report.py, manually copy each relevant File*/Relayer* folder into a new, separate directory. This directory will serve as your working set for detailed peer-request analysis and formatting.
## extract_peer_requests.py

Purpose: From the copied relayer folders, isolates all requests associated with IP addresses that had request runs passing the Levine Method, as identified within each relayer's probabilityReport.txt.

Usage:
```
python extract_peer_requests.py
```
  For each IP:port identified, creates a new text file (requests_[IP_Port].txt) containing only requests associated with that peer.  

  Each output file is saved within its respective relayer folder.  

## FTS-Reformat.py

Purpose: Reformats extracted peer request files into a concise, tab-delimited format required by the FTS Tool spreadsheet. This includes converting request timestamps into Excel-compatible serial dates and selecting essential fields.

Output columns include:

   - Date/Time (Excel serial format)

   - Port (Blank)

   - Type (R for data requests, I for inserts)

   - HTL (Hops To Live)

   - Total Blocks

   - Data Blocks

   - Peers (Count)

   - LE ID (Peer IP:Port)

   - Split Keys (Request keys)

Usage:
```
python FTS-Reformat.py
```
  Processes all requests_[IP_Port].txt files created by extract_peer_requests.py.  

  Generates corresponding summary_ready_[IP_Port].txt files, formatted and ready to copy directly into the FTS spreadsheet.  

🗃️ Workflow Summary  

Raw Logs  
  └── Initial Parsing & Levine Method Analysis  
        └──── false_positive_report.py  
              └────── Manually copy relevant Relayer folders  
                    └──────── extract_peer_requests.py  
                          └─────────── FTS-Reformat.py  
                                └───────────── FTS Spreadsheet (only available through discovery subject to protective order)

This streamlined workflow allows precise and efficient data extraction, ensuring accurate analysis and straightforward input into forensic analysis tools.  


# Requirements & Dependencies

  - Perl (for .pl scripts)
  - PowerShell (for running the main orchestration script)
  - Python (for post-processing prior to use of the FTS Tool)
