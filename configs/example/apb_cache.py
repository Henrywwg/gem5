import argparse

from caches import *

import m5
from m5.objects import *

parser = argparse.ArgumentParser()
parser.add_argument(
    "--cpu",
    type=str,
    default="MinorCPU",
    choices=["TimingSimpleCPU", "MinorCPU", "O3CPU"],
    help="CPU model to use",
)
parser.add_argument(
    "--freq",
    type=str,
    default="1GHz",
    help="CPU clock frequency (e.g., 1GHz, 2GHz, 4GHz)",
)
parser.add_argument(
    "--mem",
    type=str,
    default="HBM_2000_4H_1x64",
    choices=[
        "DDR3_1600_8x8",
        "DDR3_2133_8x8",
        "DDR4_2400_8x8",
        "DDR5_4400_4x8",
        "LPDDR2_S4_1066_1x32",
        "HBM_1000_4H_1x64",
        "HBM_2000_4H_1x64",
    ],
    help="Memory configuration to use",
)
parser.add_argument(
    "--l1i_size",
    type=str,
    default="16KiB",
    help="L1 instruction cache size",
)
parser.add_argument(
    "--l1i_assoc",
    type=int,
    default=8,
    help="L1 instruction cache associativity",
)
parser.add_argument(
    "--l1d_size",
    type=str,
    default="16KiB",
    help="L1 data cache size",
)
parser.add_argument(
    "--l1d_assoc",
    type=int,
    default=8,
    help="L1 data cache associativity",
)
parser.add_argument(
    "--l2_size",
    type=str,
    default="128KiB",
    help="L2 cache size",
)
parser.add_argument(
    "--l2_assoc",
    type=int,
    default=16,
    help="L2 cache associativity",
)
args = parser.parse_args()

# Create the system
system = System()

# Clock and voltage domains
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = args.freq
system.clk_domain.voltage_domain = VoltageDomain()

# Memory setup
system.mem_mode = "timing"
system.mem_ranges = [AddrRange("512MB")]

# Pick CPU model
if args.cpu == "TimingSimpleCPU":
    system.cpu = X86TimingSimpleCPU()
elif args.cpu == "MinorCPU":
    system.cpu = X86MinorCPU()
elif args.cpu == "O3CPU":
    system.cpu = X86O3CPU()

# Add L1 caches
system.cpu.icache = L1ICache(options=args)
system.cpu.dcache = L1DCache(options=args)
system.cpu.icache.connectCPU(system.cpu)
system.cpu.dcache.connectCPU(system.cpu)

# --- Add APB ---
# APB parameters: example, 64 entries of 64 bytes each
system.apb = APB(num_entries=64, line_size=64)

# Connect CPU fetch port to APB
system.cpu.fetch_from_apb_port = system.apb.cpu_side
system.apb.l1i_side = system.cpu.icache.cpu_side
system.cpu.apb = system.apb

# L2 bus (connects L1 caches to L2)
system.l2bus = L2XBar()
system.cpu.icache.connectBus(system.l2bus)
system.cpu.dcache.connectBus(system.l2bus)

# L2 cache
system.l2cache = L2Cache(options=args)
system.l2cache.connectCPUSideBus(system.l2bus)

# System memory bus
system.membus = SystemXBar()
system.l2cache.connectMemSideBus(system.membus)

# Interrupts (x86-specific)
system.cpu.createInterruptController()
system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

# Functional-only port
system.system_port = system.membus.cpu_side_ports

# Memory controller
system.mem_ctrl = MemCtrl()

mem_dict = {
    "DDR3_1600_8x8": DDR3_1600_8x8,
    "DDR3_2133_8x8": DDR3_2133_8x8,
    "DDR4_2400_8x8": DDR4_2400_8x8,
    "DDR5_4400_4x8": DDR5_4400_4x8,
    "LPDDR2_S4_1066_1x32": LPDDR2_S4_1066_1x32,
    "HBM_1000_4H_1x64": HBM_1000_4H_1x64,
    "HBM_2000_4H_1x64": HBM_2000_4H_1x64,
}

system.mem_ctrl.dram = mem_dict[args.mem]()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

# Workload
binary = "tests/test-progs/saxpy/saxpy"
system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary, args.options]
system.cpu.workload = process
system.cpu.createThreads()

root = Root(full_system=False, system=system)
m5.instantiate()

print("Beginning simulation with APB + caches!")
exit_event = m5.simulate()

print(f"Exiting @ tick {m5.curTick()} because {exit_event.getCause()}")
