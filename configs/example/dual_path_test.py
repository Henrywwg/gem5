#!/usr/bin/env python3
# Copyright (c) 2024 The Regents of the University of Wisconsin-Madison
# All rights reserved.

"""
Example configuration for testing dual-path execution with APB.
Demonstrates both "global" and "selective" fetch policies.

Usage:
  # Test with global policy (fetch alternate path for ALL branches)
  gem5.opt configs/example/dual_path_test.py --fetch-policy=global

  # Test with selective policy (fetch only for low-confidence branches)
  gem5.opt configs/example/dual_path_test.py --fetch-policy=selective --confidence-threshold=50
"""

import argparse
import sys

import m5
from m5.objects import *

# Add options
parser = argparse.ArgumentParser()
parser.add_argument(
    "--fetch-policy",
    type=str,
    default="global",
    choices=["global", "selective"],
    help="Alternate path fetch policy: 'global' or 'selective'",
)
parser.add_argument(
    "--confidence-threshold",
    type=int,
    default=50,
    help="Confidence threshold for selective policy (0-100)",
)
parser.add_argument(
    "--window-size",
    type=int,
    default=100,
    help="Sliding window size for accuracy tracking",
)
parser.add_argument(
    "--high-threshold",
    type=int,
    default=85,
    help="Accuracy threshold to switch to single-path (%)",
)
parser.add_argument(
    "--low-threshold",
    type=int,
    default=70,
    help="Accuracy threshold to switch to dual-path (%)",
)
parser.add_argument(
    "--apb-entries", type=int, default=16, help="Number of entries in the APB"
)
parser.add_argument(
    "--apb-line-size",
    type=int,
    default=64,
    help="Line size of APB entries (bytes)",
)
parser.add_argument(
    "--binary",
    type=str,
    default="tests/test-progs/hello/bin/x86/linux/hello",
    help="Binary to run",
)

args = parser.parse_args()

# Create the system
system = System()
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "3GHz"
system.clk_domain.voltage_domain = VoltageDomain()
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]

# Create the DualPathSwitcher with specified policy
system.dual_path_switcher = DualPathSwitcher(
    window_size=args.window_size,
    high_threshold=args.high_threshold,
    low_threshold=args.low_threshold,
    initial_dual_path=True,
    fetch_policy=args.fetch_policy,
    confidence_threshold=args.confidence_threshold,
)

# Create the APB
system.apb = APB(num_entries=args.apb_entries, line_size=args.apb_line_size)

# Create the CPU with dual-path support
system.cpu = O3CPU(dualPathSwitcher=system.dual_path_switcher, apb=system.apb)

# Set up the memory system
system.membus = SystemXBar()
system.cpu.icache_port = system.membus.cpu_side_ports
system.cpu.dcache_port = system.membus.cpu_side_ports
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports

# Set up the process
process = Process()
process.cmd = [args.binary]
system.cpu.workload = process
system.cpu.createThreads()

# Set up the root
root = Root(full_system=False, system=system)
m5.instantiate()

# Print configuration
print("=" * 60)
print("Dual-Path Execution Configuration:")
print("=" * 60)
print(f"Fetch Policy:         {args.fetch_policy}")
if args.fetch_policy == "selective":
    print(f"Confidence Threshold: {args.confidence_threshold}%")
print(f"Window Size:          {args.window_size} branches")
print(f"High Threshold:       {args.high_threshold}%")
print(f"Low Threshold:        {args.low_threshold}%")
print(f"APB Entries:          {args.apb_entries}")
print(f"APB Line Size:        {args.apb_line_size} bytes")
print(f"Binary:               {args.binary}")
print("=" * 60)

# Run the simulation
print("Beginning simulation!")
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")

# Print statistics
print("\n" + "=" * 60)
print("Dual-Path Execution Statistics:")
print("=" * 60)
m5.stats.dump()
