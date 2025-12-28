<?php
// File: getversions.php

// Directory to read
$dir = "/home/j0sd9px3jsq7o44y/public_html/pybrowser.mekabrine.space/versions/";

// Scan directory and keep only files matching PyBrowser_v*.py
$all = scandir($dir);
$files = [];

foreach ($all as $f) {
    if (is_dir($dir . $f)) {
        continue;
    }
    // Match filenames like PyBrowser_v1_2_3.py
    if (preg_match('/^PyBrowser_v(.+)\.py$/', $f, $m)) {
        // Store original filename and normalized version string (1.2.3 style)
        $version = str_replace('_', '.', $m[1]);
        $files[] = [
            'filename' => $f,
            'version'  => $version
        ];
    }
}

// Sort by version (descending)
usort($files, function($a, $b) {
    // version_compare: returns > 0 if a > b
    return version_compare($b['version'], $a['version']); // descending
});

// Return only filenames in sorted order
$sortedFilenames = array_map(function($item) {
    return $item['filename'];
}, $files);

header('Content-Type: application/json');
echo json_encode($sortedFilenames);
