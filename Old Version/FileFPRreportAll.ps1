New-Item -Path . -Name "FileFPRreportAll.txt" -ItemType "file" -force

for ($i=0;$i -lt 10; $i++) {
	$folderName = "File" + ($i+1)
	cd $folderName
	$lines = Get-Content -Path .\fullDownloadReport.txt
	
	cd ..

	$percent = ""
	For ($j = 0; $j -lt $lines.Length;$j++) {
		$line = $lines[$j]
		if($line -match "False Positive Rate") {
			$arr = $line.split(" ")
			$arr2 = $arr[4].split("%")
			$percent = $arr2[0]
		}				
	}
	$percent | Out-File -FilePath "FileFPRreportAll.txt" -Append


}