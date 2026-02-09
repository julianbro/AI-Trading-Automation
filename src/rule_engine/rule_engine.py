import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import structlog

from src.common.models import MarketData, SetupEvent, PatternType, Timeframe

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RuleParams:
    # Data requirements
    min_bars_1d: int = 120
    min_bars_4h: int = 120
    min_bars_15m: int = 300

    # Pivot / level detection
    pivot_left: int = 2
    pivot_right: int = 2
    min_level_touches: int = 2
    max_level_age_bars_1d: int = 80
    max_level_age_bars_4h: int = 120

    # Dynamic tolerance (zone width)
    tolerance_pct_floor: float = 0.003  # 0.3% minimum zone
    tolerance_atr_mult: float = 0.35  # zone expands with ATR

    # Breakout / retest logic
    breakout_max_age_bars_1d: int = 6
    breakout_close_buffer_atr: float = (
        0.15  # breakout close must exceed level by this*ATR (or pct floor)
    )
    retest_max_bars_15m: int = 160  # ~40h on 15m
    reclaim_lookahead_15m: int = 24  # next 6h of 15m candles for reclaim

    # Candle quality gates
    close_pos_min: float = 0.60  # bullish close location in candle range
    close_pos_max_bear: float = 0.40  # bearish close location in candle range
    wick_frac_min: float = 0.45  # wick must be >= this fraction of full candle range

    # Volatility gates (tune per market)
    min_atr_pct_1d: float = 0.007  # 0.7% daily ATR as % of price
    min_atr_pct_4h: float = 0.004  # 0.4% 4h ATR as % of price

    # Anti-spam
    cooldown_minutes: int = 90
    dedupe_level_pct: float = 0.0015  # 0.15% level similarity


