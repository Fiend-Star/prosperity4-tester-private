# Round 5 — "The Final Stretch"

50 products in 10 groups of 5, **all position limit = 10**. Days 2/3/4 historical, IMC live runs day 4 1k as the leaderboard probe.

## Files

| Path | Role |
|---|---|
| `thedarkmarc_do_nothing.py` ★ | **Current best** — 6-product selective strategy from team Discord. Live submission **551021** = $1,725 day-4 1k. |
| `oracle/god_logger_r5.py` | Zero-order trader using standard Logger.flush — submit to capture pristine live state. |
| `archive/lab_v1_to_v11/` | Earlier all-50-product penny-MM iterations. **Bogus BT numbers** ($604k claimed) — were built with `LIMIT=80` before R5 brief revealed limit=10. With correct limit, v11 = $31k 3-day default and -$50k day 4. Kept for reference only. |

## Live calibration (verified vs sub 551021, 2026-04-29)

| Metric | day 4 1k |
|---|--:|
| Live (IMC leaderboard) | **$1,725** |
| BT default mode | $433 (-75% — too pessimistic) |
| BT imc mode | $1,433 (-17% — close match) ★ |

**Use `--match-mode imc` as the primary R5 BT predictor.** Default mode misses invisible-taker fills that R5 live engine actually delivers.

## Run commands

```bash
export PYTHONPATH='C:/Users/gurms/PycharmProjects/imc-prosperity-4-backtester/prosperity4bt'

# Day 4 1k probe (matches IMC live leaderboard scope)
python -m prosperity4bt trader-logic/round-5/thedarkmarc_do_nothing.py 5-4 --ticks 1000 --no-out --no-progress --match-mode imc

# Full 3-day (sanity benchmark)
python -m prosperity4bt trader-logic/round-5/thedarkmarc_do_nothing.py 5 --no-progress --no-out --match-mode imc

# Capture live state (submit to IMC; BT also works for consistency check)
python -m prosperity4bt trader-logic/round-5/oracle/god_logger_r5.py 5-4 --ticks 1000

# Extract any submitted run-log into a CSV usable as a fresh dataset
python run-logs/round-5/extract_live_csv.py 551021
```

## thedarkmarc strategy summary

R1 ASH/PEPPER template ported, trades 6 of 50 products:
- **MEAN_REVERSION** (revert 25% of last return): SNACKPACK_CHOCOLATE, ROBOT_IRONING, OXYGEN_SHAKE_EVENING_BREATH, OXYGEN_SHAKE_CHOCOLATE
- **MOMENTUM** (skew toward daily-range percentile): PEBBLES_XL
- **HIDDEN_LIQUIDITY** (penny inside spread): ROBOT_LAUNDRY
- All other 44 products: skipped, no orders.

3-day BT (default / imc):
| Day | default | imc |
|---|--:|--:|
| 2 | 59,847 | 14,944 |
| 3 | 31,514 | 11,788 |
| 4 | 48,932 | -3,375 |
| **Total** | **140,294** | **23,357** |

Default mode matches teammate's reported live "69/31/49" (off only on day 2). imc mode is more conservative. Live d4 1k probe came in at $1,725 vs imc-BT $1,433 → calibration ratio ~1.20.

## Discord intel (cross-team EDA, 2026-04-28/29)

- **Mean reverters** (1-lag AC ≈ −0.15): ROBOT_IRONING, OXYGEN_SHAKE_EVENING_BREATH, OXYGEN_SHAKE_CHOCOLATE.
- **SNACKPACK correlations**: PIST↔STRAW +0.91, RASP↔STRAW −0.93, CHOC↔VAN −0.92, RASP↔PIST −0.83.
- **PEBBLES**: XL vs each smaller size −0.49.
- **Spread vs daily-range percentile**: spread widens at top of daily range universally (PEBBLES_XL 12.7→17.0 ticks bottom→top).
- **K-means trade archetypes** (4 clusters): whale-sellers at high-price/wide-spread (cluster 0), weak-hand sellers at low-price/tight-spread (cluster 2), standard buyers, HFT bursts. Suggests fade-the-weak-hand mean reversion.
- **SNACKPACK_CHOCOLATE spread regime**: visibly different at spread=18 vs spread=16 (Superduperbread, undocumented detail).

## Round 5 brief

50 products in 10 groups of 5: GALAXY_SOUNDS, SLEEP_POD, MICROCHIP, PEBBLES, ROBOT, UV_VISOR, TRANSLATOR, PANEL, OXYGEN_SHAKE, SNACKPACK. All position limits = 10.

Manual: Ignith portfolio. Quadratic fee `(volume/100)² × budget`. Budget = 1,000,000. Use Ashflow Alpha news. 9 goods.
