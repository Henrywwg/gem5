#!/usr/bin/env python3
"""
Example: Adapted daxpy_config.py for evaluation
This shows how to modify your existing config for comprehensive evaluation
"""

from caches import *

import m5
from m5.objects import *

m5.util.addToPath("../../configs")
from common import SimpleOpts

# Add evaluation-specific options
SimpleOpts.add_option("--cpu-type", default="X86O3CPU")
SimpleOpts.add_option("--binary", default="src/hw7/daxpy_m5")
SimpleOpts.add_option("--outdir", default="m5out_O3_daxpy")

# NEW: Add options for evaluation modes
SimpleOpts.add_option(
    "--enable-dual-path",
    action="store_true",
    default=False,
    help="Enable dual-path execution with APB",
)
SimpleOpts.add_option(
    "--apb-entries",
    type=int,
    default=64,
    help="Number of APB entries (if dual-path enabled)",
)
SimpleOpts.add_option(
    "--stats-interval",
    type=int,
    default=0,
    help="Periodic stats dump interval in ticks (0=disable)",
)

opts = SimpleOpts.parse_args()


def make_cpu(name: str):
    mapping = {
        "X86O3CPU": X86O3CPU,
        "X86MinorCPU": X86MinorCPU,
    }
    if name not in mapping:
        raise ValueError(
            f"Unknown --cpu-type '{name}'. Choose: {', '.join(mapping.keys())}"
        )
    return mapping[name]()


# Cache class definitions (same as before)
class L1ICache(Cache):
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20
    size = "16kB"

    def connectCPU(self, cpu):
        self.cpu_side = cpu.icache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L1DCache(Cache):
    assoc = 2
    tag_latency = 2
    data_latency = 2
    response_latency = 2
    mshrs = 4
    tgts_per_mshr = 20
    size = "64kB"

    def connectCPU(self, cpu):
        self.cpu_side = cpu.dcache_port

    def connectBus(self, bus):
        self.mem_side = bus.cpu_side_ports


class L2Cache(Cache):
    assoc = 8
    tag_latency = 20
    data_latency = 20
    response_latency = 20
    mshrs = 20
    tgts_per_mshr = 12
    size = "256kB"

    def connectCPUSideBus(self, bus):
        self.cpu_side = bus.mem_side_ports

    def connectMemSideBus(self, bus):
        self.mem_side = bus.cpu_side_ports


system = System()

# Clock & voltage
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "2GHz"
system.clk_domain.voltage_domain = VoltageDomain()

# Memory & address space
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MiB")]

# CPU
system.cpu = make_cpu(opts.cpu_type)

# NEW: Conditionally add dual-path execution support
if opts.enable_dual_path:
    # Add APB
    system.cpu.apb = APB(num_entries=opts.apb_entries, line_size=64)

    # Add DualPathSwitcher
    system.cpu.dualPathSwitcher = DualPathSwitcher(
        window_size=100,
        high_threshold=85,
        low_threshold=70,
        initial_dual_path=True,  # Start in dual-path for cold-start evaluation
    )

    print(f"Dual-path execution ENABLED (APB entries: {opts.apb_entries})")
else:
    print("Dual-path execution DISABLED (baseline mode)")

# Cache hierarchy (same as before)
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

system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

system.system_port = system.membus.cpu_side_ports

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

binary = opts.binary
system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary]
system.cpu.workload = process
system.cpu.createThreads()

root = Root(full_system=False, system=system)

import os

os.makedirs(opts.outdir, exist_ok=True)
m5.core.setOutputDir(opts.outdir)

m5.instantiate()

print("=" * 70)
print("Beginning simulation!")
print(f"Binary: {binary}")
print(f"Output directory: {opts.outdir}")
print(
    f"Stats interval: {opts.stats_interval if opts.stats_interval > 0 else 'disabled'}"
)
print("=" * 70)

# Run simulation
exit_event = m5.simulate()

# NEW: Periodic stats dumps for temporal analysis
if opts.stats_interval > 0:
    interval = opts.stats_interval
    dump_count = 1

    while exit_event.getCause() != "exiting with last active thread context":
        print(f"[Stats Dump #{dump_count}] @ tick {m5.curTick()}")
        m5.stats.dump()
        m5.stats.reset()
        exit_event = m5.simulate(interval)
        dump_count += 1

print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")

# NEW: Print summary statistics if dual-path was enabled
if opts.enable_dual_path:
    print("\n" + "=" * 70)
    print("Dual-Path Execution Summary")
    print("=" * 70)
    print("Check stats.txt for detailed metrics:")
    print("  - system.cpu.apb.* (APB statistics)")
    print("  - system.cpu.dualPathSwitcher.* (mode switching)")
    print("  - system.cpu.commit.branchMispredicts (mispredictions)")
    print("=" * 70)
