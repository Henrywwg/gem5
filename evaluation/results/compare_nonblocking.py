#!/usr/bin/env python3
"""Compare blocking vs non-blocking alternate path fetch results"""

import re


def parse_stats(filepath):
    stats = {}
    with open(filepath) as f:
        content = f.read()

        # Extract key statistics
        patterns = {
            "simTicks": r"simTicks\s+(\d+)",
            "simInsts": r"simInsts\s+(\d+)",
            "ipc": r"system\.cpu\.ipc\s+([\d.]+)",
            "branches": r"system\.cpu\.branchPred\.condPredicted\s+(\d+)",
            "mispredicts": r"system\.cpu\.branchPred\.condIncorrect\s+(\d+)",
            # APB statistics
            "apb_accesses": r"system\.cpu\.apb\.accesses\s+(\d+)",
            "apb_hits": r"system\.cpu\.apb\.hits\s+(\d+)",
            "apb_misses": r"system\.cpu\.apb\.misses\s+(\d+)",
            "apb_inserts": r"system\.cpu\.apb\.inserts\s+(\d+)",
            # Alternate path fetch statistics
            "alt_requests": r"system\.cpu\.fetch\.altPathFetchRequests\s+(\d+)",
            "alt_completed": r"system\.cpu\.fetch\.altPathFetchCompleted\s+(\d+)",
            "alt_squashed": r"system\.cpu\.fetch\.altPathFetchSquashed\s+(\d+)",
            # Deferred fetch statistics (non-blocking only)
            "alt_deferred": r"system\.cpu\.fetch\.altPathFetchDeferred\s+(\d+)",
            "alt_deferred_processed": r"system\.cpu\.fetch\.altPathFetchDeferredProcessed\s+(\d+)",
            "alt_deferred_dropped": r"system\.cpu\.fetch\.altPathFetchDeferredDropped\s+(\d+)",
            # Recovery statistics
            "recovery_hits": r"system\.cpu\.fetch\.apbRecoveryHits\s+(\d+)",
            "recovery_misses": r"system\.cpu\.fetch\.apbRecoveryMisses\s+(\d+)",
            "recovery_cycles": r"system\.cpu\.fetch\.branchMispredRecoveryCycles\s+(\d+)",
            # Recovery latency
            "apb_hit_recovery_mean": r"system\.cpu\.fetch\.apbHitRecoveryLatency::mean\s+([\d.]+)",
            "apb_miss_recovery_mean": r"system\.cpu\.fetch\.apbMissRecoveryLatency::mean\s+([\d.]+)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                try:
                    stats[key] = float(match.group(1))
                except ValueError:
                    stats[key] = match.group(1)
            else:
                stats[key] = 0

    return stats


# Parse both results
blocking = parse_stats("evaluation/results/dualpath_progressive_256/stats.txt")
nonblocking = parse_stats(
    "evaluation/results/dualpath_progressive_nonblocking/stats.txt"
)

print("=" * 80)
print("BLOCKING vs NON-BLOCKING ALTERNATE PATH FETCH COMPARISON")
print("=" * 80)
print()
print("Configuration: 256-entry APB, daxpy_progressive benchmark")
print()

print("-" * 80)
print("PERFORMANCE METRICS:")
print("-" * 80)
print(f"{'Metric':<40} {'Blocking':>15} {'Non-Blocking':>15} {'Change':>10}")
print("-" * 80)

# IPC
ipc_change = ((nonblocking["ipc"] - blocking["ipc"]) / blocking["ipc"]) * 100
print(
    f"{'IPC':<40} {blocking['ipc']:>15.6f} {nonblocking['ipc']:>15.6f} {ipc_change:>9.2f}%"
)

# Simulation time
print(
    f"{'Sim Ticks':<40} {blocking['simTicks']:>15,.0f} {nonblocking['simTicks']:>15,.0f}"
)
print(
    f"{'Instructions':<40} {blocking['simInsts']:>15,.0f} {nonblocking['simInsts']:>15,.0f}"
)

print()
print("-" * 80)
print("ALTERNATE PATH FETCH STATISTICS:")
print("-" * 80)
print(f"{'Metric':<40} {'Blocking':>15} {'Non-Blocking':>15} {'Change':>10}")
print("-" * 80)

# Alternate path requests
req_change = nonblocking["alt_requests"] - blocking["alt_requests"]
print(
    f"{'Alt Path Requests':<40} {blocking['alt_requests']:>15,.0f} {nonblocking['alt_requests']:>15,.0f} {req_change:>9.0f}x"
    if req_change > 1000
    else f"{'Alt Path Requests':<40} {blocking['alt_requests']:>15,.0f} {nonblocking['alt_requests']:>15,.0f} +{req_change:>8.0f}"
)

comp_change = nonblocking["alt_completed"] - blocking["alt_completed"]
print(
    f"{'Alt Path Completed':<40} {blocking['alt_completed']:>15,.0f} {nonblocking['alt_completed']:>15,.0f} +{comp_change:>8.0f}"
)

# Deferred statistics (non-blocking only)
print(
    f"{'Alt Path Deferred':<40} {'N/A':>15} {nonblocking['alt_deferred']:>15,.0f}"
)
print(
    f"{'Alt Path Deferred Processed':<40} {'N/A':>15} {nonblocking['alt_deferred_processed']:>15,.0f}"
)
print(
    f"{'Alt Path Deferred Dropped':<40} {'N/A':>15} {nonblocking['alt_deferred_dropped']:>15,.0f}"
)

print()
print("-" * 80)
print("APB STATISTICS:")
print("-" * 80)
print(f"{'Metric':<40} {'Blocking':>15} {'Non-Blocking':>15} {'Change':>10}")
print("-" * 80)

# APB inserts
insert_change = (
    (nonblocking["apb_inserts"] - blocking["apb_inserts"])
    / blocking["apb_inserts"]
) * 100
print(
    f"{'APB Inserts':<40} {blocking['apb_inserts']:>15,.0f} {nonblocking['apb_inserts']:>15,.0f} {insert_change:>9.1f}%"
)

# APB hits
hit_change = (
    (nonblocking["apb_hits"] - blocking["apb_hits"]) / blocking["apb_hits"]
) * 100
print(
    f"{'APB Hits':<40} {blocking['apb_hits']:>15,.0f} {nonblocking['apb_hits']:>15,.0f} {hit_change:>9.1f}%"
)

# APB hit rate
blocking_hit_rate = (
    (blocking["apb_hits"] / blocking["apb_accesses"]) * 100
    if blocking["apb_accesses"] > 0
    else 0
)
nonblocking_hit_rate = (
    (nonblocking["apb_hits"] / nonblocking["apb_accesses"]) * 100
    if nonblocking["apb_accesses"] > 0
    else 0
)
print(
    f"{'APB Hit Rate':<40} {blocking_hit_rate:>14.2f}% {nonblocking_hit_rate:>14.2f}% {nonblocking_hit_rate - blocking_hit_rate:>9.2f}pp"
)

print()
print("-" * 80)
print("RECOVERY STATISTICS:")
print("-" * 80)
print(f"{'Metric':<40} {'Blocking':>15} {'Non-Blocking':>15} {'Change':>10}")
print("-" * 80)

# Recovery hits
rec_hit_change = (
    (nonblocking["recovery_hits"] - blocking["recovery_hits"])
    / blocking["recovery_hits"]
) * 100
print(
    f"{'Recovery Hits':<40} {blocking['recovery_hits']:>15,.0f} {nonblocking['recovery_hits']:>15,.0f} {rec_hit_change:>9.1f}%"
)

# Recovery misses
print(
    f"{'Recovery Misses':<40} {blocking['recovery_misses']:>15,.0f} {nonblocking['recovery_misses']:>15,.0f}"
)

# Recovery hit rate
total_recoveries_b = blocking["recovery_hits"] + blocking["recovery_misses"]
total_recoveries_nb = (
    nonblocking["recovery_hits"] + nonblocking["recovery_misses"]
)
blocking_rec_rate = (
    (blocking["recovery_hits"] / total_recoveries_b) * 100
    if total_recoveries_b > 0
    else 0
)
nonblocking_rec_rate = (
    (nonblocking["recovery_hits"] / total_recoveries_nb) * 100
    if total_recoveries_nb > 0
    else 0
)
print(
    f"{'Recovery Hit Rate':<40} {blocking_rec_rate:>14.2f}% {nonblocking_rec_rate:>14.2f}% {nonblocking_rec_rate - blocking_rec_rate:>9.2f}pp"
)

# Recovery latency
print(
    f"{'APB Hit Recovery Latency':<40} {blocking['apb_hit_recovery_mean']:>14.1f}c {nonblocking['apb_hit_recovery_mean']:>14.1f}c"
)
print(
    f"{'APB Miss Recovery Latency':<40} {blocking['apb_miss_recovery_mean']:>14.1f}c {nonblocking['apb_miss_recovery_mean']:>14.1f}c"
)

print()
print("=" * 80)
print("KEY FINDINGS:")
print("=" * 80)

# Calculate multiplier
request_multiplier = (
    nonblocking["alt_requests"] / blocking["alt_requests"]
    if blocking["alt_requests"] > 0
    else 0
)

print(f"✅ ALTERNATE PATH COVERAGE: {request_multiplier:.1f}x increase!")
print(f"   • Blocking:     {blocking['alt_requests']:,.0f} requests")
print(f"   • Non-Blocking: {nonblocking['alt_requests']:,.0f} requests")
print(
    f"   • Increase:     {nonblocking['alt_requests'] - blocking['alt_requests']:,.0f} additional fetches"
)
print()

print(f"✅ APB INSERTS: {insert_change:+.1f}% change")
print(f"   • Blocking:     {blocking['apb_inserts']:,.0f} inserts")
print(f"   • Non-Blocking: {nonblocking['apb_inserts']:,.0f} inserts")
print()

print(
    f"✅ RECOVERY HIT RATE: {nonblocking_rec_rate - blocking_rec_rate:+.1f} percentage points"
)
print(
    f"   • Blocking:     {blocking_rec_rate:.1f}% ({blocking['recovery_hits']:,.0f} hits)"
)
print(
    f"   • Non-Blocking: {nonblocking_rec_rate:.1f}% ({nonblocking['recovery_hits']:,.0f} hits)"
)
print(
    f"   • Additional:   {nonblocking['recovery_hits'] - blocking['recovery_hits']:,.0f} more recovery hits"
)
print()

print(f"✅ IPC IMPROVEMENT: {ipc_change:+.2f}%")
print(f"   • Blocking:     {blocking['ipc']:.6f}")
print(f"   • Non-Blocking: {nonblocking['ipc']:.6f}")
print()

if nonblocking["alt_deferred"] > 0:
    defer_rate = (
        nonblocking["alt_deferred_processed"] / nonblocking["alt_deferred"]
    ) * 100
    print(f"📊 DEFERRED FETCH EFFICIENCY:")
    print(f"   • Total Deferred:  {nonblocking['alt_deferred']:,.0f}")
    print(
        f"   • Processed Later: {nonblocking['alt_deferred_processed']:,.0f} ({defer_rate:.1f}%)"
    )
    print(f"   • Dropped (full):  {nonblocking['alt_deferred_dropped']:,.0f}")
    print()

print("=" * 80)
