#!/usr/bin/env python3
"""
Statistics Analysis Tool for Dual-Path Execution Evaluation
Analyzes gem5 stats.txt output to extract key metrics
"""

import argparse
import csv
import json
import re
from pathlib import Path


class StatsAnalyzer:
    """Parse and analyze gem5 stats.txt files"""

    def __init__(self, stats_file):
        self.stats_file = Path(stats_file)
        self.stats = {}
        self.periodic_stats = []
        self._parse()

    def _parse(self):
        """Parse stats.txt file"""
        if not self.stats_file.exists():
            raise FileNotFoundError(f"Stats file not found: {self.stats_file}")

        current_dump = {}
        dump_num = 0

        with open(self.stats_file) as f:
            for line in f:
                line = line.strip()

                # Detect stats dump boundaries
                if line.startswith(
                    "---------- Begin Simulation Statistics ----------"
                ):
                    current_dump = {}
                    continue
                elif line.startswith(
                    "---------- End Simulation Statistics ----------"
                ):
                    if current_dump:
                        self.periodic_stats.append(current_dump.copy())
                        dump_num += 1
                    continue

                # Parse stat lines (format: stat_name value # description)
                match = re.match(r"^([\w\.]+)\s+(\S+)", line)
                if match:
                    stat_name = match.group(1)
                    stat_value = match.group(2)

                    # Try to convert to number
                    try:
                        if "." in stat_value:
                            stat_value = float(stat_value)
                        else:
                            stat_value = int(stat_value)
                    except ValueError:
                        pass  # Keep as string

                    current_dump[stat_name] = stat_value

        # Store final stats (or only stats if no periodic dumps)
        if current_dump:
            self.stats = current_dump

    def get_stat(self, stat_name, default=0):
        """Get a specific statistic"""
        return self.stats.get(stat_name, default)

    def get_periodic_stat(self, stat_name):
        """Get time series of a statistic across periodic dumps"""
        return [dump.get(stat_name, 0) for dump in self.periodic_stats]

    def extract_branch_stats(self):
        """Extract branch prediction related statistics"""
        stats = {}

        # Common O3CPU branch stats
        stats["branches"] = self.get_stat("system.cpu.commit.branches", 0)
        stats["branch_mispredicts"] = self.get_stat(
            "system.cpu.commit.branchMispredicts", 0
        )

        # Calculate misprediction rate
        if stats["branches"] > 0:
            stats["mispred_rate"] = (
                stats["branch_mispredicts"] / stats["branches"]
            ) * 100
        else:
            stats["mispred_rate"] = 0

        # Predictor-specific stats (if available)
        stats["bp_lookups"] = self.get_stat("system.cpu.branchPred.lookups", 0)
        stats["bp_cond_predicted"] = self.get_stat(
            "system.cpu.branchPred.condPredicted", 0
        )
        stats["bp_cond_incorrect"] = self.get_stat(
            "system.cpu.branchPred.condIncorrect", 0
        )

        if stats["bp_cond_predicted"] > 0:
            stats["bp_accuracy"] = (
                (stats["bp_cond_predicted"] - stats["bp_cond_incorrect"])
                / stats["bp_cond_predicted"]
            ) * 100
        else:
            stats["bp_accuracy"] = 0

        return stats

    def extract_performance_stats(self):
        """Extract performance metrics"""
        stats = {}

        stats["sim_ticks"] = self.get_stat("simTicks", 0)
        stats["sim_seconds"] = self.get_stat("simSeconds", 0)
        stats["sim_insts"] = self.get_stat(
            "system.cpu.commit.committedInsts", 0
        )
        stats["sim_ops"] = self.get_stat("system.cpu.commit.committedOps", 0)

        # IPC
        stats["host_inst_rate"] = self.get_stat("hostInstRate", 0)
        stats["ipc"] = self.get_stat("system.cpu.ipc", 0)
        stats["cpi"] = self.get_stat("system.cpu.cpi", 0)

        # Pipeline stats
        stats["fetch_rate"] = self.get_stat(
            "system.cpu.fetch.rateDist::mean", 0
        )
        stats["decode_rate"] = self.get_stat(
            "system.cpu.decode.rateDist::mean", 0
        )
        stats["issue_rate"] = self.get_stat("system.cpu.iq.rateDist::mean", 0)
        stats["commit_rate"] = self.get_stat(
            "system.cpu.commit.rateDist::mean", 0
        )

        # ROB stats
        stats["rob_full_events"] = self.get_stat("system.cpu.rob.rob_full", 0)

        return stats

    def extract_dual_path_stats(self):
        """Extract dual-path specific statistics (if available)"""
        stats = {}

        # APB stats
        stats["apb_hits"] = self.get_stat("system.cpu.apb.hits", 0)
        stats["apb_misses"] = self.get_stat("system.cpu.apb.misses", 0)
        stats["apb_inserts"] = self.get_stat("system.cpu.apb.inserts", 0)
        stats["apb_evictions"] = self.get_stat("system.cpu.apb.evictions", 0)

        if (stats["apb_hits"] + stats["apb_misses"]) > 0:
            stats["apb_hit_rate"] = (
                stats["apb_hits"] / (stats["apb_hits"] + stats["apb_misses"])
            ) * 100
        else:
            stats["apb_hit_rate"] = 0

        # Switcher stats
        stats["dual_path_cycles"] = self.get_stat(
            "system.cpu.dualPathSwitcher.dualPathCycles", 0
        )
        stats["single_path_cycles"] = self.get_stat(
            "system.cpu.dualPathSwitcher.singlePathCycles", 0
        )
        stats["mode_switches"] = self.get_stat(
            "system.cpu.dualPathSwitcher.modeSwitches", 0
        )

        total_cycles = stats["dual_path_cycles"] + stats["single_path_cycles"]
        if total_cycles > 0:
            stats["dual_path_percent"] = (
                stats["dual_path_cycles"] / total_cycles
            ) * 100
        else:
            stats["dual_path_percent"] = 0

        return stats

    def extract_cache_stats(self):
        """Extract cache statistics"""
        stats = {}

        # L1 I-cache
        stats["l1i_accesses"] = self.get_stat(
            "system.cpu.icache.overall_accesses::total", 0
        )
        stats["l1i_misses"] = self.get_stat(
            "system.cpu.icache.overall_misses::total", 0
        )
        stats["l1i_miss_rate"] = self.get_stat(
            "system.cpu.icache.overall_miss_rate::total", 0
        )

        # L1 D-cache
        stats["l1d_accesses"] = self.get_stat(
            "system.cpu.dcache.overall_accesses::total", 0
        )
        stats["l1d_misses"] = self.get_stat(
            "system.cpu.dcache.overall_misses::total", 0
        )
        stats["l1d_miss_rate"] = self.get_stat(
            "system.cpu.dcache.overall_miss_rate::total", 0
        )

        # L2 cache
        stats["l2_accesses"] = self.get_stat(
            "system.l2cache.overall_accesses::total", 0
        )
        stats["l2_misses"] = self.get_stat(
            "system.l2cache.overall_misses::total", 0
        )
        stats["l2_miss_rate"] = self.get_stat(
            "system.l2cache.overall_miss_rate::total", 0
        )

        return stats

    def get_temporal_mispred_rate(self):
        """Calculate misprediction rate over time from periodic dumps"""
        if not self.periodic_stats:
            return []

        rates = []
        for dump in self.periodic_stats:
            branches = dump.get("system.cpu.commit.branches", 0)
            mispredicts = dump.get("system.cpu.commit.branchMispredicts", 0)

            if branches > 0:
                rate = (mispredicts / branches) * 100
            else:
                rate = 0

            rates.append(rate)

        return rates

    def generate_report(self):
        """Generate comprehensive analysis report"""
        report = {
            "branch_stats": self.extract_branch_stats(),
            "performance_stats": self.extract_performance_stats(),
            "dual_path_stats": self.extract_dual_path_stats(),
            "cache_stats": self.extract_cache_stats(),
        }

        # Add temporal data if available
        if self.periodic_stats:
            report["temporal_mispred_rates"] = self.get_temporal_mispred_rate()

        return report


