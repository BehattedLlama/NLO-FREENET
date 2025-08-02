use 5.10.0; 

#1
  $readFile = $ARGV[0];
  open(FH, '<', $readFile) or Error("Could not read file ($!)");

 $readFile2 = 'downloadKeys.txt';
  open(FH2, '<', $readFile2) or Error("Could not read file ($!)");


#2
  $writeFile2 = 'downloadRequests.txt';
  open(NFH2, '>', $writeFile2) or Error("Cannot write to file ($!)");

#2
  $writeFile3 = 'sentToPeer.txt';
  open(NFH3, '>', $writeFile3) or Error("Cannot write to file ($!)");

#2
  $writeFile4 = 'requestLocs.txt';
  open(NFH4, '>', $writeFile4) or Error("Cannot write to file ($!)");

$writeFile5 = 'avgPeers.txt';
  open(NFH5, '>', $writeFile5) or Error("Cannot write to file ($!)");



@reqLines = <FH>;
my $count = 0;

@lines2 = <FH2>;
my @patterns;
$count = 0;
LINE: foreach my $line (@lines2)
{
	chomp($line);
	$patterns[$count] = qr/$line/;
	$count++;
}


my @filteredReq;
$count = 0;
LINE: foreach my $linei (@reqLines) {
	#chomp($linei);
	#push @filteredReq, $linei if $linei ~~ @patterns;
	LINE: foreach my $linej (@patterns) {
		if($linei =~ $linej) {
			if($linei =~ "Insert") {
				#next;
			}
			$filteredReq[$count] = $linei;
			$count++;
			last;
		}
	}
}
print NFH2 "$_" for @filteredReq;

my @ipAdd;
$count = 0;
my @requestLocs;
my @numPeers;
LINE: foreach my $line (@filteredReq) {
	chomp($line);
	my @spl = split(',',$line);
	$ipAdd[$count] = $spl[5];
	$numPeers[$count] = $spl[8];
	$requestLocs[$count] = $spl[3];
	$count++;
}
print NFH4 "$_\n" for @requestLocs;
my $sum = 0;
foreach my $i (@numPeers) {
	$sum += $i;
}

my $avgPeers;
if($count > 0) {
	$avgPeers= $sum / $count;
} else {
	$avgPeers = 0;
}
print NFH5 $avgPeers;


my @uniqueIp = uniq(@ipAdd);
my @uniqueIpCount;
$count = 0;
my $innerCount = 0;
LINE: foreach my $linei (@uniqueIp) {
	$innerCount = 0;
	LINE: foreach my $linej (@ipAdd) {
		if($linei eq $linej) {
			$innerCount++;
		}
	}
	$uniqueIpCount[$count] = $innerCount;
	$count++;
	print NFH3 $linei . "   was sent " . $innerCount . " requests\n";
}



close NFH2;
close NFH3;
close NFH4;
close NFH5;
close FH;
close FH2;

sub uniq {
  my %seen;
  return grep { !$seen{$_}++ } @_;
}