"""Day-type / regime detection library for delta-1 products.

Ported and generalised from competitor 401389.py (R3 Hydrogel Pack day-type
detection at row 20, drift threshold 20, trend invalidation safety).

Empirical R3 calibration (alpha_hunt3.py):
  Day 0: VFE drift -6,  HP drift -42 -> DOWN/MR
  Day 1: VFE drift +20.5, HP drift +57  -> UP day
  Day 2: VFE drift +28, HP drift -1  -> VFE UP, HP MR

Detection at ts ~ 2000 via rm20 + linear slope; LOCKED for rest of day.

Usage:
    from trader_logic.lib.regime import detect_day_type, RegimeState
    rs = RegimeState.load(trader_data, key="vfe_regime")
    rs.update(mid)
    if rs.row >= 20 and rs.day_type == 0:
        rs.day_type = detect_day_type(rs.mid_history, global_mean,
                                      drift_threshold=20, slope_threshold=0.5)
    # ... use rs.day_type in 1=TREND_SHORT, -1=TREND_LONG, 2=MEAN_REVERT
"""

from typing import List, Optional, Dict, Any
import json


# Regime constants (sentinel values, JSON-friendly)
UNKNOWN       = 0
TREND_SHORT   = 1   # price too high, will fall -> short bias
TREND_LONG    = -1  # price too low, will rise -> long bias
MEAN_REVERT   = 2


def _mean(buf: List[float]) -> Optional[float]:
    return sum(buf) / len(buf) if buf else None


def _slope(prices: List[float]) -> float:
    """Linear regression slope over a price series.

    Returns slope per index step (not per timestamp); multiply by step size
    to get per-tick / per-ts drift if needed.
    """
    n = len(prices)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(prices) / n
    num = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def detect_day_type(
    mid_history: List[float],
    global_mean: float,
    warmup_ticks: int = 20,
    drift_threshold: float = 20.0,
    slope_threshold: float = 0.5,
) -> int:
    """Classify the current trading day from rm20 drift + linear slope.

    Args:
        mid_history: list of recent mids (must have >= warmup_ticks entries)
        global_mean: anchor "fair" level for the product
        warmup_ticks: rolling-mean window (default 20 from 401389)
        drift_threshold: |rm20 - global_mean| > this -> trending classification
        slope_threshold: |slope| > this -> trending classification (alternative)

    Returns:
        TREND_SHORT (1) | TREND_LONG (-1) | MEAN_REVERT (2) | UNKNOWN (0)

    Decision rule:
      - If |drift| > drift_threshold OR |slope| > slope_threshold:
        * positive => TREND_SHORT (price will fall)
        * negative => TREND_LONG (price will rise)
      - Else => MEAN_REVERT
      - If insufficient data => UNKNOWN

    Notes:
      - Uses BOTH drift and slope (logical OR). drift catches a day that opened
        offset; slope catches a day that's been moving in one direction even if
        rm20 isn't yet far from mean.
      - 401389 used drift only with thresh=20. Adding slope catches edge cases
        where rm20 is still close to mean but the trajectory is clear.
    """
    if len(mid_history) < warmup_ticks:
        return UNKNOWN

    rm = _mean(mid_history[-warmup_ticks:])
    drift = rm - global_mean if rm is not None else 0.0
    slope = _slope(mid_history[-warmup_ticks:])

    is_up = drift > drift_threshold or slope > slope_threshold
    is_down = drift < -drift_threshold or slope < -slope_threshold

    if is_up and not is_down:
        return TREND_SHORT  # price too high, expected to fall
    if is_down and not is_up:
        return TREND_LONG   # price too low, expected to rise
    return MEAN_REVERT