def compare_configurations(baseline_stats, dualpath_stats):
    """Compare baseline vs dual-path configuration"""
    comparison = {}

    # Branch prediction improvement
    baseline_mispred = baseline_stats["branch_stats"]["branch_mispredicts"]
    dualpath_mispred = dualpath_stats["branch_stats"]["branch_mispredicts"]

    if baseline_mispred > 0:
        mispred_reduction = (
            (baseline_mispred - dualpath_mispred) / baseline_mispred
        ) * 100
        comparison["mispred_reduction_percent"] = mispred_reduction
    else:
        comparison["mispred_reduction_percent"] = 0

    # Performance comparison
    baseline_ipc = baseline_stats["performance_stats"]["ipc"]
    dualpath_ipc = dualpath_stats["performance_stats"]["ipc"]

    if baseline_ipc > 0:
        ipc_improvement = ((dualpath_ipc - baseline_ipc) / baseline_ipc) * 100
        comparison["ipc_improvement_percent"] = ipc_improvement
    else:
        comparison["ipc_improvement_percent"] = 0

    # Execution time comparison
    baseline_ticks = baseline_stats["performance_stats"]["sim_ticks"]
    dualpath_ticks = dualpath_stats["performance_stats"]["sim_ticks"]

    if baseline_ticks > 0:
        speedup = baseline_ticks / dualpath_ticks if dualpath_ticks > 0 else 0
        comparison["speedup"] = speedup
        comparison["time_reduction_percent"] = (
            (baseline_ticks - dualpath_ticks) / baseline_ticks
        ) * 100
    else:
        comparison["speedup"] = 0
        comparison["time_reduction_percent"] = 0

    return comparison


