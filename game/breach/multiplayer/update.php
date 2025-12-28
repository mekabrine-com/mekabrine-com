<?php
// /home/j0sd9px3jsq7o44y/public_html/game/breach/multiplayer/update.php
header('Content-Type: text/plain; charset=utf-8');

$file = __DIR__ . '/players.txt';
if (!file_exists($file)) { @file_put_contents($file, ""); }

function clean_str($s, $max, $pattern) {
    $s = is_string($s) ? $s : '';
    $s = preg_replace($pattern, '', $s);
    $s = trim($s);
    if (strlen($s) > $max) $s = substr($s, 0, $max);
    return $s;
}

$id       = clean_str($_POST['id'] ?? '', 32, '/[^a-zA-Z0-9_\-]/');
$username = clean_str($_POST['username'] ?? '', 16, '/[^a-zA-Z0-9_\- ]/');
$room     = clean_str($_POST['room'] ?? '', 64, '/[^a-zA-Z0-9_\-: ]/');
$class    = clean_str($_POST['class'] ?? 'ds', 8, '/[^a-zA-Z0-9_\-]/');

$sector = intval($_POST['sector'] ?? 0);
$x      = intval($_POST['x'] ?? 0);
$y      = intval($_POST['y'] ?? 0);

$facing = intval($_POST['facing'] ?? 1);
if ($facing !== -1) $facing = 1;

$aim  = floatval($_POST['aim'] ?? 0);
$item = clean_str($_POST['item'] ?? 'melee', 16, '/[^a-zA-Z0-9_\-]/');

if ($id === '' || $username === '' || $room === '') {
    http_response_code(400);
    echo "BAD";
    exit;
}

$now = time();
$ttl = 15;

$fp = @fopen($file, 'c+');
if (!$fp) {
    http_response_code(500);
    echo "ERR";
    exit;
}

flock($fp, LOCK_EX);
rewind($fp);

$rows = [];
while (($line = fgets($fp)) !== false) {
    $line = trim($line);
    if ($line === '') continue;

    $parts = explode('|', $line);
    if (count($parts) < 11) continue;

    $ts = intval($parts[10]);
    if (($now - $ts) > $ttl) continue;

    $rows[] = $parts;
}

$newRow = [
    $id,
    $username,
    $room,
    strval($sector),
    strval($x),
    strval($y),
    strval($facing),
    sprintf('%.4f', $aim),
    $item,
    $class,
    strval($now)
];

$found = false;
for ($i = 0; $i < count($rows); $i++) {
    if ($rows[$i][0] === $id) {
        $rows[$i] = $newRow;
        $found = true;
        break;
    }
}
if (!$found) $rows[] = $newRow;

rewind($fp);
ftruncate($fp, 0);

$out = [];
foreach ($rows as $r) $out[] = implode('|', $r);
fwrite($fp, implode("\n", $out));
fflush($fp);

flock($fp, LOCK_UN);
fclose($fp);

echo "OK";
