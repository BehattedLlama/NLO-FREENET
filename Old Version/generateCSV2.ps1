$folders = Get-ChildItem -Name -Attributes Directory
$folders
$instancesNames = Get-Content -Path .\instancesNames.txt
New-Item -Path .\Requests.txt -ItemType File  -force
New-Item -Path .\Metadata.txt -ItemType File  -force

Add-Content -Path .\Requests.txt -Value "Header"
For ($i=0;$i -lt $instancesNames.Length; $i++) {
	$folder = $instancesNames[$i]
	Add-Content -Path .\Requests.txt -Value "$folder, " -NoNewLine
	cd $folder
	if($i -eq 0) {
		$keys = Get-Content -Path .\downloadKeys.txt
		$keysLength = $keys.Length
		Add-Content -Path ..\Metadata.txt -Value "TotalBlocks, $keysLength"
	}
	Add-Content -Path ..\Metadata.txt -Value "$folder, " -NoNewLine

	$peers = Get-Content -Path .\avgPeers.txt
	Add-Content -Path ..\Metadata.txt -Value "$peers"

	$lines = Get-Content -Path .\dataRequestsNum.txt
	For ($j = 0; $j -lt $lines.Length;$j++) {
		$line = $lines[$j]
		#$arr = $line.split("\n")
		#$requestsij = $arr[0]
		$requestsij = $line
		Add-Content -Path ..\Requests.txt -Value "$requestsij" -NoNewLine
		if ($j -ne $lines.Length-1) {
			Add-Content -Path ..\Requests.txt -Value ", " -NoNewLine
		}
	}
	if($i -ne $instancesNames.Length-1) {
        	Add-Content -Path ..\Requests.txt -Value ""
	}

	cd ..
}

$numCategories = $instancesNames.Length
$maxLength = 0
$lines2 = Get-Content -Path .\Requests.txt
For ($i=1;$i -lt $lines2.Length; $i++) {
	$line = $lines2[$i]
	$arr = $line.split(",")
	if($arr.Length -gt $maxLength) {
		$maxLength = $arr.Length
	}
}

<#
$dataArrLength = $maxLength+1
$dataArrLength
$dataArr = New-Object 'object[,]' $numCategories,$dataArrLength
New-Item -Path .\RequestsVertical.csv -ItemType File -force
For ($i=1;$i -lt $lines2.Length; $i++) {
	$line = $lines2[$i]
	$arr = $line.split(",")
	For ($j=0;$j -lt $arr.Length; $j++) {
		$dataArr[$i,$j] = $arr[$j] + ", "
	}
	For ($j=$arr.Length;$j -lt $maxLength; $j++) {
		$dataArr[$i,$j] = ", "
	}
}

For ($i=0;$i -lt $dataArrLength; $i++) {
	For ($j=1;$j -lt $lines2.Length;$j++) {
		Add-Content -Path .\RequestsVertical.csv -Value $dataArr[$j,$i] -NoNewLine
	}
	Add-Content -Path .\RequestsVertical.csv -Value ""
}
#>