#!/usr/bin/env python3
"""
Generate visualization plots for DAXPY benchmark evaluation
"""
import json

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def create_comparison_plot(results, output_dir):
    """Create bar chart comparing benchmarks"""
    benchmarks = list(results.keys())

    # Extract metrics
    ipc = [results[b]["ipc"] for b in benchmarks]
    mispred_rate = [results[b]["mispred_rate"] for b in benchmarks]
    sim_time = [
        results[b]["sim_seconds"] * 1000 for b in benchmarks
    ]  # Convert to ms

    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        "DAXPY Benchmark Comparison - Baseline O3CPU",
        fontsize=16,
        fontweight="bold",
    )

    # Colors
    colors = ["#2ecc71", "#3498db", "#e74c3c"]

    # Plot 1: IPC Comparison
    ax1 = axes[0, 0]
    bars1 = ax1.bar(
        range(len(benchmarks)), ipc, color=colors, alpha=0.8, edgecolor="black"
    )
    ax1.set_ylabel(
        "Instructions Per Cycle (IPC)", fontsize=11, fontweight="bold"
    )
    ax1.set_title("Performance Comparison", fontsize=12, fontweight="bold")
    ax1.set_xticks(range(len(benchmarks)))
    ax1.set_xticklabels(
        [b.replace(" (", "\n(") for b in benchmarks], fontsize=9
    )
    ax1.grid(axis="y", alpha=0.3, linestyle="--")
    ax1.set_ylim([0, max(ipc) * 1.2])

    # Add value labels
    for bar in bars1:
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.2f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    # Plot 2: Misprediction Rate
    ax2 = axes[0, 1]
    bars2 = ax2.bar(
        range(len(benchmarks)),
        mispred_rate,
        color=colors,
        alpha=0.8,
        edgecolor="black",
    )
    ax2.set_ylabel(
        "Branch Misprediction Rate (%)", fontsize=11, fontweight="bold"
    )
    ax2.set_title("Branch Prediction Accuracy", fontsize=12, fontweight="bold")
    ax2.set_xticks(range(len(benchmarks)))
    ax2.set_xticklabels(
        [b.replace(" (", "\n(") for b in benchmarks], fontsize=9
    )
    ax2.grid(axis="y", alpha=0.3, linestyle="--")
    ax2.set_ylim([0, max(mispred_rate) * 1.3])

    # Add value labels
    for bar in bars2:
        height = bar.get_height()
        ax2.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.2f}%",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    # Plot 3: Simulation Time
    ax3 = axes[1, 0]
    bars3 = ax3.bar(
        range(len(benchmarks)),
        sim_time,
        color=colors,
        alpha=0.8,
        edgecolor="black",
    )
    ax3.set_ylabel("Simulation Time (ms)", fontsize=11, fontweight="bold")
    ax3.set_title("Execution Time", fontsize=12, fontweight="bold")
    ax3.set_xticks(range(len(benchmarks)))
    ax3.set_xticklabels(
        [b.replace(" (", "\n(") for b in benchmarks], fontsize=9
    )
    ax3.grid(axis="y", alpha=0.3, linestyle="--")
    ax3.set_ylim([0, max(sim_time) * 1.2])

    # Add value labels
    for bar in bars3:
        height = bar.get_height()
        ax3.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{height:.2f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    # Plot 4: Summary Table
    ax4 = axes[1, 1]
    ax4.axis("off")

    # Create summary table
    table_data = []
    table_data.append(["Metric", "Baseline", "Progressive", "Random"])
    table_data.append(
        ["IPC", f"{ipc[0]:.2f}", f"{ipc[1]:.2f}", f"{ipc[2]:.2f}"]
    )
    table_data.append(
        [
            "Mispred %",
            f"{mispred_rate[0]:.2f}",
            f"{mispred_rate[1]:.2f}",
            f"{mispred_rate[2]:.2f}",
        ]
    )
    table_data.append(
        [
            "Time (ms)",
            f"{sim_time[0]:.2f}",
            f"{sim_time[1]:.2f}",
            f"{sim_time[2]:.2f}",
        ]
    )

    # Calculate relative performance
    ipc_change_prog = ((ipc[1] / ipc[0]) - 1) * 100
    ipc_change_rand = ((ipc[2] / ipc[0]) - 1) * 100
    table_data.append(
        [
            "IPC vs Base",
            "—",
            f"{ipc_change_prog:+.1f}%",
            f"{ipc_change_rand:+.1f}%",
        ]
    )

    table = ax4.table(
        cellText=table_data,
        cellLoc="center",
        loc="center",
        colWidths=[0.25, 0.25, 0.25, 0.25],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)

    # Style header row
    for i in range(4):
        table[(0, i)].set_facecolor("#34495e")
        table[(0, i)].set_text_props(weight="bold", color="white")

    # Style data rows
    for i in range(1, 5):
        for j in range(4):
            if j == 0:
                table[(i, j)].set_facecolor("#ecf0f1")
                table[(i, j)].set_text_props(weight="bold")
            else:
                table[(i, j)].set_facecolor("#ffffff")

    ax4.set_title("Summary Statistics", fontsize=12, fontweight="bold", pad=20)

    plt.tight_layout()

    output_file = output_dir / "benchmark_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Created: {output_file}")

    return output_file


