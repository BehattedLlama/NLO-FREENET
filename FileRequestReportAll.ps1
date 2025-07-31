New-Item -Path . -Name "FileRequestReportAll.txt" -ItemType "file" -force

$instance = "downloader"
for ($i=0;$i -lt 10; $i++) {
	$folderName = "File" + ($i+1)
	cd $folderName

	cd $instance
	$lines = Get-Content -Path .\probabilityReport.txt
	
	cd ../..

	$percent = ""
	For ($j = 0; $j -lt $lines.Length;$j++) {
		$line = $lines[$j]
		if($line -match "Percent of File Requested") {
			$arr = $line.split(" ")
			$percent = $arr[4]
		}				
	}
	$percent | Out-File -FilePath "FileRequestReportAll.txt" -Append


}