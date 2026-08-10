<?php
declare(strict_types=1);

header('X-Robots-Tag: noindex, nofollow, noarchive', true);
header('Cache-Control: no-store, max-age=0', true);
header('Content-Type: application/json; charset=UTF-8', true);

ini_set('display_errors', '0');
ini_set('log_errors', '1');
ini_set('session.use_strict_mode', '1');
ini_set('session.use_only_cookies', '1');

const CONTACT_RECIPIENT = 'contact@ridersfanatics.com';
const MAX_REQUEST_BYTES = 16384;
const ALLOWED_HOSTS = ['ridersfanatics.com', 'www.ridersfanatics.com'];

function wants_json(): bool
{
    return str_contains(strtolower($_SERVER['HTTP_ACCEPT'] ?? ''), 'application/json')
        || strtolower($_SERVER['HTTP_X_REQUESTED_WITH'] ?? '') === 'xmlhttprequest';
}

function finish_request(bool $ok, string $message, int $status = 200): never
{
    http_response_code($status);
    if (wants_json()) {
        echo json_encode(['ok' => $ok, 'message' => $message], JSON_UNESCAPED_SLASHES);
        exit;
    }
    header('Location: contact.html?' . ($ok ? 'sent=1' : 'error=1'), true, 303);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    finish_request(false, 'Method not allowed.', 405);
}

$requestHost = strtolower(preg_replace('/:\d+$/', '', $_SERVER['HTTP_HOST'] ?? ''));
if (!in_array($requestHost, ALLOWED_HOSTS, true)) {
    finish_request(false, 'Invalid request host.', 400);
}

$contentLength = filter_var($_SERVER['CONTENT_LENGTH'] ?? 0, FILTER_VALIDATE_INT);
if ($contentLength !== false && $contentLength > MAX_REQUEST_BYTES) {
    finish_request(false, 'Request too large.', 413);
}

$contentType = strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0]));
if (!in_array($contentType, ['application/x-www-form-urlencoded', 'multipart/form-data'], true)) {
    finish_request(false, 'Unsupported content type.', 415);
}

$fetchSite = strtolower($_SERVER['HTTP_SEC_FETCH_SITE'] ?? '');
if ($fetchSite !== '' && !in_array($fetchSite, ['same-origin', 'same-site', 'none'], true)) {
    finish_request(false, 'Cross-site request rejected.', 403);
}

session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/',
    'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off',
    'httponly' => true,
    'samesite' => 'Strict',
]);
session_start();

function clean_line(string $value, int $max): string
{
    $value = trim(preg_replace('/[\r\n\t]+/u', ' ', $value) ?? '');
    return mb_substr($value, 0, $max, 'UTF-8');
}

$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin !== '') {
    $originHost = strtolower((string) parse_url($origin, PHP_URL_HOST));
    if ($originHost === '' || !hash_equals($requestHost, $originHost)) {
        finish_request(false, 'Invalid request origin.', 403);
    }
}

$referer = $_SERVER['HTTP_REFERER'] ?? '';
if ($origin === '' && $referer !== '') {
    $refererHost = strtolower((string) parse_url($referer, PHP_URL_HOST));
    if ($refererHost === '' || !hash_equals($requestHost, $refererHost)) {
        finish_request(false, 'Invalid request source.', 403);
    }
}

// Honeypot: bots receive a neutral success but no message is sent.
if (trim((string) ($_POST['company'] ?? '')) !== '') {
    finish_request(true, 'Message received.');
}

$now = time();
$last = (int) ($_SESSION['contact_last_attempt'] ?? 0);
if ($last > 0 && ($now - $last) < 60) {
    finish_request(false, 'Please wait before sending another message.', 429);
}

$started = filter_var($_POST['form_started'] ?? null, FILTER_VALIDATE_INT);
if ($started !== false && $started > 0 && (($now - $started) < 3 || ($now - $started) > 86400)) {
    finish_request(false, 'Please reload the form and try again.', 400);
}

$name = clean_line((string) ($_POST['name'] ?? ''), 100);
$email = clean_line((string) ($_POST['email'] ?? ''), 254);
$reason = clean_line((string) ($_POST['reason'] ?? ''), 30);
$pageUrl = trim((string) ($_POST['page_url'] ?? ''));
$message = trim((string) ($_POST['message'] ?? ''));
$consent = (string) ($_POST['consent'] ?? '');

$reasonLabels = [
    'correction' => 'Data correction',
    'source' => 'New source or equipment update',
    'partnership' => 'Partnership or media',
    'technical' => 'Website issue',
    'other' => 'Other',
];

if ($name === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)
    || !isset($reasonLabels[$reason]) || mb_strlen($message, 'UTF-8') < 10
    || mb_strlen($message, 'UTF-8') > 5000 || $consent !== 'yes') {
    finish_request(false, 'Please complete all required fields.', 422);
}

if ($pageUrl !== '') {
    if (strlen($pageUrl) > 500 || !filter_var($pageUrl, FILTER_VALIDATE_URL)
        || !in_array(strtolower((string) parse_url($pageUrl, PHP_URL_SCHEME)), ['http', 'https'], true)) {
        finish_request(false, 'The relevant page URL is invalid.', 422);
    }
}

$_SESSION['contact_last_attempt'] = $now;
$safeMessage = str_replace(["\r\n", "\r"], "\n", $message);
$subject = '[RidersFanatics] ' . $reasonLabels[$reason];
$body = "New RidersFanatics contact message\n\n"
    . "Reason: " . $reasonLabels[$reason] . "\n"
    . "Name: " . $name . "\n"
    . "Email: " . $email . "\n"
    . "Relevant page: " . ($pageUrl !== '' ? $pageUrl : 'Not provided') . "\n\n"
    . "Message:\n" . $safeMessage . "\n";
$headers = [
    'From: RidersFanatics Website <contact@ridersfanatics.com>',
    'Reply-To: ' . $email,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: 8bit',
];

$sent = mail(CONTACT_RECIPIENT, $subject, $body, implode("\r\n", $headers));
if (!$sent) {
    finish_request(false, 'The message could not be delivered.', 503);
}

finish_request(true, 'Message sent.');
