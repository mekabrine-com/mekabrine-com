<?php
// message-helper.php
// Handles saving Caesar-shifted messages, and deleting messages
// older than 60 seconds (server-verified).

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(["success" => false, "error" => "Only POST allowed"]);
    exit;
}

$root = __DIR__ . "/c"; // /home/.../c.mekabrine.space/c

// Sanitize folder and filename safely
function clean_folder($s) {
    // allow alnum, underscore, hyphen, slash for subfolders if you want — here we restrict to single-level
    return preg_replace('/[^a-zA-Z0-9_-]/', '', $s);
}
function clean_filename($s) {
    // make sure it's only a basename like 92820252020.txt
    $s = basename($s);
    return preg_replace('/[^a-zA-Z0-9_.-]/', '', $s);
}

$action = isset($_POST['action']) ? strtolower($_POST['action']) : 'save';
$folder = isset($_POST['folder']) ? clean_folder($_POST['folder']) : 'public';

if ($folder === '') $folder = 'public';
$targetDir = $root . "/" . $folder;

// Ensure directory exists on both actions if needed
if (!is_dir($targetDir)) {
    if ($action === 'save') {
        if (!mkdir($targetDir, 0775, true)) {
            http_response_code(500);
            echo json_encode(["success" => false, "error" => "Failed to create folder"]);
            exit;
        }
    } else {
        // For delete, if folder doesn't exist, treat as nothing to delete
        echo json_encode(["success" => true, "deleted" => false, "reason" => "Folder not found"]);
        exit;
    }
}

if ($action === 'save') {
    $filename = isset($_POST['filename']) ? clean_filename($_POST['filename']) : '';
    $message  = isset($_POST['message'])  ? $_POST['message'] : '';

    if ($filename === '' || $message === '') {
        http_response_code(400);
        echo json_encode(["success" => false, "error" => "Missing filename or message"]);
        exit;
    }

    $targetFile = $targetDir . "/" . $filename;
    if (file_put_contents($targetFile, $message) === false) {
        http_response_code(500);
        echo json_encode(["success" => false, "error" => "Failed to write file"]);
        exit;
    }

    $publicUrl = "https://c.mekabrine.space/c/" . rawurlencode($folder) . "/" . rawurlencode($filename);
    echo json_encode(["success" => true, "file" => $publicUrl, "action" => "save"]);
    exit;
}

if ($action === 'delete') {
    $filename = isset($_POST['filename']) ? clean_filename($_POST['filename']) : '';
    if ($filename === '') {
        http_response_code(400);
        echo json_encode(["success" => false, "error" => "Missing filename for delete"]);
        exit;
    }

    $targetFile = $targetDir . "/" . $filename;
    if (!file_exists($targetFile)) {
        echo json_encode(["success" => true, "deleted" => false, "reason" => "File not found", "action" => "delete"]);
        exit;
    }

    $now = time();
    $mtime = filemtime($targetFile);
    if ($mtime === false) {
        http_response_code(500);
        echo json_encode(["success" => false, "error" => "Failed to read file mtime"]);
        exit;
    }

    $age = $now - $mtime;
    if ($age >= 60) {
        if (@unlink($targetFile)) {
            echo json_encode(["success" => true, "deleted" => true, "age" => $age, "action" => "delete"]);
        } else {
            http_response_code(500);
            echo json_encode(["success" => false, "deleted" => false, "error" => "Failed to delete file"]);
        }
    } else {
        echo json_encode([
            "success" => true,
            "deleted" => false,
            "age" => $age,
            "reason" => "Not old enough",
            "action" => "delete"
        ]);
    }
    exit;
}

// Unknown action
http_response_code(400);
echo json_encode(["success" => false, "error" => "Unknown action"]);
