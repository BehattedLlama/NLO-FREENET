$isDownloader = $ARGV[0];

$sentToPeerFile = 'sentToPeer.txt';
open(FH, '<', $sentToPeerFile) or Error("Could not read file ($!)");
@sentToPeerLines = <FH>;
close FH;

$downloadKeysFile = 'downloadKeys.txt';
open(FH2, '<', $downloadKeysFile) or Error("Could not read file ($!)");
@downloadKeysLines = <FH2>;
close FH2;

$avgPeersFile = 'avgPeers.txt';
open(FH3, '<', $avgPeersFile) or Error("Could not read file ($!)");
@avgPeersLines = <FH3>;
close FH3;

$actualRequestsFile = 'downloadRequests.txt';
open(FH4, '<', $actualRequestsFile) or Error("Could not read file ($!)");
@actualRequestsLines = <FH4>;
close FH4;


my @peers;
foreach my $line (@sentToPeerLines) {
	chomp($line);
	my @spl = split(" ", $line);
	push(@peers, $spl[0]);
}

my $count = 1;
foreach my $peer (@peers) {
$reportFile = 'requestTimestamps' . $count . '.txt';
open(NFH2, '>', $reportFile) or Error("Could not read file ($!)");
$reportFile = 'keys' . $count . '.txt';
open(NFH3, '>', $reportFile) or Error("Could not read file ($!)");
$reportFile = 'requests' . $count . '.txt';
open(NFH4, '>', $reportFile) or Error("Could not read file ($!)");
foreach my $req (@actualRequestsLines) {
	chomp($req);
	my @spl = split(",", $req);
	my $ip = $spl[5];
	#print $ip . "\n";
	if ($ip eq $peer) {
		
		print NFH3 $spl[2] . "\n";
		print NFH4 $req . "\n";

		my @spl2 = split("T",$spl[0]);
		my @spl3 = split(":",$spl2[1]);
		my $time = (3600*$spl3[0]) + (60*$spl3[1]) + $spl3[2];
		print NFH2 $time . "\n";
		#print $time . "\n";
	}
}
close NFH2;
close NFH3;
close NFH4;
$count++;	
}

$count = 1;
foreach my $peer (@peers) {
	$intervalFile = 'requestIntervals' . $count . '.txt';
	open(NFH2, '>', $intervalFile) or Error("Could not read file ($!)");

	$reportFile = 'requestTimestamps' . $count . '.txt';
	open(FH5, '<', $reportFile) or Error("Could not read file ($!)");
	my @reqTimes = <FH5>;
	close FH5;

	my $count2 = 0;
	foreach my $req (@reqTimes) {
		if($count2 ne 0) {
			my $interval = $req - $reqTimes[$count2-1];
			print NFH2 $interval . "\n";
		}
		$count2++;
	}
	close NFH2;
	$count++;
}

$count = 1;
$intervalsFile = 'avgIntervals.txt';
open(NFH2, '>', $intervalsFile) or Error("Could not read file ($!)");
foreach my $peer (@peers) {
	$intervalFile = 'requestIntervals' . $count . '.txt';
	open(FH7, '<', $intervalFile) or Error("Could not read file ($!)");
	my @intervals = <FH7>;
	close FH7;
        my $numIntervals = scalar(@intervals);
	sort(@intervals);

	if($numIntervals > 0) {
		my $avgInterval = avg(@intervals);
		print NFH2 $avgInterval . "\n";
	} else {
		print NFH2 "nan\n";
	}

	$count++;
}
close NFH2;




