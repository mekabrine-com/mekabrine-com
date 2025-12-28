<?php
// /home/j0sd9px3jsq7o44jy/public_html/game/breach/multiplayer/state.php

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

function safe_key($s, $max = 64) {
    $s = (string)$s;
    $s = trim($s);
    $s = preg_replace('/[^a-zA-Z0-9_\-\.]/', '_', $s);
    if (strlen($s) > $max) $s = substr($s, 0, $max);
    return $s;
}

// ids need to preserve ":" because the client uses ":" in mpId strings
function safe_id($s, $max = 128) {
    $s = (string)$s;
    $s = trim($s);
    $s = preg_replace('/[^a-zA-Z0-9_\-\.\:]/', '_', $s);
    if (strlen($s) > $max) $s = substr($s, 0, $max);
    return $s;
}

function read_json_file($path, $default) {
    if (!is_file($path)) return $default;
    $raw = @file_get_contents($path);
    if ($raw === false || $raw === '') return $default;
    $d = json_decode($raw, true);
    return is_array($d) ? $d : $default;
}

function write_json_file_atomic($path, $data) {
    $tmp = $path . '.tmp';
    $json = json_encode($data, JSON_UNESCAPED_SLASHES);
    if ($json === false) $json = '{}';
    $fp = @fopen($tmp, 'wb');
    if (!$fp) return false;
    if (!flock($fp, LOCK_EX)) { fclose($fp); return false; }
    fwrite($fp, $json);
    fflush($fp);
    flock($fp, LOCK_UN);
    fclose($fp);
    @rename($tmp, $path);
    return true;
}

function default_sector_state() {
    return [
        'deadEnemies' => [],
        'removedItems' => [],
        'drops' => [],
        'glowsticks' => [],
        'removedGlowsticks' => [],
        'shots' => []
    ];
}

$raw = file_get_contents('php://input');
$body = [];
if ($raw) {
    $dec = json_decode($raw, true);
    if (is_array($dec)) $body = $dec;
}

$seed    = safe_key($body['seed']    ?? ($_GET['seed']    ?? ''), 48);
$sector  = safe_key($body['sector']  ?? ($_GET['sector']  ?? '0'), 24);
$user    = safe_key($body['username']?? ($_GET['username']?? ''), 24);

$now = time();
$nowf = microtime(true);

$baseDir = __DIR__;
$playersFile = $baseDir . '/players.txt';
$seedsFile = $baseDir . '/seeds.txt';

$players = read_json_file($playersFile, []);
if (!is_array($players)) $players = [];

$seedsData = read_json_file($seedsFile, ['seeds' => []]);
if (!is_array($seedsData)) $seedsData = ['seeds' => []];
if (!isset($seedsData['seeds']) || !is_array($seedsData['seeds'])) $seedsData['seeds'] = [];
$seeds = $seedsData['seeds'];

/* cleanup stale players */
foreach ($players as $uname => $p) {
    $ls = isset($p['lastSeen']) ? (int)$p['lastSeen'] : 0;
    if ($ls <= 0 || ($now - $ls) > 12) {
        unset($players[$uname]);
    }
}

$method = $_SERVER['REQUEST_METHOD'];

