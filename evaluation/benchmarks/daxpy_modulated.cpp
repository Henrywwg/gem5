/*
 * Randomly Modulated DAXPY Benchmark
 * Modified DAXPY with branches that randomly reset progress
 *
 * The branch prediction progressively warms up from 50% to 95% predictable,
 * but randomly resets back to 50% at unpredictable intervals.
 *
 * This simulates workloads with phase changes - perfect for testing dual-path
 * execution's ability to handle sudden shifts in predictability.
 *
 * Example pattern:
 *   Iterations 0-1000:    50% -> 70% (warming)
 *   Iterations 1001:      RESET to 50%
 *   Iterations 1002-2500: 50% -> 85% (warming)
 *   Iterations 2501:      RESET to 50%
 *   ... and so on
 */

#include <cstdio>
#include <random>
#include "gem5/m5ops.h"

int main()
{
    const int N = 65536;
    static double X[N], Y[N];  // Make arrays static to avoid stack overflow
    double alpha = 0.5;

    // Progressive thresholds
    const double INITIAL_THRESHOLD = 0.50;  // 50% predictable at reset
    const double FINAL_THRESHOLD = 0.95;     // 95% predictable at peak

    // Modulation parameters
    const double RESET_PROBABILITY = 0.02;   // 2% chance of reset per iteration

    // Pre-generate reset pattern using simple C rand() to avoid C++ RNG issues in gem5
    // Create array of 0s and 1s where 1 indicates a reset should occur
    static bool reset_pattern[N];  // Make static to avoid stack overflow
    srand(42);  // Fixed seed for reproducibility

    int expected_resets = 0;
    for (int i = 0; i < N; ++i)
    {
        double r = static_cast<double>(rand()) / RAND_MAX;
        reset_pattern[i] = (r < RESET_PROBABILITY);
        if (reset_pattern[i]) expected_resets++;
    }

    // Initialize arrays with random values
    std::mt19937 gen(42);
    std::uniform_real_distribution<> dis(1, 2);
    std::uniform_real_distribution<> probability(0.0, 1.0);

    for (int i = 0; i < N; ++i)
    {
        X[i] = dis(gen);
        Y[i] = dis(gen);
    }

    printf("Starting modulated DAXPY (N=%d)\n", N);
    printf("Branch predictability: %.0f%% -> %.0f%% (with random resets)\n",
           INITIAL_THRESHOLD * 100, FINAL_THRESHOLD * 100);
    printf("Reset probability: %.1f%% per iteration\n", RESET_PROBABILITY * 100);
    printf("Pre-generated pattern has %d resets\n", expected_resets);

    // Start measurement
    m5_dump_reset_stats(0, 0);

    // Track progress with modulation
    int phase_start = 0;
    int reset_count = 0;

    // DAXPY with randomly modulated branches
    for (int i = 0; i < N; ++i)
    {
        // Check for reset using pre-generated pattern
        if (i > 0 && reset_pattern[i])
        {
            phase_start = i;
            reset_count++;
            // Debug: print first few resets
            if (reset_count <= 5) {
                printf("  Reset #%d at iteration %d\n", reset_count, i);
            }
        }

        // Calculate current threshold (linear progression from phase start)
        int iterations_in_phase = i - phase_start;
        double progress = static_cast<double>(iterations_in_phase) / N;
        double current_threshold = INITIAL_THRESHOLD +
                                   (FINAL_THRESHOLD - INITIAL_THRESHOLD) * progress;

        // Clamp to final threshold
        if (current_threshold > FINAL_THRESHOLD)
            current_threshold = FINAL_THRESHOLD;

        // Random decision with modulated bias
        if (probability(gen) < current_threshold)
        {
            // Path A (increasingly likely within each phase)
            Y[i] = alpha * X[i] + Y[i];
        }
        else
        {
            // Path B (increasingly rare within each phase)
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

    printf("Modulated DAXPY complete. Resets: %d, Checksum: %lf\n", reset_count, sum);

    return 0;
}
