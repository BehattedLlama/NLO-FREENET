use List::Util qw(min max);

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

$duplicatesFile = 'duplicates.txt';
open(FH5, '<', $duplicatesFile) or Error("Could not read file ($!)");
@duplicates = <FH5>;
close FH5;

$insertsFile = 'inserts.txt';
open(FH6, '<', $insertsFile) or Error("Could not read file ($!)");
@inserts = <FH6>;
close FH6;

$htlFile = 'HTL.txt';
open(FH7, '<', $htlFile) or Error("Could not read file ($!)");
@htls = <FH7>;
close FH7;

$reportFile = 'probabilityReport.txt';
open(NFH, '>', $reportFile) or Error("Could not read file ($!)");

my $avgPeers = $avgPeersLines[0];
my $numTotalBlocks = scalar(@downloadKeysLines);
my $T = int(0.8*$numTotalBlocks);
my $numPeersSentTo = scalar(@sentToPeerLines);
my $numRequestsSent = scalar(@actualRequestsLines);

my $adjRequestsSent = 0;
foreach my $line (@actualRequestsLines) {
	chomp($line);
	my @spl = split(",", $line);
	my $reqType = $spl[1];
	if(lc($reqType) =~ "insert") {
		next;
	} else {
		$adjRequestsSent++;
	}
}

my $numRuns = 0;
my $numFalsePositives = 0;
my $count = 0;
#foreach my $line (@sentToPeerLines) {
foreach my $line (@htls) {
	#chomp($line);
	#my @spl = split(" ", $line);
	#my $peer = $spl[0];
	#my $requests = $spl[3];

	chomp($sentToPeerLines[$count]);
	my @splPeer = split(" ", $sentToPeerLines[$count]);
	my $peer = $splPeer[0];

	chomp($line);
	my @htl;
	my @spl = split(",",$line);
	my @spl2 = split(" ", $spl[0]);
	push(@htl,$spl2[2]);
	my @spl3 = split(" ", $spl[1]);	
	push(@htl,$spl3[2]);
	my @spl4 = split(" ", $spl[2]);	
	push(@htl,$spl4[2]);
	my $requests = max(@htl);
	

	chomp($duplicates[$count]);
	chomp($inserts[$count]);
	my $adjRequests = $requests - ($inserts[$count]) - (3*$duplicates[$count]);
	if($requests >= 20) {
		$numRuns++;
		my $downloaderProbability = calcEvenShareProbability($avgPeers,$T,$adjRequests);	
		my $downloaderDecision = "No";
		if($downloaderProbability > 0.98) {
			$downloaderDecision = "Yes";
			$numFalsePositives++;
		}
		print NFH $peer . " had a run. Requests: " . $requests . ", Duplicates: " . $duplicates[$count] . ", Inserts: " . $inserts[$count] . ", Adj. Requests: " . $adjRequests . ", Passes Levine: " . $downloaderDecision . ", Levine Downloader probability: " . $downloaderProbability . "\n";
	} else {
		print NFH $peer . " did not see a run. Requests: " . $requests . ", Duplicates: " . $duplicates[$count] . ", Inserts: " . $inserts[$count] . ", Adj. Requests: " . $adjRequests . "\n";
	}
	$count++;
}

print NFH "\n";
print NFH "Average Peers: ". $avgPeers . "\n";
print NFH "Number of Unique Peers Requests were Sent To: " . $numPeersSentTo . "\n";
if($numPeersSentTo > 0) {
	print NFH "Percent of Runs out of Peers Requests were Sent To: " . 100.0*($numRuns/$numPeersSentTo) . " %\n";
} else {
	print NFH "Percent of Runs out of Peers Requests were Sent To:  0 %\n";
}
print NFH "Number of Runs: " . $numRuns . "\n";
if(!$isDownloader) {
	print NFH "Number of False Positive Runs: " . $numFalsePositives . "\n";
	if($numRuns > 0) {
		print NFH "Local Rate of False Positive Runs: " . 100.0*($numFalsePositives/$numRuns) . " %\n";
	} else {
		print NFH "Local Rate of False Positive Runs: Not Applicable" . "\n";
	}
} else {
	print NFH "Number of True Positive Runs: " . $numFalsePositives . "\n";
	if($numRuns > 0) {
		print NFH "Local Rate of True Positive Runs: " . 100.0*($numFalsePositives/$numRuns) . " %\n";
	} else {
		print NFH "Local Rate of True Positive Runs: Not Applicable" . "\n";
	}
	print NFH "Total Number of Blocks for File: " . $numTotalBlocks . "\n";
	print NFH "Unique Requests sent: " . $adjRequestsSent . "\n";
	print NFH "Percent of File Requested: " . (100.0)*$adjRequestsSent/$numTotalBlocks . " %\n";
}

close NFH;

sub factorialLog {
	$input = $_[0];

	if($input < 0) { 
		return "NaN";
	}
	if($input == 1 || $input == 0) {
		return 1.0;
	}
		
	my $total = log($input);
	for(my $i = ($input-1); $i > 0; $i--) {
		$total += log($i);
	}
	return $total;
}

sub nChoosek {
	$n = $_[0];
	$k = $_[1];

	my $numerator = factorialLog($n);
	my $denom = factorialLog($k)+factorialLog($n-$k);
	return $numerator-$denom;
}

sub binom {
	$k = $_[0];
	$n = $_[1];
	$p = $_[2];

	my $temp = nChoosek($n,$k) + (($k*log($p)) + (($n-$k)*log(1.0-$p)));
	return exp($temp);
}

sub calcEvenShareProbability {
	$g = $_[0];
	$T = $_[1];
	$r = $_[2];

	my $gp1 = ($g+1);
	my $gInv = 1.0/$g;
	my $h = 8.0;
	my $ghInv = 1.0/($g*$h);
		
	my $numerator = (1.0/$gp1)*binom($r,$T,$gInv);
	my $denom = $numerator + ($g/$gp1)*binom($r,$T,$ghInv);
	return $numerator/$denom;
}

sub downloaderDecision {
	$g = $_[0];
	$T = $_[1];
	$r = $_[2];

	my $downloaderProbablity = calcEvenShareProbability($g,$T,$r);
	if($downloaderProbablity > 0.98) {
		return 1;
	}else{
		return 0;
	}
}
	