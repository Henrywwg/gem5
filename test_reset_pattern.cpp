#include <cstdio>
#include <random>

int main() {
    const int N = 65536;
    const double RESET_PROBABILITY = 0.02;

    bool reset_pattern[N];
    std::mt19937 gen(42);
    std::uniform_real_distribution<> reset_prob(0.0, 1.0);

    for (int i = 0; i < N; ++i) {
        reset_pattern[i] = (reset_prob(gen) < RESET_PROBABILITY);
    }

    int reset_count = 0;
    for (int i = 1; i < N; ++i) {
        if (reset_pattern[i]) {
            reset_count++;
            if (reset_count <= 10) {
                printf("Reset #%d at iteration %d\n", reset_count, i);
            }
        }
    }

    printf("\nTotal resets: %d (expected ~%d)\n", reset_count, (int)(N * RESET_PROBABILITY));

    return 0;
}
