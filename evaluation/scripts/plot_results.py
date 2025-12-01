#!/usr/bin/env python3
"""
Plotting Script for Dual-Path Execution Evaluation
Generates visualization plots from gem5 statistics
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    print("Error: matplotlib and numpy required for plotting")
    print("Install with: pip install matplotlib numpy")
    sys.exit(1)


def plot_temporal_mispred_rate(baseline_rates, dualpath_rates, output_file):
    """Plot misprediction rate over time"""
    plt.figure(figsize=(12, 6))

    x_baseline = np.arange(1, len(baseline_rates) + 1)
    x_dualpath = np.arange(1, len(dualpath_rates) + 1)

    plt.plot(
        x_baseline,
        baseline_rates,
        "o-",
        label="Baseline",
        linewidth=2,
        markersize=6,
        color="#d62728",
    )
    plt.plot(
        x_dualpath,
        dualpath_rates,
        "s-",
        label="Dual-Path",
        linewidth=2,
        markersize=6,
        color="#2ca02c",
    )

    plt.xlabel("Time Interval", fontsize=12)
    plt.ylabel("Branch Misprediction Rate (%)", fontsize=12)
    plt.title(
        "Branch Misprediction Rate Over Time", fontsize=14, fontweight="bold"
    )
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Temporal plot saved to: {output_file}")
    plt.close()


def plot_comparison_bars(baseline_report, dualpath_report, output_file):
    """Plot comparison bar charts"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Misprediction Rate
    ax = axes[0, 0]
    baseline_mispred = baseline_report["branch_stats"]["mispred_rate"]
    dualpath_mispred = dualpath_report["branch_stats"]["mispred_rate"]

    x = np.arange(2)
    values = [baseline_mispred, dualpath_mispred]
    colors = ["#d62728", "#2ca02c"]
    bars = ax.bar(
        x, values, color=colors, alpha=0.8, edgecolor="black", linewidth=1.5
    )
    ax.set_xticks(x)
    ax.set_xticklabels(["Baseline", "Dual-Path"])
    ax.set_ylabel("Misprediction Rate (%)", fontsize=11)
    ax.set_title("Branch Misprediction Rate", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.2f}%",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    # IPC
    ax = axes[0, 1]
    baseline_ipc = baseline_report["performance_stats"]["ipc"]
    dualpath_ipc = dualpath_report["performance_stats"]["ipc"]

    values = [baseline_ipc, dualpath_ipc]
    bars = ax.bar(
        x, values, color=colors, alpha=0.8, edgecolor="black", linewidth=1.5
    )
    ax.set_xticks(x)
    ax.set_xticklabels(["Baseline", "Dual-Path"])
    ax.set_ylabel("Instructions Per Cycle", fontsize=11)
    ax.set_title("IPC Comparison", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.3f}",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    # Execution Time
    ax = axes[1, 0]
    baseline_ticks = baseline_report["performance_stats"]["sim_ticks"]
    dualpath_ticks = dualpath_report["performance_stats"]["sim_ticks"]

    values = [
        baseline_ticks / 1e9,
        dualpath_ticks / 1e9,
    ]  # Convert to billions
    bars = ax.bar(
        x, values, color=colors, alpha=0.8, edgecolor="black", linewidth=1.5
    )
    ax.set_xticks(x)
    ax.set_xticklabels(["Baseline", "Dual-Path"])
    ax.set_ylabel("Execution Time (Billion Ticks)", fontsize=11)
    ax.set_title("Execution Time Comparison", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.2f}B",
            ha="center",
            va="bottom",
            fontsize=10,
        )

    # APB Hit Rate (if available)
    ax = axes[1, 1]
    dp_stats = dualpath_report["dual_path_stats"]

    if dp_stats["apb_hits"] > 0:
        apb_hit_rate = dp_stats["apb_hit_rate"]
        dual_path_pct = dp_stats["dual_path_percent"]

        metrics = ["APB Hit Rate", "Dual-Path Usage"]
        values = [apb_hit_rate, dual_path_pct]
        x_pos = np.arange(len(metrics))

        bars = ax.bar(
            x_pos,
            values,
            color="#1f77b4",
            alpha=0.8,
            edgecolor="black",
            linewidth=1.5,
        )
        ax.set_xticks(x_pos)
        ax.set_xticklabels(metrics, rotation=15, ha="right")
        ax.set_ylabel("Percentage (%)", fontsize=11)
        ax.set_title("Dual-Path Metrics", fontsize=12, fontweight="bold")
        ax.grid(axis="y", alpha=0.3)

        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                fontsize=10,
            )
    else:
        ax.text(
            0.5,
            0.5,
            "No Dual-Path Data",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=14,
        )
        ax.set_xticks([])
        ax.set_yticks([])

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Comparison plot saved to: {output_file}")
    plt.close()


