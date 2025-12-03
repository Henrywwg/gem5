#!/usr/bin/env python3
"""
Dual-Path Evaluation Configuration
O3CPU with APB and dual-path execution enabled
"""

import argparse
import os

import m5
from m5.objects import *

# Add common scripts to path
m5.util.addToPath("../../configs")
from common import SimpleOpts

# Parse arguments
parser = argparse.ArgumentParser(
    description="Dual-path O3CPU evaluation configuration"
)
parser.add_argument(
    "--binary", type=str, required=True, help="Binary to execute"
)
parser.add_argument(
    "--outdir",
    type=str,
    default="m5out_dualpath",
    help="Output directory for simulation results",
)
parser.add_argument(
    "--clock", type=str, default="2GHz", help="CPU clock frequency"
)
parser.add_argument(
    "--mem-size", type=str, default="512MiB", help="Memory size"
)
parser.add_argument(
    "--l1i-size", type=str, default="16kB", help="L1 instruction cache size"
)
parser.add_argument(
    "--l1d-size", type=str, default="64kB", help="L1 data cache size"
)
parser.add_argument(
    "--l2-size", type=str, default="256kB", help="L2 cache size"
)

# Dual-path specific parameters
parser.add_argument(
    "--apb-entries", type=int, default=16, help="Number of APB entries"
)
parser.add_argument(
    "--apb-line-size", type=int, default=64, help="APB line size in bytes"
)
parser.add_argument(
    "--initial-dual-path",
    action="store_true",
    default=True,
    help="Start in dual-path mode (default: True)",
)
parser.add_argument(
    "--no-initial-dual-path",
    action="store_false",
    dest="initial_dual_path",
    help="Start in single-path mode",
)
parser.add_argument(
    "--window-size",
    type=int,
    default=100,
    help="Branch history window size for confidence estimation",
)
parser.add_argument(
    "--high-threshold",
    type=int,
    default=85,
    help="Accuracy threshold to switch from dual to single-path (%)",
)
parser.add_argument(
    "--low-threshold",
    type=int,
    default=70,
    help="Accuracy threshold to switch from single to dual-path (%)",
)
parser.add_argument(
    "--fetch-policy",
    type=str,
    default="global",
    choices=["global", "selective"],
    help="Fetch policy: 'global' (all branches) or 'selective' (low-confidence only)",
)
parser.add_argument(
    "--confidence-threshold",
    type=int,
    default=70,
    help="Confidence threshold for selective fetch policy (%)",
)
parser.add_argument(
    "--icache-filter",
    action="store_true",
    default=True,
    help="Enable I-cache filtering for APB inserts (default: True)",
)
parser.add_argument(
    "--no-icache-filter",
    action="store_false",
    dest="icache_filter",
    help="Disable I-cache filtering (insert all alternate paths into APB)",
)
parser.add_argument(
    "--switching-mode",
    type=str,
    default="accuracy",
    choices=["accuracy", "confidence"],
    help="Switching mode: 'accuracy' (historical accuracy) or 'confidence' (predictor confidence)",
)
parser.add_argument(
    "--stats-interval",
    type=int,
    default=10000000,
    help="Statistics dump interval in ticks (0=disable periodic dumps)",
)
args = parser.parse_args()


# Define cache classes
class L1ICache(Cache):
    """L1 Instruction Cache"""

    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20
    size = args.l1i_size

    def connectCPU(self, cpu):
        self.cpu_side = cpu.icache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L1DCache(Cache):
    """L1 Data Cache"""

    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20
    size = args.l1d_size

    def connectCPU(self, cpu):
        self.cpu_side = cpu.dcache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L2Cache(Cache):
    """L2 Cache"""

    assoc = 8
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 20
    tgts_per_mshr = 12
    size = args.l2_size

    def connectCPUSideBus(self, bus):
        self.cpu_side = bus.mem_side_ports

    def connectMemSideBus(self, bus):
        self.mem_side = bus.cpu_side_ports


# Create system
system = System()

# Clock and voltage domain
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = args.clock
system.clk_domain.voltage_domain = VoltageDomain()

