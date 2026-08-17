<?php

declare(strict_types=1);

/**
 * WhatsAppService
 * ================
 * Communicates with the local Node.js WhatsApp server.
 *
 * Flow:
 *   PHP -> HTTP POST -> Node.js (port 3333) -> WhatsApp -> Customer
 *
 * Usage:
 *   WhatsAppService::sendDebtorReceipt($debtor, $pdo);
 */
final class WhatsAppService
{
    private const TIMEOUT      = 60; // PDF generation takes time

    private static function getServerUrl(): string
    {
        $configPath = __DIR__ . '/config.php';
        if (file_exists($configPath)) {
            $config = require $configPath;
            if (!empty($config['wa_server_url'])) {
                return rtrim($config['wa_server_url'], '/');
            }
        }
        return 'http://127.0.0.1:3333';
    }

    private static function getSecretToken(): string
    {
        return 'YTSK_WA_Secret_2024';
    }

    // ── WhatsApp Message Template ─────────────────────────────────────────
    private const TEMPLATE = <<<MSG
Thank you for choosing Shree Shubh Travel.

An outstanding amount of ₹{AMOUNT} is pending for your railway ticket booking.

PNR Number: {PNR}
Booking Date: {BOOKED_DATE}
Outstanding Amount: ₹{AMOUNT}

Kindly clear the pending payment at your earliest convenience.

For assistance, please contact: +91 9415345750

Shree Shubh Travel
MSG;

    /**
     * Check if the Node.js WhatsApp server is running and ready
     */
    public static function isReady(): bool
    {
        try {
            $ch = curl_init(self::getServerUrl() . '/status');
            curl_setopt_array($ch, [
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT        => 3,
                CURLOPT_CONNECTTIMEOUT => 2,
                CURLOPT_SSL_VERIFYPEER => false,
                CURLOPT_SSL_VERIFYHOST => 0,
                CURLOPT_HTTPHEADER     => ['ngrok-skip-browser-warning: 1'],
            ]);
            $resp = curl_exec($ch);
            $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            if ($code !== 200 || !$resp) return false;
            $data = json_decode($resp, true);
            return ($data['ready'] ?? false) === true;
        } catch (Throwable) {
            return false;
        }
    }

    /**
     * Get connection status and QR code data URL from Node.js server
     */
    public static function getStatus(): array
    {
        try {
            $ch = curl_init(self::getServerUrl() . '/status');
            curl_setopt_array($ch, [
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT        => 3,
                CURLOPT_CONNECTTIMEOUT => 2,
                CURLOPT_SSL_VERIFYPEER => false,
                CURLOPT_SSL_VERIFYHOST => 0,
                CURLOPT_HTTPHEADER     => ['ngrok-skip-browser-warning: 1'],
            ]);
            $resp = curl_exec($ch);
            $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            if ($code !== 200 || !$resp) {
                return ['ready' => false, 'qr' => null];
            }
            $data = json_decode($resp, true);
            return [
                'ready' => ($data['ready'] ?? false) === true,
                'qr'    => $data['qr'] ?? null
            ];
        } catch (Throwable) {
            return ['ready' => false, 'qr' => null];
        }
    }

    /**
     * Format mobile number to 91XXXXXXXXXX structure
     */
    public static function formatMobile(string $mobile): ?string
    {
        $num = preg_replace('/\D/', '', $mobile);
        if (str_starts_with($num, '0')) {
            $num = substr($num, 1);
        }
        if (!str_starts_with($num, '91')) {
            $num = '91' . $num;
        }
        return strlen($num) === 12 ? $num : null;
    }

    /**
     * Build the WhatsApp message template from debtor data
     */
    public static function buildMessage(array $debtor): string
    {
        $pnr      = $debtor['pnr_no'] ?? 'N/A';
        $amount   = number_format(
                        max(0.0, (float)($debtor['amount_due'] ?? 0) - (float)($debtor['settled_amount'] ?? 0)),
                        2
                    );

        $bookedDate = !empty($debtor['booked_date'])
            ? date('d-M-Y', strtotime($debtor['booked_date']))
            : (!empty($debtor['due_date']) ? date('d-M-Y', strtotime($debtor['due_date'])) : 'N/A');

        return str_replace(
            ['{PNR}', '{AMOUNT}', '{BOOKED_DATE}'],
            [$pnr, $amount, $bookedDate],
            self::TEMPLATE
        );
    }

