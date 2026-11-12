from pathlib import Path

path = Path("backtest.py")
text = path.read_text(encoding="utf-8")

start_marker = "def run_backtest("
end_marker = "\n\n# ============================================================\n# REPORTING"

start = text.index(start_marker)
end = text.index(end_marker, start)

new_function = '''def run_backtest(dfs, mode_name, mode_cfg, bt_cfg, verbose=False, start=None, end=None):
    aligned = build_aligned_frames(dfs, mode_cfg)

    df_trig = aligned["trigger"]
    n = len(df_trig)
    ts_index_for_range = df_trig.index

    # Convert to numpy arrays for speed.
    o = df_trig["open"].to_numpy()
    h = df_trig["high"].to_numpy()
    l = df_trig["low"].to_numpy()
    c = df_trig["close"].to_numpy()
    rsi_t = df_trig["rsi"].to_numpy()
    ema_fast_t = df_trig["ema_fast"].to_numpy()
    spread_t = df_trig["spread"].to_numpy()
    ts_index = df_trig.index

    # HTF aligned arrays.
    bias_ema_mid  = aligned["bias_tf"]["ema_mid"].to_numpy()
    bias_ema_slow = aligned["bias_tf"]["ema_slow"].to_numpy()
    bias_adx      = aligned["bias_tf"]["adx"].to_numpy()
    bias_close    = aligned["bias_tf"]["close"].to_numpy()

    conf_ema_mid  = aligned["confirm_tf"]["ema_mid"].to_numpy()
    conf_close    = aligned["confirm_tf"]["close"].to_numpy()

    setup_ema_fast = aligned["setup_tf"]["ema_fast"].to_numpy()
    setup_ema_mid  = aligned["setup_tf"]["ema_mid"].to_numpy()
    setup_ema_slow = aligned["setup_tf"]["ema_slow"].to_numpy()
    setup_atr      = aligned["setup_tf"]["atr"].to_numpy()
    setup_rsi      = aligned["setup_tf"]["rsi"].to_numpy()
    setup_close    = aligned["setup_tf"]["close"].to_numpy()

    trades = []
    open_trade: Optional[Trade] = None
    open_trade_bar = -1
    cooldown_until = 0

    warmup = max(
        cfg.EMA_SLOW,
        cfg.ATR_PERIOD,
        cfg.ADX_PERIOD,
    ) + 20

    # --------------------------------------------------------
    # Requested backtest range
    # --------------------------------------------------------
    # Indicators are still calculated from the complete dataset
    # so EMA200/ATR/etc. have sufficient warmup history.
    #
    # However:
    #   - signals may only OPEN inside the requested range;
    #   - a signal on the final allowed bar cannot open outside it;
    #   - an open trade is forcibly closed at the final bar of the
    #     requested range.
    range_start_i = warmup
    range_end_i = n

    if start is not None:
        start_ts = pd.Timestamp(start, tz="UTC")
        range_start_i = max(
            range_start_i,
            ts_index_for_range.searchsorted(
                start_ts,
                side="left",
            ),
        )

    if end is not None:
        end_ts = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
        range_end_i = min(
            range_end_i,
            ts_index_for_range.searchsorted(
                end_ts,
                side="left",
            ),
        )

    # Last bar that belongs to the requested range.
    # If the requested range ends before the dataset, this is
    # range_end_i - 1. Otherwise it is the final dataset bar.
    range_last_i = range_end_i - 1

    if range_last_i < warmup:
        return trades

    # --------------------------------------------------------
    # BACKTEST LOOP
    # --------------------------------------------------------
    for i in range(warmup, range_end_i):

        # ----------------------------------------------------
        # Manage open trade
        # ----------------------------------------------------
        if open_trade is not None:

            # Never allow a training/test trade to be managed
            # beyond the requested range.
            if i > range_last_i:
                break

            # SL / TP checks
            if open_trade.direction == "BUY":
                hit_sl = l[i] <= open_trade.stop_loss
                hit_tp = h[i] >= open_trade.take_profit
            else:
                hit_sl = h[i] >= open_trade.stop_loss
                hit_tp = l[i] <= open_trade.take_profit

            if hit_sl:
                open_trade.exit_time = ts_index[i]
                open_trade.exit_price = open_trade.stop_loss
                open_trade.exit_reason = "SL"

                open_trade.pips_result = (
                    -open_trade.stop_pips
                    - cfg.SPREAD_PIPS
                )

                open_trade.usd_result = usd_pnl(
                    open_trade.pips_result,
                    open_trade.lot_size,
                )

                open_trade.r_multiple = (
                    open_trade.pips_result
                    / open_trade.stop_pips
                )

                trades.append(open_trade)
                open_trade = None
                cooldown_until = i + bt_cfg["cooldown_bars"]
                continue

            if hit_tp:
                open_trade.exit_time = ts_index[i]
                open_trade.exit_price = open_trade.take_profit
                open_trade.exit_reason = "TP"

                open_trade.pips_result = (
                    open_trade.stop_pips
                    * open_trade.rr
                    - cfg.SPREAD_PIPS
                )

                open_trade.usd_result = usd_pnl(
                    open_trade.pips_result,
                    open_trade.lot_size,
                )

                open_trade.r_multiple = (
                    open_trade.pips_result
                    / open_trade.stop_pips
                )

                trades.append(open_trade)
                open_trade = None
                cooldown_until = i + bt_cfg["cooldown_bars"]
                continue

            # Time exit
            if bt_cfg["time_exit_bars"] is not None:
                if (i - open_trade_bar) >= bt_cfg["time_exit_bars"]:

                    pips = (
                        (c[i] - open_trade.entry_price)
                        / cfg.PIP_SIZE
                    )

                    if open_trade.direction == "SELL":
                        pips = -pips

                    pips -= cfg.SPREAD_PIPS

                    open_trade.exit_time = ts_index[i]
                    open_trade.exit_price = c[i]
                    open_trade.exit_reason = "TIME"
                    open_trade.pips_result = pips
                    open_trade.usd_result = usd_pnl(
                        pips,
                        open_trade.lot_size,
                    )
                    open_trade.r_multiple = (
                        pips / open_trade.stop_pips
                    )

                    trades.append(open_trade)
                    open_trade = None
                    cooldown_until = i + bt_cfg["cooldown_bars"]
                    continue

            # Trade still open.
            continue

        # ----------------------------------------------------
        # No open trade
        # ----------------------------------------------------
        if i < cooldown_until:
            continue

        if i < range_start_i or i >= range_end_i:
            continue

        # ----------------------------------------------------
        # Regime
        # ----------------------------------------------------
        bias = "RANGING"

        if not (
            pd.isna(bias_ema_slow[i])
            or pd.isna(conf_ema_mid[i])
        ):
            bull = 0
            bear = 0

            if bias_ema_mid[i] > bias_ema_slow[i]:
                bull += 1
            elif bias_ema_mid[i] < bias_ema_slow[i]:
                bear += 1

            if conf_close[i] > conf_ema_mid[i]:
                bull += 1
            elif conf_close[i] < conf_ema_mid[i]:
                bear += 1

            if bull > bear:
                bias = "BULLISH"
            elif bear > bull:
                bias = "BEARISH"

        if bias == "RANGING":
            continue

        # ----------------------------------------------------
        # Setup
        # ----------------------------------------------------
        if (
            pd.isna(setup_ema_mid[i])
            or pd.isna(setup_rsi[i])
            or pd.isna(setup_atr[i])
        ):
            continue

        near_fast = (
            abs(setup_close[i] - setup_ema_fast[i])
            < 1.0 * setup_atr[i]
        )

        near_mid = (
            abs(setup_close[i] - setup_ema_mid[i])
            < 1.0 * setup_atr[i]
        )

        in_pull = near_fast or near_mid
        rsi_ok = 35 <= setup_rsi[i] <= 65

        setup_ok = False

        if (
            bias == "BULLISH"
            and in_pull
            and setup_close[i] > setup_ema_slow[i]
            and rsi_ok
        ):
            setup_ok = True

        if (
            bias == "BEARISH"
            and in_pull
            and setup_close[i] < setup_ema_slow[i]
            and rsi_ok
        ):
            setup_ok = True

        if not setup_ok:
            continue

        # ----------------------------------------------------
        # Trigger
        # ----------------------------------------------------
        if (
            i < 1
            or pd.isna(rsi_t[i])
            or pd.isna(rsi_t[i - 1])
        ):
            continue

        trigger_ok = False

        if bias == "BULLISH":
            if rsi_t[i - 1] < 50 <= rsi_t[i]:
                trigger_ok = True
            elif c[i] > ema_fast_t[i] and c[i] > o[i]:
                trigger_ok = True

        else:
            if rsi_t[i - 1] > 50 >= rsi_t[i]:
                trigger_ok = True
            elif c[i] < ema_fast_t[i] and c[i] < o[i]:
                trigger_ok = True

        if not trigger_ok:
            continue

        # ----------------------------------------------------
        # Session
        # ----------------------------------------------------
        ts = ts_index[i]
        in_session = session_ok(ts)

        if bt_cfg["require_session"] and not in_session:
            continue

        # ----------------------------------------------------
        # Confidence
        # ----------------------------------------------------
        confidence = 1  # regime
        confidence += 1  # setup
        confidence += 1  # trigger

        if in_session:
            confidence += 1

        spread_pips = spread_t[i] / 10.0

        if spread_pips <= cfg.MAX_SPREAD_PIPS:
            confidence += 1

        if confidence < mode_cfg["min_confidence"]:
            continue

        # ----------------------------------------------------
        # Next-bar execution
        # ----------------------------------------------------
        fill_i = i + 1

        # Critical split-boundary protection:
        # the signal must be able to fill INSIDE the requested
        # range. A final training signal cannot create a trade
        # whose entry occurs in the test period.
        if fill_i >= n or fill_i >= range_end_i:
            continue

        entry = o[fill_i]
        atr_setup = setup_atr[i]

        risk = compute_risk(
            entry,
            bias_to_signal(bias),
            atr_setup,
            mode_cfg,
            spread_pips,
        )

        trade = Trade(
            mode=mode_name,
            direction=bias_to_signal(bias),
            signal_time=ts,
            entry_time=ts_index[fill_i],
            entry_price=entry,
            stop_loss=risk["stop_loss"],
            take_profit=risk["take_profit_1"],
            stop_pips=risk["stop_pips"],
            lot_size=risk["lot_size"],
            confidence=confidence,
            rr=mode_cfg["rr_tp1"],
        )

        open_trade = trade
        open_trade_bar = fill_i

        if verbose:
            print(
                f"[{fill_i}] "
                f"{trade.entry_time} "
                f"{trade.direction} @ "
                f"{trade.entry_price}"
            )

    # --------------------------------------------------------
    # Range-end close
    # --------------------------------------------------------
    # If a trade remains open when the requested range ends,
    # close it at the LAST BAR OF THAT RANGE — never at the end
    # of the full dataset.
    if open_trade is not None:

        exit_i = range_last_i

        if exit_i >= open_trade_bar:

            pips = (
                (c[exit_i] - open_trade.entry_price)
                / cfg.PIP_SIZE
            )

            if open_trade.direction == "SELL":
                pips = -pips

            pips -= cfg.SPREAD_PIPS

            open_trade.exit_time = ts_index[exit_i]
            open_trade.exit_price = c[exit_i]
            open_trade.exit_reason = "END"
            open_trade.pips_result = pips
            open_trade.usd_result = usd_pnl(
                pips,
                open_trade.lot_size,
            )
            open_trade.r_multiple = (
                pips / open_trade.stop_pips
            )

            trades.append(open_trade)

    return trades
'''

updated = text[:start] + new_function + text[end:]

path.write_text(updated, encoding="utf-8")

print("backtest.py updated successfully.")
print("Backup created: backtest.py.backup")
