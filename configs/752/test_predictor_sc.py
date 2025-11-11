import m5
from m5.objects import *

#import cache
from caches import *

#options parsing

import argparse
import sys

parser = argparse.ArgumentParser(description='A simple system with 2-level cache.')
parser.add_argument("--input",
                    help="input argument for binary target. Default: null")

parser.add_argument("--program",
                    help="The program binary/executable to run with the simulator. Default: none")


options = parser.parse_args()

#end options parsing

if options.program == None:
  print("\n\nPlease enter a program to run with --program <binary_path>\n\n")
  sys.exit(1)

system = System()

system.clk_domain = SrcClockDomain()
system.clk_domain.clock = "1GHz"
system.clk_domain.voltage_domain = VoltageDomain()

system.mem_mode = 'timing'

system.mem_ranges = [AddrRange('512MB')]

system.cpu = O3CPU()

system.membus = SystemXBar()

system.cpu.createInterruptController()

#create caches
system.cpu.dcache = L1DCache(options)
system.cpu.icache = L1ICache(options)

system.cpu.dcache.connectCPU(system.cpu)
system.cpu.icache.connectCPU(system.cpu)


#connect l1 to l2 cache with bus
system.l2bus = L2XBar()

system.cpu.icache.connectBus(system.l2bus)
system.cpu.dcache.connectBus(system.l2bus)

system.l2cache = L2Cache(options)
system.l2cache.connectCPUSideBus(system.l2bus)
system.membus = SystemXBar()
system.l2cache.connectMemSideBus(system.membus)


system.cpu.interrupts[0].pio = system.membus.mem_side_ports
system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

system.system_port = system.membus.cpu_side_ports

system.mem_ctrl = MemCtrl()

#Arbitrary memory model
system.mem_ctrl.dram = DDR3_1600_8x8()

system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports



#Setup process


binary = options.program

system.workload = SEWorkload.init_compatible(binary)

process = Process()
process.cmd = [binary, options.input] 
system.cpu.workload = process
system.cpu.createThreads()

#instantiate system and exec

root = Root(full_system = False, system = system)
m5.instantiate()

print("Beginning sim!")
exit_event = m5.simulate()

print('Exiting @ tick {} because {}'
		.format(m5.curTick(), exit_event.getCause()))
