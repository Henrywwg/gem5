#!/bin/bash
# Quick evaluation script for dual-path execution project
# Usage: ./quick_eval.sh <binary_path>

set -e  # Exit on error

# Configuration
GEM5_ROOT="/home/dlnavarro/ece752proj/gem5"
GEM5_BIN="${GEM5_ROOT}/build/X86/gem5.opt"
RESULTS_DIR="${GEM5_ROOT}/eval_results"
EVAL_DIR="${GEM5_ROOT}/evaluation"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <binary_path> [options]"
    echo ""
    echo "Options:"
    echo "  --baseline-only    Run only baseline configuration"
    echo "  --dualpath-only    Run only dual-path configuration"
    echo "  --quick            Run quick parameter sweep"
    echo "  --no-plots         Skip plot generation"
    echo ""
    echo "Example:"
    echo "  $0 src/hw7/daxpy_m5"
    echo "  $0 src/hw7/daxpy_m5 --quick"
    exit 1
fi

BINARY=$1
shift

# Parse options
BASELINE_ONLY=false
DUALPATH_ONLY=false
QUICK_SWEEP=false
NO_PLOTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --baseline-only)
            BASELINE_ONLY=true
            shift
            ;;
        --dualpath-only)
            DUALPATH_ONLY=true
            shift
            ;;
        --quick)
            QUICK_SWEEP=true
            shift
            ;;
        --no-plots)
            NO_PLOTS=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if binary exists
if [ ! -f "${GEM5_ROOT}/${BINARY}" ]; then
    print_error "Binary not found: ${GEM5_ROOT}/${BINARY}"
    exit 1
fi

# Check if gem5 is built
if [ ! -f "${GEM5_BIN}" ]; then
    print_error "gem5 not built. Run: scons build/X86/gem5.opt"
    exit 1
fi

# Create results directory
mkdir -p "${RESULTS_DIR}"

# Get binary name for output directories
BINARY_NAME=$(basename ${BINARY} | sed 's/\.[^.]*$//')

print_header "Dual-Path Execution Evaluation"
echo "Binary: ${BINARY}"
echo "Results: ${RESULTS_DIR}"
echo ""

# Run quick sweep if requested
if [ "$QUICK_SWEEP" = true ]; then
    print_header "Running Quick Parameter Sweep"
    cd "${GEM5_ROOT}"
    python3 evaluation/scripts/run_sweep.py --binary "${BINARY}" --mode quick
    print_success "Parameter sweep complete"
    exit 0
fi

# Run baseline
if [ "$DUALPATH_ONLY" = false ]; then
    print_header "Running Baseline Configuration"
    BASELINE_DIR="${RESULTS_DIR}/baseline_${BINARY_NAME}"
    mkdir -p "${BASELINE_DIR}"

    print_info "Starting baseline simulation..."
    cd "${GEM5_ROOT}"

    if ${GEM5_BIN} evaluation/configs/eval_baseline.py \
        --binary "${BINARY}" \
        --outdir "${BASELINE_DIR}" \
        --stats-interval 10000000; then
        print_success "Baseline simulation complete"

        # Analyze results
        print_info "Analyzing baseline results..."
        python3 evaluation/scripts/analyze_stats.py \
            "${BASELINE_DIR}/stats.txt" \
            --output "${BASELINE_DIR}/report.json" \
            --csv "${BASELINE_DIR}/temporal.csv"
        print_success "Baseline analysis complete"
    else
        print_error "Baseline simulation failed"
        exit 1
    fi
fi

