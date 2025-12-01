#!/usr/bin/env python3
"""
Baseline Evaluation Configuration for Dual-Path Execution Project
Standard O3CPU without dual-path execution for comparison
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
    description="Baseline O3CPU evaluation configuration"
)
parser.add_argument(
    "--binary", type=str, required=True, help="Binary to execute"
)
parser.add_argument(
    "--cpu-type",
    type=str,
    default="X86O3CPU",
    choices=["X86O3CPU", "X86MinorCPU"],
    help="CPU type to use",
)
parser.add_argument(
    "--outdir",
    type=str,
    default="m5out_baseline",
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
if args.cpu_type == "X86O3CPU":
    system.cpu = X86O3CPU()
elif args.cpu_type == "X86MinorCPU":
    system.cpu = X86MinorCPU()

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
print("BASELINE EVALUATION CONFIGURATION")
print("=" * 70)
print(f"CPU Type:              {args.cpu_type}")
print(f"Clock Frequency:       {args.clock}")
print(f"Memory Size:           {args.mem_size}")
print(f"L1I Cache Size:        {args.l1i_size}")
print(f"L1D Cache Size:        {args.l1d_size}")
print(f"L2 Cache Size:         {args.l2_size}")
print(f"Binary:                {args.binary}")
print(f"Output Directory:      {args.outdir}")
print(f"Stats Interval:        {args.stats_interval} ticks")
print(f"Dual-Path Execution:   DISABLED (Baseline)")
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

print(f"\nExiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("=" * 70)
print("SIMULATION COMPLETE")
print(f"Results saved to: {args.outdir}")
print("=" * 70)