if ($method === 'POST' && $seed !== '' && $user !== '') {
    $px = isset($body['x']) ? (float)$body['x'] : 0.0;
    $py = isset($body['y']) ? (float)$body['y'] : 0.0;
    $facing = (isset($body['facing']) && ((int)$body['facing'] === -1)) ? -1 : 1;
    $aim = isset($body['aimAngle']) ? (float)$body['aimAngle'] : 0.0;
    $holding = safe_key($body['holding'] ?? 'melee', 16);
    $hp = isset($body['hp']) ? (float)$body['hp'] : 150.0;
    $dead = !empty($body['dead']);
    $hasKeycard = !empty($body['hasKeycard']);
    $crouch = !empty($body['crouch']);
    $ammo = $body['ammo'] ?? null;
    $reloading = isset($body['reloading']) ? (int)$body['reloading'] : 0;

    $players[$user] = [
        'username' => $user,
        'seed' => $seed,
        'sector' => $sector,
        'x' => $px,
        'y' => $py,
        'facing' => $facing,
        'aimAngle' => $aim,
        'holding' => $holding,
        'hp' => $hp,
        'dead' => $dead,
        'hasKeycard' => $hasKeycard,
        'crouch' => $crouch,
        'ammo' => $ammo,
        'reloading' => $reloading,
        'lastSeen' => $now
    ];

    $events = $body['events'] ?? [];
    if (!is_array($events)) $events = [];

    $glowState = $body['glowState'] ?? [];
    if (!is_array($glowState)) $glowState = [];

    $seedHasEntry = (isset($seeds[$seed]) && is_array($seeds[$seed]));
    $needsSeedState = $seedHasEntry || (count($events) > 0) || (count($glowState) > 0);

    if ($needsSeedState) {
        if (!$seedHasEntry) {
            $seeds[$seed] = [
                'lastActive' => $now,
                'sectors' => []
            ];
        }
        if (!isset($seeds[$seed]['sectors']) || !is_array($seeds[$seed]['sectors'])) $seeds[$seed]['sectors'] = [];
        $seeds[$seed]['lastActive'] = $now;

        $sectorKey = (string)$sector;
        if (!isset($seeds[$seed]['sectors'][$sectorKey]) || !is_array($seeds[$seed]['sectors'][$sectorKey])) {
            $seeds[$seed]['sectors'][$sectorKey] = default_sector_state();
        }

        $world = $seeds[$seed]['sectors'][$sectorKey];

        if (!isset($world['deadEnemies']) || !is_array($world['deadEnemies'])) $world['deadEnemies'] = [];
        if (!isset($world['removedItems']) || !is_array($world['removedItems'])) $world['removedItems'] = [];
        if (!isset($world['drops']) || !is_array($world['drops'])) $world['drops'] = [];
        if (!isset($world['glowsticks']) || !is_array($world['glowsticks'])) $world['glowsticks'] = [];
        if (!isset($world['removedGlowsticks']) || !is_array($world['removedGlowsticks'])) $world['removedGlowsticks'] = [];
        if (!isset($world['shots']) || !is_array($world['shots'])) $world['shots'] = [];

        $deadSet = array_fill_keys(array_map('strval', $world['deadEnemies']), true);
        $remSet  = array_fill_keys(array_map('strval', $world['removedItems']), true);
        $drops = $world['drops'];
        $glows = $world['glowsticks'];
        $glowRemSet = array_fill_keys(array_map('strval', $world['removedGlowsticks']), true);

        // prune old shots (ephemeral)
        $shots = [];
        foreach ($world['shots'] as $s) {
            if (!is_array($s)) continue;
            $t = isset($s['t']) ? (float)$s['t'] : 0.0;
            if ($t > 0 && ($nowf - $t) < 2.5) $shots[] = $s;
        }
        if (count($shots) > 80) $shots = array_slice($shots, -80);

        // owner-authoritative glow updates
        foreach ($glowState as $gs) {
            if (!is_array($gs)) continue;
            $id = safe_id($gs['id'] ?? '', 128);
            if ($id === '') continue;
            if (isset($glowRemSet[$id])) continue;

            $x = isset($gs['x']) ? (float)$gs['x'] : 0.0;
            $y = isset($gs['y']) ? (float)$gs['y'] : 0.0;
            $vx = isset($gs['vx']) ? (float)$gs['vx'] : 0.0;
            $vy = isset($gs['vy']) ? (float)$gs['vy'] : 0.0;
            $rot = isset($gs['rot']) ? (float)$gs['rot'] : 0.0;
            $frozen = !empty($gs['frozen']);
            $freezeTimer = isset($gs['freezeTimer']) ? (int)$gs['freezeTimer'] : 0;

            // create if missing, but only for the posting user
            if (!isset($glows[$id]) || !is_array($glows[$id])) {
                $glows[$id] = [
                    'owner' => $user,
                    'x' => $x, 'y' => $y,
                    'vx' => $vx, 'vy' => $vy,
                    'rot' => $rot,
                    'frozen' => $frozen,
                    'freezeTimer' => $freezeTimer
                ];
            } else {
                $owner = isset($glows[$id]['owner']) ? (string)$glows[$id]['owner'] : '';
                if ($owner === '' || $owner === $user) {
                    $glows[$id]['owner'] = $owner === '' ? $user : $owner;
                    $glows[$id]['x'] = $x;
                    $glows[$id]['y'] = $y;
                    $glows[$id]['vx'] = $vx;
                    $glows[$id]['vy'] = $vy;
                    $glows[$id]['rot'] = $rot;
                    $glows[$id]['frozen'] = $frozen;
                    $glows[$id]['freezeTimer'] = $freezeTimer;
                }
            }
        }

        foreach ($events as $ev) {
            if (!is_array($ev) || !isset($ev['type'])) continue;
            $type = (string)$ev['type'];

            if ($type === 'enemy_dead') {
                $id = safe_id($ev['id'] ?? '', 128);
                if ($id !== '' && !isset($deadSet[$id])) $deadSet[$id] = true;
            }

            if ($type === 'item_remove') {
                $id = safe_id($ev['id'] ?? '', 128);
                if ($id !== '' && !isset($remSet[$id])) {
                    $remSet[$id] = true;
                    if (isset($drops[$id])) unset($drops[$id]);
                }
            }

            if ($type === 'drop_add') {
                $id = safe_id($ev['id'] ?? '', 128);
                $it = $ev['item'] ?? null;
                if ($id !== '' && !isset($remSet[$id]) && !isset($drops[$id]) && is_array($it)) {
                    $drops[$id] = [
                        'type' => safe_key($it['type'] ?? 'melee', 16),
                        'x' => isset($it['x']) ? (float)$it['x'] : 0.0,
                        'y' => isset($it['y']) ? (float)$it['y'] : 0.0
                    ];
                }
            }

            if ($type === 'glow_add') {
                $id = safe_id($ev['id'] ?? '', 128);
                $g = $ev['glow'] ?? null;
                if ($id !== '' && !isset($glowRemSet[$id]) && is_array($g)) {
                    $owner = safe_key($g['owner'] ?? $user, 24);
                    if ($owner === '') $owner = $user;

                    if (!isset($glows[$id]) || !is_array($glows[$id])) {
                        $glows[$id] = [
                            'owner' => $owner,
                            'x' => isset($g['x']) ? (float)$g['x'] : 0.0,
                            'y' => isset($g['y']) ? (float)$g['y'] : 0.0,
                            'vx' => isset($g['vx']) ? (float)$g['vx'] : 0.0,
                            'vy' => isset($g['vy']) ? (float)$g['vy'] : 0.0,
                            'rot' => isset($g['rot']) ? (float)$g['rot'] : 0.0,
                            'frozen' => !empty($g['frozen']),
                            'freezeTimer' => isset($g['freezeTimer']) ? (int)$g['freezeTimer'] : 0
                        ];
                    }
                }
            }

            if ($type === 'glow_freeze') {
                $id = safe_id($ev['id'] ?? '', 128);
                if ($id !== '' && !isset($glowRemSet[$id])) {
                    if (!isset($glows[$id]) || !is_array($glows[$id])) {
                        $glows[$id] = [
                            'owner' => $user,
                            'x' => isset($ev['x']) ? (float)$ev['x'] : 0.0,
                            'y' => isset($ev['y']) ? (float)$ev['y'] : 0.0,
                            'vx' => 0.0,
                            'vy' => 0.0,
                            'rot' => isset($ev['rot']) ? (float)$ev['rot'] : 0.0,
                            'frozen' => true,
                            'freezeTimer' => 0
                        ];
                    } else {
                        $owner = isset($glows[$id]['owner']) ? (string)$glows[$id]['owner'] : '';
                        if ($owner === '' || $owner === $user) {
                            $glows[$id]['x'] = isset($ev['x']) ? (float)$ev['x'] : (float)($glows[$id]['x'] ?? 0.0);
                            $glows[$id]['y'] = isset($ev['y']) ? (float)$ev['y'] : (float)($glows[$id]['y'] ?? 0.0);
                            $glows[$id]['rot'] = isset($ev['rot']) ? (float)$ev['rot'] : (float)($glows[$id]['rot'] ?? 0.0);
                            $glows[$id]['vx'] = 0.0;
                            $glows[$id]['vy'] = 0.0;
                            $glows[$id]['frozen'] = true;
                            $glows[$id]['freezeTimer'] = 0;
                        }
                    }
                }
            }

            if ($type === 'glow_remove') {
                $id = safe_id($ev['id'] ?? '', 128);
                if ($id !== '' && !isset($glowRemSet[$id])) {
                    $glowRemSet[$id] = true;
                    if (isset($glows[$id])) unset($glows[$id]);
                }
            }

            if ($type === 'shot') {
                $sid = safe_id($ev['id'] ?? '', 128);
                if ($sid !== '') {
                    $shots[] = [
                        'id' => $sid,
                        'shooter' => $user,
                        'weapon' => safe_key($ev['weapon'] ?? 'pistol', 16),
                        'sx' => isset($ev['sx']) ? (float)$ev['sx'] : 0.0,
                        'sy' => isset($ev['sy']) ? (float)$ev['sy'] : 0.0,
                        'ex' => isset($ev['ex']) ? (float)$ev['ex'] : 0.0,
                        'ey' => isset($ev['ey']) ? (float)$ev['ey'] : 0.0,
                        't' => $nowf
                    ];
                    if (count($shots) > 80) $shots = array_slice($shots, -80);
                }
            }

            if ($type === 'player_hit') {
                $victim = safe_key($ev['victim'] ?? '', 24);
                $dmg = isset($ev['dmg']) ? (float)$ev['dmg'] : 0.0;
                if ($victim !== '' && $dmg > 0 && isset($players[$victim])) {
                    $vp = $players[$victim];

                    if (($vp['seed'] ?? '') === $seed && (string)($vp['sector'] ?? '') === (string)$sector) {
                        $newHp = (float)($vp['hp'] ?? 150.0) - $dmg;
                        if ($newHp <= 0) {
                            $newHp = 0;
                            $vp['dead'] = true;
                        }
                        $vp['hp'] = $newHp;
                        $players[$victim] = $vp;
                    }
                }
            }
        }

        $world['deadEnemies'] = array_keys($deadSet);
        $world['removedItems'] = array_keys($remSet);
        $world['drops'] = $drops;
        $world['glowsticks'] = $glows;
        $world['removedGlowsticks'] = array_keys($glowRemSet);
        $world['shots'] = $shots;

        $seeds[$seed]['sectors'][$sectorKey] = $world;
    }
}

