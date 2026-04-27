#!/bin/bash
# Master orchestrator — runs all 4 phases sequentially.
# Each phase reads the previous phase's output JSON.

set -e
cd "$(dirname "$0")"

echo "==================================================================="
echo "RUN ALL PHASES — R4 Manual Challenge GPU Pipeline"
echo "==================================================================="

# Phase 1: huge grid sweep (~30-60 min depending on grid size)
echo ""
echo "===== PHASE 1: HUGE GRID SWEEP ====="
python phase1_huge_grid.py \
    --paths 50000000 \
    --chunk 1000000 \
    --strat_batch 500 \
    --out phase1_results.json
echo "Phase 1 complete."

# Phase 2: deep verification of top 100
echo ""
echo "===== PHASE 2: DEEP MULTI-SEED VERIFICATION ====="
python phase2_deep_verify.py \
    --phase1_results phase1_results.json \
    --paths_per_seed 200000000 \
    --n_seeds 5 \
    --top_n 100 \
    --out phase2_results.json
echo "Phase 2 complete."

# Phase 3: sensitivity (sigma + KO + jumps) for top 20
echo ""
echo "===== PHASE 3: SENSITIVITY ANALYSIS ====="
python phase3_sensitivity.py \
    --phase2_results phase2_results.json \
    --paths_per_test 50000000 \
    --top_n 20 \
    --out phase3_results.json
echo "Phase 3 complete."

# Phase 4: antithetic for top 10
echo ""
echo "===== PHASE 4: ANTITHETIC TAIL ESTIMATION ====="
python phase4_antithetic.py \
    --phase2_results phase2_results.json \
    --pairs_per_strat 50000000 \
    --top_n 10 \
    --out phase4_results.json
echo "Phase 4 complete."

echo ""
echo "==================================================================="
echo "ALL PHASES COMPLETE"
echo "==================================================================="
echo "Outputs:"
echo "  phase1_results.json — huge grid (~30K candidates)"
echo "  phase2_results.json — deep verify top 100"
echo "  phase3_results.json — sensitivity for top 20"
echo "  phase4_results.json — antithetic tight CVaR for top 10"
