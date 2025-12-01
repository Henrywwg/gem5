#!/usr/bin/env python3
# Simple test for dual-path execution

import m5
from m5.objects import *

# Create system
system = System()
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "3GHz"
system.clk_domain.voltage_domain = VoltageDomain()
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]

# Create DualPathSwitcher with global policy
system.dual_path_switcher = DualPathSwitcher(
    window_size=100,
    high_threshold=85,
    low_threshold=70,
    initial_dual_path=False,  # Start disabled to test basic functionality
    fetch_policy="global",
    confidence_threshold=70,
)

# Create APB
system.apb = APB(num_entries=16, line_size=64)

# Create CPU with dual-path support
system.cpu = O3CPU(dualPathSwitcher=system.dual_path_switcher, apb=system.apb)
system.cpu.createInterruptController()

# Memory system
system.membus = SystemXBar()
system.cpu.icache_port = system.membus.cpu_side_ports
system.cpu.dcache_port = system.membus.cpu_side_ports

# Connect interrupt controller
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

system.system_port = system.membus.cpu_side_ports

# Set up process with hello world
binary = "tests/test-progs/hello/bin/x86/linux/hello"
system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary]
system.cpu.workload = process
system.cpu.createThreads()

# Instantiate
root = Root(full_system=False, system=system)
m5.instantiate()

print("=" * 60)
print("Starting Dual-Path Execution Test")
print("Fetch Policy: global")
print("=" * 60)

# Run simulation
exit_event = m5.simulate()
print(f"\nExiting @ tick {m5.curTick()} because {exit_event.getCause()}")
print("\nSimulation completed successfully!")
