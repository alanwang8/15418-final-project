#pragma once
#include <vector>
#include <array>
#include "cell.h"

enum class FloorplanPattern {
    UNIFORM,    // All cells are CACHE type, uniform low power
    HOTSPOT_1,  // One ALU cluster at center with high power
    HOTSPOT_4,  // Four ALU clusters at quadrant centers
    RANDOM      // Randomly assigned types
};

// Neighbor indices for a 4-connected grid (N, S, E, W).
// -1 means no neighbor (boundary).
struct NeighborList {
    int idx[4];  // indices into the flat cell array; -1 = no neighbor
    int count;
};

class Mesh {
public:
    int rows;
    int cols;
    float cell_size;  // nominal cell side length

    // Primary cell state array (current timestep)
    std::vector<Cell> cells;

    // Write buffer for double-buffering (next timestep temperatures)
    std::vector<float> T_buf;

    // SoA temperature array: dense floats for fast neighbor reads
    std::vector<float> T_flat;

    // Precomputed conductances: cond_[i*4+n] = min(ki,kj)/dist3D(i,j)
    std::vector<float> cond_;

    // Precomputed neighbor lists (stable for structured grid)
    std::vector<NeighborList> neighbors;

    Mesh(int rows, int cols, float cell_size = 1.0f, int nthreads = 1);

    // Initialize cell material properties from a floorplan pattern.
    // Seeds the RNG with `seed` for reproducibility of RANDOM pattern.
    void initFloorplan(FloorplanPattern pattern, unsigned seed = 42);

    // Access cell at (row, col)
    Cell& at(int r, int c) { return cells[r * cols + c]; }
    const Cell& at(int r, int c) const { return cells[r * cols + c]; }
    int idx(int r, int c) const { return r * cols + c; }

    int totalCells() const { return rows * cols; }

private:
    void buildNeighbors();
    void setTypedCell(Cell& cell, CellType type, float power_multiplier = 1.0f);
};
