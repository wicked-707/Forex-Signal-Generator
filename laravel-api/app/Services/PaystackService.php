<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;

/**
 * Paystack — card/mobile-money payments for subscribers outside Kenya
 * (or anyone who prefers card over M-Pesa). Paystack also supports
 * M-Pesa in some markets if you'd rather use one provider for both.
 *
 * Setup: get keys from https://dashboard.paystack.com/#/settings/developer
 *   PAYSTACK_SECRET_KEY=sk_...
 */
class PaystackService
{
    private string $base = 'https://api.paystack.co';

    public function initializeTransaction(string $email, int $amountSubunit, ?string $planCode = null): array
    {
        $payload = array_filter([
            'email'  => $email,
            'amount' => $amountSubunit,  // smallest currency unit (e.g. kobo, cents)
            'plan'   => $planCode,       // optional: use a Paystack Plan for recurring billing
        ]);

        $response = Http::withToken(config('services.paystack.secret_key'))
            ->post("{$this->base}/transaction/initialize", $payload);

        return $response->json();
    }

    public function verifyTransaction(string $reference): array
    {
        $response = Http::withToken(config('services.paystack.secret_key'))
            ->get("{$this->base}/transaction/verify/{$reference}");

        return $response->json();
    }
}
