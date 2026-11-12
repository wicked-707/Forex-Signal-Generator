<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Cache;

/**
 * M-Pesa Daraja API — STK Push (Lipa Na M-Pesa Online).
 *
 * Setup:
 *   1. Register at https://developer.safaricom.co.ke and create an app
 *      to get a Consumer Key/Secret (sandbox first, then go-live).
 *   2. Add to .env:
 *        MPESA_ENV=sandbox            (or 'production')
 *        MPESA_CONSUMER_KEY=...
 *        MPESA_CONSUMER_SECRET=...
 *        MPESA_SHORTCODE=...          (Paybill/Till number)
 *        MPESA_PASSKEY=...
 *        MPESA_CALLBACK_URL=https://your-domain.example.com/api/mpesa/callback
 *   3. Register the callback route (see routes/api.php) — Safaricom
 *      posts the payment result there asynchronously; this is NOT
 *      returned synchronously from stkPush().
 *
 * This is a skeleton — it has NOT been run against Safaricom's sandbox
 * in this environment. Test thoroughly against sandbox before going live.
 */
class DarajaService
{
    private function baseUrl(): string
    {
        return config('services.mpesa.env') === 'production'
            ? 'https://api.safaricom.co.ke'
            : 'https://sandbox.safaricom.co.ke';
    }

    private function accessToken(): string
    {
        return Cache::remember('mpesa_access_token', 3500, function () {
            $response = Http::withBasicAuth(
                config('services.mpesa.consumer_key'),
                config('services.mpesa.consumer_secret'),
            )->get($this->baseUrl() . '/oauth/v1/generate?grant_type=client_credentials');

            return $response->json('access_token');
        });
    }

    /**
     * Prompt the subscriber's phone for an M-Pesa PIN to pay for their plan.
     * $phone must be in 2547XXXXXXXX format (no leading 0 or +).
     */
    public function stkPush(string $phone, int $amountKes, string $accountReference): array
    {
        $shortcode = config('services.mpesa.shortcode');
        $passkey   = config('services.mpesa.passkey');
        $timestamp = now()->format('YmdHis');
        $password  = base64_encode($shortcode . $passkey . $timestamp);

        $response = Http::withToken($this->accessToken())
            ->post($this->baseUrl() . '/mpesa/stkpush/v1/processrequest', [
                'BusinessShortCode' => $shortcode,
                'Password'          => $password,
                'Timestamp'         => $timestamp,
                'TransactionType'   => 'CustomerPayBillOnline',
                'Amount'            => $amountKes,
                'PartyA'            => $phone,
                'PartyB'            => $shortcode,
                'PhoneNumber'       => $phone,
                'CallBackURL'       => config('services.mpesa.callback_url'),
                'AccountReference'  => $accountReference,
                'TransactionDesc'   => 'Forex alerts subscription',
            ]);

        return $response->json();
    }
}
