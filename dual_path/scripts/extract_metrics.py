#!/usr/bin/env python3
"""
Extract Key Performance Metrics from gem5 stats.txt
Usage: python3 extract_metrics.py <path_to_stats.txt>
"""

import sys
import re
from pathlib import Path


def extract_stat(content, stat_name):
    """Extract a single statistic value from stats.txt content."""
    pattern = rf'{stat_name}\s+(\d+(?:\.\d+)?)'
    match = re.search(pattern, content)
    if match:
        value = match.group(1)
        # Return as int if no decimal, else float
        return int(value) if '.' not in value else float(value)
    return None


def extract_confidence_histogram(content):
    """Extract confidence level histogram from stats.txt."""
    histogram = {}
    
    # Pattern for dualPathSwitcher confidence distribution
    # Example: system.cpu.dualPathSwitcher.confidenceDistribution::10-14   200861  16.96%
    # Get the first occurrence (before duplication in stats)
    pattern = r'system\.cpu\.dualPathSwitcher\.confidenceDistribution::(\d+)-(\d+)\s+(\d+)\s+[\d.]+%'
    
    # Find the first set of histogram data (stops at first "total" marker)
    lines = content.split('\n')
    in_first_section = False
    first_total_seen = False
    
    for line in lines:
        if 'confidenceDistribution::underflows' in line and not first_total_seen:
            in_first_section = True
            continue
        
        if in_first_section and 'confidenceDistribution::total' in line:
            first_total_seen = True
            break
        
        if in_first_section:
            match = re.search(pattern, line)
            if match:
                range_start = int(match.group(1))
                range_end = int(match.group(2))
                count = int(match.group(3))
                range_key = f"{range_start}-{range_end}"
                if count > 0:  # Only include non-zero bins
                    histogram[range_key] = count
            
            # Check for single value (100)
            pattern_single = r'system\.cpu\.dualPathSwitcher\.confidenceDistribution::(\d+)\s+(\d+)\s+[\d.]+%'
            match_single = re.search(pattern_single, line)
            if match_single and '-' not in line:
                value = match_single.group(1)
                count = int(match_single.group(2))
                if count > 0 and value not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
                    histogram[value] = count
            
            # Check for overflows (>100)
            if 'overflows' in line:
                match_overflow = re.search(r'overflows\s+(\d+)\s+[\d.]+%', line)
                if match_overflow:
                    count = int(match_overflow.group(1))
                    if count > 0:
                        histogram['100+'] = count
    
    return histogram if histogram else None


def extract_metrics(stats_file):
    """Extract all key metrics from a stats.txt file."""
    
    if not Path(stats_file).exists():
        print(f"Error: File not found: {stats_file}")
        sys.exit(1)
    
    with open(stats_file, 'r') as f:
        content = f.read()
    
    metrics = {}
    
    # Core Performance Metrics
    metrics['numCycles'] = extract_stat(content, r'system\.cpu\.numCycles')
    metrics['ipc'] = extract_stat(content, r'system\.cpu\.ipc')
    metrics['simSeconds'] = extract_stat(content, r'simSeconds')
    metrics['simInsts'] = extract_stat(content, r'simInsts')
    
    # Branch Prediction Metrics
    metrics['condPredicted'] = extract_stat(content, r'system\.cpu\.branchPred\.condPredicted')
    metrics['branchMispredicts'] = extract_stat(content, r'system\.cpu\.commit\.branchMispredicts')
    metrics['squashedInsts'] = extract_stat(content, r'system\.cpu\.commit\.squashedInsts')
    
    # Dual-Path Fetching Metrics (updated to match actual implementation)
    metrics['altPathFetchRequests'] = extract_stat(content, r'system\.cpu\.fetch\.alternatePathFetches')
    metrics['altPathFetchCompleted'] = extract_stat(content, r'system\.cpu\.fetch\.alternatePathFetchesCompleted')
    metrics['altPathFetchSquashed'] = extract_stat(content, r'system\.cpu\.fetch\.alternatePathFetchesSquashed')
    metrics['apbInserts'] = extract_stat(content, r'system\.cpu\.apb\.inserts')
    metrics['apbLookups'] = extract_stat(content, r'system\.cpu\.apb\.lookups')
    
    # APB Recovery Metrics  
    metrics['apbRecoveryHits'] = extract_stat(content, r'system\.cpu\.apb\.hits')
    metrics['apbRecoveryMisses'] = extract_stat(content, r'system\.cpu\.apb\.misses')
    metrics['apbEvictions'] = extract_stat(content, r'system\.cpu\.apb\.evictions')
    metrics['branchMispredRecoveryCycles'] = extract_stat(content, r'system\.cpu\.fetch\.branchMispredRecoveryCycles')
    
    # APB occupancy
    metrics['apbOccupancy'] = extract_stat(content, r'system\.cpu\.apb\.occupancy::mean')
    
    # Speculative path metrics
    metrics['speculativePathsSpawned'] = extract_stat(content, r'system\.cpu\.speculativePathsSpawned')
    metrics['speculativePathsSquashed'] = extract_stat(content, r'system\.cpu\.speculativePathsSquashed')
    metrics['speculativePathsCompleted'] = extract_stat(content, r'system\.cpu\.speculativePathsCompleted')
    
    # DPS-TAGE switching (if using DPS-TAGE predictor)
    metrics['dualPathModeActive'] = extract_stat(content, r'system\.cpu\.branchPred\.dualPathMode')
    metrics['switchesToDualPath'] = extract_stat(content, r'system\.cpu\.branchPred\.switchesToDualPath')
    metrics['switchesToSinglePath'] = extract_stat(content, r'system\.cpu\.branchPred\.switchesToSinglePath')
    
    # Cache Metrics
    metrics['icacheMisses'] = extract_stat(content, r'system\.cpu\.icache\.overallMisses::total')
    metrics['icacheAccesses'] = extract_stat(content, r'system\.cpu\.icache\.overallAccesses::total')
    metrics['l2Accesses'] = extract_stat(content, r'system\.l2\.overallAccesses::total')
    metrics['l2Misses'] = extract_stat(content, r'system\.l2\.overallMisses::total')
    
    return metrics


