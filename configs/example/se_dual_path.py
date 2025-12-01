#!/usr/bin/env python3

import argparse
import sys

import m5
from m5.objects import *

parser = argparse.ArgumentParser()
parser.add_argument("--cmd", required=True, help="Binary to run")
parser.add_argument(
    "--fetch-policy",
    default="global",
    choices=["global", "selective"],
    help="Dual-path fetch policy",
)
args = parser.parse_args()

# Create system
system = System()
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "3GHz"
system.clk_domain.voltage_domain = VoltageDomain()

system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]

# Create O3CPU
system.cpu = X86O3CPU()
system.cpu.numThreads = 1
system.cpu.createInterruptController()

# Create APB
system.apb = APB()
system.apb.num_entries = 256
system.apb.line_size = 64

# Create DualPathSwitcher
system.dual_path_switcher = DualPathSwitcher()
system.dual_path_switcher.fetch_policy = args.fetch_policy
system.dual_path_switcher.confidence_threshold = 95
system.dual_path_switcher.switching_mode = (
    "confidence"  # Use confidence-based switching, not windowed accuracy
)

# Connect DualPathSwitcher and APB to CPU
system.cpu.dualPathSwitcher = system.dual_path_switcher
system.cpu.apb = system.apb

# Create memory bus
system.membus = SystemXBar()

# Connect CPU to memory bus
system.cpu.icache_port = system.membus.cpu_side_ports
system.cpu.dcache_port = system.membus.cpu_side_ports

# Create memory controller
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# Connect system port
system.system_port = system.membus.cpu_side_ports

# Set up workload
process = Process()
process.cmd = [args.cmd]
system.cpu.workload = process
system.cpu.createThreads()

# Set up SE workload
system.workload = SEWorkload.init_compatible(args.cmd)

# Create root
root = Root(full_system=False, system=system)

# Instantiate
m5.instantiate()

# Run
print(f"Running: {args.cmd}")
print(f"Fetch policy: {args.fetch_policy}")
print(f"Switching mode: {system.dual_path_switcher.switching_mode}")
print(
    f"Confidence threshold: {system.dual_path_switcher.confidence_threshold}%"
)
print("Starting simulation...")
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
