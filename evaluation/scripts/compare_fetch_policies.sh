#!/bin/bash
# Compare baseline vs global vs selective fetch policy results

BASELINE_STATS="/home/dlnavarro/ece752proj/gem5/evaluation/results/baseline_progressive/stats.txt"
GLOBAL_STATS="/home/dlnavarro/ece752proj/gem5/evaluation/results/dualpath_progressive_global/stats.txt"
SELECTIVE_STATS="/home/dlnavarro/ece752proj/gem5/evaluation/results/dualpath_progressive_selective/stats.txt"

echo "========================================================================="
echo "BASELINE vs GLOBAL vs SELECTIVE FETCH POLICY COMPARISON"
echo "Progressive DAXPY Benchmark"
echo "========================================================================="
echo

extract_stat() {
    local file=$1
    local pattern=$2
    grep "$pattern" "$file" | head -1 | awk '{print $2}'
}

print_comparison() {
    local metric=$1
    local pattern=$2
    local unit=$3

    local baseline_val=$(extract_stat "$BASELINE_STATS" "$pattern")
    local global_val=$(extract_stat "$GLOBAL_STATS" "$pattern")
    local selective_val=$(extract_stat "$SELECTIVE_STATS" "$pattern")

    printf "%-40s | %18s | %18s | %18s\n" "$metric" "$baseline_val $unit" "$global_val $unit" "$selective_val $unit"
}

printf "%-40s | %18s | %18s | %18s\n" "Metric" "Baseline (No DP)" "Global DP" "Selective DP"
echo "--------------------------------------------------------------------------------------------------------------------"

echo "EXECUTION TIME & PERFORMANCE"
echo "--------------------------------------------------------------------------------------------------------------------"
print_comparison "Simulation Ticks" "simTicks" "ticks"
print_comparison "Simulation Seconds" "simSeconds" "s"
print_comparison "IPC (overall)" "system.cpu.ipc" ""
print_comparison "Committed Instructions" "system.cpu.commit.committedInsts" ""
print_comparison "Cycles" "system.cpu.numCycles" ""
echo

echo "BRANCH PREDICTION & SWITCHING"
echo "--------------------------------------------------------------------------------------------------------------------"
print_comparison "Total Branches" "system.cpu.commit.branches" ""
print_comparison "Branch Mispredicts" "system.cpu.branchPred.condIncorrect" ""

# Dual-path switcher stats (only in DP configs)
echo "Dual-Path Switcher Stats:"
global_dp_branches=$(extract_stat "$GLOBAL_STATS" "system.cpu.dualPathSwitcher.branchesInDualPath")
selective_dp_branches=$(extract_stat "$SELECTIVE_STATS" "system.cpu.dualPathSwitcher.branchesInDualPath")
global_switches_to_dp=$(extract_stat "$GLOBAL_STATS" "system.cpu.dualPathSwitcher.switchesToDualPath")
selective_switches_to_dp=$(extract_stat "$SELECTIVE_STATS" "system.cpu.dualPathSwitcher.switchesToDualPath")
global_spikes=$(extract_stat "$GLOBAL_STATS" "system.cpu.dualPathSwitcher.mispredictionSpikesInSinglePath")
selective_spikes=$(extract_stat "$SELECTIVE_STATS" "system.cpu.dualPathSwitcher.mispredictionSpikesInSinglePath")

printf "%-40s | %18s | %18s | %18s\n" "  Branches in Dual-Path" "N/A" "$global_dp_branches" "$selective_dp_branches"
printf "%-40s | %18s | %18s | %18s\n" "  Switches to Dual-Path" "N/A" "$global_switches_to_dp" "$selective_switches_to_dp"
printf "%-40s | %18s | %18s | %18s\n" "  Misprediction Spikes" "N/A" "$global_spikes" "$selective_spikes"
echo

echo "APB (ALTERNATE PATH BUFFER) COVERAGE"
echo "--------------------------------------------------------------------------------------------------------------------"
print_comparison "APB Hits" "system.cpu.apb.hits" ""
print_comparison "APB Misses" "system.cpu.apb.misses" ""
print_comparison "APB Hit Rate" "system.cpu.apb.hitRate" ""
print_comparison "APB Useful Restorations" "system.cpu.apb.usefulRestorations" ""
print_comparison "APB Coverage %" "system.cpu.apb.coveragePercent" "%"
echo

