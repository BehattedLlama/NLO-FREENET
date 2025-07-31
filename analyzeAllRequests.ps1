# AnalyzeAllRequests.ps1

$WorkingDirectory = (Get-Location).ProviderPath
$instancesNames = Get-Content -Path (Join-Path $WorkingDirectory 'instancesNames.txt')
$manifests = Get-ChildItem -Path $WorkingDirectory -Filter 'downloadKeys_File*.txt'
$maxParallel = 24
$allJobs = @()

# SETUP: Create per-file & per-instance folders; copy static scripts + manifest keys
foreach ($manifest in $manifests) {
    if ($manifest.BaseName -match 'downloadKeys_File(\d+)$') {
        $fileNumber = $matches[1]
    } else {
        Write-Host ("Skipping {0} (does not match pattern)" -f $manifest.Name) -ForegroundColor Yellow
        continue
    }

    $folderName = "File$fileNumber"
    $folderPath = Join-Path $WorkingDirectory $folderName

    if (-not (Test-Path $folderPath)) {
        New-Item -ItemType Directory -Path $folderPath | Out-Null
    }

    foreach ($instance in $instancesNames) {
        $instanceFolder = Join-Path $folderPath $instance

        if (-not (Test-Path $instanceFolder)) {
            New-Item -ItemType Directory -Path $instanceFolder | Out-Null
        }

        foreach ($static in @('filterRequests.pl', 'requestTimingDuplicatesInserts.pl', 'calcProbabilities.pl')) {
            Copy-Item -Path (Join-Path $WorkingDirectory $static) -Destination $instanceFolder -Force -ErrorAction Stop
        }

        Copy-Item -Path $manifest.FullName -Destination (Join-Path $instanceFolder 'downloadKeys.txt') -Force -ErrorAction Stop
    }
}

Write-Host 'SETUP COMPLETE - starting analysis jobs...' -ForegroundColor Green

# PARALLEL ANALYSIS
foreach ($manifest in $manifests) {
    if ($manifest.BaseName -match 'downloadKeys_File(\d+)$') {
        $fileNumber = $matches[1]
    } else {
        continue
    }

    $folderName = "File$fileNumber"
    $folderPath = Join-Path $WorkingDirectory $folderName

    foreach ($instance in $instancesNames) {
        $instanceFolder = Join-Path $folderPath $instance
        $requestsLog = Join-Path $WorkingDirectory ("requests_$instance.log")
        $filteredLog = Join-Path $instanceFolder ("requests_$instance.log")
        $isDownloader = if ($instance -eq 'downloader') { 1 } else { 0 }

        if (-not (Test-Path $instanceFolder)) {
            Write-Host ("ERROR: missing folder {0} - skipping" -f $instanceFolder) -ForegroundColor Red
            continue
        }
        if (-not (Test-Path $requestsLog)) {
            Write-Host ("ERROR: missing log {0} - skipping" -f $requestsLog) -ForegroundColor Red
            continue
        }

        $allJobs += Start-Job -ScriptBlock {
            param($cwd, $inLog, $outLog, $dlFlag)
            Set-Location $cwd
            perl filterRequests.pl $inLog > $outLog
            perl requestTimingDuplicatesInserts.pl
            perl calcProbabilities.pl $dlFlag
            Write-Host ("Finished analysis in {0}" -f $cwd)
        } -ArgumentList $instanceFolder, $requestsLog, $filteredLog, $isDownloader

        while ((Get-Job -State Running).Count -ge $maxParallel) {
            Start-Sleep -Seconds 2
        }
    }
}

while ((Get-Job -State Running).Count -gt 0) {
    Start-Sleep -Seconds 5
}

Get-Job | Receive-Job | Out-Null
Get-Job | Remove-Job

Write-Host 'ALL BACKGROUNDS COMPLETE - running post-processing...' -ForegroundColor Green

# POST-PROCESSING REPORTS + CSV
foreach ($manifest in $manifests) {
    if ($manifest.BaseName -match 'downloadKeys_File(\d+)$') {
        $fileNumber = $matches[1]
    } else {
        continue
    }

    $folderName = "File$fileNumber"
    $folderPath = Join-Path $WorkingDirectory $folderName

    & (Join-Path $WorkingDirectory 'fullDownloadReport.ps1')   $folderPath
    & (Join-Path $WorkingDirectory 'duplicatesReport.ps1')     $folderPath
    & (Join-Path $WorkingDirectory 'avgTimingReport.ps1')      $folderPath
    & (Join-Path $WorkingDirectory 'insertsReport.ps1')        $folderPath
    & (Join-Path $WorkingDirectory 'FileFPRreportAll.ps1')     $folderPath
    & (Join-Path $WorkingDirectory 'FileRequestReportAll.ps1') $folderPath

    Copy-Item -Path (Join-Path $WorkingDirectory 'generateCSV2.ps1') -Destination $folderPath -Force
    Copy-Item -Path (Join-Path $WorkingDirectory 'instancesNames.txt') -Destination $folderPath -Force

    Push-Location $folderPath
    & '.\generateCSV2.ps1'
    Pop-Location

    Write-Host ("Completed reports + CSV for {0}" -f $folderName)
}

Write-Host '***** ALL MANIFESTS ANALYZED SUCCESSFULLY *****' -ForegroundColor Green