def calculate_derived_metrics(m):
    """Calculate derived metrics from raw statistics."""
    derived = {}
    
    # Branch prediction accuracy
    if m['condPredicted'] and m['branchMispredicts']:
        total = m['condPredicted']
        mispred = m['branchMispredicts']
        derived['branchAccuracy'] = ((total - mispred) / total) * 100
        derived['mispredictionRate'] = (mispred / total) * 100
    
    # Dual-path activation rate
    if m['condPredicted'] and m['altPathFetchRequests']:
        derived['dualPathActivationRate'] = (m['altPathFetchRequests'] / m['condPredicted']) * 100
    
    # APB hit rate (of mispredictions)
    if m['apbRecoveryHits'] is not None and m['apbRecoveryMisses'] is not None:
        total_recovery = m['apbRecoveryHits'] + m['apbRecoveryMisses']
        if total_recovery > 0:
            derived['apbHitRate'] = (m['apbRecoveryHits'] / total_recovery) * 100
            derived['apbCoverage'] = derived['apbHitRate']  # Alias
    
    # Speculative path completion rate
    if m.get('speculativePathsSpawned') and m.get('speculativePathsCompleted'):
        if m['speculativePathsSpawned'] > 0:
            derived['specPathCompletionRate'] = (m['speculativePathsCompleted'] / m['speculativePathsSpawned']) * 100
    
    # APB utilization (inserts vs capacity)
    if m.get('apbOccupancy') is not None:
        derived['apbUtilization'] = m['apbOccupancy']
    
    # Cache hit rates
    if m.get('icacheAccesses') and m.get('icacheMisses'):
        if m['icacheAccesses'] > 0:
            derived['icacheMissRate'] = (m['icacheMisses'] / m['icacheAccesses']) * 100
            derived['icacheHitRate'] = 100 - derived['icacheMissRate']
    
    if m.get('l2Accesses') and m.get('l2Misses'):
        if m['l2Accesses'] > 0:
            derived['l2MissRate'] = (m['l2Misses'] / m['l2Accesses']) * 100
            derived['l2HitRate'] = 100 - derived['l2MissRate']
    
    return derived


