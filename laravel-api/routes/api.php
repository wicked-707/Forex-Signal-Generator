<?php

use App\Http\Controllers\Api\SignalController;
use Illuminate\Support\Facades\Route;

/*
|--------------------------------------------------------------------------
| Merge these into your existing routes/api.php
|--------------------------------------------------------------------------
*/

// Machine-to-machine: the Python bot posts new signals here.
Route::middleware('api.key')->post('/signals', [SignalController::class, 'store']);

// Public/subscriber-facing: feeds the React dashboard.
// Wrap these in ->middleware('auth:sanctum') once you have subscriber
// login, so only paying subscribers can see live signals.
Route::get('/signals', [SignalController::class, 'index']);
Route::get('/signals/performance', [SignalController::class, 'performance']);

// M-Pesa Daraja posts payment results here asynchronously — register
// once you wire up DarajaService + a PaymentController.
// Route::post('/mpesa/callback', [PaymentController::class, 'mpesaCallback']);
