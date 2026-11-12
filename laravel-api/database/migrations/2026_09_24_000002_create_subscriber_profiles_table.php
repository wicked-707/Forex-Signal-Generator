<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // Extends your existing `users` table with alerts-product fields.
        // If you'd rather keep this separate from auth users, rename this
        // to a standalone `subscribers` table instead — the notification
        // channel code doesn't care either way as long as the columns exist.
        Schema::table('users', function (Blueprint $table) {
            $table->string('telegram_chat_id')->nullable()->after('email');
            $table->string('whatsapp_number')->nullable()->after('telegram_chat_id');
            $table->enum('plan', ['trial', 'basic', 'pro'])->default('trial')->after('whatsapp_number');
            $table->timestamp('subscription_expires_at')->nullable()->after('plan');
            $table->boolean('alerts_enabled')->default(true)->after('subscription_expires_at');
        });
    }

    public function down(): void
    {
        Schema::table('users', function (Blueprint $table) {
            $table->dropColumn([
                'telegram_chat_id', 'whatsapp_number', 'plan',
                'subscription_expires_at', 'alerts_enabled',
            ]);
        });
    }
};
