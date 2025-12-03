# Dual-Path APB Evaluation Results
## Benchmark: matmul_conditional
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
| **Baseline** | 1,233,934 | 0.5529 | — | 24,732,100 | — |
| **16 Filter ON** | 1,233,934 | 0.5529 | 0% | 24,573,100 | **-0.6%** |
| **16 Filter OFF** | 1,233,938 | 0.5529 | 0% | 24,638,102 | -0.4% |
| **64 Filter ON** | 1,233,934 | 0.5529 | 0% | 24,569,600 | **-0.7%** |
| **64 Filter OFF** | 1,235,853 | 0.5521 | **-0.15%** | 24,758,102 | +0.1% |
| **256 Filter ON** | 1,233,934 | 0.5529 | 0% | 24,569,600 | **-0.7%** |
| **256 Filter OFF** | 1,233,938 | 0.5529 | 0% | 24,920,601 | +0.8% |

---

## Key Findings

### 1. Minimal Impact on This Benchmark
- matmul_conditional has very predictable branch patterns
- Low IPC (0.55) suggests memory-bound workload
- Dual-path provides negligible IPC improvement

### 2. Filter ON Still Reduces Recovery Cycles
- Consistent -0.6% to -0.7% reduction in recovery cycles
- Not enough to impact overall IPC significantly

### 3. Filter OFF Can Hurt Performance  
- 64 Filter OFF shows -0.15% IPC (worse than baseline)
- 256 Filter OFF increases recovery cycles by +0.8%

---

## Comparison with daxpy_progressive

| Metric | daxpy_progressive | matmul_conditional |
|--------|-------------------|-------------------|
| Baseline IPC | 1.4578 | 0.5529 |
| Best IPC Improvement | **+0.24%** | ~0% |
| Best Recovery Reduction | **-4.0%** | -0.7% |
| Workload Type | Branch-heavy | Memory-bound |

### Conclusion
The dual-path APB mechanism provides more benefit for workloads with:
- Higher branch misprediction rates
- More unpredictable branch patterns
- Higher baseline IPC (less memory-bound)

matmul_conditional's predictable branches and memory-bound nature limit the opportunity for dual-path improvements.
