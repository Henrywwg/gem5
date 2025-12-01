# Dual-Path Execution Configuration for DAXPY benchmark
# Based on working daxpy_config.py pattern

import m5
from m5.objects import *

# Add the common scripts to our path
m5.util.addToPath("../")

from common import SimpleOpts

# Instantiate a system
system = System()

# Initialize the clock domain and voltage domain
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "1GHz"  # Set the clock frequency
system.clk_domain.voltage_domain = VoltageDomain()

# Create a memory system
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MiB")]

# Create an O3CPU with dual-path execution support
system.cpu = X86O3CPU()

# Create and configure the DualPathSwitcher
system.cpu.dualPathSwitcher = DualPathSwitcher()
# Configuration will be set from command-line arguments after parsing

# Create and configure the Alternate Path Buffer (APB)
system.cpu.apb = APB()
system.cpu.apb.num_entries = 64  # 64-entry APB (default)
system.cpu.apb.line_size = 64  # 64-byte cache lines


# Create the L1 instruction and data caches
class L1ICache(Cache):
    """Simple L1 instruction cache"""

    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20
    size = "16kB"

    def connectCPU(self, cpu):
        """Connect this cache to a CPU icache port"""
        self.cpu_side = cpu.icache_port

    def connectBus(self, bus):
        """Connect this cache to a memory-side bus"""
        self.mem_side = bus.cpu_side_ports


class L1DCache(Cache):
    """Simple L1 data cache"""

    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20
    size = "64kB"

    def connectCPU(self, cpu):
        """Connect this cache to a CPU dcache port"""
        self.cpu_side = cpu.dcache_port

    def connectBus(self, bus):
        """Connect this cache to a memory-side bus"""
        self.mem_side = bus.cpu_side_ports


class L2Cache(Cache):
    """Simple L2 cache"""

    assoc = 8
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 20
    tgts_per_mshr = 12
    size = "256kB"

    def connectCPUSideBus(self, bus):
        """Connect this cache to the CPU-side bus"""
        self.cpu_side = bus.mem_side_ports

    def connectMemSideBus(self, bus):
        """Connect this cache to the memory-side bus"""
        self.mem_side = bus.cpu_side_ports


system.cpu.icache = L1ICache()
system.cpu.dcache = L1DCache()

# Hook up CPU and caches
system.cpu.icache.connectCPU(system.cpu)
system.cpu.dcache.connectCPU(system.cpu)

# Turn port into bus for multiple L1 caches
system.l2bus = L2XBar()

# Hook the L1 caches to the l2 bus
system.cpu.icache.connectBus(system.l2bus)
system.cpu.dcache.connectBus(system.l2bus)

# Create the L2 cache and connect it to the L2 bus
system.l2cache = L2Cache()
system.l2cache.connectCPUSideBus(system.l2bus)

# Now we need to connect to the memory bus
system.membus = SystemXBar()
system.l2cache.connectMemSideBus(system.membus)

# Create interrupt controller
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

# Now we need to create a process for the CPU to run
# Parse command-line arguments first
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "--cmd",
    default="tests/test-progs/hello/bin/x86/linux/hello",
    help="Binary to run",
)
parser.add_argument("--output-dir", default="m5out", help="Output directory")
parser.add_argument(
    "--dual-path",
    type=lambda x: x.lower() == "true",
    default=True,
    help="Enable dual-path execution (default: True)",
)
parser.add_argument(
    "--fetch-policy",
    default="selective",
    choices=["global", "selective"],
    help="Fetch policy: global or selective (default: selective)",
)
parser.add_argument(
    "--confidence-threshold",
    type=int,
    default=70,
    help="Confidence threshold for selective mode (default: 70)",
)
parser.add_argument(
    "--window-size",
    type=int,
    default=30,
    help="Window size for accuracy tracking (default: 30)",
)
args, remaining = parser.parse_known_args()

# Apply configuration
system.cpu.dualPathSwitcher.initial_dual_path = args.dual_path
system.cpu.dualPathSwitcher.fetch_policy = args.fetch_policy
system.cpu.dualPathSwitcher.confidence_threshold = args.confidence_threshold
system.cpu.dualPathSwitcher.window_size = args.window_size

# You can change this to your actual binary path
binary = args.cmd

# For gem5 V21 and beyond
system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary]
system.cpu.workload = process
system.cpu.createThreads()

# Create a root object
root = Root(full_system=False, system=system)

# Set output directory before instantiation
import os

os.makedirs(args.output_dir, exist_ok=True)
m5.core.setOutputDir(args.output_dir)

m5.instantiate()

# We are ready to run!
print("Beginning simulation!")
print(f"Dual-path mode: {system.cpu.dualPathSwitcher.initial_dual_path}")
print(f"Fetch policy: {system.cpu.dualPathSwitcher.fetch_policy}")
print(
    f"Confidence threshold: {system.cpu.dualPathSwitcher.confidence_threshold}"
)
print(f"Window size: {system.cpu.dualPathSwitcher.window_size}")
print(f"APB entries: {system.cpu.apb.num_entries}")
exit_event = m5.simulate()
print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
