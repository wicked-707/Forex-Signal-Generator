<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Jobs\NotifySubscribers;
use App\Models\Signal;
use Illuminate\Http\Request;

class SignalController extends Controller
{
    /**
     * POST /api/signals — called by the Python bot (run_live.py -> api_client.py)
     * whenever a new signal fires. Protected by VerifyApiKey middleware.
     */
    public function store(Request $request)
    {
        $validated = $request->validate([
            'strategy'     => ['required', 'string'],
            'day'          => ['required', 'date'],
            'signal_time'  => ['required', 'date'],
            'direction'    => ['required', 'in:BUY,SELL'],
            'entry_price'  => ['required', 'numeric'],
            'stop_loss'    => ['required', 'numeric'],
            'take_profit'  => ['required', 'numeric'],
            'stop_pips'    => ['required', 'numeric'],
            'lot_size'     => ['required', 'numeric'],
            'reasons'      => ['nullable', 'array'],
        ]);

        // Dedupe: don't double-post the same day's signal if the bot retries.
        $existing = Signal::where('day', $validated['day'])
            ->where('direction', $validated['direction'])
            ->where('strategy', $validated['strategy'])
            ->first();

        if ($existing) {
            return response()->json(['message' => 'Already recorded', 'signal' => $existing], 200);
        }

        $signal = Signal::create($validated);

        // Fan out to subscribers asynchronously (Telegram/WhatsApp/email per preference).
        NotifySubscribers::dispatch($signal);

        return response()->json(['message' => 'Signal recorded', 'signal' => $signal], 201);
    }

    /**
     * GET /api/signals — feeds the React dashboard.
     */
    public function index(Request $request)
    {
        $signals = Signal::orderByDesc('signal_time')
            ->limit($request->integer('limit', 100))
            ->get();

        return response()->json($signals);
    }

    /**
     * GET /api/signals/performance — live (not backtested) track record.
     */
    public function performance()
    {
        $closed = Signal::where('status', 'CLOSED')->get();

        if ($closed->isEmpty()) {
            return response()->json(['total_trades' => 0, 'message' => 'No closed live signals yet.']);
        }

        $wins = $closed->where('r_multiple', '>', 0);

        return response()->json([
            'total_trades' => $closed->count(),
            'wins'         => $wins->count(),
            'win_rate_pct' => round($wins->count() / $closed->count() * 100, 2),
            'avg_r'        => round($closed->avg('r_multiple'), 3),
            'total_r'      => round($closed->sum('r_multiple'), 2),
        ]);
    }
}
