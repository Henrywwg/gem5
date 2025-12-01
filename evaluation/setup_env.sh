#!/bin/bash
# Quick reference for using the evaluation framework
# Run this script with: source evaluation/setup_env.sh

export GEM5_ROOT="/home/dlnavarro/ece752proj/gem5"
export GEM5_BIN="${GEM5_ROOT}/build/X86/gem5.opt"
export EVAL_DIR="${GEM5_ROOT}/evaluation"

# Add aliases for convenience
alias eval-test="${EVAL_DIR}/test_framework.sh"
alias eval-quick="${EVAL_DIR}/quick_eval.sh"
alias eval-analyze="python3 ${EVAL_DIR}/scripts/analyze_stats.py"
alias eval-plot="python3 ${EVAL_DIR}/scripts/plot_results.py"
alias eval-sweep="python3 ${EVAL_DIR}/scripts/run_sweep.py"

echo "Evaluation framework environment loaded!"
echo ""
echo "Available commands:"
echo "  eval-test    - Test framework setup"
echo "  eval-quick   - Run quick evaluation"
echo "  eval-analyze - Analyze statistics"
echo "  eval-plot    - Generate plots"
echo "  eval-sweep   - Run parameter sweep"
echo ""
echo "Directory structure:"
echo "  ${EVAL_DIR}/configs/  - Configuration files"
echo "  ${EVAL_DIR}/scripts/  - Analysis scripts"
echo "  ${EVAL_DIR}/docs/     - Documentation"