def create_branch_analysis_plot(results, output_dir):
    """Create detailed branch prediction analysis plot"""
    benchmarks = list(results.keys())

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Branch Prediction Analysis", fontsize=16, fontweight="bold")

    colors = ["#2ecc71", "#3498db", "#e74c3c"]

    # Plot 1: Total branches
    ax1 = axes[0]
    branch_preds = [results[b]["branch_preds"] for b in benchmarks]
    bars1 = ax1.bar(
        range(len(benchmarks)),
        branch_preds,
        color=colors,
        alpha=0.8,
        edgecolor="black",
    )
    ax1.set_ylabel("Total Branches Predicted", fontsize=11, fontweight="bold")
    ax1.set_title("Branch Activity", fontsize=12, fontweight="bold")
    ax1.set_xticks(range(len(benchmarks)))
    ax1.set_xticklabels(
        [b.replace(" (", "\n(") for b in benchmarks], fontsize=9
    )
    ax1.grid(axis="y", alpha=0.3, linestyle="--")

    for bar in bars1:
        height = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{int(height):,}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # Plot 2: Mispredictions breakdown
    ax2 = axes[1]
    branch_mispreds = [results[b]["branch_mispreds"] for b in benchmarks]
    correct = [
        results[b]["branch_preds"] - results[b]["branch_mispreds"]
        for b in benchmarks
    ]

    x = np.arange(len(benchmarks))
    width = 0.6

    bars_correct = ax2.bar(
        x,
        correct,
        width,
        label="Correct",
        color="#2ecc71",
        alpha=0.8,
        edgecolor="black",
    )
    bars_mispred = ax2.bar(
        x,
        branch_mispreds,
        width,
        bottom=correct,
        label="Mispredicted",
        color="#e74c3c",
        alpha=0.8,
        edgecolor="black",
    )

    ax2.set_ylabel("Number of Branches", fontsize=11, fontweight="bold")
    ax2.set_title(
        "Prediction Accuracy Breakdown", fontsize=12, fontweight="bold"
    )
    ax2.set_xticks(x)
    ax2.set_xticklabels(
        [b.replace(" (", "\n(") for b in benchmarks], fontsize=9
    )
    ax2.legend(fontsize=10)
    ax2.grid(axis="y", alpha=0.3, linestyle="--")

    plt.tight_layout()

    output_file = output_dir / "branch_analysis.png"
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"Created: {output_file}")

    return output_file


def main():
    results_dir = Path("/home/dlnavarro/ece752proj/gem5/evaluation/results")

    # Load results
    json_file = results_dir / "benchmark_comparison.json"
    with open(json_file) as f:
        results = json.load(f)

    print("Generating visualization plots...")
    print("=" * 60)

    # Create plots
    plot1 = create_comparison_plot(results, results_dir)
    plot2 = create_branch_analysis_plot(results, results_dir)

    print("=" * 60)
    print(f"\nAll plots saved to: {results_dir}")
    print(f"\nPlots created:")
    print(f"  1. {plot1.name} - Overall benchmark comparison")
    print(f"  2. {plot2.name} - Branch prediction analysis")


if __name__ == "__main__":
    main()
