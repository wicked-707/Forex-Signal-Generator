<?php

namespace App\Notifications;

use App\Models\Signal;
use App\Notifications\Channels\TelegramChannel;
use Illuminate\Bus\Queueable;
use Illuminate\Notifications\Notification;

class NewSignalNotification extends Notification
{
    use Queueable;

    public function __construct(public Signal $signal)
    {
    }

    /**
     * Route per-subscriber. Extend this array (and add matching via()
     * cases below) as you add WhatsApp/SMS/email channels.
     */
    public function via(object $notifiable): array
    {
        $channels = [];

        if ($notifiable->telegram_chat_id) {
            $channels[] = TelegramChannel::class;
        }

        // Example extension point:
        // if ($notifiable->whatsapp_number) { $channels[] = WhatsAppChannel::class; }

        return $channels ?: ['mail']; // fall back to email if nothing else is set up
    }

    public function toTelegram(object $notifiable): string
    {
        $s = $this->signal;
        $emoji = $s->direction === 'BUY' ? '🟢' : '🔴';

        return "{$emoji} <b>{$s->direction} EURUSD</b>\n"
            . "Entry: <code>{$s->entry_price}</code>\n"
            . "SL: <code>{$s->stop_loss}</code> ({$s->stop_pips} pips)\n"
            . "TP: <code>{$s->take_profit}</code>\n"
            . "Lot: {$s->lot_size}";
    }

    public function toMail(object $notifiable)
    {
        $s = $this->signal;

        return (new \Illuminate\Notifications\Messages\MailMessage)
            ->subject("New {$s->direction} signal — EURUSD")
            ->line("Entry: {$s->entry_price}")
            ->line("Stop loss: {$s->stop_loss} ({$s->stop_pips} pips)")
            ->line("Take profit: {$s->take_profit}")
            ->line("Lot size: {$s->lot_size}");
    }
}