def detect_drift_open(
    mid_history: List[float],
    open_anchor: Optional[float] = None,
    warmup_ticks: int = 20,
    threshold: float = 15.0,
) -> int:
    """Alternative day-type detector using OPEN mid as anchor.

    For products where global_mean is uncertain across rounds. Uses the first
    mid recorded as the anchor; classifies based on rm20 vs open.

    Returns same enum: TREND_SHORT / TREND_LONG / MEAN_REVERT / UNKNOWN.

    Trading interpretation here is INVERTED vs detect_day_type:
      - If rm20 > open + threshold => TREND_LONG (we expect MORE up)
      - If rm20 < open - threshold => TREND_SHORT (we expect MORE down)

    This is "trend continuation" rather than "mean reversion". Use this for
    pure-drift products (e.g. INTARIAN_PEPPER_ROOT R1/R2 style).
    """
    if len(mid_history) < warmup_ticks:
        return UNKNOWN

    anchor = open_anchor if open_anchor is not None else mid_history[0]
    rm = _mean(mid_history[-warmup_ticks:])
    drift = rm - anchor if rm is not None else 0.0

    if drift > threshold:
        return TREND_LONG    # continue up
    if drift < -threshold:
        return TREND_SHORT   # continue down
    return MEAN_REVERT


class RegimeState:
    """Persistent state for regime detection across ticks.

    Tracks mid_history, row count, locked day_type, invalidation state.
    Serialises via to_dict / from_dict for trader_data persistence.
    """

    def __init__(self, max_history: int = 200):
        self.mid_history: List[float] = []
        self.max_history: int = max_history
        self.row: int = 0
        self.day_type: int = UNKNOWN

        # Invalidation tracking (from 401389:432-449)
        self.trend_built: bool = False
        self.trend_entry_mid: Optional[float] = None
        self.trend_inval_count: int = 0
        self.trend_inval_lockout_until: int = 0

    def update(self, mid: float) -> None:
        """Append mid to history and increment row."""
        self.mid_history.append(mid)
        if len(self.mid_history) > self.max_history:
            del self.mid_history[: len(self.mid_history) - self.max_history]
        self.row += 1

    def check_invalidation(
        self,
        mid: float,
        loss_thresh: float = 5.0,
        consecutive_rows: int = 40,
        cooldown: int = 200,
    ) -> bool:
        """Check if a trending bet has been losing for `consecutive_rows`.

        Returns True if invalidation fires (caller should bail to MEAN_REVERT).
        From 401389.py:432-449.
        """
        if self.day_type not in (TREND_SHORT, TREND_LONG):
            return False
        if not self.trend_built or self.trend_entry_mid is None:
            return False

        direction = -1 if self.day_type == TREND_SHORT else 1
        mtm = (mid - self.trend_entry_mid) * direction

        if mtm < -loss_thresh:
            self.trend_inval_count += 1
        else:
            self.trend_inval_count = 0

        if self.trend_inval_count >= consecutive_rows:
            self.day_type = MEAN_REVERT
            self.trend_inval_count = 0
            self.trend_inval_lockout_until = self.row + cooldown
            return True

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mh": self.mid_history,
            "row": self.row,
            "dt": self.day_type,
            "tb": self.trend_built,
            "tem": self.trend_entry_mid,
            "tic": self.trend_inval_count,
            "tlu": self.trend_inval_lockout_until,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any], max_history: int = 200) -> "RegimeState":
        s = RegimeState(max_history=max_history)
        s.mid_history = list(d.get("mh", []))[-max_history:]
        s.row = int(d.get("row", 0))
        s.day_type = int(d.get("dt", UNKNOWN))
        s.trend_built = bool(d.get("tb", False))
        s.trend_entry_mid = d.get("tem")
        s.trend_inval_count = int(d.get("tic", 0))
        s.trend_inval_lockout_until = int(d.get("tlu", 0))
        return s

    @staticmethod
    def load(trader_data: str, key: str, max_history: int = 200) -> "RegimeState":
        if not trader_data:
            return RegimeState(max_history=max_history)
        try:
            raw = json.loads(trader_data)
        except Exception:
            return RegimeState(max_history=max_history)
        return RegimeState.from_dict(raw.get(key, {}), max_history=max_history)

    def save(self, trader_data: str, key: str) -> str:
        try:
            raw = json.loads(trader_data) if trader_data else {}
        except Exception:
            raw = {}
        raw[key] = self.to_dict()
        return json.dumps(raw)
