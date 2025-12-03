#!/usr/bin/env python3
"""
Performance Analysis Script for Dual-Path Branch Predictor Evaluation

This script analyzes and compares performance metrics across different
branch predictor configurations including baseline and various dual-path modes.
"""

import os
import re
from pathlib import Path
from collections import defaultdict
import statistics

class StatsParser:
    """Parse gem5 stats.txt files and extract key performance metrics."""
    
    def __init__(self, stats_file):
        self.stats_file = stats_file
        self.metrics = {}
        self._parse()
    
    def _parse(self):
        """Parse the stats file and extract all relevant metrics from the SECOND statistics section."""
        if not os.path.exists(self.stats_file):
            return
        
        with open(self.stats_file, 'r') as f:
            full_content = f.read()
        
        # Split by "Begin Simulation Statistics" markers
        sections = full_content.split('---------- Begin Simulation Statistics ----------')
        
        # We want the SECOND section (index 2, since index 0 is before first marker)
        # The second section is between the 2nd Begin and 2nd End markers
        if len(sections) < 3:
            print(f"Warning: {self.stats_file} doesn't have a second statistics section")
            # Fall back to using the entire content
            content = full_content
        else:
            # Get the second section (between 2nd Begin and 2nd End)
            content = sections[2].split('---------- End Simulation Statistics')[0]
        
        # Core performance metrics
        self._extract_value(content, 'simSeconds', r'simSeconds\s+([\d.]+)')
        self._extract_value(content, 'simTicks', r'simTicks\s+(\d+)')
        self._extract_value(content, 'numCycles', r'system\.cpu\.numCycles\s+(\d+)')
        self._extract_value(content, 'simInsts', r'simInsts\s+(\d+)')
        self._extract_value(content, 'IPC', r'system\.cpu\.ipc\s+([\d.]+)')
        self._extract_value(content, 'CPI', r'system\.cpu\.cpi\s+([\d.]+)')
        
        # Branch prediction metrics
        self._extract_value(content, 'branchPred.lookups', r'system\.cpu\.branchPred\.lookups\s+(\d+)')
        self._extract_value(content, 'branchPred.condPredicted', r'system\.cpu\.branchPred\.condPredicted\s+(\d+)')
        self._extract_value(content, 'branchPred.condIncorrect', r'system\.cpu\.branchPred\.condIncorrect\s+(\d+)')
        
        # Squash/recovery metrics
        self._extract_value(content, 'squashedInsts', r'system\.cpu\.numSquashedInsts\s+(\d+)')
        self._extract_value(content, 'squashCycles', r'system\.cpu\.squashCycles\s+(\d+)')
        
        # Dual-path specific metrics (only present in dual-path configs)
        self._extract_value(content, 'switchesToDualPath', r'system\.cpu\.dualPathSwitcher\.switchesToDualPath\s+(\d+)')
        self._extract_value(content, 'switchesToSinglePath', r'system\.cpu\.dualPathSwitcher\.switchesToSinglePath\s+(\d+)')
        self._extract_value(content, 'branchesInDualPath', r'system\.cpu\.dualPathSwitcher\.branchesInDualPath\s+(\d+)')
        self._extract_value(content, 'branchesInSinglePath', r'system\.cpu\.dualPathSwitcher\.branchesInSinglePath\s+(\d+)')
        self._extract_value(content, 'totalBranches', r'system\.cpu\.dualPathSwitcher\.totalBranches\s+(\d+)')
        self._extract_value(content, 'currentAccuracy', r'system\.cpu\.dualPathSwitcher\.currentAccuracy\s+([\d.]+)')
        self._extract_value(content, 'avgBranchesBetweenSwitches', r'system\.cpu\.dualPathSwitcher\.avgBranchesBetweenSwitches\s+([\d.]+)')
        
        # Calculate derived metrics
        self._calculate_derived_metrics()
    
    def _extract_value(self, content, key, pattern):
        """Extract a single value using regex pattern."""
        match = re.search(pattern, content)
        if match:
            try:
                # Try to convert to int first, then float
                value = match.group(1)
                if '.' in value:
                    self.metrics[key] = float(value)
                else:
                    self.metrics[key] = int(value)
            except (ValueError, IndexError):
                self.metrics[key] = None
        else:
            self.metrics[key] = None
    
    def _calculate_derived_metrics(self):
        """Calculate derived performance metrics."""
        # Branch misprediction rate
        if self.metrics.get('branchPred.condPredicted') and self.metrics.get('branchPred.condIncorrect'):
            total = self.metrics['branchPred.condPredicted']
            incorrect = self.metrics['branchPred.condIncorrect']
            self.metrics['mispredictionRate'] = (incorrect / total * 100) if total > 0 else 0
            self.metrics['branchAccuracy'] = ((total - incorrect) / total * 100) if total > 0 else 0
        
        # Average recovery latency (cycles per misprediction)
        if self.metrics.get('squashCycles') and self.metrics.get('branchPred.condIncorrect'):
            squash = self.metrics['squashCycles']
            mispredict = self.metrics['branchPred.condIncorrect']
            self.metrics['avgRecoveryLatency'] = squash / mispredict if mispredict > 0 else 0
        
        # Dual-path mode percentage
        if self.metrics.get('branchesInDualPath') and self.metrics.get('totalBranches'):
            dual = self.metrics['branchesInDualPath']
            total = self.metrics['totalBranches']
            self.metrics['dualPathPercentage'] = (dual / total * 100) if total > 0 else 0
        
        # Switch frequency
        if self.metrics.get('switchesToDualPath') and self.metrics.get('numCycles'):
            switches = self.metrics['switchesToDualPath']
            cycles = self.metrics['numCycles']
            self.metrics['switchFrequency'] = switches / (cycles / 1000) if cycles > 0 else 0  # per 1K cycles
    
    def get(self, key, default=None):
        """Get a metric value."""
        return self.metrics.get(key, default)


