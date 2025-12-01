/*
 * Baseline DAXPY Benchmark
 * Standard DAXPY (Double-precision A*X Plus Y) operation
 * Y = a*X + Y
 *
 * This is the baseline version with predictable behavior
 * for comparing against dual-path execution performance.
 */

#include <cstdio>
#include <random>
#include "gem5/m5ops.h"

int main()
{
    const int N = 65536;
    double X[N], Y[N], alpha = 0.5;

    // Initialize with random values
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<> dis(1, 2);

    for (int i = 0; i < N; ++i)
    {
        X[i] = dis(gen);
        Y[i] = dis(gen);
    }

    printf("Starting baseline DAXPY (N=%d)\n", N);

    // Start measurement
    m5_dump_reset_stats(0, 0);

    // Standard DAXPY operation (no branches)
    for (int i = 0; i < N; ++i)
    {
        Y[i] = alpha * X[i] + Y[i];
    }

    // End measurement
    m5_dump_reset_stats(0, 0);

    // Verify result (prevent optimization)
    double sum = 0;
    for (int i = 0; i < N; ++i)
    {
        sum += Y[i];
    }

    printf("Baseline DAXPY complete. Checksum: %lf\n", sum);

    return 0;
}