echo "CACHE PERFORMANCE"
echo "--------------------------------------------------------------------------------------------------------------------"
print_comparison "L1 ICache Accesses" "system.cpu.icache.overallAccesses::total" ""
print_comparison "L1 ICache Misses" "system.cpu.icache.overallMisses::total" ""
print_comparison "L1 ICache Miss Rate" "system.cpu.icache.overallMissRate::total" ""
print_comparison "L1 DCache Accesses" "system.cpu.dcache.overallAccesses::total" ""
print_comparison "L1 DCache Misses" "system.cpu.dcache.overallMisses::total" ""
print_comparison "L1 DCache Miss Rate" "system.cpu.dcache.overallMissRate::total" ""
print_comparison "L2 Cache Accesses" "system.l2cache.overallAccesses::total" ""
print_comparison "L2 Cache Misses" "system.l2cache.overallMisses::total" ""
print_comparison "L2 Cache Miss Rate" "system.l2cache.overallMissRate::total" ""
echo

echo "RECOVERY & SQUASHING"
echo "--------------------------------------------------------------------------------------------------------------------"
print_comparison "Fetch Squash Cycles" "system.cpu.fetch.squashCycles" ""
print_comparison "Decode Squash Cycles" "system.cpu.decode.squashCycles" ""
print_comparison "Rename Squash Cycles" "system.cpu.rename.squashCycles" ""
print_comparison "IEW Squash Cycles" "system.cpu.iew.iewSquashCycles" ""
print_comparison "Commit Squash Cycles" "system.cpu.commit.commitSquashedInsts" ""
echo

echo "FRONTEND PERFORMANCE"
echo "--------------------------------------------------------------------------------------------------------------------"
print_comparison "Fetch Rate (insts/cycle)" "system.cpu.fetch.rateDist::mean" ""
print_comparison "Decode Rate (insts/cycle)" "system.cpu.decode.rateDist::mean" ""
print_comparison "IPC" "system.cpu.ipc" ""
echo

echo "========================================================================="
echo "PERFORMANCE SUMMARY"
echo "========================================================================="
baseline_ticks=$(extract_stat "$BASELINE_STATS" "simTicks")
global_ticks=$(extract_stat "$GLOBAL_STATS" "simTicks")
selective_ticks=$(extract_stat "$SELECTIVE_STATS" "simTicks")

baseline_ipc=$(extract_stat "$BASELINE_STATS" "system.cpu.ipc")
global_ipc=$(extract_stat "$GLOBAL_STATS" "system.cpu.ipc")
selective_ipc=$(extract_stat "$SELECTIVE_STATS" "system.cpu.ipc")

echo "Execution Time (lower is better):"
echo "  Baseline:  $baseline_ticks ticks"
echo "  Global:    $global_ticks ticks ($(awk "BEGIN {printf \"%.2f\", (($global_ticks - $baseline_ticks) / $baseline_ticks) * 100}")% vs baseline)"
echo "  Selective: $selective_ticks ticks ($(awk "BEGIN {printf \"%.2f\", (($selective_ticks - $baseline_ticks) / $baseline_ticks) * 100}")% vs baseline)"
echo
echo "IPC (higher is better):"
echo "  Baseline:  $baseline_ipc"
echo "  Global:    $global_ipc ($(awk "BEGIN {printf \"%.2f\", (($global_ipc - $baseline_ipc) / $baseline_ipc) * 100}")% vs baseline)"
echo "  Selective: $selective_ipc ($(awk "BEGIN {printf \"%.2f\", (($selective_ipc - $baseline_ipc) / $baseline_ipc) * 100}")% vs baseline)"
echo

baseline_apb_hits=$(extract_stat "$BASELINE_STATS" "system.cpu.apb.hits")
global_apb_hits=$(extract_stat "$GLOBAL_STATS" "system.cpu.apb.hits")
selective_apb_hits=$(extract_stat "$SELECTIVE_STATS" "system.cpu.apb.hits")

echo "APB Effectiveness:"
echo "  Baseline:  $baseline_apb_hits hits"
echo "  Global:    $global_apb_hits hits"
echo "  Selective: $selective_apb_hits hits"
echo
echo "========================================================================="
