<?php
// upload.php
$targetDir = "/home/j0sd9px3jsq7o44y/public_html/public/files/";
$maxFileSize = 10 * 1024 * 1024; // 10 MB

// Create target directory if it doesn't exist
if (!is_dir($targetDir)) {
    mkdir($targetDir, 0755, true);
}

// Check if a file is uploaded
if (!isset($_FILES["file"]) || $_FILES["file"]["error"] !== UPLOAD_ERR_OK) {
    http_response_code(400);
    echo json_encode(["error" => "No file uploaded or upload error"]);
    exit;
}

$fileTmpPath = $_FILES["file"]["tmp_name"];
$fileName = basename($_FILES["file"]["name"]);
$fileSize = $_FILES["file"]["size"];

// Block PHP, HTML, JS, EXE from execution
$forbiddenExtensions = ['php', 'php3', 'php4', 'php5', 'php7', 'phtml', 'html', 'htm', 'js', 'exe', 'sh', 'bat', 'cgi', 'pl'];
$fileExtension = strtolower(pathinfo($fileName, PATHINFO_EXTENSION));

if (in_array($fileExtension, $forbiddenExtensions)) {
    $fileExtension .= '.txt'; // Force safe extension
}

// Check file size
if ($fileSize > $maxFileSize) {
    http_response_code(400);
    echo json_encode(["error" => "File is too large"]);
    exit;
}

// Avoid overwriting existing files
$baseName = pathinfo($fileName, PATHINFO_FILENAME);
$counter = 1;
$newFileName = $baseName . '.' . $fileExtension;
while (file_exists($targetDir . $newFileName)) {
    $newFileName = $baseName . '_' . $counter++ . '.' . $fileExtension;
}

// Move uploaded file
if (move_uploaded_file($fileTmpPath, $targetDir . $newFileName)) {
    // Set safe permissions (readable but not executable)
    chmod($targetDir . $newFileName, 0644);

    echo json_encode([
        "success" => true,
        "file" => "/public/files/" . $newFileName
    ]);
} else {
    http_response_code(500);
    echo json_encode(["error" => "Error moving uploaded file"]);
}
?>
