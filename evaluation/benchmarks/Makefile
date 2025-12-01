# Makefile for DAXPY Evaluation Benchmarks
# Compiles test binaries for dual-path execution evaluation

# gem5 configuration
GEM5_ROOT = $(shell pwd)/../..
M5_LIB = $(GEM5_ROOT)/util/m5/build/x86/out/libm5.a
M5_INCLUDE = $(GEM5_ROOT)/include

# C++ compiler
CXX = g++
CXXFLAGS = -std=c++20 -O3

# Output directory
OUT_DIR = bin

# Targets
TARGETS = daxpy_baseline daxpy_progressive daxpy_random

# Default: build all
all: $(OUT_DIR) $(TARGETS)

# Create output directory
$(OUT_DIR):
	mkdir -p $(OUT_DIR)

# Baseline DAXPY (predictable)
daxpy_baseline: $(OUT_DIR)/daxpy_baseline

$(OUT_DIR)/daxpy_baseline: daxpy_baseline.cpp
	$(CXX) $(CXXFLAGS) -I$(M5_INCLUDE) -o $@ $< $(M5_LIB)
	@echo "Built: $@ (Baseline - predictable branches)"

# Progressive DAXPY (warming up - KEY TEST!)
daxpy_progressive: $(OUT_DIR)/daxpy_progressive

$(OUT_DIR)/daxpy_progressive: daxpy_progressive.cpp
	$(CXX) $(CXXFLAGS) -I$(M5_INCLUDE) -o $@ $< $(M5_LIB)
	@echo "Built: $@ (Progressive - cold start to warm up)"

# Random DAXPY (worst case for prediction)
daxpy_random: $(OUT_DIR)/daxpy_random

$(OUT_DIR)/daxpy_random: daxpy_random.cpp
	$(CXX) $(CXXFLAGS) -I$(M5_INCLUDE) -o $@ $< $(M5_LIB)
	@echo "Built: $@ (Random - consistently unpredictable)"

# Clean
clean:
	rm -rf $(OUT_DIR)

# Help
help:
	@echo "DAXPY Evaluation Benchmarks"
	@echo "============================"
	@echo ""
	@echo "Targets:"
	@echo "  all              - Build all benchmarks (default)"
	@echo "  daxpy_baseline   - Baseline DAXPY (predictable)"
	@echo "  daxpy_progressive- Progressive DAXPY (warming up) - KEY TEST!"
	@echo "  daxpy_random     - Random DAXPY (worst case)"
	@echo "  clean            - Remove all binaries"
	@echo ""
	@echo "Usage:"
	@echo "  make               # Build all"
	@echo "  make daxpy_progressive  # Build only progressive"
	@echo "  make clean         # Clean up"
	@echo ""
	@echo "Running in gem5:"
	@echo "  ./evaluation/quick_eval.sh evaluation/benchmarks/bin/daxpy_baseline"
	@echo "  ./evaluation/quick_eval.sh evaluation/benchmarks/bin/daxpy_progressive"
	@echo "  ./evaluation/quick_eval.sh evaluation/benchmarks/bin/daxpy_random"

.PHONY: all clean help daxpy_baseline daxpy_progressive daxpy_random
