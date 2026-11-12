<?php

namespace App\Notifications\Channels;

use Illuminate\Notifications\Notification;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class TelegramChannel
{
    public function send(object $notifiable, Notification $notification): void
    {
        if (! method_exists($notification, 'toTelegram')) {
            return;
        }

        $text = $notification->toTelegram($notifiable);
        $token = config('services.telegram.bot_token');

        $response = Http::post("https://api.telegram.org/bot{$token}/sendMessage", [
            'chat_id'    => $notifiable->telegram_chat_id,
            'text'       => $text,
            'parse_mode' => 'HTML',
        ]);

        if ($response->failed()) {
            Log::warning('Telegram notification failed', [
                'user_id' => $notifiable->id,
                'response' => $response->body(),
            ]);
        }
    }
}
