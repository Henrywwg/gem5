#!/bin/bash
# Quick test script for dual-path execution

set -e

GEM5_ROOT="../../.."
GEM5_BIN="${GEM5_ROOT}/build/X86/gem5.opt"
RESULTS_DIR="../results"

echo "========================================"
echo "Dual-Path Quick Test"
echo "========================================"

# Check gem5 binary exists
if [ ! -f "$GEM5_BIN" ]; then
    echo "Error: gem5 binary not found at $GEM5_BIN"
    exit 1
fi

# Make sure benchmarks are built
if [ ! -f ../benchmarks/bin/daxpy_progressive ]; then
    echo "Building benchmarks..."
    (cd ../benchmarks && make)
fi

# Test 1: DAXPY benchmark
echo ""
echo "Test 1: Running daxpy_progressive..."
mkdir -p ${RESULTS_DIR}/quick_test_daxpy
$GEM5_BIN \
    ../configs/simple_dualpath.py \
    --binary=../benchmarks/bin/daxpy_progressive \
    --outdir=${RESULTS_DIR}/quick_test_daxpy

echo ""
echo "Extracting DAXPY metrics..."
python3 extract_metrics.py ${RESULTS_DIR}/quick_test_daxpy/stats.txt

# Test 2: MatMul benchmark
echo ""
echo "========================================" 
echo "Test 2: Running matmul_conditional..."
mkdir -p ${RESULTS_DIR}/quick_test_matmul
$GEM5_BIN \
    ../configs/simple_dualpath.py \
    --binary=../benchmarks/bin/matmul_conditional \
    --outdir=${RESULTS_DIR}/quick_test_matmul

echo ""
echo "Extracting MatMul metrics..."
python3 extract_metrics.py ${RESULTS_DIR}/quick_test_matmul/stats.txt

echo ""
echo "========================================"
echo "Quick test complete!"
echo "Results in: ${RESULTS_DIR}/quick_test_*"
echo "========================================"

# Quick verification
echo ""
echo "Checking for dual-path stats..."
echo ""
echo "DAXPY - APB Stats:"
grep -E "apb\.(hits|misses|inserts)" ${RESULTS_DIR}/quick_test_daxpy/stats.txt || echo "  (No APB stats found)"
echo ""
echo "MatMul - Speculative Path Stats:"
grep -E "speculativePaths" ${RESULTS_DIR}/quick_test_matmul/stats.txt || echo "  (No speculative path stats found)"
echo ""

echo "If you see stats above, dual-path is working! 🎉"
