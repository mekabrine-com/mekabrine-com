<?php
header("Access-Control-Allow-Origin: *");
header("Content-Type: application/json");

if (!isset($_GET['url'])) {
  http_response_code(400);
  echo json_encode(["error" => "Missing URL parameter"]);
  exit;
}

$url = filter_var($_GET['url'], FILTER_SANITIZE_URL);
if (!preg_match('/^https?:\/\//', $url)) {
  http_response_code(400);
  echo json_encode(["error" => "Invalid URL"]);
  exit;
}

$ch = curl_init($url);
curl_setopt_array($ch, [
  CURLOPT_RETURNTRANSFER => true,
  CURLOPT_FOLLOWLOCATION => true,
  CURLOPT_TIMEOUT => 15,
  CURLOPT_USERAGENT => "AltAppStoreProxy/1.0",
  CURLOPT_SSL_VERIFYPEER => true,
  CURLOPT_SSL_VERIFYHOST => 2
]);
$response = curl_exec($ch);
$err = curl_error($ch);
$httpCode = curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
curl_close($ch);

if ($response === false || $httpCode >= 400) {
  http_response_code(500);
  echo json_encode(["error" => "Proxy failed for $url", "details" => $err]);
  exit;
}

echo $response;
?>
