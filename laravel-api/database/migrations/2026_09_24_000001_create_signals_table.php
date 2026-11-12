<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('signals', function (Blueprint $table) {
            $table->id();
            $table->string('strategy');           // 'breakout' | 'confluence'
            $table->date('day');
            $table->timestamp('signal_time');
            $table->enum('direction', ['BUY', 'SELL']);
            $table->decimal('entry_price', 10, 5);
            $table->decimal('stop_loss', 10, 5);
            $table->decimal('take_profit', 10, 5);
            $table->decimal('stop_pips', 8, 2);
            $table->decimal('lot_size', 6, 2);
            $table->json('reasons')->nullable();

            $table->enum('status', ['OPEN', 'CLOSED'])->default('OPEN');
            $table->timestamp('exit_time')->nullable();
            $table->decimal('exit_price', 10, 5)->nullable();
            $table->string('exit_reason')->nullable();   // TP | SL | TIME
            $table->decimal('pips_result', 8, 2)->nullable();
            $table->decimal('r_multiple', 8, 3)->nullable();

            $table->timestamps();

            $table->index(['day', 'direction', 'strategy']); // mirrors already_logged() dedupe in Python
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('signals');
    }
};
