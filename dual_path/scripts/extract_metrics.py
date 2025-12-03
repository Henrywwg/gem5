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
    
    # Dual-Path Fetching Metrics
    metrics['altPathFetchRequests'] = extract_stat(content, r'system\.cpu\.fetch\.altPathFetchRequests')
    metrics['altPathFetchCompleted'] = extract_stat(content, r'system\.cpu\.fetch\.altPathFetchCompleted')
    metrics['altPathFetchSquashed'] = extract_stat(content, r'system\.cpu\.fetch\.altPathFetchSquashed')
    
    # APB Recovery Metrics
    metrics['apbRecoveryHits'] = extract_stat(content, r'system\.cpu\.fetch\.apbRecoveryHits')
    metrics['apbRecoveryMisses'] = extract_stat(content, r'system\.cpu\.fetch\.apbRecoveryMisses')
    metrics['branchMispredRecoveryCycles'] = extract_stat(content, r'system\.cpu\.fetch\.branchMispredRecoveryCycles')
    
    # APB Recovery Latency Distributions (mean values)
    metrics['apbHitRecoveryLatencyMean'] = extract_stat(content, r'system\.cpu\.fetch\.apbHitRecoveryLatency::mean')
    metrics['apbMissRecoveryLatencyMean'] = extract_stat(content, r'system\.cpu\.fetch\.apbMissRecoveryLatency::mean')
    
    # Realistic Hardware Constraint Metrics
    metrics['altPathFetchMshrFull'] = extract_stat(content, r'system\.cpu\.fetch\.altPathFetchMshrFull')
    metrics['apbWritePortContentions'] = extract_stat(content, r'system\.cpu\.fetch\.apbWritePortContentions')
    metrics['apbWritePortStallCycles'] = extract_stat(content, r'system\.cpu\.fetch\.apbWritePortStallCycles')
    
    # Cache Metrics
    metrics['icacheMisses'] = extract_stat(content, r'system\.cpu\.icache\.overallMisses::total')
    metrics['icacheAccesses'] = extract_stat(content, r'system\.cpu\.icache\.overallAccesses::total')
    metrics['l2Accesses'] = extract_stat(content, r'system\.l2\.overallAccesses::total')
    metrics['l2Misses'] = extract_stat(content, r'system\.l2\.overallMisses::total')
    
    # Switching metrics (may not exist in all configs)
    # Try both locations: fetch and dualPathSwitcher
    metrics['switchesToDualPath'] = extract_stat(content, r'system\.cpu\.fetch\.switchesToDualPath')
    if not metrics['switchesToDualPath']:
        metrics['switchesToDualPath'] = extract_stat(content, r'system\.cpu\.dualPathSwitcher\.switchesToDualPath')
    
    metrics['switchesToSinglePath'] = extract_stat(content, r'system\.cpu\.dualPathSwitcher\.switchesToSinglePath')
    
    # Confidence histogram
    metrics['confidenceHistogram'] = extract_confidence_histogram(content)
    
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
    
    # Fetch completion rate
    if m['altPathFetchRequests'] and m['altPathFetchCompleted']:
        if m['altPathFetchRequests'] > 0:
            derived['fetchCompletionRate'] = (m['altPathFetchCompleted'] / m['altPathFetchRequests']) * 100
    
    # APB hit rate (of mispredictions)
    if m['apbRecoveryHits'] and m['apbRecoveryMisses']:
        total_recovery = m['apbRecoveryHits'] + m['apbRecoveryMisses']
        if total_recovery > 0:
            derived['apbHitRate'] = (m['apbRecoveryHits'] / total_recovery) * 100
            derived['apbCoverage'] = derived['apbHitRate']  # Alias
    
    # APB hit rate (of alternate fetches)
    if m['apbRecoveryHits'] and m['altPathFetchRequests']:
        if m['altPathFetchRequests'] > 0:
            derived['apbHitsPerFetch'] = (m['apbRecoveryHits'] / m['altPathFetchRequests']) * 100
    
    # APB recovery latencies (use distribution means if available, else calculate weighted average)
    if m.get('apbHitRecoveryLatencyMean') is not None:
        derived['apbHitRecoveryLatency'] = m['apbHitRecoveryLatencyMean']
    
    if m.get('apbMissRecoveryLatencyMean') is not None:
        derived['apbMissRecoveryLatency'] = m['apbMissRecoveryLatencyMean']
    
    # Calculate speedup if both latencies available
    if derived.get('apbHitRecoveryLatency') and derived.get('apbMissRecoveryLatency'):
        derived['apbSpeedup'] = derived['apbMissRecoveryLatency'] / derived['apbHitRecoveryLatency']
    
    # Write port contention stats
    if m['apbWritePortContentions'] and m['apbWritePortStallCycles']:
        if m['apbWritePortContentions'] > 0:
            derived['avgStallPerContention'] = m['apbWritePortStallCycles'] / m['apbWritePortContentions']
    
    # Cache hit rates
    if m.get('icacheAccesses') and m.get('icacheMisses'):
        if m['icacheAccesses'] > 0:
            derived['icacheMissRate'] = (m['icacheMisses'] / m['icacheAccesses']) * 100
            derived['icacheHitRate'] = 100 - derived['icacheMissRate']
    
    if m.get('l2Accesses') and m.get('l2Misses'):
        if m['l2Accesses'] > 0:
            derived['l2MissRate'] = (m['l2Misses'] / m['l2Accesses']) * 100
            derived['l2HitRate'] = 100 - derived['l2MissRate']
    
    # MSHR drop rate
    if m['altPathFetchMshrFull'] and m['altPathFetchRequests']:
        if m['altPathFetchRequests'] > 0:
            derived['mshrDropRate'] = (m['altPathFetchMshrFull'] / m['altPathFetchRequests']) * 100
    
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
    print(f"  Alternate Fetch Completed:     {metrics['altPathFetchCompleted']:,}" if metrics['altPathFetchCompleted'] else "  Alternate Fetch Completed:     N/A")
    print(f"  Alternate Fetch Squashed:      {metrics['altPathFetchSquashed']:,}" if metrics['altPathFetchSquashed'] else "  Alternate Fetch Squashed:      N/A")
    print(f"  Dual-Path Activation Rate:     {derived.get('dualPathActivationRate', 0):.2f}%" if 'dualPathActivationRate' in derived else "  Dual-Path Activation Rate:     N/A")
    print(f"  Fetch Completion Rate:         {derived.get('fetchCompletionRate', 0):.2f}%" if 'fetchCompletionRate' in derived else "  Fetch Completion Rate:         N/A")
    print(f"  Switches to Dual-Path:         {metrics['switchesToDualPath']:,}" if metrics['switchesToDualPath'] else "  Switches to Dual-Path:         N/A")
    print()
    
    # APB Recovery
    print("APB RECOVERY METRICS")
    print("-" * 80)
    print(f"  APB Recovery Hits:             {metrics['apbRecoveryHits']:,}" if metrics['apbRecoveryHits'] else "  APB Recovery Hits:             N/A")
    print(f"  APB Recovery Misses:           {metrics['apbRecoveryMisses']:,}" if metrics['apbRecoveryMisses'] else "  APB Recovery Misses:           N/A")
    
    if metrics['apbRecoveryHits'] and metrics['apbRecoveryMisses']:
        total = metrics['apbRecoveryHits'] + metrics['apbRecoveryMisses']
        print(f"  Total Recovery Attempts:       {total:,}")
    
    print(f"  APB Hit Rate (Coverage):       {derived.get('apbCoverage', 0):.2f}%" if 'apbCoverage' in derived else "  APB Hit Rate (Coverage):       N/A")
    print(f"  Total Recovery Cycles:         {metrics['branchMispredRecoveryCycles']:,}" if metrics['branchMispredRecoveryCycles'] else "  Total Recovery Cycles:         N/A")
    print(f"  APB HIT Recovery Latency:      {derived.get('apbHitRecoveryLatency', 0):.1f} cycles" if 'apbHitRecoveryLatency' in derived else "  APB HIT Recovery Latency:      N/A")
    print(f"  APB MISS Recovery Latency:     {derived.get('apbMissRecoveryLatency', 0):.1f} cycles" if 'apbMissRecoveryLatency' in derived else "  APB MISS Recovery Latency:     N/A")
    if 'apbSpeedup' in derived:
        print(f"  APB Speedup:                   {derived['apbSpeedup']:.2f}x faster with APB hit")
    print()
    
    # APB Utilization Analysis
    if metrics['altPathFetchRequests'] and metrics['apbRecoveryHits']:
        print("APB ALTERNATE PATH UTILIZATION")
        print("-" * 80)
        fetched = metrics['altPathFetchRequests']
        used = metrics['apbRecoveryHits']
        wasted = fetched - used
        utilization = (used / fetched * 100) if fetched > 0 else 0
        
        print(f"  Alternate Paths Fetched:       {fetched:,}")
        print(f"  Alternate Paths USED:          {used:,}")
        print(f"  Alternate Paths Wasted:        {wasted:,}")
        print(f"  Utilization Rate:              {utilization:.2f}%")
        print()
        
        # Breakdown: analyze from both perspectives
        if metrics['branchMispredicts'] and metrics['apbRecoveryMisses']:
            total_mispred = metrics['branchMispredicts']
            apb_misses = metrics['apbRecoveryMisses']
            total_recoveries = used + apb_misses
            
            print()
            print("  RECOVERY PERSPECTIVE (of all mispredictions):")
            print(f"    Total Mispredictions:            {total_mispred:,}")
            print(f"    ✅ APB Hit (fast recovery):      {used:,} ({(used/total_mispred)*100:.1f}%)")
            print(f"    ❌ APB Miss (slow recovery):     {apb_misses:,} ({(apb_misses/total_mispred)*100:.1f}%)")
            
            if total_recoveries != total_mispred:
                unaccounted = total_mispred - total_recoveries
                print(f"    ⚠️  Not attempted via APB:       {unaccounted:,} ({(unaccounted/total_mispred)*100:.1f}%)")
            print()
            
            # Reuse factor
            if utilization > 100:
                reuse_factor = used / fetched
                print(f"  REUSE FACTOR: {reuse_factor:.2f}x")
                print(f"    → Each fetched alternate was reused {reuse_factor:.2f} times on average")
                print(f"    → Indicates spatial locality (same paths used for multiple mispredictions)")
            else:
                # Normal case: fetches >= uses
                correct_pred_waste = fetched - total_mispred if fetched > total_mispred else 0
                actual_waste = fetched - used
                
                print("  FETCH PERSPECTIVE (waste analysis):")
                print(f"    ✅ Used (APB hit):               {used:,} ({utilization:.1f}%)")
                print(f"    ❌ Wasted (correct prediction):  ~{correct_pred_waste:,} ({(correct_pred_waste/fetched)*100:.1f}%)")
                print(f"    ❌ Wasted (other):               ~{actual_waste - correct_pred_waste:,} ({((actual_waste - correct_pred_waste)/fetched)*100:.1f}%)")
                print()
                print("    • Correct prediction: Low-confidence branch predicted RIGHT")
                print("    • Other waste: APB evicted or not dual-path misprediction")
            print()
        else:
            print(f"  → {utilization:.1f}% of fetched alternate paths were actually needed")
            if utilization <= 100:
                print(f"  → {(100-utilization):.1f}% were fetched but never used")
            print()
    
    # Realistic Hardware Constraints
    print("REALISTIC HARDWARE CONSTRAINT METRICS")
    print("-" * 80)
    print(f"  MSHR Limit Drops:              {metrics['altPathFetchMshrFull']:,}" if metrics['altPathFetchMshrFull'] is not None else "  MSHR Limit Drops:              N/A")
    print(f"  MSHR Drop Rate:                {derived.get('mshrDropRate', 0):.2f}%" if 'mshrDropRate' in derived else "  MSHR Drop Rate:                N/A")
    print(f"  Write Port Contentions:        {metrics['apbWritePortContentions']:,}" if metrics['apbWritePortContentions'] is not None else "  Write Port Contentions:        N/A")
    print(f"  Write Port Stall Cycles:       {metrics['apbWritePortStallCycles']:,}" if metrics['apbWritePortStallCycles'] is not None else "  Write Port Stall Cycles:       N/A")
    print(f"  Avg Stall per Contention:      {derived.get('avgStallPerContention', 0):.2f} cycles" if 'avgStallPerContention' in derived else "  Avg Stall per Contention:      N/A")
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
    
    # Confidence Histogram
    if metrics.get('confidenceHistogram'):
        print("CONFIDENCE LEVEL DISTRIBUTION")
        print("-" * 80)
        histogram = metrics['confidenceHistogram']
        
        # Calculate total for percentages
        total_predictions = sum(histogram.values())
        
        # Sort by range start value
        sorted_ranges = []
        for range_key in histogram.keys():
            if '-' in range_key:
                start = int(range_key.split('-')[0])
            elif '+' in range_key:
                start = int(range_key.replace('+', ''))
            else:
                start = int(range_key)
            sorted_ranges.append((start, range_key))
        sorted_ranges.sort()
        
        # Print histogram
        max_count = max(histogram.values())
        for _, range_key in sorted_ranges:
            count = histogram[range_key]
            percentage = (count / total_predictions * 100) if total_predictions > 0 else 0
            bar_length = int((count / max_count) * 40) if max_count > 0 else 0
            bar = '█' * bar_length
            print(f"  {range_key:>6}%: {count:>10,} ({percentage:5.2f}%) {bar}")
        
        print(f"\n  Total Predictions: {total_predictions:,}")
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