    /**
     * MAIN METHOD: Send receipt (PDF) + text message to debtor via WhatsApp
     *
     * @param array    $debtor  Debtor record array
     * @param PDO|null $pdo     Optional PDO connection for database logging
     * @return array   ['ok' => true/false, 'error' => '...']
     */
    public static function sendDebtorReceipt(array $debtor, ?PDO $pdo = null): array
    {
        $mobile = trim((string)($debtor['mobile'] ?? ''));

        if ($mobile === '') {
            return ['ok' => false, 'error' => 'Debtor mobile number is missing'];
        }

        $formattedMobile = self::formatMobile($mobile);
        if ($formattedMobile === null) {
            return ['ok' => false, 'error' => "Invalid mobile number: $mobile (must be 10 digits)"];
        }

        $message = self::buildMessage($debtor);

        // Detect if running on localhost (Windows development or localhost hostnames)
        $isLocalhost = (DIRECTORY_SEPARATOR === '\\')
                    || in_array($_SERVER['HTTP_HOST'] ?? '', ['localhost', '127.0.0.1', '::1'], true)
                    || str_contains($_SERVER['HTTP_HOST'] ?? '', 'localhost');

        $payload = [
            'token'       => self::getSecretToken(),
            'debtor_id'   => (int)($debtor['debtor_id'] ?? 0),
            'mobile'      => $formattedMobile,
            'debtor_name' => $debtor['debtor_name'] ?? '',
            'message'     => $message,
            'skip_pdf'    => false, // Always generate and send receipt PDF on production domain
        ];

        $result = self::httpPost('/send-receipt', $payload);

        // Log to Database
        if ($pdo !== null) {
            self::logToDb($pdo, $debtor, $formattedMobile, $message, $result);
        }

        return $result;
    }

    /**
     * Send plain text message only (without PDF attachment)
     */
    public static function sendText(string $mobile, string $message): array
    {
        $formatted = self::formatMobile($mobile);
        if ($formatted === null) {
            return ['ok' => false, 'error' => "Invalid mobile: $mobile"];
        }
        return self::httpPost('/send-text', [
            'token'   => self::getSecretToken(),
            'mobile'  => $formatted,
            'message' => $message,
        ]);
    }
    /**
     * Clear WhatsApp session on Node.js server
     */
    public static function logout(): array
    {
        return self::httpPost('/logout', [
            'token' => self::getSecretToken()
        ]);
    }
    // ── Private: HTTP POST to Node.js server ─────────────────────────────
    private static function httpPost(string $endpoint, array $data): array
    {
        $ch = curl_init(self::getServerUrl() . $endpoint);
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => json_encode($data),
            CURLOPT_HTTPHEADER     => [
                'Content-Type: application/json',
                'ngrok-skip-browser-warning: 1'
            ],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => self::TIMEOUT,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_SSL_VERIFYPEER => false,
            CURLOPT_SSL_VERIFYHOST => 0,
        ]);

        $resp    = curl_exec($ch);
        $code    = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curlErr = curl_error($ch);
        curl_close($ch);

        if ($curlErr !== '') {
            return [
                'ok'    => false,
                'error' => "Connection failed: $curlErr — Is the Node.js WhatsApp server running?"
            ];
        }

        if (!$resp) {
            return ['ok' => false, 'error' => "Empty response from server (HTTP $code)"];
        }

        $decoded = json_decode($resp, true);
        return is_array($decoded) ? $decoded : ['ok' => false, 'error' => "Invalid JSON: $resp"];
    }

    // ── Private: DB log ───────────────────────────────────────────────────
    private static function logToDb(PDO $pdo, array $debtor, string $mobile, string $message, array $result): void
    {
        try {
            // Ensure table exists (create automatically if missing)
            $pdo->exec("
                CREATE TABLE IF NOT EXISTS whatsapp_log (
                    log_id       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    debtor_id    INT UNSIGNED NOT NULL,
                    mobile       VARCHAR(20)  NOT NULL,
                    debtor_name  VARCHAR(200) DEFAULT NULL,
                    message_text TEXT         DEFAULT NULL,
                    status       ENUM('SENT','FAILED') NOT NULL DEFAULT 'SENT',
                    api_response TEXT         DEFAULT NULL,
                    sent_by      VARCHAR(100) DEFAULT NULL,
                    sent_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_debtor_id (debtor_id),
                    INDEX idx_sent_at   (sent_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ");

            $stmt = $pdo->prepare(
                'INSERT INTO whatsapp_log
                 (debtor_id, mobile, debtor_name, message_text, status, api_response, sent_by)
                 VALUES (?, ?, ?, ?, ?, ?, ?)'
            );
            $stmt->execute([
                (int)($debtor['debtor_id'] ?? 0),
                $mobile,
                $debtor['debtor_name'] ?? '',
                substr($message, 0, 500),
                ($result['ok'] ?? false) ? 'SENT' : 'FAILED',
                json_encode($result),
                $_SESSION['username'] ?? 'system',
            ]);
        } catch (Throwable $e) {
            error_log('[WhatsAppService] DB log error: ' . $e->getMessage());
        }
    }
}
