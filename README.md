# Freenet/Hyphanet Outgoing Request Log Analysis

> **Scripts and tooling for parsing, organizing, and applying the Levine Method to Freenet/Hyphanet outgoing request logs.**

---

## Overview

This repository contains scripts designed to analyze outgoing request logs from downloader and relayer nodes within Freenet/Hyphanet. Logs are parsed, organized per test file, and evaluated using the **Levine Method** to detect anomalous request patterns and estimate false positive rates.

---

## Directory Structure (Example)

After processing logs, your directory structure will look similar to this:  

File1/  
├── avgTimingReport.txt  
├── duplicatesReport.txt  
├── fullDownloadReport.txt  
├── generateCSV2.ps1  
├── insertsReport.txt  
├── instanceNames.txt  
├── Metadata.txt  
├── Requests.txt  
├── downloader/  
│ ├── downloadRequests.txt  
│ ├── requestsLocs.txt  
│ ├── avgPeers.txt  
│ ├── sentToPeer.txt  
│ ├── probabilityReport.txt  
│ ├── requestTimestamps*.txt  
│ ├── keys*.txt  
│ ├── requests*.txt  
│ ├── requestIntervals*.txt  
│ ├── avgIntervals*.txt  
│ ├── duplicates.txt  
│ ├── inserts.txt  
│ ├── dataRequestsOnly*.txt  
│ ├── dataRequestsNum.txt  
│ └── HTL.txt  
├── Relayer1/  
│ └── [similar structure as downloader/]  
└── Relayer.../  
File2/  
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

Requirements & Dependencies

  - Perl (for .pl scripts)
  - PowerShell (for running the main orchestration script)
  - Python (for post-processing prior to use of the FTS Tool)
