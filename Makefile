CXX      = g++
CXXFLAGS = -O2 -std=c++17 -Wall -Wextra
OMP_FLAG = -fopenmp

SRCDIR = src
SRCS   = $(SRCDIR)/mesh.cpp $(SRCDIR)/simulator.cpp $(SRCDIR)/main.cpp

TARGET_PAR    = sim
TARGET_SER    = sim_serial
TARGET_PADDED = sim_padded

.PHONY: all parallel serial padded clean test

all: parallel serial

# Parallel build (with OpenMP)
parallel: $(SRCS) $(SRCDIR)/mesh.h $(SRCDIR)/simulator.h $(SRCDIR)/cell.h
	$(CXX) $(CXXFLAGS) $(OMP_FLAG) -o $(TARGET_PAR) $(SRCS)
	@echo "Built $(TARGET_PAR) (OpenMP enabled)"

# Serial build (no OpenMP — for correctness baseline and timing comparison)
serial: $(SRCS) $(SRCDIR)/mesh.h $(SRCDIR)/simulator.h $(SRCDIR)/cell.h
	$(CXX) $(CXXFLAGS) -o $(TARGET_SER) $(SRCS)
	@echo "Built $(TARGET_SER) (serial, no OpenMP)"

# Padded build: Cell struct aligned to 64 bytes (one cache line) to
# eliminate false sharing. Compare ./sim_padded vs ./sim to measure
# the impact of false sharing at high thread counts.
padded: $(SRCS) $(SRCDIR)/mesh.h $(SRCDIR)/simulator.h $(SRCDIR)/cell.h
	$(CXX) $(CXXFLAGS) $(OMP_FLAG) -DUSE_PADDED_CELL -o $(TARGET_PADDED) $(SRCS)
	@echo "Built $(TARGET_PADDED) (OpenMP + 64-byte padded Cell)"

# Quick correctness smoke test: 50x50 mesh, 100 steps
test: parallel serial
	@echo "=== Serial correctness test ==="
	./$(TARGET_SER) --size 50 --steps 100 --pattern hotspot1 --verbose
	@echo "=== Parallel correctness test (4 threads) ==="
	./$(TARGET_PAR) --size 50 --steps 100 --pattern hotspot1 --threads 4 --verbose
	@echo "=== Flat mode test (2D-only, no z-feedback) ==="
	./$(TARGET_PAR) --size 50 --steps 100 --pattern hotspot1 --threads 4 --flat --verbose
	@echo "=== Heatmap dump test ==="
	./$(TARGET_PAR) --size 50 --steps 100 --pattern hotspot4 --threads 4 \
		--heatmap results/test_heatmap.csv --verbose
	@echo "=== Per-thread timing test ==="
	./$(TARGET_PAR) --size 50 --steps 100 --pattern hotspot4 --threads 4 \
		--track-threads --verbose
	@echo "Tests done."

clean:
	rm -f $(TARGET_PAR) $(TARGET_SER) $(TARGET_PADDED)
	rm -f results/*.csv results/*.png results/*.gif
