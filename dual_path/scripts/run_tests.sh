#!/bin/bash
# Run dual-path evaluation tests
# Usage: ./run_tests.sh <benchmark> [baseline|dualpath|all]

set -e

GEM5_ROOT="/home/dlnavarro/ece752proj/gem5"
GEM5_BIN="${GEM5_ROOT}/build/X86/gem5.opt"
CONFIG="${GEM5_ROOT}/dual_path/configs/eval_dualpath.py"

# Default benchmark
BENCHMARK="${1:-daxpy_progressive}"
MODE="${2:-all}"

# Check if benchmark path is absolute or relative
if [[ "$BENCHMARK" != /* ]]; then
    BENCH_PATH="${GEM5_ROOT}/dual_path/benchmarks/bin/${BENCHMARK}"
else
    BENCH_PATH="$BENCHMARK"
fi

# Check benchmark exists
if [ ! -f "$BENCH_PATH" ]; then
    echo "Error: Benchmark not found: $BENCH_PATH"
    echo "Available benchmarks:"
    ls -1 "${GEM5_ROOT}/dual_path/benchmarks/bin/" 2>/dev/null || echo "  (none built yet)"
    exit 1
fi

BENCH_NAME=$(basename "$BENCH_PATH")
RESULTS_DIR="${GEM5_ROOT}/dual_path/results/${BENCH_NAME}"
mkdir -p "$RESULTS_DIR"

echo "========================================"
echo "Dual-Path APB Evaluation"
echo "========================================"
echo "Benchmark: $BENCH_NAME"
echo "Results:   $RESULTS_DIR"
echo ""

run_baseline() {
    echo ">>> Running BASELINE (threshold=0)..."
    $GEM5_BIN $CONFIG \
        --binary="$BENCH_PATH" \
        --confidence-threshold=0 \
        --outdir="${RESULTS_DIR}/baseline" 2>&1 | tail -3
    echo "    Done: ${RESULTS_DIR}/baseline/stats.txt"
}

run_dualpath() {
    local entries=$1
    local filter=$2
    local outdir="${RESULTS_DIR}/apb${entries}_filter_${filter}"
    
    if [ "$filter" = "on" ]; then
        filter_flag="--icache-filter"
    else
        filter_flag="--no-icache-filter"
    fi
    
    echo ">>> Running APB=${entries}, Filter=${filter}..."
    $GEM5_BIN $CONFIG \
        --binary="$BENCH_PATH" \
        --confidence-threshold=70 \
        --apb-entries=$entries \
        $filter_flag \
        --outdir="$outdir" 2>&1 | tail -3
    echo "    Done: ${outdir}/stats.txt"
}

case $MODE in
    baseline)
        run_baseline
        ;;
    dualpath)
        run_dualpath 64 on
        ;;
    sweep)
        run_baseline
        for entries in 16 64 256; do
            for filter in on off; do
                run_dualpath $entries $filter
            done
        done
        ;;
    all|*)
        run_baseline
        run_dualpath 64 on
        run_dualpath 64 off
        ;;
esac

echo ""
echo "========================================"
echo "COMPLETE"
echo "========================================"
echo ""
echo "Compare results:"
echo "  python3 dual_path/scripts/extract_metrics.py ${RESULTS_DIR}/baseline/stats.txt"
echo "  python3 dual_path/scripts/extract_metrics.py ${RESULTS_DIR}/apb64_filter_on/stats.txt"
