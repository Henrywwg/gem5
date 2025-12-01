#!/usr/bin/env python3
"""
Compare all three DAXPY benchmark results
"""
import json
import os
import re
import sys
from pathlib import Path


def parse_stats(stats_file):
    """Extract key statistics from stats.txt - middle section only (ROI)"""
    stats = {}

    with open(stats_file) as f:
        content = f.read()

        # Split by "Begin Simulation Statistics" markers
        sections = re.split(r"-+ Begin Simulation Statistics -+", content)

        # We want the MIDDLE section (index 2 out of 4 sections total)
        # Section 0: empty/header, Section 1: init, Section 2: ROI (our target), Section 3: final
        if len(sections) >= 3:
            roi_section = sections[2]
            # Get content until the next "End Simulation Statistics"
            roi_content = roi_section.split(
                "---------- End Simulation Statistics"
            )[0]
        else:
            # Fallback to full content if sections not found
            roi_content = content

        # Extract key metrics from ROI section
        patterns = {
            "sim_ticks": r"simTicks\s+(\d+)",
            "sim_seconds": r"simSeconds\s+([\d.]+)",
            "ipc": r"system\.cpu\.ipc\s+([\d.]+)",
            "num_cycles": r"system\.cpu\.numCycles\s+(\d+)",
            "branch_mispreds": r"system\.cpu\.branchPred\.condIncorrect\s+(\d+)",
            "branch_preds": r"system\.cpu\.branchPred\.condPredicted\s+(\d+)",
            "committed_insts": r"system\.cpu\.committedInsts\s+(\d+)",
            "committed_ops": r"system\.cpu\.committedOps\s+(\d+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, roi_content)
            if match:
                stats[key] = float(match.group(1))
            else:
                stats[key] = 0

    # Calculate misprediction rate
    if stats["branch_preds"] > 0:
        stats["mispred_rate"] = (
            stats["branch_mispreds"] / stats["branch_preds"]
        ) * 100
    else:
        stats["mispred_rate"] = 0

    return stats


def main():
    results_dir = Path("/home/dlnavarro/ece752proj/gem5/evaluation/results")

    benchmarks = {
        "Baseline (No Branches)": results_dir / "baseline_daxpy" / "stats.txt",
        "Progressive (50%→95%)": results_dir
        / "baseline_progressive"
        / "stats.txt",
        "Random (50/50)": results_dir / "baseline_random" / "stats.txt",
    }

    print("=" * 80)
    print("DAXPY BENCHMARK COMPARISON - Baseline O3CPU Configuration")
    print("=" * 80)
    print()

    results = {}
    for name, stats_file in benchmarks.items():
        if stats_file.exists():
            print(f"Analyzing: {name}")
            results[name] = parse_stats(stats_file)
        else:
            print(f"WARNING: {name} results not found at {stats_file}")

    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()

    # Print comparison table
    headers = [
        "Benchmark",
        "Sim Time (s)",
        "IPC",
        "Branches",
        "Mispreds",
        "Mispred Rate",
    ]
    print(
        f"{'Benchmark':<30} {'Sim Time (s)':>12} {'IPC':>8} {'Branches':>12} {'Mispreds':>10} {'Mispred %':>10}"
    )
    print("-" * 90)

    for name, stats in results.items():
        print(
            f"{name:<30} {stats['sim_seconds']:>12.6f} {stats['ipc']:>8.2f} "
            f"{int(stats['branch_preds']):>12} {int(stats['branch_mispreds']):>10} "
            f"{stats['mispred_rate']:>9.2f}%"
        )

    print()
    print("=" * 80)
    print("KEY OBSERVATIONS")
    print("=" * 80)
    print()

    if (
        "Baseline (No Branches)" in results
        and "Progressive (50%→95%)" in results
    ):
        baseline = results["Baseline (No Branches)"]
        progressive = results["Progressive (50%→95%)"]
        random = results.get("Random (50/50)", {})

        print(f"1. Baseline (No Branches) Performance:")
        print(f"   - IPC: {baseline['ipc']:.2f} (expected highest)")
        print(
            f"   - Misprediction Rate: {baseline['mispred_rate']:.2f}% (expected near 0%)"
        )
        print()

        print(f"2. Progressive Warming Behavior:")
        print(
            f"   - IPC: {progressive['ipc']:.2f} ({(progressive['ipc']/baseline['ipc']-1)*100:+.1f}% vs baseline)"
        )
        print(f"   - Misprediction Rate: {progressive['mispred_rate']:.2f}%")
        print(
            f"   - Expected: Should show intermediate mispred rate as predictor warms"
        )
        print()

        if random:
            print(f"3. Random Branch Performance:")
            print(
                f"   - IPC: {random['ipc']:.2f} ({(random['ipc']/baseline['ipc']-1)*100:+.1f}% vs baseline)"
            )
            print(
                f"   - Misprediction Rate: {random['mispred_rate']:.2f}% (expected ~50%)"
            )
            print(f"   - Expected: Worst performance, highest mispredictions")
            print()

    print("=" * 80)
    print("INTERPRETATION FOR DUAL-PATH EXECUTION")
    print("=" * 80)
    print()
    print("These baseline results establish the performance characteristics:")
    print()
    print("• Baseline shows optimal performance with no branch penalties")
    print(
        "• Progressive shows predictor learning over time (50% → 95% predictable)"
    )
    print("• Random shows worst-case constant mispredictions")
    print()
    print("When dual-path execution is enabled, we expect:")
    print(
        "• Early phase (high mispreds): Dual-path mode active, APB beneficial"
    )
    print("• Middle phase: Transition period as predictor learns")
    print("• Late phase (low mispreds): Single-path mode, efficient execution")
    print()
    print("=" * 80)

    # Save results as JSON
    output_file = results_dir / "benchmark_comparison.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
