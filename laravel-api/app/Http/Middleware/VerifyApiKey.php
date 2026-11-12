<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;

class VerifyApiKey
{
    /**
     * Simple shared-secret check for the Python bot's POST /api/signals.
     * Set BOT_API_KEY in .env — it must match config_alerts.LARAVEL_API_KEY
     * on the Python side exactly.
     */
    public function handle(Request $request, Closure $next)
    {
        $provided = $request->header('X-API-Key');

        if (! $provided || ! hash_equals((string) config('services.bot.api_key'), (string) $provided)) {
            return response()->json(['message' => 'Invalid API key.'], 401);
        }

        return $next($request);
    }
}
