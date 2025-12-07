#!/usr/bin/env python3
"""
Quick verification that dual-path execution is active in gem5 stats
"""

import sys
import re
from pathlib import Path

def check_dual_path_stats(stats_file):
    """Check if dual-path stats exist and are non-zero."""
    
    if not Path(stats_file).exists():
        print(f"❌ Error: {stats_file} not found")
        return False
    
    with open(stats_file, 'r') as f:
        content = f.read()
    
    print(f"\n{'='*70}")
    print(f"Checking: {stats_file}")
    print(f"{'='*70}\n")
    
    # Stats to check
    checks = [
        ('APB Hits', r'system\.cpu\.apb\.hits\s+(\d+)'),
        ('APB Misses', r'system\.cpu\.apb\.misses\s+(\d+)'),
        ('APB Inserts', r'system\.cpu\.apb\.inserts\s+(\d+)'),
        ('Alternate Path Fetches', r'system\.cpu\.fetch\.alternatePathFetches\s+(\d+)'),
        ('Speculative Paths Spawned', r'system\.cpu\.speculativePathsSpawned\s+(\d+)'),
        ('Speculative Paths Squashed', r'system\.cpu\.speculativePathsSquashed\s+(\d+)'),
    ]
    
    found_any = False
    active_features = []
    
    for name, pattern in checks:
        match = re.search(pattern, content)
        if match:
            value = int(match.group(1))
            if value > 0:
                print(f"✅ {name:30s} {value:,}")
                found_any = True
                active_features.append(name)
            else:
                print(f"⚠️  {name:30s} 0 (present but not used)")
        else:
            print(f"❌ {name:30s} NOT FOUND")
    
    # DPS-TAGE switching (optional)
    dpstage_checks = [
        ('Switches to Dual-Path', r'system\.cpu\.branchPred\.switchesToDualPath\s+(\d+)'),
        ('Switches to Single-Path', r'system\.cpu\.branchPred\.switchesToSinglePath\s+(\d+)'),
        ('Dual-Path Mode Active', r'system\.cpu\.branchPred\.dualPathMode\s+(\d+)'),
    ]
    
    print(f"\n{'DPS-TAGE PREDICTOR (optional):'}")
    dpstage_active = False
    for name, pattern in dpstage_checks:
        match = re.search(pattern, content)
        if match:
            value = int(match.group(1))
            if value > 0:
                print(f"✅ {name:30s} {value:,}")
                dpstage_active = True
            else:
                print(f"⚠️  {name:30s} {value:,}")
        else:
            print(f"   {name:30s} N/A (not using DPS-TAGE)")
    
    print(f"\n{'='*70}")
    
    if found_any:
        print("✅ SUCCESS: Dual-path execution is ACTIVE!")
        print(f"\nActive features: {', '.join(active_features)}")
        if dpstage_active:
            print("+ DPS-TAGE dynamic switching enabled")
        return True
    else:
        print("❌ PROBLEM: No dual-path activity detected")
        print("\nPossible reasons:")
        print("  1. Not enough branch mispredictions")
        print("  2. Wrong CPU type (need O3CPU)")
        print("  3. Benchmark too simple")
        print("\nTry:")
        print("  - Longer running benchmark")
        print("  - Check: grep 'cpu_type' m5out/config.ini")
        print("  - Verify compilation included dual-path code")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 verify_dualpath.py <stats.txt>")
        print("\nExample:")
        print("  python3 verify_dualpath.py m5out/stats.txt")
        print("  python3 verify_dualpath.py results/*/stats.txt")
        sys.exit(1)
    
    all_good = True
    for stats_file in sys.argv[1:]:
        if not check_dual_path_stats(stats_file):
            all_good = False
        if len(sys.argv) > 2:
            print("\n")
    
    sys.exit(0 if all_good else 1)

if __name__ == "__main__":
    main()
