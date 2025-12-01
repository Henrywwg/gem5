#include <cstdio>
#include <random>

int main() {
    const int N = 65536;
    const double RESET_PROBABILITY = 0.02;  // 2%

    // Test 1: Using random_device (what the benchmark uses)
    std::random_device rd;
    std::mt19937 gen1(rd());
    std::uniform_real_distribution<> prob1(0.0, 1.0);

    int resets1 = 0;
    for (int i = 1; i < N; ++i) {
        if (prob1(gen1) < RESET_PROBABILITY) {
            resets1++;
        }
    }

    // Test 2: Using fixed seed
    std::mt19937 gen2(12345);
    std::uniform_real_distribution<> prob2(0.0, 1.0);

    int resets2 = 0;
    for (int i = 1; i < N; ++i) {
        if (prob2(gen2) < RESET_PROBABILITY) {
            resets2++;
        }
    }

    // Test 3: Simulate the actual benchmark pattern
    std::random_device rd3;
    std::mt19937 gen3(rd3());
    std::uniform_real_distribution<> prob3(0.0, 1.0);

    int resets3 = 0;
    for (int i = 0; i < N; ++i) {
        // Check for reset (like the benchmark)
        if (i > 0 && prob3(gen3) < RESET_PROBABILITY) {
            resets3++;
        }

        // Also consume a random number for branch decision (like the benchmark)
        double threshold = 0.5 + (0.45 * i / N);  // 50% -> 95%
        double branch_decision = prob3(gen3);
        // Don't need to do anything with it, just consume it
    }

    printf("Test 1 (random_device, reset only):     %d resets\n", resets1);
    printf("Test 2 (fixed seed 12345, reset only):  %d resets\n", resets2);
    printf("Test 3 (random_device, with branches):  %d resets\n", resets3);
    printf("\nExpected: ~%d resets (2%% of %d)\n", (int)(N * RESET_PROBABILITY), N);

    return 0;
}
