# Laravel API — setup notes

These files are meant to be dropped into an existing (or new)
Laravel project — they were not run through `composer install` in this
sandbox (no internet access to packagist.org here), so test them in
your own environment before relying on them.

## 1. Copy files in
Copy `app/`, `database/migrations/`, and `routes/api.php` contents into
the matching folders of your Laravel project (merge `routes/api.php`
rather than overwrite, if you already have routes there).

## 2. Register the middleware
In `bootstrap/app.php` (Laravel 11+) or `app/Http/Kernel.php` (Laravel 10-):

```php
// bootstrap/app.php example (Laravel 11+)
->withMiddleware(function (Middleware $middleware) {
    $middleware->alias(['api.key' => \App\Http\Middleware\VerifyApiKey::class]);
})
```

## 3. Add to config/services.php
```php
'bot' => [
    'api_key' => env('BOT_API_KEY'),
],
'telegram' => [
    'bot_token' => env('TELEGRAM_BOT_TOKEN'),
],
'mpesa' => [
    'env'             => env('MPESA_ENV', 'sandbox'),
    'consumer_key'    => env('MPESA_CONSUMER_KEY'),
    'consumer_secret' => env('MPESA_CONSUMER_SECRET'),
    'shortcode'       => env('MPESA_SHORTCODE'),
    'passkey'         => env('MPESA_PASSKEY'),
    'callback_url'    => env('MPESA_CALLBACK_URL'),
],
'paystack' => [
    'secret_key' => env('PAYSTACK_SECRET_KEY'),
],
```

## 4. .env additions
```
BOT_API_KEY=                  # must match config_alerts.LARAVEL_API_KEY in the Python bot
TELEGRAM_BOT_TOKEN=           # same bot token as the Python side, or a separate bot — your call
MPESA_ENV=sandbox
MPESA_CONSUMER_KEY=
MPESA_CONSUMER_SECRET=
MPESA_SHORTCODE=
MPESA_PASSKEY=
MPESA_CALLBACK_URL=
PAYSTACK_SECRET_KEY=
```

## 5. Run migrations
```
php artisan migrate
```

## 6. Run the queue worker
`NotifySubscribers` is queued — signals won't actually reach anyone
until a worker is running:
```
php artisan queue:work
```

## 7. Point the Python bot at this API
In `config_alerts.py`:
```python
LARAVEL_API_ENABLED = True
LARAVEL_API_URL = "https://your-domain.example.com/api/signals"
LARAVEL_API_KEY = "<same value as BOT_API_KEY above>"
```

## Order of operations
Don't flip `LARAVEL_API_ENABLED = True` (or open subscriptions) until
`run_live.py` has been alerting you alone for a real stretch of time
and `signal_store.performance_summary()` shows something worth other
people's money.
