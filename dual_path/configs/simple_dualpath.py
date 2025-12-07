#!/usr/bin/env python3
"""
Simple Dual-Path Test Configuration
Runs benchmarks with O3CPU to test dual-path execution

Modern gem5 style configuration (no deprecated scripts)
"""

import argparse
import os
import m5
from m5.objects import *

parser = argparse.ArgumentParser(description="Dual-path O3CPU test configuration")
parser.add_argument("--binary", type=str, required=True, help="Binary to execute")
parser.add_argument("--outdir", type=str, default="m5out_dualpath", help="Output directory")
parser.add_argument("--cpu-clock", type=str, default="2GHz", help="CPU clock frequency")
parser.add_argument("--mem-size", type=str, default="512MB", help="Memory size")
args = parser.parse_args()

# Create system
system = System()

# Clock domain
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = args.cpu_clock
system.clk_domain.voltage_domain = VoltageDomain()

# Memory configuration
system.mem_mode = "timing"
system.mem_ranges = [AddrRange(args.mem_size)]

# O3CPU with dual-path support built-in
system.cpu = X86O3CPU()

# Use LTAGE predictor for better branch prediction
# (DPS-TAGE if you want dynamic switching)
system.cpu.branchPred = LTAGE()

# Create memory bus
system.membus = SystemXBar()

# Connect CPU ports to memory bus
system.cpu.icache_port = system.membus.cpu_side_ports
system.cpu.dcache_port = system.membus.cpu_side_ports

# Create interrupt controller
system.cpu.createInterruptController()

# For X86 only - connect interrupts to memory
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
print("DUAL-PATH O3CPU SIMULATION")
print("="*70)
print(f"Binary:       {args.binary}")
print(f"CPU:          O3CPU @ {args.cpu_clock}")
print(f"Predictor:    {type(system.cpu.branchPred).__name__}")
print(f"Memory:       {args.mem_size}")
print(f"Output:       {args.outdir}")
print("="*70)

# Run simulation
print("\nStarting simulation...")
exit_event = m5.simulate()

print(f"\nExiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print(f"Results saved to: {args.outdir}")