def print_metrics(stats_file, metrics, derived):
    """Print formatted metrics report."""
    
    print("=" * 80)
    print(f"GEM5 DUAL-PATH PERFORMANCE METRICS")
    print(f"Stats File: {stats_file}")
    print("=" * 80)
    print()
    
    # Core Performance
    print("CORE PERFORMANCE METRICS")
    print("-" * 80)
    print(f"  Total CPU Cycles:              {metrics['numCycles']:,}" if metrics['numCycles'] else "  Total CPU Cycles:              N/A")
    print(f"  Instructions Per Cycle (IPC):  {metrics['ipc']:.6f}" if metrics['ipc'] else "  Instructions Per Cycle (IPC):  N/A")
    print(f"  Simulation Time:               {metrics['simSeconds']:.6f} seconds" if metrics['simSeconds'] else "  Simulation Time:               N/A")
    print(f"  Total Instructions:            {metrics['simInsts']:,}" if metrics['simInsts'] else "  Total Instructions:            N/A")
    print()
    
    # Branch Prediction
    print("BRANCH PREDICTION METRICS")
    print("-" * 80)
    print(f"  Total Conditional Branches:    {metrics['condPredicted']:,}" if metrics['condPredicted'] else "  Total Conditional Branches:    N/A")
    print(f"  Branch Mispredictions:         {metrics['branchMispredicts']:,}" if metrics['branchMispredicts'] else "  Branch Mispredictions:         N/A")
    print(f"  Branch Accuracy:               {derived.get('branchAccuracy', 0):.2f}%" if 'branchAccuracy' in derived else "  Branch Accuracy:               N/A")
    print(f"  Misprediction Rate:            {derived.get('mispredictionRate', 0):.2f}%" if 'mispredictionRate' in derived else "  Misprediction Rate:            N/A")
    print(f"  Squashed Instructions:         {metrics['squashedInsts']:,}" if metrics['squashedInsts'] else "  Squashed Instructions:         N/A")
    print()
    
    # Dual-Path Activity
    print("DUAL-PATH FETCHING METRICS")
    print("-" * 80)
    print(f"  Alternate Fetch Requests:      {metrics['altPathFetchRequests']:,}" if metrics['altPathFetchRequests'] else "  Alternate Fetch Requests:      N/A")
    print(f"  Dual-Path Activation Rate:     {derived.get('dualPathActivationRate', 0):.2f}%" if 'dualPathActivationRate' in derived else "  Dual-Path Activation Rate:     N/A")
    
    # Speculative paths
    if metrics.get('speculativePathsSpawned'):
        print(f"  Speculative Paths Spawned:     {metrics['speculativePathsSpawned']:,}")
        print(f"  Speculative Paths Completed:   {metrics.get('speculativePathsCompleted', 0):,}")
        print(f"  Speculative Paths Squashed:    {metrics.get('speculativePathsSquashed', 0):,}")
        if 'specPathCompletionRate' in derived:
            print(f"  Completion Rate:               {derived['specPathCompletionRate']:.2f}%")
    
    # APB metrics
    if metrics.get('apbInserts'):
        print(f"  APB Inserts:                   {metrics['apbInserts']:,}")
        print(f"  APB Lookups:                   {metrics.get('apbLookups', 0):,}")
        print(f"  APB Evictions:                 {metrics.get('apbEvictions', 0):,}")
        if 'apbUtilization' in derived:
            print(f"  APB Avg Occupancy:             {derived['apbUtilization']:.1f} entries")
    
    # DPS-TAGE switching
    if metrics.get('switchesToDualPath') is not None:
        print(f"  Switches to Dual-Path:         {metrics['switchesToDualPath']:,}")
        print(f"  Switches to Single-Path:       {metrics.get('switchesToSinglePath', 0):,}")
        if metrics.get('dualPathModeActive') is not None:
            mode = "DUAL-PATH" if metrics['dualPathModeActive'] == 1 else "SINGLE-PATH"
            print(f"  Final Mode:                    {mode}")
    print()
    
    # APB Recovery
    print("APB RECOVERY METRICS")
    print("-" * 80)
    print(f"  APB Recovery Hits:             {metrics['apbRecoveryHits']:,}" if metrics['apbRecoveryHits'] else "  APB Recovery Hits:             N/A")
    print(f"  APB Recovery Misses:           {metrics['apbRecoveryMisses']:,}" if metrics['apbRecoveryMisses'] else "  APB Recovery Misses:           N/A")
    
    if metrics.get('apbRecoveryHits') is not None and metrics.get('apbRecoveryMisses') is not None:
        total = (metrics['apbRecoveryHits'] or 0) + (metrics['apbRecoveryMisses'] or 0)
        if total > 0:
            print(f"  Total Recovery Attempts:       {total:,}")
    
    print(f"  APB Hit Rate (Coverage):       {derived.get('apbCoverage', 0):.2f}%" if 'apbCoverage' in derived else "  APB Hit Rate (Coverage):       N/A")
    print()
    
    # Cache Metrics
    print("CACHE METRICS")
    print("-" * 80)
    print(f"  I-cache Accesses:              {metrics.get('icacheAccesses'):,}" if metrics.get('icacheAccesses') else "  I-cache Accesses:              N/A")
    print(f"  I-cache Misses:                {metrics.get('icacheMisses'):,}" if metrics.get('icacheMisses') else "  I-cache Misses:                N/A")
    print(f"  I-cache Miss Rate:             {derived.get('icacheMissRate', 0):.2f}%" if 'icacheMissRate' in derived else "  I-cache Miss Rate:             N/A")
    print(f"  I-cache Hit Rate:              {derived.get('icacheHitRate', 0):.2f}%" if 'icacheHitRate' in derived else "  I-cache Hit Rate:              N/A")
    print(f"  L2 Accesses:                   {metrics.get('l2Accesses'):,}" if metrics.get('l2Accesses') else "  L2 Accesses:                   N/A")
    print(f"  L2 Misses:                     {metrics.get('l2Misses'):,}" if metrics.get('l2Misses') else "  L2 Misses:                     N/A")
    print(f"  L2 Miss Rate:                  {derived.get('l2MissRate', 0):.2f}%" if 'l2MissRate' in derived else "  L2 Miss Rate:                  N/A")
    print(f"  L2 Hit Rate:                   {derived.get('l2HitRate', 0):.2f}%" if 'l2HitRate' in derived else "  L2 Hit Rate:                   N/A")
    print()
    
    print("=" * 80)