/* reset seeds when nobody is connected to them */
$activeSeeds = [];
foreach ($players as $uname => $p) {
    if (!is_array($p)) continue;
    $s = safe_key($p['seed'] ?? '', 48);
    if ($s !== '') $activeSeeds[$s] = true;
}
foreach ($seeds as $sname => $entry) {
    if (!isset($activeSeeds[$sname])) unset($seeds[$sname]);
}
$seedsData['seeds'] = $seeds;

write_json_file_atomic($playersFile, $players);
write_json_file_atomic($seedsFile, $seedsData);

/* response: players in same seed+sector */
$outPlayers = [];
if ($seed !== '') {
    foreach ($players as $uname => $p) {
        if (!is_array($p)) continue;
        if (($p['seed'] ?? '') !== $seed) continue;
        if ((string)($p['sector'] ?? '') !== (string)$sector) continue;

        $outPlayers[] = [
            'username' => $uname,
            'x' => $p['x'] ?? 0,
            'y' => $p['y'] ?? 0,
            'facing' => $p['facing'] ?? 1,
            'aimAngle' => $p['aimAngle'] ?? 0,
            'holding' => $p['holding'] ?? 'melee',
            'hp' => $p['hp'] ?? 150,
            'dead' => $p['dead'] ?? false,
            'hasKeycard' => $p['hasKeycard'] ?? false,
            'crouch' => $p['crouch'] ?? false,
            'ammo' => $p['ammo'] ?? null,
            'reloading' => $p['reloading'] ?? 0
        ];
    }
}