# Run dual-path
if [ "$BASELINE_ONLY" = false ]; then
    print_header "Running Dual-Path Configuration"
    DUALPATH_DIR="${RESULTS_DIR}/dualpath_${BINARY_NAME}"
    mkdir -p "${DUALPATH_DIR}"

    print_info "Starting dual-path simulation..."
    cd "${GEM5_ROOT}"

    if ${GEM5_BIN} evaluation/configs/eval_dualpath.py \
        --binary "${BINARY}" \
        --outdir "${DUALPATH_DIR}" \
        --stats-interval 10000000 \
        --apb-entries 64 \
        --window-size 100 \
        --high-threshold 85 \
        --low-threshold 70; then
        print_success "Dual-path simulation complete"

        # Analyze results
        print_info "Analyzing dual-path results..."

        if [ -f "${RESULTS_DIR}/baseline_${BINARY_NAME}/stats.txt" ]; then
            # Compare with baseline
            python3 evaluation/scripts/analyze_stats.py \
                "${DUALPATH_DIR}/stats.txt" \
                --baseline "${RESULTS_DIR}/baseline_${BINARY_NAME}/stats.txt" \
                --output "${DUALPATH_DIR}/report.json" \
                --csv "${DUALPATH_DIR}/temporal.csv"
        else
            # No baseline available
            python3 evaluation/scripts/analyze_stats.py \
                "${DUALPATH_DIR}/stats.txt" \
                --output "${DUALPATH_DIR}/report.json" \
                --csv "${DUALPATH_DIR}/temporal.csv"
        fi
        print_success "Dual-path analysis complete"
    else
        print_error "Dual-path simulation failed"
        exit 1
    fi
fi

# Generate plots
if [ "$NO_PLOTS" = false ] && [ "$BASELINE_ONLY" = false ] && [ "$DUALPATH_ONLY" = false ]; then
    print_header "Generating Plots"

    # Check if matplotlib is available
    if python3 -c "import matplotlib" 2>/dev/null; then
        PLOT_DIR="${RESULTS_DIR}/plots_${BINARY_NAME}"
        mkdir -p "${PLOT_DIR}"

        print_info "Creating visualization plots..."
        python3 evaluation/scripts/plot_results.py \
            --baseline-json "${RESULTS_DIR}/baseline_${BINARY_NAME}/report.json" \
            --dualpath-json "${RESULTS_DIR}/dualpath_${BINARY_NAME}/report.json" \
            --output-dir "${PLOT_DIR}"

        print_success "Plots generated in ${PLOT_DIR}"
    else
        print_error "matplotlib not found. Install with: pip install matplotlib numpy"
        print_info "Skipping plot generation"
    fi
fi

# Print summary
print_header "Evaluation Complete"
echo ""
echo "Results saved to: ${RESULTS_DIR}"
echo ""

if [ "$BASELINE_ONLY" = false ] && [ "$DUALPATH_ONLY" = false ]; then
    echo "Baseline:  ${RESULTS_DIR}/baseline_${BINARY_NAME}/"
    echo "Dual-Path: ${RESULTS_DIR}/dualpath_${BINARY_NAME}/"

    if [ "$NO_PLOTS" = false ] && python3 -c "import matplotlib" 2>/dev/null; then
        echo "Plots:     ${RESULTS_DIR}/plots_${BINARY_NAME}/"
    fi

    echo ""
    echo "Key files:"
    echo "  - stats.txt      : Raw gem5 statistics"
    echo "  - report.json    : Analyzed metrics"
    echo "  - temporal.csv   : Time-series data"
    echo "  - *.png          : Visualization plots"

    # Print quick summary if comparison was done
    if [ -f "${RESULTS_DIR}/dualpath_${BINARY_NAME}/report.json" ]; then
        echo ""
        print_info "Quick Summary:"
        python3 -c "
import json
import sys

try:
    with open('${RESULTS_DIR}/dualpath_${BINARY_NAME}/report.json') as f:
        report = json.load(f)

    branch = report['branch_stats']
    perf = report['performance_stats']

    print(f'  Branches:          {branch[\"branches\"]:,}')
    print(f'  Mispredictions:    {branch[\"branch_mispredicts\"]:,}')
    print(f'  Mispred Rate:      {branch[\"mispred_rate\"]:.2f}%')
    print(f'  IPC:               {perf[\"ipc\"]:.3f}')

    if 'comparison' in report:
        comp = report['comparison']
        print(f'  ')
        print(f'  vs Baseline:')
        print(f'    Mispred Reduction: {comp[\"mispred_reduction_percent\"]:+.2f}%')
        print(f'    IPC Improvement:   {comp[\"ipc_improvement_percent\"]:+.2f}%')
        print(f'    Speedup:           {comp[\"speedup\"]:.3f}x')
except Exception as e:
    print(f'  (Could not load summary: {e})', file=sys.stderr)
"
    fi
fi

echo ""
print_success "All done!"
