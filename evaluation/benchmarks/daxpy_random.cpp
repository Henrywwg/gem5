/*
 * Random Branch DAXPY Benchmark
 * Modified DAXPY with consistently unpredictable branches
 *
 * This benchmark maintains a constant 50/50 split throughout execution,
 * creating consistently difficult branch prediction conditions.
 *
 * This represents the worst-case scenario for branch prediction
 * and should show the maximum benefit of dual-path execution.
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
    std::uniform_real_distribution<> probability(0.0, 1.0);

    for (int i = 0; i < N; ++i)
    {
        X[i] = dis(gen);
        Y[i] = dis(gen);
    }

    printf("Starting random branch DAXPY (N=%d)\n", N);
    printf("Branch predictability: 50%% (consistently unpredictable)\n");

    // Start measurement
    m5_dump_reset_stats(0, 0);

    // DAXPY with random 50/50 branches
    for (int i = 0; i < N; ++i)
    {
        // Random decision (50/50 split)
        if (probability(gen) < 0.5)
        {
            // Path A (50% probability)
            Y[i] = alpha * X[i] + Y[i];
        }
        else
        {
            // Path B (50% probability)
            Y[i] = (alpha + 0.1) * X[i] + Y[i];
        }
    }

    // End measurement
    m5_dump_reset_stats(0, 0);

    // Verify result (prevent optimization)
    double sum = 0;
    for (int i = 0; i < N; ++i)
    {
        sum += Y[i];
    }

    printf("Random DAXPY complete. Checksum: %lf\n", sum);

    return 0;
}