def analyze_results(results_dir):
    """Analyze all result directories and generate comparison report."""
    
    results_path = Path(results_dir)
    
    # Find all stats.txt files
    all_stats = {}
    
    for config_dir in results_path.iterdir():
        if not config_dir.is_dir():
            continue
        
        config_name = config_dir.name
        all_stats[config_name] = {}
        
        # Find all benchmark subdirectories
        for benchmark_dir in config_dir.iterdir():
            if not benchmark_dir.is_dir():
                continue
            
            stats_file = benchmark_dir / 'stats.txt'
            if stats_file.exists():
                benchmark_name = benchmark_dir.name
                parser = StatsParser(str(stats_file))
                all_stats[config_name][benchmark_name] = parser
    
    return all_stats


def print_comparison_table(all_stats, metric_name, metric_key, format_str='{:.4f}', 
                          higher_is_better=True, show_delta=True):
    """Print a comparison table for a specific metric."""
    
    # Get all configurations and benchmarks
    configs = sorted(all_stats.keys())
    benchmarks = set()
    for config_stats in all_stats.values():
        benchmarks.update(config_stats.keys())
    benchmarks = sorted(benchmarks)
    
    print(f"\n{'='*100}")
    print(f"{metric_name}")
    print(f"{'='*100}")
    
    # Header
    header = f"{'Benchmark':<25}"
    for config in configs:
        header += f"{config[:20]:>22}"
    print(header)
    print('-' * 100)
    
    # Baseline reference (if exists)
    baseline_config = 'baseline'
    
    # Data rows
    for benchmark in benchmarks:
        row = f"{benchmark:<25}"
        baseline_value = None
        
        # Get baseline value for delta calculation
        if baseline_config in all_stats and benchmark in all_stats[baseline_config]:
            baseline_value = all_stats[baseline_config][benchmark].get(metric_key)
        
        for config in configs:
            if config in all_stats and benchmark in all_stats[config]:
                value = all_stats[config][benchmark].get(metric_key)
                if value is not None:
                    value_str = format_str.format(value)
                    
                    # Show delta from baseline
                    if show_delta and baseline_value is not None and config != baseline_config and value != baseline_value:
                        if higher_is_better:
                            delta = ((value - baseline_value) / baseline_value * 100)
                        else:
                            delta = ((baseline_value - value) / baseline_value * 100)
                        
                        if abs(delta) >= 0.01:  # Only show if significant
                            delta_str = f" ({delta:+.1f}%)"
                            value_str = value_str[:12] + delta_str  # Truncate if needed
                    
                    row += f"{value_str:>22}"
                else:
                    row += f"{'N/A':>22}"
            else:
                row += f"{'-':>22}"
        
        print(row)


def print_summary_statistics(all_stats):
    """Print summary statistics across all benchmarks for each configuration."""
    
    configs = sorted(all_stats.keys())
    
    print(f"\n{'='*100}")
    print("SUMMARY STATISTICS (Geometric Mean across benchmarks)")
    print(f"{'='*100}")
    
    metrics_to_summarize = [
        ('IPC', 'IPC', True),
        ('CPI', 'CPI', False),
        ('Branch Accuracy (%)', 'branchAccuracy', True),
        ('Misprediction Rate (%)', 'mispredictionRate', False),
        ('Avg Recovery Latency', 'avgRecoveryLatency', False),
    ]
    
    header = f"{'Metric':<30}"
    for config in configs:
        header += f"{config[:18]:>20}"
    print(header)
    print('-' * 100)
    
    for metric_name, metric_key, higher_is_better in metrics_to_summarize:
        row = f"{metric_name:<30}"
        
        for config in configs:
            values = []
            for benchmark, parser in all_stats[config].items():
                value = parser.get(metric_key)
                if value is not None and value > 0:
                    values.append(value)
            
            if values:
                # Use geometric mean for ratios/rates
                if len(values) > 1:
                    geo_mean = statistics.geometric_mean(values)
                else:
                    geo_mean = values[0]
                row += f"{geo_mean:>20.4f}"
            else:
                row += f"{'N/A':>20}"
        
        print(row)


