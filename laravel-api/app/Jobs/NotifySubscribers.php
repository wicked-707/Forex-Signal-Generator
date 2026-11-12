<?php

namespace App\Jobs;

use App\Models\Signal;
use App\Models\User;
use App\Notifications\NewSignalNotification;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;

class NotifySubscribers implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public function __construct(public Signal $signal)
    {
    }

    public function handle(): void
    {
        User::query()
            ->where('alerts_enabled', true)
            ->where(function ($q) {
                // Active paid plan OR still within trial — adjust to your billing logic.
                $q->where('plan', '!=', 'trial')
                  ->orWhere('subscription_expires_at', '>=', now());
            })
            ->chunk(200, function ($users) {
                foreach ($users as $user) {
                    $user->notify(new NewSignalNotification($this->signal));
                }
            });
    }
}
