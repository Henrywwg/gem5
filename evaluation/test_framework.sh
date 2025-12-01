#!/bin/bash
# Test script to verify evaluation framework setup
# Usage: ./test_framework.sh

set -e

GEM5_ROOT="/home/dlnavarro/ece752proj/gem5"
PASSED=0
FAILED=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_test() {
    echo -e "${YELLOW}Testing: $1${NC}"
}

print_pass() {
    echo -e "${GREEN}✓ PASS: $1${NC}"
    PASSED=$((PASSED + 1))
}

print_fail() {
    echo -e "${RED}✗ FAIL: $1${NC}"
    FAILED=$((FAILED + 1))
}

echo "================================================"
echo "Dual-Path Evaluation Framework Test"
echo "================================================"
echo ""

# Test 1: Check gem5 build
print_test "gem5 build exists"
if [ -f "${GEM5_ROOT}/build/X86/gem5.opt" ]; then
    print_pass "gem5.opt found"
else
    print_fail "gem5.opt not found - run: scons build/X86/gem5.opt"
fi

# Test 2: Check config files
print_test "Configuration files exist"
for config in eval_baseline.py eval_dualpath.py daxpy_eval_example.py; do
    if [ -f "${GEM5_ROOT}/evaluation/configs/${config}" ]; then
        print_pass "${config}"
    else
        print_fail "${config} missing"
    fi
done

# Test 3: Check analysis tools
print_test "Analysis tools exist"
for tool in analyze_stats.py plot_results.py run_sweep.py; do
    if [ -f "${GEM5_ROOT}/evaluation/scripts/${tool}" ]; then
        print_pass "${tool}"
    else
        print_fail "${tool} missing"
    fi
done

# Test 4: Check quick_eval.sh
print_test "Quick eval script"
if [ -f "${GEM5_ROOT}/evaluation/quick_eval.sh" ] && [ -x "${GEM5_ROOT}/evaluation/quick_eval.sh" ]; then
    print_pass "quick_eval.sh exists and is executable"
else
    print_fail "quick_eval.sh missing or not executable"
fi

# Test 5: Check Python syntax
print_test "Python script syntax"
for script in evaluation/configs/eval_baseline.py evaluation/configs/eval_dualpath.py evaluation/scripts/analyze_stats.py; do
    if python3 -m py_compile "${GEM5_ROOT}/${script}" 2>/dev/null; then
        print_pass "$(basename $script) syntax OK"
    else
        print_fail "$(basename $script) has syntax errors"
    fi
done

# Test 6: Check Python dependencies
print_test "Python dependencies"
if python3 -c "import argparse, json, csv, re, pathlib" 2>/dev/null; then
    print_pass "Core Python modules available"
else
    print_fail "Missing core Python modules"
fi

if python3 -c "import matplotlib, numpy" 2>/dev/null; then
    print_pass "matplotlib and numpy available"
else
    print_fail "matplotlib/numpy not installed (optional, for plotting)"
fi

# Test 7: Check documentation
print_test "Documentation files"
for doc in QUICK_START.md EVALUATION_README.md FRAMEWORK_SUMMARY.md; do
    if [ -f "${GEM5_ROOT}/evaluation/docs/${doc}" ]; then
        print_pass "${doc}"
    else
        print_fail "${doc} missing"
    fi
done

# Test 8: Check directory structure
print_test "Directory structure"
if [ -d "${GEM5_ROOT}/evaluation" ]; then
    print_pass "evaluation directory exists"
else
    print_fail "evaluation directory missing"
fi

# Test 9: Try importing gem5 m5 module
print_test "gem5 Python modules"
cd "${GEM5_ROOT}"
if python3 -c "import sys; sys.path.insert(0, 'build/X86/python'); import m5" 2>/dev/null; then
    print_pass "gem5 m5 module can be imported"
else
    print_fail "Cannot import gem5 m5 module (may need full build)"
fi

# Test 10: Check for sample binaries
print_test "Test binaries"
if [ -f "${GEM5_ROOT}/tests/test-progs/hello/bin/x86/linux/hello" ]; then
    print_pass "Sample hello binary found"
else
    print_fail "Sample binaries not found (optional)"
fi

# Summary
echo ""
echo "================================================"
echo "Test Summary"
echo "================================================"
echo -e "Passed: ${GREEN}${PASSED}${NC}"
echo -e "Failed: ${RED}${FAILED}${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo ""
    echo "You're ready to run evaluations!"
    echo ""
    echo "Quick start:"
    echo "  ./quick_eval.sh <path-to-binary>"
    echo ""
    echo "Or see QUICK_START.md for detailed instructions."
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Please fix the issues above before running evaluations."
    echo "See QUICK_START.md for setup instructions."
    exit 1
fi