def print_csv_header():
    """Print CSV header row."""
    headers = [
        "stats_file",
        "numCycles",
        "ipc",
        "simSeconds",
        "simInsts",
        "condPredicted",
        "branchMispredicts",
        "branchAccuracy",
        "mispredictionRate",
        "squashedInsts",
        "altPathFetchRequests",
        "altPathFetchCompleted",
        "dualPathActivationRate",
        "fetchCompletionRate",
        "apbRecoveryHits",
        "apbRecoveryMisses",
        "apbCoverage",
        "branchMispredRecoveryCycles",
        "avgRecoveryLatency",
        "altPathFetchMshrFull",
        "mshrDropRate",
        "apbWritePortContentions",
        "apbWritePortStallCycles",
        "avgStallPerContention"
    ]
    print(",".join(headers))


def print_csv_row(stats_file, metrics, derived):
    """Print metrics as CSV row."""
    values = [
        stats_file,
        metrics.get('numCycles', 0),
        metrics.get('ipc', 0),
        metrics.get('simSeconds', 0),
        metrics.get('simInsts', 0),
        metrics.get('condPredicted', 0),
        metrics.get('branchMispredicts', 0),
        derived.get('branchAccuracy', 0),
        derived.get('mispredictionRate', 0),
        metrics.get('squashedInsts', 0),
        metrics.get('altPathFetchRequests', 0),
        metrics.get('altPathFetchCompleted', 0),
        derived.get('dualPathActivationRate', 0),
        derived.get('fetchCompletionRate', 0),
        metrics.get('apbRecoveryHits', 0),
        metrics.get('apbRecoveryMisses', 0),
        derived.get('apbCoverage', 0),
        metrics.get('branchMispredRecoveryCycles', 0),
        derived.get('avgRecoveryLatency', 0),
        metrics.get('altPathFetchMshrFull', 0),
        derived.get('mshrDropRate', 0),
        metrics.get('apbWritePortContentions', 0),
        metrics.get('apbWritePortStallCycles', 0),
        derived.get('avgStallPerContention', 0)
    ]
    print(",".join(str(v) for v in values))


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_metrics.py <stats_file> [--csv]")
        print()
        print("Examples:")
        print("  python3 extract_metrics.py results/my_config/stats.txt")
        print("  python3 extract_metrics.py results/my_config/stats.txt --csv")
        print("  python3 extract_metrics.py results/*/stats.txt --csv > all_metrics.csv")
        sys.exit(1)
    
    csv_mode = '--csv' in sys.argv
    stats_files = [arg for arg in sys.argv[1:] if arg != '--csv']
    
    if csv_mode:
        print_csv_header()
        for stats_file in stats_files:
            metrics = extract_metrics(stats_file)
            derived = calculate_derived_metrics(metrics)
            print_csv_row(stats_file, metrics, derived)
    else:
        for stats_file in stats_files:
            metrics = extract_metrics(stats_file)
            derived = calculate_derived_metrics(metrics)
            print_metrics(stats_file, metrics, derived)
            if len(stats_files) > 1:
                print("\n" * 2)


if __name__ == "__main__":
    main()