# Memory
system.mem_mode = "timing"
system.mem_ranges = [AddrRange(args.mem_size)]

# CPU
system.cpu = X86O3CPU()

# Configure TAGE branch predictor for confidence estimation
system.cpu.branchPred = TAGE()

# Create and attach APB
system.cpu.apb = APB(
    num_entries=args.apb_entries, line_size=args.apb_line_size
)

# Configure I-cache filtering for APB inserts
system.cpu.icacheFilterEnabled = args.icache_filter

# Create and attach DualPathSwitcher
system.cpu.dualPathSwitcher = DualPathSwitcher(
    window_size=args.window_size,
    high_threshold=args.high_threshold,
    low_threshold=args.low_threshold,
    initial_dual_path=args.initial_dual_path,
    fetch_policy=args.fetch_policy,
    confidence_threshold=args.confidence_threshold,
    switching_mode=args.switching_mode,
)

# Create cache hierarchy
system.cpu.icache = L1ICache()
system.cpu.dcache = L1DCache()
system.cpu.icache.connectCPU(system.cpu)
system.cpu.dcache.connectCPU(system.cpu)

system.l2bus = L2XBar()
system.cpu.icache.connectBus(system.l2bus)
system.cpu.dcache.connectBus(system.l2bus)

system.l2cache = L2Cache()
system.l2cache.connectCPUSideBus(system.l2bus)

system.membus = SystemXBar()
system.l2cache.connectMemSideBus(system.membus)

# Interrupt controller
system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

system.system_port = system.membus.cpu_side_ports

# Memory controller
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# Workload
system.workload = SEWorkload.init_compatible(args.binary)
process = Process()
process.cmd = [args.binary]
system.cpu.workload = process
system.cpu.createThreads()

# Create root
root = Root(full_system=False, system=system)

# Setup output directory
os.makedirs(args.outdir, exist_ok=True)
m5.core.setOutputDir(args.outdir)

# Instantiate
m5.instantiate()

# Print configuration
print("=" * 70)
print("DUAL-PATH EVALUATION CONFIGURATION")
print("=" * 70)
print(f"CPU Type:              X86O3CPU")
print(f"Clock Frequency:       {args.clock}")
print(f"Memory Size:           {args.mem_size}")
print(f"L1I Cache Size:        {args.l1i_size}")
print(f"L1D Cache Size:        {args.l1d_size}")
print(f"L2 Cache Size:         {args.l2_size}")
print(f"Binary:                {args.binary}")
print(f"Output Directory:      {args.outdir}")
print(f"Stats Interval:        {args.stats_interval} ticks")
print("-" * 70)
print("DUAL-PATH CONFIGURATION:")
print(f"  APB Entries:         {args.apb_entries}")
print(f"  APB Line Size:       {args.apb_line_size} bytes")
print(f"  I-cache Filter:      {'Enabled' if args.icache_filter else 'Disabled'}")
print(
    f"  Initial Mode:        {'Dual-Path' if args.initial_dual_path else 'Single-Path'}"
)
print(f"  Switching Mode:      {args.switching_mode}")
print(f"  Fetch Policy:        {args.fetch_policy}")
if args.fetch_policy == "selective":
    print(f"  Confidence Threshold: {args.confidence_threshold}%")
print(f"  Window Size:         {args.window_size} branches")
print(f"  High Threshold:      {args.high_threshold}% (switch to single-path)")
print(f"  Low Threshold:       {args.low_threshold}% (switch to dual-path)")
print("=" * 70)

# Run simulation
print("\nBeginning simulation...")
exit_event = m5.simulate()

# Periodic stats dumps for temporal analysis
if args.stats_interval > 0:
    interval = args.stats_interval
    dump_count = 1
    while exit_event.getCause() != "exiting with last active thread context":
        print(f"Stats dump #{dump_count} at tick {m5.curTick()}")
        m5.stats.dump()
        m5.stats.reset()
        exit_event = m5.simulate(interval)
        dump_count += 1

# Always dump final stats at end of simulation
m5.stats.dump()

print(f"\nExiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 70)
print("SIMULATION COMPLETE")
print(f"Results saved to: {args.outdir}")
print("=" * 70)
