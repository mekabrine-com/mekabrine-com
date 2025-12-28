<?php

function make_absolute($url, $base) {
    $parsed_url = parse_url($url);
    if (isset($parsed_url['scheme'])) {
        return $url;
    }

    $parsed_base = parse_url($base);
    $scheme = isset($parsed_base['scheme']) ? $parsed_base['scheme'] . '://' : 'https://';
    $host   = isset($parsed_base['host'])   ? $parsed_base['host']            : '';
    $port   = isset($parsed_base['port'])   ? ':' . $parsed_base['port']      : '';
    $path   = isset($parsed_base['path'])   ? $parsed_base['path']            : '/';

    if ($url[0] === '#' || $url[0] === '?') {
        return $base . $url;
    }

    if ($url[0] === '/') {
        $new_path = $url;
    } else {
        $base_dir = (substr($path, -1) === '/') ? $path : dirname($path);
        $new_path = $base_dir . '/' . $url;
    }

    $path_parts = explode('/', $new_path);
    $abs_path   = [];
    foreach ($path_parts as $part) {
        if ($part === '' || $part === '.') continue;
        if ($part === '..') {
            array_pop($abs_path);
        } else {
            $abs_path[] = $part;
        }
    }
    $new_path = '/' . implode('/', $abs_path);

    $result = $scheme . $host . $port . $new_path;
    if (isset($parsed_base['query'])) {
        $result .= '?' . $parsed_base['query'];
    }
    if (isset($parsed_base['fragment'])) {
        $result .= '#' . $parsed_base['fragment'];
    }

    return $result;
}

if (empty($_GET['url'])) {
    http_response_code(400);
    die('No URL provided');
}

$target_url = urldecode($_GET['url']);
if (!filter_var($target_url, FILTER_VALIDATE_URL)) {
    http_response_code(400);
    die('Invalid URL');
}

// Use visitor's browser UA (fallback if missing)
$userAgent = !empty($_SERVER['HTTP_USER_AGENT'])
    ? $_SERVER['HTTP_USER_AGENT']
    : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36';

// Fetch with cURL
$ch = curl_init($target_url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
curl_setopt($ch, CURLOPT_USERAGENT, $userAgent);
curl_setopt($ch, CURLOPT_HEADER, false);
$response      = curl_exec($ch);
$content_type  = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
$effective_url = curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);
curl_close($ch);

if ($response === false) {
    http_response_code(500);
    die('Failed to fetch URL');
}

// Non-HTML: just passthrough
if (strpos($content_type, 'text/html') === false) {
    if ($content_type) {
        header("Content-Type: $content_type");
    }
    echo $response;
    exit;
}

// Parse HTML
libxml_use_internal_errors(true);
$dom = new DOMDocument();
$dom->loadHTML($response, LIBXML_HTML_NOIMPLIED | LIBXML_HTML_NODEFDTD);

// base href
$base_nodes = $dom->getElementsByTagName('base');
$base_href  = ($base_nodes->length > 0)
    ? $base_nodes->item(0)->getAttribute('href')
    : $effective_url;

// tags to rewrite
$rewrite_map = [
    'a'      => 'href',
    'link'   => 'href',
    'img'    => 'src',
    'script' => 'src',
    'iframe' => 'src',
    'embed'  => 'src',
    'object' => 'data',
    'source' => 'src',
    'form'   => 'action',
];

$proxy_script = basename(__FILE__);

foreach ($rewrite_map as $tag => $attr) {
    $nodes = $dom->getElementsByTagName($tag);
    for ($i = $nodes->length - 1; $i >= 0; $i--) {
        $node = $nodes->item($i);
        if ($node->hasAttribute($attr)) {
            $original_val = $node->getAttribute($attr);
            if (!empty($original_val)
                && stripos($original_val, 'javascript:') !== 0
                && stripos($original_val, 'data:') !== 0
            ) {
                $absolute_url = make_absolute($original_val, $base_href);
                $proxied_url  = $proxy_script . '?url=' . urlencode($absolute_url);
                $node->setAttribute($attr, $proxied_url);
            }
        }
    }
}

// serialize HTML
$html = $dom->saveHTML();

// === Inject JS to catch client-side navigation like "/results" ===

// origin and path of the ORIGINAL site (not your proxy)
$parsed_base = parse_url($effective_url);
$origin = ($parsed_base['scheme'] ?? 'https') . '://' . ($parsed_base['host'] ?? '');
if (!empty($parsed_base['port'])) {
    $origin .= ':' . $parsed_base['port'];
}
$path_for_js = $parsed_base['path'] ?? '/';

$proxy_js = <<<JS
<script>
(function () {
    var proxyScript = "{$proxy_script}";
    var originalOrigin = "{$origin}";
    var originalPath = "{$path_for_js}";

    function absFromOriginal(url) {
        if (!url) return originalOrigin + originalPath;

        // already absolute (has scheme)
        if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(url)) {
            return url;
        }

        // protocol-relative
        if (url.substring(0, 2) === "//") {
            return window.location.protocol + url;
        }

        // query or fragment only
        if (url[0] === "?" || url[0] === "#") {
            return originalOrigin + originalPath + url;
        }

        // root-relative
        if (url[0] === "/") {
            return originalOrigin + url;
        }

        // relative path
        var basePath = originalPath;
        if (!basePath.endsWith("/")) {
            var idx = basePath.lastIndexOf("/");
            basePath = (idx >= 0 ? basePath.substring(0, idx + 1) : "/");
        }
        var combined = basePath + url;

        var segments = combined.split("/");
        var out = [];
        for (var i = 0; i < segments.length; i++) {
            var seg = segments[i];
            if (seg === "" || seg === ".") continue;
            if (seg === "..") {
                if (out.length) out.pop();
            } else {
                out.push(seg);
            }
        }
        return originalOrigin + "/" + out.join("/");
    }

    function proxify(url) {
        var abs = absFromOriginal(url);
        return proxyScript + "?url=" + encodeURIComponent(abs);
    }

    // intercept History API
    try {
        var _pushState = history.pushState;
        history.pushState = function (state, title, url) {
            if (url) url = proxify(url);
            return _pushState.call(this, state, title, url);
        };

        var _replaceState = history.replaceState;
        history.replaceState = function (state, title, url) {
            if (url) url = proxify(url);
            return _replaceState.call(this, state, title, url);
        };
    } catch (e) {}

    // intercept location.assign / location.replace
    try {
        var _assign = window.location.assign.bind(window.location);
        window.location.assign = function (url) {
            return _assign(proxify(url));
        };

        var _replace = window.location.replace.bind(window.location);
        window.location.replace = function (url) {
            return _replace(proxify(url));
        };
    } catch (e) {}

})();
</script>
JS;

// inject before </body>, or at end if no body tag
if (stripos($html, '</body>') !== false) {
    $html = preg_replace('~</body>~i', $proxy_js . '</body>', $html, 1);
} else {
    $html .= $proxy_js;
}

// Output
if ($content_type) {
    header("Content-Type: $content_type");
}
echo $html;
