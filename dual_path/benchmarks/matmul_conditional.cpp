/*
 * Matrix Multiplication with Conditional Logic Benchmark
 * 
 * Performs matrix multiplication with data-dependent branches.
 * Tests dual-path execution with realistic computational kernel
 * that has both predictable (loop bounds) and unpredictable 
 * (data-dependent) branch behavior.
 *
 * Region of Interest: The main matrix multiplication loop
 */

#include <cstdio>
#include <cstdlib>
#include <ctime>
#include "gem5/m5ops.h"

#define N 64  // Matrix size (64x64 = 4096 elements, ~260K branches)
#define THRESHOLD 50  // Value threshold for conditional logic

int main()
{
    int A[N][N], B[N][N], C[N][N];
    int i, j, k;
    int conditional_count = 0;
    int total_operations = 0;
    
    printf("Matrix Multiplication with Conditional Logic\n");
    printf("Matrix size: %dx%d\n", N, N);
    printf("Threshold: %d\n", THRESHOLD);
    
    // Initialize matrices with pseudo-random values
    srand(42);  // Fixed seed for reproducibility
    for (i = 0; i < N; i++) {
        for (j = 0; j < N; j++) {
            A[i][j] = rand() % 100;
            B[i][j] = rand() % 100;
            C[i][j] = 0;
        }
    }
    
    printf("Matrices initialized. Starting computation...\n");
    
    // ========== BEGIN REGION OF INTEREST ==========
    m5_work_begin(0, 0);
    m5_dump_reset_stats(0, 0);
    
    // Matrix multiplication with conditional logic
    // This creates data-dependent branches that vary in predictability
    for (i = 0; i < N; i++) {
        for (j = 0; j < N; j++) {
            for (k = 0; k < N; k++) {
                int product = A[i][k] * B[k][j];
                total_operations++;
                
                // Branch based on intermediate result
                // This creates unpredictable branches based on data values
                if (product > THRESHOLD * THRESHOLD) {
                    // High value path - use full product
                    C[i][j] += product;
                    conditional_count++;
                } else {
                    // Low value path - use reduced product
                    C[i][j] += product / 2;
                }
            }
        }
    }
    
    m5_dump_reset_stats(0, 0);
    m5_work_end(0, 0);
    // ========== END REGION OF INTEREST ==========
    
    // Verify results (prevent optimization)
    long long checksum = 0;
    for (i = 0; i < N; i++) {
        for (j = 0; j < N; j++) {
            checksum += C[i][j];
        }
    }
    
    printf("Matrix multiplication complete.\n");
    printf("Total operations: %d\n", total_operations);
    printf("Conditional (high value) operations: %d (%.1f%%)\n", 
           conditional_count, 100.0 * conditional_count / total_operations);
    printf("Checksum: %lld\n", checksum);
    
    return 0;
}