def print_dualpath_specific_metrics(all_stats):
    """Print dual-path specific metrics."""
    
    print(f"\n{'='*100}")
    print("DUAL-PATH SPECIFIC METRICS")
    print(f"{'='*100}")
    
    configs = sorted([c for c in all_stats.keys() if c != 'baseline'])
    benchmarks = set()
    for config in configs:
        if config in all_stats:
            benchmarks.update(all_stats[config].keys())
    benchmarks = sorted(benchmarks)
    
    # Dual-path mode percentage
    print(f"\n{'Benchmark':<25}", end='')
    for config in configs:
        print(f"{config[:20]:>22}", end='')
    print()
    print('-' * 100)
    
    print("\n=== Percentage of Branches in Dual-Path Mode ===")
    for benchmark in benchmarks:
        row = f"{benchmark:<25}"
        for config in configs:
            if config in all_stats and benchmark in all_stats[config]:
                value = all_stats[config][benchmark].get('dualPathPercentage')
                if value is not None:
                    row += f"{value:>20.2f}%"
                else:
                    row += f"{'N/A':>22}"
            else:
                row += f"{'-':>22}"
        print(row)
    
    # Mode switches
    print("\n=== Switches to Dual-Path Mode ===")
    for benchmark in benchmarks:
        row = f"{benchmark:<25}"
        for config in configs:
            if config in all_stats and benchmark in all_stats[config]:
                value = all_stats[config][benchmark].get('switchesToDualPath')
                if value is not None:
                    row += f"{value:>22}"
                else:
                    row += f"{'N/A':>22}"
            else:
                row += f"{'-':>22}"
        print(row)
    
    # Switch frequency
    print("\n=== Switch Frequency (per 1K cycles) ===")
    for benchmark in benchmarks:
        row = f"{benchmark:<25}"
        for config in configs:
            if config in all_stats and benchmark in all_stats[config]:
                value = all_stats[config][benchmark].get('switchFrequency')
                if value is not None:
                    row += f"{value:>20.2f}"
                else:
                    row += f"{'N/A':>22}"
            else:
                row += f"{'-':>22}"
        print(row)


def main():
    """Main entry point."""
    results_dir = '/home/dlnavarro/ece752proj/gem5/results'
    
    print("="*100)
    print("GEM5 DUAL-PATH BRANCH PREDICTOR PERFORMANCE ANALYSIS")
    print("="*100)
    print(f"\nAnalyzing results from: {results_dir}\n")
    
    # Parse all stats
    all_stats = analyze_results(results_dir)
    
    # Print number of configurations found
    print(f"Found {len(all_stats)} configurations:")
    for config in sorted(all_stats.keys()):
        num_benchmarks = len(all_stats[config])
        print(f"  - {config}: {num_benchmarks} benchmarks")
    
    # Core performance metrics
    print_comparison_table(all_stats, 
                          "IPC (Instructions Per Cycle) - Higher is Better",
                          'IPC', '{:.6f}', higher_is_better=True)
    
    print_comparison_table(all_stats,
                          "Simulation Time (seconds) - Lower is Better", 
                          'simSeconds', '{:.6f}', higher_is_better=False)
    
    print_comparison_table(all_stats,
                          "Number of CPU Cycles - Lower is Better",
                          'numCycles', '{:,.0f}', higher_is_better=False)
    
    # Branch prediction metrics
    print_comparison_table(all_stats,
                          "Branch Prediction Accuracy (%) - Higher is Better",
                          'branchAccuracy', '{:.2f}', higher_is_better=True, show_delta=False)
    
    print_comparison_table(all_stats,
                          "Branch Misprediction Rate (%) - Lower is Better",
                          'mispredictionRate', '{:.2f}', higher_is_better=False, show_delta=False)
    
    print_comparison_table(all_stats,
                          "Conditional Branches Mispredicted - Lower is Better",
                          'branchPred.condIncorrect', '{:,.0f}', higher_is_better=False)
    
    # Recovery metrics
    print_comparison_table(all_stats,
                          "Average Recovery Latency (cycles/misprediction) - Lower is Better",
                          'avgRecoveryLatency', '{:.2f}', higher_is_better=False)
    
    print_comparison_table(all_stats,
                          "Total Squashed Instructions - Lower is Better",
                          'squashedInsts', '{:,.0f}', higher_is_better=False)
    
    # Dual-path specific metrics
    print_dualpath_specific_metrics(all_stats)
    
    # Summary statistics
    print_summary_statistics(all_stats)
    
    print("\n" + "="*100)
    print("Analysis Complete")
    print("="*100)


if __name__ == '__main__':
    main()
