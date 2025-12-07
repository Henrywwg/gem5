#!/usr/bin/env python3
"""
Simple Dual-Path Test Configuration
Runs benchmarks with O3CPU to test dual-path execution
"""

import argparse
import os
import m5
from m5.objects import *

parser = argparse.ArgumentParser()
parser.add_argument("--binary", type=str, required=True)
parser.add_argument("--outdir", type=str, default="m5out_dualpath")
args = parser.parse_args()

# Create system
system = System()
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "2GHz"
system.clk_domain.voltage_domain = VoltageDomain()

system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]

# O3CPU with dual-path support built-in
system.cpu = X86O3CPU()

# Use TAGE predictor (supports confidence for DPS-TAGE)
system.cpu.branchPred = LTAGE()

# Simple cache hierarchy
system.cpu.icache_port = system.membus.cpu_side_ports
system.cpu.dcache_port = system.membus.cpu_side_ports

system.membus = SystemXBar()
system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

system.system_port = system.membus.cpu_side_ports

# Memory
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

# Setup
root = Root(full_system=False, system=system)
os.makedirs(args.outdir, exist_ok=True)
m5.core.setOutputDir(args.outdir)

m5.instantiate()

print("="*70)
print(f"Running: {args.binary}")
print(f"Output: {args.outdir}")
print("="*70)

# Run
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