/* world */
$worldOut = [
    'deadEnemies' => [],
    'removedItems' => [],
    'drops' => new stdClass(),
    'glowsticks' => new stdClass(),
    'removedGlowsticks' => [],
    'shots' => []
];

if ($seed !== '' && isset($seeds[$seed]) && is_array($seeds[$seed])) {
    $sectorKey = (string)$sector;
    $sec = $seeds[$seed]['sectors'][$sectorKey] ?? null;
    if (is_array($sec)) {
        $worldOut['deadEnemies'] = (isset($sec['deadEnemies']) && is_array($sec['deadEnemies'])) ? $sec['deadEnemies'] : [];
        $worldOut['removedItems'] = (isset($sec['removedItems']) && is_array($sec['removedItems'])) ? $sec['removedItems'] : [];
        $drops = (isset($sec['drops']) && is_array($sec['drops'])) ? $sec['drops'] : [];
        $worldOut['drops'] = $drops;

        $glows = (isset($sec['glowsticks']) && is_array($sec['glowsticks'])) ? $sec['glowsticks'] : [];
        $worldOut['glowsticks'] = $glows;

        $worldOut['removedGlowsticks'] = (isset($sec['removedGlowsticks']) && is_array($sec['removedGlowsticks'])) ? $sec['removedGlowsticks'] : [];

        // prune shots again at output time (in case of GET)
        $shots = [];
        $nowf = microtime(true);
        if (isset($sec['shots']) && is_array($sec['shots'])) {
            foreach ($sec['shots'] as $s) {
                if (!is_array($s)) continue;
                $t = isset($s['t']) ? (float)$s['t'] : 0.0;
                if ($t > 0 && ($nowf - $t) < 2.5) $shots[] = $s;
            }
        }
        $worldOut['shots'] = $shots;
    }
}

echo json_encode([
    'ok' => true,
    'serverTime' => $now,
    'players' => $outPlayers,
    'world' => $worldOut
], JSON_UNESCAPED_SLASHES);