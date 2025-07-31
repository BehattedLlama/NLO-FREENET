$instancesNames = Get-Content -Path .\instancesNames.txt;
$folderName = $args[0]

$numRuns = 0
$numFalseRuns = 0

cd $folderName
New-Item -Path . -Name "duplicatesReport.txt" -ItemType "file" -force

For ($i=0;$i -lt $instancesNames.Length; $i++) {
	$instance = $instancesNames[$i]

	cd $instance
	$lines = Get-Content -Path .\duplicates.txt
	
	cd ..

	$str = ""
	For ($j = 0; $j -lt $lines.Length;$j++) {
		$line = $lines[$j]
		if ($line) {
			$str = $str + $line + ","
		}				
	}
	#$str = $str + "\n"
	$str | Out-File -FilePath "duplicatesReport.txt" -Append
}

cd ..