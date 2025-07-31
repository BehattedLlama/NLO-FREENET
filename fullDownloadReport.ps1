$instancesNames = Get-Content -Path .\instancesNames.txt;
$folderName = $args[0]

$numRuns = 0
$numFalseRuns = 0

For ($i=0;$i -lt $instancesNames.Length; $i++) {
	$instance = $instancesNames[$i]
	if($instance -match "downloader") {
		continue
	}
	cd $folderName/$instance
	$lines = Get-Content -Path .\probabilityReport.txt
	For ($j = 0; $j -lt $lines.Length;$j++) {
		$line = $lines[$j]
		if($line -match "Number of Runs") {
			$arr = $line.split(" ")
			$numRuns += $arr[-1]
		}
		if($line -match "Number of False Positive Runs") {
			$arr = $line.split(" ")
			$numFalseRuns += $arr[-1]
		}				
	}
	cd ../..
}

$globalFalsePositiveRate = 0
if($numRuns -gt 0) {
	$globalFalsePositiveRate = 100.0*($numFalseRuns/$numRuns)
}else {
	$globalFalsePositiveRate = "NaN"
}

cd $folderName
New-Item -Path . -Name "fullDownloadReport.txt" -ItemType "file" -force
"Total Number of Runs: ${numRuns}" | Out-File -FilePath "fullDownloadReport.txt" -Append
"Total Number of False Positive Runs: ${numFalseRuns}" | Out-File -FilePath "fullDownloadReport.txt" -Append
"Whole-File False Positive Rate: ${globalFalsePositiveRate}%" | Out-File -FilePath "fullDownloadReport.txt" -Append
cd ..

Write-Output ""
Write-Output "Total Number of Runs: ${numRuns}"
Write-Output "Total Number of False Positive Runs: ${numFalseRuns}"
Write-Output "Whole-File False Positive Rate: ${globalFalsePositiveRate}%"