def plot_parameter_sweep(results_dir, output_file):
    """Plot results from parameter sweep"""
    results_dir = Path(results_dir)

    # Collect all results
    configs = []

    for result_dir in results_dir.iterdir():
        if not result_dir.is_dir():
            continue

        stats_file = result_dir / "stats.txt"
        if not stats_file.exists():
            continue

        # Parse directory name to extract parameters
        # Format: dualpath_apbXX_winXXX_hXX_lXX
        name = result_dir.name
        if not name.startswith("dualpath_"):
            continue

        try:
            from analyze_stats import StatsAnalyzer

            analyzer = StatsAnalyzer(stats_file)
            report = analyzer.generate_report()

            # Extract parameters from directory name
            parts = name.split("_")
            apb = int(parts[1].replace("apb", ""))
            win = int(parts[2].replace("win", ""))
            high = int(parts[3].replace("h", ""))
            low = int(parts[4].replace("l", ""))

            configs.append(
                {
                    "apb_entries": apb,
                    "window_size": win,
                    "high_thresh": high,
                    "low_thresh": low,
                    "mispred_rate": report["branch_stats"]["mispred_rate"],
                    "ipc": report["performance_stats"]["ipc"],
                }
            )
        except Exception as e:
            print(f"Warning: Could not parse {result_dir.name}: {e}")
            continue

    if not configs:
        print("No valid configurations found")
        return

    # Plot APB size vs performance
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Group by APB size
    apb_sizes = sorted({c["apb_entries"] for c in configs})
    apb_mispred = []
    apb_ipc = []

    for apb in apb_sizes:
        matching = [c for c in configs if c["apb_entries"] == apb]
        avg_mispred = np.mean([c["mispred_rate"] for c in matching])
        avg_ipc = np.mean([c["ipc"] for c in matching])
        apb_mispred.append(avg_mispred)
        apb_ipc.append(avg_ipc)

    ax = axes[0]
    ax.plot(
        apb_sizes,
        apb_mispred,
        "o-",
        linewidth=2,
        markersize=8,
        color="#ff7f0e",
    )
    ax.set_xlabel("APB Entries", fontsize=11)
    ax.set_ylabel("Avg Misprediction Rate (%)", fontsize=11)
    ax.set_title("Impact of APB Size", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(
        apb_sizes, apb_ipc, "s-", linewidth=2, markersize=8, color="#2ca02c"
    )
    ax.set_xlabel("APB Entries", fontsize=11)
    ax.set_ylabel("Avg IPC", fontsize=11)
    ax.set_title("Impact of APB Size on IPC", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Parameter sweep plot saved to: {output_file}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Generate plots for dual-path evaluation"
    )
    parser.add_argument(
        "--baseline-json",
        type=str,
        help="Baseline JSON report from analyze_stats.py",
    )
    parser.add_argument(
        "--dualpath-json",
        type=str,
        help="Dual-path JSON report from analyze_stats.py",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        help="Directory with parameter sweep results",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="plots",
        help="Output directory for plots",
    )
    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Plot comparison if both configs provided
    if args.baseline_json and args.dualpath_json:
        with open(args.baseline_json) as f:
            baseline_report = json.load(f)
        with open(args.dualpath_json) as f:
            dualpath_report = json.load(f)

        # Comparison bars
        plot_comparison_bars(
            baseline_report,
            dualpath_report,
            output_dir / "comparison_bars.png",
        )

        # Temporal plot if available
        if (
            "temporal_mispred_rates" in baseline_report
            and "temporal_mispred_rates" in dualpath_report
        ):
            plot_temporal_mispred_rate(
                baseline_report["temporal_mispred_rates"],
                dualpath_report["temporal_mispred_rates"],
                output_dir / "temporal_mispred.png",
            )

    # Plot parameter sweep if provided
    if args.results_dir:
        plot_parameter_sweep(
            args.results_dir, output_dir / "parameter_sweep.png"
        )

    print(f"\nAll plots saved to: {output_dir}")


if __name__ == "__main__":
    main()