def print_report(report, name="Configuration"):
    """Print formatted report"""
    print(f"\n{'='*70}")
    print(f"{name} - Analysis Report")
    print(f"{'='*70}")

    print("\nBRANCH PREDICTION STATISTICS:")
    print("-" * 70)
    branch = report["branch_stats"]
    print(f"  Total Branches:        {branch['branches']:,}")
    print(f"  Branch Mispredicts:    {branch['branch_mispredicts']:,}")
    print(f"  Misprediction Rate:    {branch['mispred_rate']:.2f}%")
    print(f"  Predictor Accuracy:    {branch['bp_accuracy']:.2f}%")

    print("\nPERFORMANCE STATISTICS:")
    print("-" * 70)
    perf = report["performance_stats"]
    print(f"  Simulation Ticks:      {perf['sim_ticks']:,}")
    print(f"  Committed Insts:       {perf['sim_insts']:,}")
    print(f"  IPC:                   {perf['ipc']:.3f}")
    print(f"  CPI:                   {perf['cpi']:.3f}")

    print("\nDUAL-PATH STATISTICS:")
    print("-" * 70)
    dp = report["dual_path_stats"]
    if dp["apb_hits"] > 0 or dp["dual_path_cycles"] > 0:
        print(f"  APB Hits:              {dp['apb_hits']:,}")
        print(f"  APB Misses:            {dp['apb_misses']:,}")
        print(f"  APB Hit Rate:          {dp['apb_hit_rate']:.2f}%")
        print(f"  Dual-Path Cycles:      {dp['dual_path_cycles']:,}")
        print(f"  Single-Path Cycles:    {dp['single_path_cycles']:,}")
        print(f"  Dual-Path Usage:       {dp['dual_path_percent']:.2f}%")
        print(f"  Mode Switches:         {dp['mode_switches']:,}")
    else:
        print("  N/A (baseline configuration)")

    print("\nCACHE STATISTICS:")
    print("-" * 70)
    cache = report["cache_stats"]
    print(f"  L1I Miss Rate:         {cache['l1i_miss_rate']:.4f}")
    print(f"  L1D Miss Rate:         {cache['l1d_miss_rate']:.4f}")
    print(f"  L2 Miss Rate:          {cache['l2_miss_rate']:.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze gem5 stats for dual-path evaluation"
    )
    parser.add_argument("stats_file", type=str, help="Path to stats.txt file")
    parser.add_argument(
        "--baseline",
        type=str,
        help="Path to baseline stats.txt for comparison",
    )
    parser.add_argument(
        "--output", type=str, help="Output file for JSON report"
    )
    parser.add_argument(
        "--csv", type=str, help="Output CSV file for temporal data"
    )
    args = parser.parse_args()

    # Analyze main stats
    analyzer = StatsAnalyzer(args.stats_file)
    report = analyzer.generate_report()
    print_report(report, "Main Configuration")

    # Compare with baseline if provided
    if args.baseline:
        baseline_analyzer = StatsAnalyzer(args.baseline)
        baseline_report = baseline_analyzer.generate_report()
        print_report(baseline_report, "Baseline Configuration")

        comparison = compare_configurations(baseline_report, report)

        print(f"\n{'='*70}")
        print("COMPARISON: Dual-Path vs Baseline")
        print(f"{'='*70}")
        print(
            f"  Misprediction Reduction:  {comparison['mispred_reduction_percent']:+.2f}%"
        )
        print(
            f"  IPC Improvement:          {comparison['ipc_improvement_percent']:+.2f}%"
        )
        print(f"  Speedup:                  {comparison['speedup']:.3f}x")
        print(
            f"  Time Reduction:           {comparison['time_reduction_percent']:+.2f}%"
        )

        report["comparison"] = comparison

    # Save JSON report
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nJSON report saved to: {args.output}")

    # Save temporal CSV
    if args.csv and "temporal_mispred_rates" in report:
        with open(args.csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Dump", "Misprediction_Rate"])
            for i, rate in enumerate(report["temporal_mispred_rates"], 1):
                writer.writerow([i, rate])
        print(f"Temporal data saved to: {args.csv}")


if __name__ == "__main__":
    main()
