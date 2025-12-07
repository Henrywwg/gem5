# Updated Testing Scripts - Modern gem5 Style

## Changes Made

All test scripts have been updated to use **modern gem5 configuration style** instead of the deprecated `configs/example/se.py` script.

## What Changed

### ✅ Updated Files:

1. **`configs/simple_dualpath.py`** 
   - Complete rewrite using learning_gem5 style
   - Direct Python configuration, no deprecated scripts
   - Simple O3CPU + LTAGE predictor + dual-path

2. **`configs/o3_with_caches.py`** (NEW)
   - O3CPU with L1/L2 cache hierarchy
   - Supports multiple predictors: TAGE, LTAGE, DPSTAGE
   - Configurable cache sizes

3. **`scripts/quick_test.sh`**
   - Now uses `simple_dualpath.py` instead of deprecated `se.py`
   - Cleaner invocation

4. **`scripts/extract_metrics.py`**
   - Updated stat names to match actual implementation
   - Removed non-existent stats (MSHR limits, write ports, etc.)
   - Added actual stats (APB inserts, speculative paths, etc.)

5. **`scripts/verify_dualpath.py`** (NEW)
   - Quick verification script
   - Just checks if dual-path is active

6. **`TESTING.md`**
   - Updated all examples to use new configs
   - Added config comparison section

## How to Use

### Quick Test
```bash
cd dual_path/scripts
chmod +x quick_test.sh
./quick_test.sh
```

### Manual Test (Simple)
```bash
./build/X86/gem5.opt \
    dual_path/configs/simple_dualpath.py \
    --binary=dual_path/benchmarks/bin/daxpy_progressive
```

### Manual Test (With Caches)
```bash
./build/X86/gem5.opt \
    dual_path/configs/o3_with_caches.py \
    --binary=dual_path/benchmarks/bin/matmul_conditional \
    --predictor=DPSTAGE \
    --l2-size=512kB
```

### Verify Results
```bash
python3 dual_path/scripts/verify_dualpath.py m5out/stats.txt
```

### Extract Metrics
```bash
python3 dual_path/scripts/extract_metrics.py m5out/stats.txt
```

## Key Stats to Look For

Your implementation adds these stats:
- `system.cpu.apb.hits` - APB successful recoveries
- `system.cpu.apb.misses` - APB missed, fetched from memory
- `system.cpu.apb.inserts` - Alternate paths stored in APB
- `system.cpu.apb.evictions` - APB entry replacements
- `system.cpu.apb.occupancy::mean` - Average APB utilization
- `system.cpu.fetch.alternatePathFetches` - Fetched alternate paths
- `system.cpu.speculativePathsSpawned` - Created spec paths
- `system.cpu.speculativePathsSquashed` - Killed wrong paths
- `system.cpu.speculativePathsCompleted` - Useful spec paths
- `system.cpu.branchPred.switchesToDualPath` - Switched to dual mode (DPSTAGE only)
- `system.cpu.branchPred.switchesToSinglePath` - Switched to single mode (DPSTAGE only)
- `system.cpu.branchPred.dualPathMode` - Current mode (DPSTAGE only)

## Why the Change?

gem5 deprecated `configs/example/se.py` in favor of simpler, more maintainable Python scripts. The new approach:
- ✅ Easier to understand
- ✅ More flexible
- ✅ Better documented
- ✅ Follows modern gem5 style
- ✅ No hidden magic from deprecated scripts

## Notes

- The `eval_dualpath.py` config is **legacy** - it references SimObjects (APB, DualPathSwitcher) that don't exist as separate objects. They're built into the O3CPU now.
- Use `simple_dualpath.py` or `o3_with_caches.py` instead
- All scripts tested with gem5 stable branch (2024+)
