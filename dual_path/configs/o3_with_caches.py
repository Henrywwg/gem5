#!/usr/bin/env python3
"""
Dual-Path O3CPU Configuration with Cache Hierarchy
For more realistic performance testing
"""

import argparse
import os
import m5
from m5.objects import *

parser = argparse.ArgumentParser(description="Dual-path O3CPU with caches")
parser.add_argument("--binary", type=str, required=True, help="Binary to execute")
parser.add_argument("--outdir", type=str, default="m5out_dualpath", help="Output directory")
parser.add_argument("--cpu-clock", type=str, default="2GHz", help="CPU clock frequency")
parser.add_argument("--mem-size", type=str, default="2GB", help="Memory size")
parser.add_argument("--l1i-size", type=str, default="32kB", help="L1 I-cache size")
parser.add_argument("--l1d-size", type=str, default="64kB", help="L1 D-cache size")
parser.add_argument("--l2-size", type=str, default="256kB", help="L2 cache size")
parser.add_argument("--predictor", type=str, default="LTAGE", 
                    choices=["TAGE", "LTAGE", "DPSTAGE"],
                    help="Branch predictor type")
args = parser.parse_args()

# Cache classes
class L1ICache(Cache):
    """L1 Instruction Cache"""
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20
    size = args.l1i_size

class L1DCache(Cache):
    """L1 Data Cache"""
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20
    size = args.l1d_size

class L2Cache(Cache):
    """L2 Cache"""
    assoc = 8
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 20
    tgts_per_mshr = 12
    size = args.l2_size

# Create system
system = System()

# Clock domain
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = args.cpu_clock
system.clk_domain.voltage_domain = VoltageDomain()

# Memory configuration
system.mem_mode = "timing"
system.mem_ranges = [AddrRange(args.mem_size)]

# O3CPU with dual-path support
system.cpu = X86O3CPU()

# Branch predictor selection
if args.predictor == "TAGE":
    system.cpu.branchPred = TAGE()
elif args.predictor == "LTAGE":
    system.cpu.branchPred = LTAGE()
elif args.predictor == "DPSTAGE":
    # DPS-TAGE with dual-path switching
    system.cpu.branchPred = DPSTAGE()
else:
    system.cpu.branchPred = LTAGE()

# Enable dual-path execution
system.cpu.apb = APB()
system.cpu.dualPathSwitcher = DualPathSwitcher()

# Create cache hierarchy
system.cpu.icache = L1ICache()
system.cpu.dcache = L1DCache()

# Connect L1 caches
system.cpu.icache.cpu_side = system.cpu.icache_port
system.cpu.dcache.cpu_side = system.cpu.dcache_port

# Create L2 bus
system.l2bus = L2XBar()

# Connect L1 to L2 bus
system.cpu.icache.mem_side = system.l2bus.cpu_side_ports
system.cpu.dcache.mem_side = system.l2bus.cpu_side_ports

# Create L2 cache
system.l2cache = L2Cache()
system.l2cache.cpu_side = system.l2bus.mem_side_ports

# Create memory bus
system.membus = SystemXBar()

# Connect L2 to memory bus
system.l2cache.mem_side = system.membus.cpu_side_ports

# Create interrupt controller
system.cpu.createInterruptController()

# For X86 - connect interrupts to memory
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

# Connect system port to memory bus
system.system_port = system.membus.cpu_side_ports

# Memory controller
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# Set up workload
system.workload = SEWorkload.init_compatible(args.binary)

# Create process
process = Process()
process.cmd = [args.binary]
system.cpu.workload = process
system.cpu.createThreads()

# Create root object
root = Root(full_system=False, system=system)

# Set output directory
os.makedirs(args.outdir, exist_ok=True)
m5.core.setOutputDir(args.outdir)

# Instantiate system
m5.instantiate()

print("="*70)
print("DUAL-PATH O3CPU SIMULATION (WITH CACHES)")
print("="*70)
print(f"Binary:       {args.binary}")
print(f"CPU:          O3CPU @ {args.cpu_clock}")
print(f"Predictor:    {args.predictor}")
print(f"L1-I Cache:   {args.l1i_size}")
print(f"L1-D Cache:   {args.l1d_size}")
print(f"L2 Cache:     {args.l2_size}")
print(f"Memory:       {args.mem_size}")
print(f"Output:       {args.outdir}")
print("="*70)

# Run simulation
print("\nStarting simulation...")
exit_event = m5.simulate()

print(f"\nExiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print(f"Results saved to: {args.outdir}")
