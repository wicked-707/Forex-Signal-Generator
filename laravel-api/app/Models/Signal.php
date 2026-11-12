<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class Signal extends Model
{
    protected $fillable = [
        'strategy', 'day', 'signal_time', 'direction',
        'entry_price', 'stop_loss', 'take_profit', 'stop_pips',
        'lot_size', 'reasons', 'status',
        'exit_time', 'exit_price', 'exit_reason', 'pips_result', 'r_multiple',
    ];

    protected $casts = [
        'day'         => 'date',
        'signal_time' => 'datetime',
        'exit_time'   => 'datetime',
        'reasons'     => 'array',
    ];
}
