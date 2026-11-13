# Polymarket NVIDIA CEO forecaster (make.fun polymarket-nvidia-ceo-forecast-01).
#
# Idea, tuned on the practice cases p00-p04 (reconstructed from the
# overlapping case files, since Polymarket's price-history API refuses this
# machine): Polymarket Yes prices for this event move in steps -- flat for
# minutes, then a jump, often partly reversed. A plain random-walk forecast
# around the last price wins or loses on how wide its quantiles are, so the
# whole game is per-market volatility, measured robustly:
#
#   * sigma_i from the last 600 minutes of 1-minute moves, taking the
#     larger of that and the last 120 minutes' measure, so a volatility
#     regime that just changed is caught sooner: the larger of
#     1.4826 * MAD(|moves|) and 0.35 * the 90th percentile |move|, floored
#     at 0.0003. MAD alone reads ~0 (most minutes are flat) and plain
#     standard deviation is wrecked by the rare jumps; the p90 term keeps
#     the jumps in the picture without letting one spike set the scale.
#   * Quantiles are Student-t with 5 degrees of freedom
#     (-2.015, -0.727, 0, 0.727, 2.015): fat tails for the jumps, a tighter
#     centre for the flat minutes. Normal quantiles and raw empirical
#     h-step quantiles both scored worse on p00-p04.
#   * Spread grows like sqrt(h) -- saturating (mean-reverting) shapes,
#     trend extrapolation and EMA pull toward recent levels all scored
#     worse, so the median stays at the last price.
#
# Practice backtest (p00-p04, mean pinball loss): house baseline 0.4206,
# this forecaster 0.3345 (0.3428 before the 120-minute sigma term).
# The house baseline's published practice loss
# over all six cases is 0.3636.
#
# Python 3.13, standard library only. Reads every *.in in the input
# directory (the grader runs one case at a time) and writes one *.out
# per case. Deterministic: no randomness, no clock, no network.

import json
import math
import os
from pathlib import Path

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
# Student-t(5) quantiles at the five levels, to 6 decimals.
T5 = [-2.015048, -0.726687, 0.0, 0.726687, 2.015048]
SIGMA_FLOOR = 0.0003


def price6(x):
    """x clamped to [0, 1] and rounded to 6 decimals (0, never -0)."""
    return round(min(1.0, max(0.0, x)), 6) + 0.0


def market_sigma(prices):
    """Robust per-minute move scale for one market.

    The larger of the 600-minute and the 120-minute measures: the short
    window catches a market whose volatility regime just changed (a jump
    cluster starting), which the long window alone is slow to notice.
    On p00-p04 this max() scores 0.3345 vs 0.3428 for the 600-minute
    measure alone.
    """
    return max(_sigma_window(prices, 600), _sigma_window(prices, 120))


def _sigma_window(prices, lookback):
    window = prices[-lookback:] if len(prices) > lookback else prices
    if len(window) < 2:
        return SIGMA_FLOOR
    moves = sorted(abs(window[i + 1] - window[i]) for i in range(len(window) - 1))
    mad = moves[len(moves) // 2]
    p90 = moves[int(0.9 * len(moves))]
    return max(1.4826 * mad, 0.35 * p90, SIGMA_FLOOR)


def forecast_market(prices, horizon):
    """240 (horizon) rows of five quantiles around the last price."""
    x = prices[-1] if prices else 0.5
    sigma = market_sigma(prices)
    rows = []
    for h in range(1, horizon + 1):
        spread = sigma * math.sqrt(h)
        row = []
        prev = -1.0
        for z in T5:
            value = price6(x + z * spread)
            value = max(value, prev)  # keep each row non-decreasing
            row.append(value)
            prev = value
        rows.append(row)
    return rows


def main():
    input_dir = Path(INPUT_DIR)
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(p for p in input_dir.iterdir() if p.name.endswith(".in")):
        case = json.loads(name.read_text(encoding="utf-8"))
        horizon = int(case["horizon_minutes"])
        forecasts = [
            {"id": market["id"],
             "q": forecast_market(market["prices"], horizon)}
            for market in case["markets"]
        ]
        out_path = output_dir / f"{name.stem}.out"
        out_path.write_text(json.dumps({"forecasts": forecasts}) + "\n",
                            encoding="utf-8")


if __name__ == "__main__":
    main()
