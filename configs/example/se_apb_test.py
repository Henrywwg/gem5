# Simple test configuration to verify APB can be instantiated with O3CPU

import argparse
import sys

import m5
from m5.objects import *

parser = argparse.ArgumentParser()
parser.add_argument("binary", type=str, help="Binary to execute")
parser.add_argument(
    "--apb-entries", type=int, default=64, help="Number of APB entries"
)
parser.add_argument(
    "--apb-line-size", type=int, default=64, help="APB line size in bytes"
)
parser.add_argument(
    "--dual-path",
    action="store_true",
    help="Enable dual-path execution with switcher",
)
args = parser.parse_args()

# Create system
system = System()
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "2GHz"
system.clk_domain.voltage_domain = VoltageDomain()
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]

# Create O3 CPU
system.cpu = X86O3CPU()

# Create and attach APB
system.cpu.apb = APB(
    num_entries=args.apb_entries, line_size=args.apb_line_size
)

# Create and attach DualPathSwitcher if requested
if args.dual_path:
    system.cpu.dualPathSwitcher = DualPathSwitcher(
        window_size=100,
        high_threshold=85,  # Switch to single-path at 85% accuracy
        low_threshold=70,  # Switch back to dual-path at 70% accuracy
        initial_dual_path=True,  # Start in dual-path mode
    )
    print(
        f"Dual-path execution enabled (start: dual-path, switch at 85% accuracy)"
    )


# Memory bus (create before using it)
system.membus = SystemXBar()

# Create caches
system.cpu.icache_port = system.membus.cpu_side_ports
system.cpu.dcache_port = system.membus.cpu_side_ports

system.system_port = system.membus.cpu_side_ports

# Memory controller
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# Interrupts
system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

# Workload
system.workload = SEWorkload.init_compatible(args.binary)
process = Process()
process.cmd = [args.binary]
system.cpu.workload = process
system.cpu.createThreads()

# Setup simulation
root = Root(full_system=False, system=system)
m5.instantiate()

print(
    f"Starting simulation with APB ({args.apb_entries} entries, {args.apb_line_size}B lines)"
)
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
