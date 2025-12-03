/*
 * Progressive Warming DAXPY Benchmark
 * Modified DAXPY with branches that progressively warm up
 *
 * The branch prediction starts very difficult (50% predictable)
 * and progressively becomes easier (95% predictable at the end).
 *
 * This simulates a cold-start scenario where the branch predictor
 * gradually learns the pattern - perfect for testing dual-path
 * execution during the warming period.
 */

#include <cstdio>
#include <random>
#include "gem5/m5ops.h"

int main()
{
    const int N = 65536;
    double X[N], Y[N], alpha = 0.5;

    // Progressive thresholds
    const double INITIAL_THRESHOLD = 0.50;  // 50% predictable at start
    const double FINAL_THRESHOLD = 0.95;     // 95% predictable at end

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

    printf("Starting progressive warming DAXPY (N=%d)\n", N);
    printf("Branch predictability: %.0f%% -> %.0f%%\n",
           INITIAL_THRESHOLD * 100, FINAL_THRESHOLD * 100);

    // Start measurement
    m5_dump_reset_stats(0, 0);

    // DAXPY with progressively warming branches
    for (int i = 0; i < N; ++i)
    {
        // Calculate current threshold (linear progression)
        double progress = static_cast<double>(i) / N;
        double current_threshold = INITIAL_THRESHOLD +
                                   (FINAL_THRESHOLD - INITIAL_THRESHOLD) * progress;

        // Random decision with progressive bias
        if (probability(gen) < current_threshold)
        {
            // Path A (increasingly likely)
            Y[i] = alpha * X[i] + Y[i];
        }
        else
        {
            // Path B (increasingly rare)
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

    printf("Progressive DAXPY complete. Checksum: %lf\n", sum);

    return 0;
}
