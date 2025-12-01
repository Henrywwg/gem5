#!/usr/bin/env python3
"""
Parameter Sweep Script for Dual-Path Execution Evaluation
Runs multiple simulations with different configurations to find optimal parameters
"""

import itertools
import os
import subprocess
from pathlib import Path

# Base configuration
BASE_DIR = Path(__file__).parent.parent.parent
BINARY = (
    "tests/test-progs/hello/bin/x86/linux/hello"  # Update with your binary
)
GEM5_BINARY = BASE_DIR / "build/X86/gem5.opt"
CONFIG_BASELINE = BASE_DIR / "evaluation/configs/eval_baseline.py"
CONFIG_DUALPATH = BASE_DIR / "evaluation/configs/eval_dualpath.py"
OUTPUT_BASE = BASE_DIR / "eval_results"

# Create output directory
OUTPUT_BASE.mkdir(exist_ok=True)

# Parameter sweep ranges
SWEEP_PARAMS = {
    "apb_entries": [16, 32, 64, 128],
    "window_size": [50, 100, 200],
    "high_threshold": [80, 85, 90],
    "low_threshold": [60, 70, 75],
}


def run_baseline(binary, name="baseline"):
    """Run baseline configuration"""
    outdir = OUTPUT_BASE / f"{name}"
    cmd = [
        str(GEM5_BINARY),
        str(CONFIG_BASELINE),
        "--binary",
        binary,
        "--outdir",
        str(outdir),
        "--stats-interval",
        "10000000",
    ]

    print(f"\n{'='*70}")
    print(f"Running BASELINE: {name}")
    print(f"Output: {outdir}")
    print(f"{'='*70}")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def run_dualpath(
    binary, apb_entries, window_size, high_thresh, low_thresh, name=None
):
    """Run dual-path configuration with specified parameters"""
    if name is None:
        name = f"dualpath_apb{apb_entries}_win{window_size}_h{high_thresh}_l{low_thresh}"

    outdir = OUTPUT_BASE / name
    cmd = [
        str(GEM5_BINARY),
        str(CONFIG_DUALPATH),
        "--binary",
        binary,
        "--outdir",
        str(outdir),
        "--apb-entries",
        str(apb_entries),
        "--window-size",
        str(window_size),
        "--high-threshold",
        str(high_thresh),
        "--low-threshold",
        str(low_thresh),
        "--stats-interval",
        "10000000",
    ]

    print(f"\n{'='*70}")
    print(f"Running DUAL-PATH: {name}")
    print(f"  APB Entries: {apb_entries}")
    print(f"  Window Size: {window_size}")
    print(f"  High Threshold: {high_thresh}%")
    print(f"  Low Threshold: {low_thresh}%")
    print(f"Output: {outdir}")
    print(f"{'='*70}")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def quick_sweep(binary):
    """Run a quick parameter sweep with selected configurations"""
    print("\n" + "=" * 70)
    print("STARTING QUICK PARAMETER SWEEP")
    print("=" * 70)

    # Run baseline first
    run_baseline(binary, "baseline")

    # Test a few key configurations
    configs = [
        # (apb_entries, window_size, high_thresh, low_thresh)
        (32, 100, 85, 70),  # Small APB, medium window
        (64, 100, 85, 70),  # Medium APB, medium window (default)
        (128, 100, 85, 70),  # Large APB, medium window
        (64, 50, 85, 70),  # Medium APB, small window
        (64, 200, 85, 70),  # Medium APB, large window
        (64, 100, 90, 75),  # Medium APB, conservative thresholds
        (64, 100, 80, 60),  # Medium APB, aggressive thresholds
    ]

    results = []
    for apb, win, high, low in configs:
        success = run_dualpath(binary, apb, win, high, low)
        results.append((apb, win, high, low, success))

    print("\n" + "=" * 70)
    print("QUICK SWEEP COMPLETE")
    print("=" * 70)
    print("\nResults Summary:")
    print(f"{'APB':<6} {'Window':<8} {'High':<6} {'Low':<6} {'Status'}")
    print("-" * 40)
    for apb, win, high, low, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{apb:<6} {win:<8} {high:<6} {low:<6} {status}")

    return results


def full_sweep(binary):
    """Run full parameter sweep (warning: takes a long time!)"""
    print("\n" + "=" * 70)
    print("STARTING FULL PARAMETER SWEEP")
    print("This will take a very long time!")
    print("=" * 70)

    # Run baseline first
    run_baseline(binary, "baseline")

    # Generate all combinations
    keys = list(SWEEP_PARAMS.keys())
    values = [SWEEP_PARAMS[k] for k in keys]
    combinations = list(itertools.product(*values))

    print(f"\nTotal configurations to test: {len(combinations)}")

    results = []
    for i, combo in enumerate(combinations, 1):
        apb, win, high, low = combo
        print(f"\n[{i}/{len(combinations)}] Testing configuration...")
        success = run_dualpath(binary, apb, win, high, low)
        results.append((apb, win, high, low, success))

    print("\n" + "=" * 70)
    print("FULL SWEEP COMPLETE")
    print("=" * 70)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run parameter sweep for dual-path evaluation"
    )
    parser.add_argument(
        "--binary", type=str, required=True, help="Binary to execute"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="quick",
        choices=["quick", "full", "baseline"],
        help="Sweep mode: quick (7 configs), full (all combinations), or baseline only",
    )
    args = parser.parse_args()

    # Verify gem5 binary exists
    if not GEM5_BINARY.exists():
        print(f"ERROR: gem5 binary not found at {GEM5_BINARY}")
        print("Please build gem5 first: scons build/X86/gem5.opt")
        exit(1)

    # Verify config files exist
    if not CONFIG_BASELINE.exists():
        print(f"ERROR: Baseline config not found at {CONFIG_BASELINE}")
        exit(1)

    if not CONFIG_DUALPATH.exists():
        print(f"ERROR: Dual-path config not found at {CONFIG_DUALPATH}")
        exit(1)

    # Run sweep based on mode
    if args.mode == "baseline":
        run_baseline(args.binary)
    elif args.mode == "quick":
        quick_sweep(args.binary)
    elif args.mode == "full":
        full_sweep(args.binary)

    print(f"\n{'='*70}")
    print("ALL SIMULATIONS COMPLETE")
    print(f"Results saved to: {OUTPUT_BASE}")
    print(f"{'='*70}")
