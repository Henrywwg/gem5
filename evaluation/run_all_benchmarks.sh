#!/bin/bash
# Run all DAXPY benchmark evaluations
# This script runs baseline, progressive, and random DAXPY tests
# with both baseline and dual-path configurations

set -e

GEM5_ROOT="/home/dlnavarro/ece752proj/gem5"
GEM5_BIN="${GEM5_ROOT}/build/X86/gem5.opt"
RESULTS_DIR="${GEM5_ROOT}/eval_results"
BENCH_DIR="${GEM5_ROOT}/evaluation/benchmarks"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check if benchmarks are built
if [ ! -f "${BENCH_DIR}/bin/daxpy_baseline" ]; then
    print_error "Benchmarks not built!"
    echo "Please run: cd evaluation/benchmarks && make"
    exit 1
fi

# Check if gem5 is built
if [ ! -f "${GEM5_BIN}" ]; then
    print_error "gem5 not built!"
    echo "Please run: scons build/X86/gem5.opt"
    exit 1
fi

mkdir -p "${RESULTS_DIR}"

print_header "DAXPY Benchmark Evaluation Suite"
echo "This will run 6 simulations:"
echo "  1. Baseline DAXPY - Baseline Config"
echo "  2. Baseline DAXPY - Dual-Path Config"
echo "  3. Random DAXPY - Baseline Config"
echo "  4. Random DAXPY - Dual-Path Config"
echo "  5. Progressive DAXPY - Baseline Config"
echo "  6. Progressive DAXPY - Dual-Path Config ⭐ KEY TEST"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

# Function to run simulation
run_sim() {
    local config=$1
    local binary=$2
    local outdir=$3
    local stats_interval=$4
    local extra_args=$5

    print_info "Running: $(basename $binary) with $(basename $config)"

    if ${GEM5_BIN} ${config} \
        --binary ${binary} \
        --outdir ${outdir} \
        --stats-interval ${stats_interval} \
        ${extra_args}; then
        print_success "Complete: ${outdir}"
        return 0
    else
        print_error "Failed: ${outdir}"
        return 1
    fi
}

# Counters
total=6
completed=0

# 1. Baseline DAXPY - Baseline Config
print_header "[1/6] Baseline DAXPY - Baseline Config"
if run_sim \
    "${GEM5_ROOT}/evaluation/configs/eval_baseline.py" \
    "${BENCH_DIR}/bin/daxpy_baseline" \
    "${RESULTS_DIR}/baseline_baseline" \
    10000000; then
    ((completed++))
fi
echo ""

# 2. Baseline DAXPY - Dual-Path Config
print_header "[2/6] Baseline DAXPY - Dual-Path Config"
if run_sim \
    "${GEM5_ROOT}/evaluation/configs/eval_dualpath.py" \
    "${BENCH_DIR}/bin/daxpy_baseline" \
    "${RESULTS_DIR}/dualpath_baseline" \
    10000000; then
    ((completed++))
fi
echo ""

# 3. Random DAXPY - Baseline Config
print_header "[3/6] Random DAXPY - Baseline Config"
if run_sim \
    "${GEM5_ROOT}/evaluation/configs/eval_baseline.py" \
    "${BENCH_DIR}/bin/daxpy_random" \
    "${RESULTS_DIR}/baseline_random" \
    10000000; then
    ((completed++))
fi
echo ""

# 4. Random DAXPY - Dual-Path Config
print_header "[4/6] Random DAXPY - Dual-Path Config"
if run_sim \
    "${GEM5_ROOT}/evaluation/configs/eval_dualpath.py" \
    "${BENCH_DIR}/bin/daxpy_random" \
    "${RESULTS_DIR}/dualpath_random" \
    10000000; then
    ((completed++))
fi
echo ""

# 5. Progressive DAXPY - Baseline Config
print_header "[5/6] Progressive DAXPY - Baseline Config"
if run_sim \
    "${GEM5_ROOT}/evaluation/configs/eval_baseline.py" \
    "${BENCH_DIR}/bin/daxpy_progressive" \
    "${RESULTS_DIR}/baseline_progressive" \
    2000000; then  # Smaller interval to capture transition
    ((completed++))
fi
echo ""

# 6. Progressive DAXPY - Dual-Path Config ⭐ KEY TEST
print_header "[6/6] Progressive DAXPY - Dual-Path Config ⭐ KEY TEST"
if run_sim \
    "${GEM5_ROOT}/evaluation/configs/eval_dualpath.py" \
    "${BENCH_DIR}/bin/daxpy_progressive" \
    "${RESULTS_DIR}/dualpath_progressive" \
    2000000 \
    "--initial-dual-path"; then  # Start in dual-path mode
    ((completed++))
fi
echo ""

# Summary
print_header "Evaluation Complete"
echo "Completed: ${completed}/${total} simulations"
echo ""
echo "Results saved to: ${RESULTS_DIR}"
echo ""

if [ ${completed} -eq ${total} ]; then
    print_success "All simulations completed successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Analyze results:"
    echo "     python3 evaluation/scripts/analyze_stats.py \\"
    echo "       ${RESULTS_DIR}/dualpath_progressive/stats.txt \\"
    echo "       --baseline ${RESULTS_DIR}/baseline_progressive/stats.txt"
    echo ""
    echo "  2. Generate plots:"
    echo "     python3 evaluation/scripts/plot_results.py \\"
    echo "       --baseline-json ${RESULTS_DIR}/baseline_progressive/report.json \\"
    echo "       --dualpath-json ${RESULTS_DIR}/dualpath_progressive/report.json"
    echo ""
    echo "  3. Review key test (Progressive DAXPY):"
    echo "     cat ${RESULTS_DIR}/dualpath_progressive/stats.txt | grep -A5 'dualPath'"
else
    print_error "Some simulations failed (${completed}/${total})"
    echo "Check the output above for errors"
    exit 1
fi
