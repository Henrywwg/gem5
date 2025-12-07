# Testing Your Dual-Path Implementation

## Quick Start

The simplest way to test:

```bash
cd dual_path/scripts

# Make scripts executable
chmod +x quick_test.sh

# Run quick test (takes ~10-20 minutes)
./quick_test.sh
```

This will:
1. Build your benchmarks
2. Run both DAXPY and MatMul with O3CPU
3. Extract dual-path metrics automatically
4. Show you if APB/speculative paths are active

---

## Manual Testing

### Step 1: Run a Single Benchmark

```bash
cd /path/to/gem5

# Run with standard O3CPU config (dual-path is built-in)
./build/X86/gem5.opt \
    configs/example/se.py \
    --cpu-type=O3CPU \
    --caches \
    --l2cache \
    --cmd=dual_path/benchmarks/bin/daxpy_progressive
```

### Step 2: Check for Dual-Path Activity

```bash
# Look at the stats
less m5out/stats.txt

# Quick grep for dual-path stats
grep -E "apb|speculativePath|alternatePathFetch" m5out/stats.txt
```

**Key Stats to Look For:**

```
system.cpu.apb.hits                              # APB provided fast recovery
system.cpu.apb.misses                            # Had to fetch from memory
system.cpu.apb.inserts                           # Alternate paths stored
system.cpu.fetch.alternatePathFetches            # Fetched alternate paths
system.cpu.speculativePathsSpawned               # Created speculative paths
system.cpu.speculativePathsSquashed              # Killed wrong paths
```

### Step 3: Use Analysis Scripts

```bash
# Detailed metrics report
python3 dual_path/scripts/extract_metrics.py m5out/stats.txt

# CSV for multiple runs
python3 dual_path/scripts/extract_metrics.py \
    results/*/stats.txt \
    --csv > all_metrics.csv
```

---

## What Success Looks Like

✅ **APB is active:**
```
system.cpu.apb.hits                    1234
system.cpu.apb.misses                   456
system.cpu.apb.inserts                 1890
```

✅ **Speculative paths running:**
```
system.cpu.speculativePathsSpawned     3421
system.cpu.speculativePathsCompleted   2156
system.cpu.speculativePathsSquashed    1265
```

✅ **DPS-TAGE switching (if using DPS-TAGE predictor):**
```
system.cpu.branchPred.switchesToDualPath       15
system.cpu.branchPred.switchesToSinglePath     12
system.cpu.branchPred.dualPathMode              1
```

---

## Expected Performance Gains

Your implementation should show:

1. **Lower misprediction penalty** - APB hits recover ~2-5x faster than normal
2. **Better IPC** - 5-15% improvement on branch-heavy code
3. **High APB coverage** - 60-80% of mispredictions should hit in APB

### Benchmarks Sensitivity:

- **daxpy_progressive**: Progressive pattern, medium branch predictability → moderate gains
- **matmul_conditional**: Conditional loops → higher dual-path activation

---

## Troubleshooting

### No dual-path stats appearing?

Check that you're using **X86O3CPU**:
```bash
grep "cpu_type" m5out/config.ini
# Should show: type=X86O3CPU
```

### APB always showing 0 hits?

- Check `apb.inserts` - if 0, alternate paths not being fetched
- Might need higher branch misprediction rate
- Try with TAGE predictor for confidence estimation

### Build successful but crashes on run?

```bash
# Check for uninitialized variables
./build/X86/gem5.opt --debug-flags=Fetch,APB,Branch \
    configs/example/se.py \
    --cpu-type=O3CPU \
    --cmd=dual_path/benchmarks/bin/daxpy_progressive \
    2>&1 | less
```

---

## Comparing Baseline vs Dual-Path

To see the actual benefit, you'd compare against gem5 without dual-path (if you had that version). But since it's built-in now, focus on:

1. **APB hit rate** - Higher is better (shows alternate paths are useful)
2. **Speculative path completion rate** - Shows efficiency
3. **IPC** - Overall performance metric

---

## Advanced: Custom Test

Create custom config to tweak parameters:

```python
# my_test.py
import m5
from m5.objects import *

system = System()
system.clk_domain = SrcClockDomain(clock='2GHz',
                                    voltage_domain=VoltageDomain())
system.mem_mode = 'timing'
system.mem_ranges = [AddrRange('512MB')]

# O3CPU (dual-path built-in)
system.cpu = X86O3CPU()

# Use LTAGE for better predictions
system.cpu.branchPred = LTAGE()

# Rest of config...
```

Run:
```bash
./build/X86/gem5.opt my_test.py
```

---

## Next Steps After Testing

Once you confirm dual-path is working:

1. **Run larger benchmarks** - SPEC CPU2017, etc.
2. **Vary APB size** - Modify in src/cpu/o3/fetch.cc (APB_SIZE constant)
3. **Compare predictors** - TAGE vs LTAGE vs DPSTAGE
4. **Analyze switching behavior** - Plot dual/single path mode over time
5. **Write paper** 📝

Good luck! 🚀