$count = 1;
$duplicatesFile = 'duplicates.txt';
open(NFH2, '>', $duplicatesFile) or Error("Could not read file ($!)");
my @keys;
my @reqs;
foreach my $peer (@peers) {
	$reportFile = 'keys' . $count . '.txt';
	open(FH6, '<', $reportFile) or Error("Could not read file ($!)");
	@keys = <FH6>;
	close FH6;
	my $numKeys = scalar(@keys);

	$reportFile = 'requests' . $count . '.txt';
	open(FH7, '<', $reportFile) or Error("Could not read file ($!)");
	@reqs = <FH7>;
	close FH7;

	
	my $duplicates = 0;
	for(my $i = 0; $i < $numKeys; $i++) {
		chomp($reqs[$i]);
		my @spl = split(",", $reqs[$i]);
		my $reqType = $spl[1];
		if(lc($reqType) =~ "insert") {
			next;
		}

		chomp($keys[$i]);
		my $key = $keys[$i];
		for(my $j = 0; $j < $numKeys; $j++) {
			chomp($reqs[$j]);
			my @spl = split(",", $reqs[$j]);
			my $reqType = $spl[1];
			if(lc($reqType) =~ "insert") {
				next;
			}

			if($j ne $i) {
				chomp($keys[$j]);
				my $keyj = $keys[$j];
				if($key eq $keyj) {
					$duplicates++;
				}	
			}
		}
	}
	$duplicates = $duplicates / 2;
	print NFH2 $duplicates . "\n";
	$count++;
}
close NFH2;

$count = 1;
$insertsFile = 'inserts.txt';
open(NFH5, '>', $insertsFile) or Error("Could not read file ($!)");
my @reqs;
foreach my $peer (@peers) {
	$reportFile = 'requests' . $count . '.txt';
	open(FH7, '<', $reportFile) or Error("Could not read file ($!)");
	@reqs = <FH7>;
	close FH7;
	my $numReqs = scalar(@reqs);

	
	my $inserts = 0;
	foreach my $req (@reqs) {
		chomp($req);
		my @spl = split(",", $req);
		my $reqType = $spl[1];
		if(lc($reqType) =~ "insert") {
			$inserts++;
		}
	}
	print NFH5 $inserts . "\n";
	$count++;
}
close NFH5;


$count = 1;
my $dataReqFile = 'dataRequestsNum.txt';
open(NFH6, '>', $dataReqFile) or Error("Could not read file ($!)");
foreach my $peer (@peers) {
	my $dataReqFile = 'dataRequestsOnly' . $count . '.txt';
	open(NFH5, '>', $dataReqFile) or Error("Could not read file ($!)");

	my $numReq = 0;

	$reportFile = 'requests' . $count . '.txt';
	open(FH7, '<', $reportFile) or Error("Could not read file ($!)");
	my @reqs = <FH7>;
	close FH7;

	foreach my $req (@reqs) {
		chomp($req);
		my @spl = split(",", $req);
		my $reqType = $spl[1];
		if(lc($reqType) !~ "insert") {
			print NFH5 $req . "\n";
			$numReq++;
		}
	}
	$count++;
	close NFH5;
	print NFH6 $numReq . "\n";
}
close NFH6;

$count = 1;
$HTLFile = 'HTL.txt';
open(NFH5, '>', $HTLFile) or Error("Could not read file ($!)");
my @reqs;
foreach my $peer (@peers) {
	$reportFile = 'requests' . $count . '.txt';
	open(FH7, '<', $reportFile) or Error("Could not read file ($!)");
	@reqs = <FH7>;
	close FH7;
	my $numReqs = scalar(@reqs);

	my @htl16;
	my @htl17;
	my @htl18;
	
	my $inserts = 0;
	foreach my $req (@reqs) {
		chomp($req);
		my @spl = split(",", $req);
		my $htl = $spl[4];
		if($htl eq "16") {
			push(@htl16, $htl);
		}
		if($htl eq "17") {
			push(@htl17, $htl);
		}
		if($htl eq "18") {
			push(@htl18, $htl);
		}
		
	}
	my $numHTL16 = scalar(@htl16);
	my $numHTL17 = scalar(@htl17);
	my $numHTL18 = scalar(@htl18);
	#print NFH5 "HTL 16: " . $numHTL16 . ", HTL 17: " . $numHTL17 . ", HTL 18: " . $numHTL18 . "\n";
	print NFH5 "HTL 18: " . $numHTL18 . ", HTL 17: " . $numHTL17 . ", HTL 16: " . $numHTL16 . "\n";
	$count++;
}
close NFH5;


sub avg {
    my $total;
    $total += $_ foreach @_;
    # sum divided by number of components.
    return $total / @_;
}

sub std {
    my $total;
    $total += $_ foreach @_;
    # sum divided by number of components.
    return $total / @_;
}