class RuleEngine:
    """
    Deterministic setup detection engine.
    Emits "worth-a-human-look" setup events (NOT trade decisions).
    """

    def __init__(self, params: Optional[RuleParams] = None):
        self.p = params or RuleParams()
        self._last_emitted: Dict[Tuple[str, PatternType], Dict[str, Any]] = {}
        logger.info("Rule Engine initialized", params=self.p)

    def detect_setups(
        self, market_data: Dict[Union[str, Timeframe], MarketData]
    ) -> List[SetupEvent]:
        md = self._normalize_market_data_keys(market_data)

        if self._has_open_htf_bar(md):
            logger.info("Skipping setup detection: HTF bar not closed")
            return []

        setups: List[SetupEvent] = []

        for checker in (
            self._check_breakout_retest,
            self._check_support_bounce,
            self._check_resistance_rejection,
        ):
            ev = checker(md)
            if ev is not None and self._should_emit(ev):
                setups.append(ev)

        logger.info("Detected setups", setup_count=len(setups))
        return setups

    def _has_open_htf_bar(self, md: Dict[Timeframe, MarketData]) -> bool:
        """Check if any higher timeframe bar is still open."""
        for timeframe in (Timeframe.ONE_DAY, Timeframe.FOUR_HOURS):
            data = md.get(timeframe)
            if data is not None and not data.is_closed:
                return True
        return False

    # -----------------------
    # Pattern Detectors
    # -----------------------

    def _check_breakout_retest(
        self, md: Dict[Timeframe, MarketData]
    ) -> Optional[SetupEvent]:
        """
        BREAKOUT + RETEST (long bias):
        - Find a "real" resistance level (pivot highs + multi-touch)
        - Confirm breakout happened recently via DAILY close above resistance
        - Confirm retest happened via 15m touch of the zone
        - Confirm reclaim: 15m close back above zone after touch
        """

        if Timeframe.ONE_DAY not in md or Timeframe.FIFTEEN_MIN not in md:
            return None

        d = self._to_df(md[Timeframe.ONE_DAY])
        i = self._to_df(md[Timeframe.FIFTEEN_MIN])

        if len(d) < self.p.min_bars_1d or len(i) < self.p.min_bars_15m:
            return None

        atr_d = self._atr(d, period=14)
        if not np.isfinite(atr_d):
            return None

        last_close = float(d["close"].iloc[-1])
        atr_pct = atr_d / max(last_close, 1e-12)
        if atr_pct < self.p.min_atr_pct_1d:
            return None

        # 1) Find resistance (multi-touch pivots)
        level_info = self._find_level(
            df=d,
            kind="resistance",
            atr=atr_d,
            max_age_bars=self.p.max_level_age_bars_1d,
        )
        if level_info is None:
            return None

        resistance = level_info["level"]
        tol = level_info["tolerance"]
        touches = level_info["touches"]

        # 2) Breakout must be a DAILY close above resistance (recent)
        breakout_idx = self._find_recent_breakout_close(
            df=d,
            level=resistance,
            atr=atr_d,
            max_age_bars=self.p.breakout_max_age_bars_1d,
        )
        if breakout_idx is None:
            return None

        breakout_ts = d["timestamp"].iloc[breakout_idx]

        # 3) Retest must occur AFTER breakout (on 15m)
        i_after = i[i["timestamp"] >= breakout_ts].reset_index(drop=True)
        if len(i_after) < 40:
            return None

        zone_low = resistance - tol
        zone_high = resistance + tol

        touched_mask = (i_after["low"] <= zone_high) & (i_after["high"] >= zone_low)
        touch_idxs = np.flatnonzero(touched_mask.to_numpy())

        if len(touch_idxs) == 0:
            return None

        # Use the most recent touch, but not too old
        touch_idx = int(touch_idxs[-1])
        if (len(i_after) - 1 - touch_idx) > self.p.retest_max_bars_15m:
            return None

        # 4) Reclaim confirmation: after touch, find first candle that closes back above zone_high
        confirm_window = i_after.iloc[
            touch_idx + 1 : touch_idx + 1 + self.p.reclaim_lookahead_15m
        ]
        if len(confirm_window) == 0:
            return None

        confirm_idx = None
        for k in range(len(confirm_window)):
            row = confirm_window.iloc[k]
            if self._bullish_reclaim(row, zone_high):
                confirm_idx = touch_idx + 1 + k
                break

        if confirm_idx is None:
            return None

        signal_row = i_after.iloc[confirm_idx]
        signal_ts = pd.Timestamp(signal_row["timestamp"]).to_pydatetime()

        # Deterministic "quality hints" (NOT a decision)
        breakout_row = d.iloc[breakout_idx]
        quality = self._quality_breakout_retest(
            d, breakout_idx, touches, atr_d, resistance, signal_row
        )

        return SetupEvent(
            event_id=str(uuid.uuid4()),
            symbol=md[Timeframe.ONE_DAY].symbol,
            pattern_type=PatternType.BREAKOUT_RETEST,
            timestamp=signal_ts,
            timeframes=[Timeframe.ONE_DAY, Timeframe.FIFTEEN_MIN],
            context_data={
                "direction_bias": "long",
                "level": {
                    "resistance": float(resistance),
                    "zone_low": float(zone_low),
                    "zone_high": float(zone_high),
                    "touches": int(touches),
                    "tolerance": float(tol),
                },
                "volatility": {
                    "atr_14": float(atr_d),
                    "atr_pct": float(atr_pct),
                },
                "breakout": {
                    "daily_breakout_bar_time": breakout_ts.isoformat(),
                    "daily_breakout_bar_ohlc": {
                        "open": float(breakout_row["open"]),
                        "high": float(breakout_row["high"]),
                        "low": float(breakout_row["low"]),
                        "close": float(breakout_row["close"]),
                        "volume": float(breakout_row["volume"]),
                    },
                },
                "retest": {
                    "touch_bar_time": pd.Timestamp(
                        i_after.iloc[touch_idx]["timestamp"]
                    ).isoformat(),
                    "confirm_bar_time": pd.Timestamp(
                        signal_row["timestamp"]
                    ).isoformat(),
                    "confirm_bar_ohlc": {
                        "open": float(signal_row["open"]),
                        "high": float(signal_row["high"]),
                        "low": float(signal_row["low"]),
                        "close": float(signal_row["close"]),
                        "volume": float(signal_row["volume"]),
                    },
                },
                "quality": quality,
                "human_validation_checklist": [
                    "Is the daily breakout candle a real close above resistance (not just wick)?",
                    "Did the retest respect the zone without deep acceptance below?",
                    "Is market regime supportive (trend/range/news)?",
                    "Any nearby overhead liquidity/next resistance too close?",
                ],
            },
        )

    def _check_support_bounce(
        self, md: Dict[Timeframe, MarketData]
    ) -> Optional[SetupEvent]:
        """
        SUPPORT BOUNCE (long bias):
        - Find support via pivot lows + multi-touch
        - Last 4h candle must touch/sweep support zone
        - Candle must show rejection: long lower wick + close in upper portion + close >= support
        """

        if Timeframe.FOUR_HOURS not in md:
            return None

        df = self._to_df(md[Timeframe.FOUR_HOURS])
        if len(df) < self.p.min_bars_4h:
            return None

        atr = self._atr(df, period=14)
        if not np.isfinite(atr):
            return None

        last_close = float(df["close"].iloc[-1])
        atr_pct = atr / max(last_close, 1e-12)
        if atr_pct < self.p.min_atr_pct_4h:
            return None

        level_info = self._find_level(
            df=df,
            kind="support",
            atr=atr,
            max_age_bars=self.p.max_level_age_bars_4h,
        )
        if level_info is None:
            return None

        support = level_info["level"]
        tol = level_info["tolerance"]
        touches = level_info["touches"]

        zone_low = support - tol
        zone_high = support + tol

        last = df.iloc[-1]
        if not self._intersects_zone(last, zone_low, zone_high):
            return None

        if not self._bullish_rejection(last):
            return None

        # close must be at/above support (avoid "falling knife" closes below level)
        if float(last["close"]) < support:
            return None

        signal_ts = pd.Timestamp(last["timestamp"]).to_pydatetime()
        quality = self._quality_bounce_rejection(
            df, touches, atr, support, last, kind="support"
        )

        return SetupEvent(
            event_id=str(uuid.uuid4()),
            symbol=md[Timeframe.FOUR_HOURS].symbol,
            pattern_type=PatternType.SUPPORT_BOUNCE,
            timestamp=signal_ts,
            timeframes=[Timeframe.FOUR_HOURS],
            context_data={
                "direction_bias": "long",
                "level": {
                    "support": float(support),
                    "zone_low": float(zone_low),
                    "zone_high": float(zone_high),
                    "touches": int(touches),
                    "tolerance": float(tol),
                },
                "volatility": {
                    "atr_14": float(atr),
                    "atr_pct": float(atr_pct),
                },
                "signal_bar": {
                    "time": pd.Timestamp(last["timestamp"]).isoformat(),
                    "open": float(last["open"]),
                    "high": float(last["high"]),
                    "low": float(last["low"]),
                    "close": float(last["close"]),
                    "volume": float(last["volume"]),
                },
                "quality": quality,
                "human_validation_checklist": [
                    "Is this support obvious on a higher timeframe too?",
                    "Was this a sweep + reclaim, or just noise inside a range?",
                    "Any major news/earnings/macro event nearby?",
                    "Where is next resistance (room for R)?",
                ],
            },
        )

    def _check_resistance_rejection(
        self, md: Dict[Timeframe, MarketData]
    ) -> Optional[SetupEvent]:
        """
        RESISTANCE REJECTION (short bias):
        Symmetric to support bounce but for resistance:
        - Find resistance via pivot highs + multi-touch
        - Last 4h candle intersects zone
        - Candle shows bearish rejection: long upper wick + close in lower portion + close <= resistance
        """

        if Timeframe.FOUR_HOURS not in md:
            return None

        df = self._to_df(md[Timeframe.FOUR_HOURS])
        if len(df) < self.p.min_bars_4h:
            return None

        atr = self._atr(df, period=14)
        if not np.isfinite(atr):
            return None

        last_close = float(df["close"].iloc[-1])
        atr_pct = atr / max(last_close, 1e-12)
        if atr_pct < self.p.min_atr_pct_4h:
            return None

        level_info = self._find_level(
            df=df,
            kind="resistance",
            atr=atr,
            max_age_bars=self.p.max_level_age_bars_4h,
        )
        if level_info is None:
            return None

        resistance = level_info["level"]
        tol = level_info["tolerance"]
        touches = level_info["touches"]

        zone_low = resistance - tol
        zone_high = resistance + tol

        last = df.iloc[-1]
        if not self._intersects_zone(last, zone_low, zone_high):
            return None

        if not self._bearish_rejection(last):
            return None

        if float(last["close"]) > resistance:
            return None

        signal_ts = pd.Timestamp(last["timestamp"]).to_pydatetime()
        quality = self._quality_bounce_rejection(
            df, touches, atr, resistance, last, kind="resistance"
        )

        return SetupEvent(
            event_id=str(uuid.uuid4()),
            symbol=md[Timeframe.FOUR_HOURS].symbol,
            pattern_type=PatternType.RESISTANCE_REJECTION,
            timestamp=signal_ts,
            timeframes=[Timeframe.FOUR_HOURS],
            context_data={
                "direction_bias": "short",
                "level": {
                    "resistance": float(resistance),
                    "zone_low": float(zone_low),
                    "zone_high": float(zone_high),
                    "touches": int(touches),
                    "tolerance": float(tol),
                },
                "volatility": {
                    "atr_14": float(atr),
                    "atr_pct": float(atr_pct),
                },
                "signal_bar": {
                    "time": pd.Timestamp(last["timestamp"]).isoformat(),
                    "open": float(last["open"]),
                    "high": float(last["high"]),
                    "low": float(last["low"]),
                    "close": float(last["close"]),
                    "volume": float(last["volume"]),
                },
                "quality": quality,
                "human_validation_checklist": [
                    "Is the resistance clean and respected on higher timeframe?",
                    "Did price sweep liquidity above resistance and reject?",
                    "Is downside room sufficient before next support?",
                    "Any catalyst risk (news/earnings/macro)?",
                ],
            },
        )

    # -----------------------
    # Helpers: Dedupe / Cooldown
    # -----------------------

    def _should_emit(self, ev: SetupEvent) -> bool:
        key = (ev.symbol, ev.pattern_type)

        # Try to extract a "primary level" to dedupe on (support/resistance)
        level = None
        lvl = (ev.context_data or {}).get("level", {})
        if "support" in lvl:
            level = float(lvl["support"])
        elif "resistance" in lvl:
            level = float(lvl["resistance"])
        else:
            # fallback
            level = float((ev.context_data or {}).get("trigger_price", 0.0) or 0.0)

        now_ts = (
            ev.timestamp
            if ev.timestamp.tzinfo
            else ev.timestamp.replace(tzinfo=timezone.utc)
        )

        prev = self._last_emitted.get(key)
        if prev is not None:
            prev_level = float(prev["level"])
            prev_ts = prev["ts"]
            level_similar = (
                abs(level - prev_level) / max(level, 1e-12)
            ) <= self.p.dedupe_level_pct
            too_soon = (now_ts - prev_ts) <= timedelta(minutes=self.p.cooldown_minutes)
            if level_similar and too_soon:
                return False

        self._last_emitted[key] = {"level": level, "ts": now_ts}
        return True

    def _normalize_market_data_keys(
        self, market_data: Dict[Union[str, Timeframe], MarketData]
    ) -> Dict[Timeframe, MarketData]:
        out: Dict[Timeframe, MarketData] = {}
        for k, v in market_data.items():
            if isinstance(k, Timeframe):
                out[k] = v
                continue
            try:
                out[Timeframe(str(k))] = v
            except Exception:
                # Ignore unknown keys
                continue
        return out

    # -----------------------
    # Helpers: Data / Indicators
    # -----------------------

    def _to_df(self, data: MarketData) -> pd.DataFrame:
        df = pd.DataFrame(
            data.ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        ).copy()

        # Sort + clean
        df = df.dropna()
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df = (
            df.dropna(subset=["timestamp"])
            .sort_values("timestamp")
            .drop_duplicates("timestamp")
        )
        df = df.reset_index(drop=True)

        # Convert epoch seconds vs ms -> timezone-aware datetime
        ts = df["timestamp"].astype(float)
        # crude but practical detection
        unit = "ms" if float(ts.iloc[-1]) > 1e11 else "s"
        df["timestamp"] = pd.to_datetime(ts, unit=unit, utc=True)

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
        return df

    def _atr(self, df: pd.DataFrame, period: int = 14) -> float:
        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        close = df["close"].to_numpy(dtype=float)

        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]

        tr = np.maximum(
            high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))
        )
        if len(tr) < period + 1:
            return float("nan")

        atr = pd.Series(tr).rolling(period).mean().iloc[-1]
        return float(atr)

    def _pivot_points(
        self, arr: np.ndarray, left: int, right: int, mode: str
    ) -> np.ndarray:
        """
        Returns boolean array indicating pivot highs/lows.
        Strict pivot: value must be unique extreme inside window.
        """
        n = len(arr)
        piv = np.zeros(n, dtype=bool)

        for i in range(left, n - right):
            window = arr[i - left : i + right + 1]
            if not np.all(np.isfinite(window)):
                continue

            val = arr[i]
            if mode == "high":
                m = window.max()
                if val == m and np.sum(window == m) == 1:
                    piv[i] = True
            elif mode == "low":
                m = window.min()
                if val == m and np.sum(window == m) == 1:
                    piv[i] = True
            else:
                raise ValueError("mode must be 'high' or 'low'")

        return piv

    def _find_level(
        self,
        df: pd.DataFrame,
        kind: str,
        atr: float,
        max_age_bars: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a high-quality support/resistance level:
        - Use pivot highs/lows
        - Require multi-touch within tolerance
        - Prefer more touches and more recent touches
        """

        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        close = float(df["close"].iloc[-1])

        tol = max(close * self.p.tolerance_pct_floor, atr * self.p.tolerance_atr_mult)

        if kind == "resistance":
            piv_mask = self._pivot_points(
                highs, self.p.pivot_left, self.p.pivot_right, "high"
            )
            piv_prices = highs[piv_mask]
            piv_idx = np.flatnonzero(piv_mask)
        elif kind == "support":
            piv_mask = self._pivot_points(
                lows, self.p.pivot_left, self.p.pivot_right, "low"
            )
            piv_prices = lows[piv_mask]
            piv_idx = np.flatnonzero(piv_mask)
        else:
            raise ValueError("kind must be 'support' or 'resistance'")

        if len(piv_prices) < self.p.min_level_touches:
            return None

        # Only consider relatively recent pivots (prevents ancient levels)
        last_bar = len(df) - 1
        recent_mask = piv_idx >= max(0, last_bar - max_age_bars)
        piv_prices = piv_prices[recent_mask]
        piv_idx = piv_idx[recent_mask]

        if len(piv_prices) < self.p.min_level_touches:
            return None

        # Score candidate levels by how many pivots fall within tolerance
        best = None
        for j in range(len(piv_prices)):
            level0 = piv_prices[j]
            mask = np.abs(piv_prices - level0) <= tol
            touches = int(mask.sum())
            if touches < self.p.min_level_touches:
                continue

            level = float(np.median(piv_prices[mask]))
            last_touch = int(np.max(piv_idx[mask]))

            score = (touches * 10_000) + last_touch  # deterministic scoring
            if best is None or score > best["score"]:
                best = {
                    "level": level,
                    "touches": touches,
                    "last_touch_index": last_touch,
                    "tolerance": float(tol),
                    "score": score,
                }

        return best

    # -----------------------
    # Helpers: Pattern Conditions
    # -----------------------

    def _find_recent_breakout_close(
        self, df: pd.DataFrame, level: float, atr: float, max_age_bars: int
    ) -> Optional[int]:
        """
        Find a recent bar where CLOSE crosses above level with buffer.
        """
        closes = df["close"].to_numpy(dtype=float)

        buffer = max(level * 0.002, atr * self.p.breakout_close_buffer_atr)
        threshold = level + buffer

        start = max(1, len(df) - max_age_bars - 1)
        for i in range(len(df) - 1, start - 1, -1):
            if closes[i] > threshold and closes[i - 1] <= threshold:
                # Also require breakout candle closes relatively strong
                row = df.iloc[i]
                if self._close_position(row) >= self.p.close_pos_min:
                    return i
        return None

    def _intersects_zone(
        self, row: pd.Series, zone_low: float, zone_high: float
    ) -> bool:
        return (float(row["low"]) <= zone_high) and (float(row["high"]) >= zone_low)

    def _close_position(self, row: pd.Series) -> float:
        lo = float(row["low"])
        hi = float(row["high"])
        c = float(row["close"])
        rng = max(hi - lo, 1e-12)
        return (c - lo) / rng  # 0..1

    def _bullish_reclaim(self, row: pd.Series, reclaim_above: float) -> bool:
        # close back above reclaim_above + strong close in candle
        c = float(row["close"])
        o = float(row["open"])
        if c <= reclaim_above:
            return False
        if c <= o:
            return False
        if self._close_position(row) < self.p.close_pos_min:
            return False
        return True

    def _bullish_rejection(self, row: pd.Series) -> bool:
        o = float(row["open"])
        c = float(row["close"])
        h = float(row["high"])
        l = float(row["low"])

        rng = max(h - l, 1e-12)
        lower_wick = min(o, c) - l

        # Long lower wick relative to full candle
        if (lower_wick / rng) < self.p.wick_frac_min:
            return False

        # Close in upper portion
        if self._close_position(row) < self.p.close_pos_min:
            return False

        return True

    def _bearish_rejection(self, row: pd.Series) -> bool:
        o = float(row["open"])
        c = float(row["close"])
        h = float(row["high"])
        l = float(row["low"])

        rng = max(h - l, 1e-12)
        upper_wick = h - max(o, c)

        if (upper_wick / rng) < self.p.wick_frac_min:
            return False

        # Close in lower portion (bearish close location)
        if self._close_position(row) > self.p.close_pos_max_bear:
            return False

        # Prefer bearish body (optional but reduces noise)
        if c >= o:
            return False

        return True

    # -----------------------
    # Helpers: deterministic quality scoring (for triage, not decisions)
    # -----------------------

    def _quality_breakout_retest(
        self,
        df_daily: pd.DataFrame,
        breakout_idx: int,
        touches: int,
        atr: float,
        level: float,
        confirm_row_15m: pd.Series,
    ) -> Dict[str, Any]:
        br = df_daily.iloc[breakout_idx]
        close_pos = self._close_position(br)

        # volume boost (simple)
        vol = float(br["volume"])
        vol_ma = (
            float(df_daily["volume"].rolling(20).mean().iloc[breakout_idx])
            if "volume" in df_daily
            else float("nan")
        )
        vol_ok = np.isfinite(vol_ma) and vol_ma > 0 and vol > 1.2 * vol_ma

        # retest depth (did it hold near level?)
        retest_low = float(confirm_row_15m["low"])
        depth = level - retest_low

        # deterministic score 0..10-ish
        score = 0
        score += min(touches, 4)  # up to 4
        score += 2 if close_pos >= 0.70 else 1 if close_pos >= 0.60 else 0
        score += 2 if vol_ok else 0
        score += 2 if depth <= (0.5 * atr) else 1 if depth <= (1.0 * atr) else 0

        return {
            "score_0_10": int(min(score, 10)),
            "touches": int(touches),
            "breakout_close_position": float(close_pos),
            "breakout_volume_boost": bool(vol_ok),
            "retest_depth_vs_atr": float(depth / max(atr, 1e-12)),
        }

    def _quality_bounce_rejection(
        self,
        df: pd.DataFrame,
        touches: int,
        atr: float,
        level: float,
        signal_row: pd.Series,
        kind: str,
    ) -> Dict[str, Any]:
        close_pos = self._close_position(signal_row)

        o = float(signal_row["open"])
        c = float(signal_row["close"])
        h = float(signal_row["high"])
        l = float(signal_row["low"])
        rng = max(h - l, 1e-12)

        if kind == "support":
            wick = (min(o, c) - l) / rng
            depth = (level - l) / max(atr, 1e-12)
        else:
            wick = (h - max(o, c)) / rng
            depth = (h - level) / max(atr, 1e-12)

        score = 0
        score += min(touches, 4)
        score += 2 if wick >= 0.55 else 1 if wick >= 0.45 else 0
        score += (
            2
            if (kind == "support" and close_pos >= 0.70)
            else 2 if (kind == "resistance" and close_pos <= 0.30) else 1
        )
        score += 2 if depth <= 0.8 else 1 if depth <= 1.5 else 0

        return {
            "score_0_10": int(min(score, 10)),
            "touches": int(touches),
            "wick_fraction": float(wick),
            "close_position": float(close_pos),
            "depth_vs_atr": float(depth),
        }
