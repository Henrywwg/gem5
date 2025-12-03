# Dual-Path APB Evaluation Results
## Benchmark: daxpy_progressive
## Date: December 2, 2025

### Configuration
- **Switching Mode:** Confidence-based
- **Confidence Threshold:** 70%
- **I-cache Filter:** Tested ON and OFF
- **APB Sizes:** 16, 64, 256 entries
- **APB Read Latency:** 3 cycles
- **APB Write Latency:** 2 cycles

---

## Summary Table

| Config | CPU Cycles | IPC | IPC Change | Recovery Cycles | Recovery Change |
|--------|------------|-----|------------|-----------------|-----------------|
| **Baseline** | 7,996,616 | 1.4578 | — | 59,371,670 | — |
| **16 Filter ON** | 7,986,852 | 1.4596 | +0.12% | 56,981,691 | **-4.0%** |
| **16 Filter OFF** | 7,995,096 | 1.4581 | +0.02% | 59,406,195 | +0.06% |
| **64 Filter ON** | 7,977,520 | **1.4613** | **+0.24%** | 57,607,191 | **-3.0%** |
| **64 Filter OFF** | 7,987,194 | 1.4595 | +0.12% | 60,563,686 | +2.0% |
| **256 Filter ON** | 7,977,520 | **1.4613** | **+0.24%** | 57,499,190 | **-3.2%** |
| **256 Filter OFF** | 7,986,833 | 1.4596 | +0.12% | 60,137,682 | +1.3% |

---

## Detailed Metrics

| Config | Alt Fetches | APB Hits | APB Misses | Hit Rate | Reuse Factor |
|--------|-------------|----------|------------|----------|--------------|
| **Baseline** | 0 | 0 | 13,411 | — | — |
| **16 Filter ON** | 107 | 944 | 11,702 | 7.46% | 8.8x |
| **16 Filter OFF** | 4,428 | 5,401 | 7,218 | 42.80% | 1.2x |
| **64 Filter ON** | 106 | 1,146 | 11,485 | 9.07% | 10.8x |
| **64 Filter OFF** | 1,249 | 7,423 | 5,175 | 58.92% | 5.9x |
| **256 Filter ON** | 105 | 1,155 | 11,476 | 9.14% | 11.0x |
| **256 Filter OFF** | 869 | 7,983 | 4,601 | 63.44% | 9.2x |

---

## Key Findings

### 1. I-Cache Filter is Critical
- **Filter ON reduces recovery cycles** by 3-4% vs baseline
- **Filter OFF increases recovery cycles** by 0.06-2% (worse than baseline!)
- The filter prevents wasted memory bandwidth on paths already in I-cache

### 2. Best Configuration: 64 or 256 Entries with Filter ON
- Both achieve **+0.24% IPC improvement**
- 64 entries is sufficient - no benefit from 256 entries
- Very few alternate path fetches needed (~105-107)

### 3. Higher Hit Rate ≠ Better Performance
- Filter OFF has much higher hit rates (42-63%)
- But the overhead of fetching all those paths hurts overall performance
- Filter ON with ~9% hit rate performs better due to quality over quantity

### 4. Reuse Factor Explains the Difference
- Filter ON: 11x reuse factor (each prefetch used 11 times)
- Filter OFF: 1.2-9.2x reuse factor (lower efficiency)
- Higher reuse = better use of APB entries

---

## Conclusion

The dual-path APB with I-cache filtering provides a modest but consistent **+0.24% IPC improvement** on daxpy_progressive. The key insight is that selective prefetching (only paths not in I-cache) is more effective than aggressive prefetching of all alternate paths.

**Recommended Configuration:**
- APB Size: 64 entries (sufficient, diminishing returns beyond)
- I-Cache Filter: ON (critical for performance)
- Switching Mode: Confidence-based with 70% threshold
