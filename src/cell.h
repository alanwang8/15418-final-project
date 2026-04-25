#pragma once
#include <cstddef>  // offsetof, size_t

// Cell types representing functional units on a processor floorplan
enum CellType {
    ALU          = 0,
    CACHE        = 1,
    MEMORY       = 2,
    INTERCONNECT = 3
};

// Default thermal/mechanical parameters per cell type
struct CellTypeParams {
    float c;      // heat capacity
    float k;      // thermal conductivity
    float p;      // base power generation
    float alpha;  // coefficient of thermal expansion
};

static const CellTypeParams CELL_TYPE_DEFAULTS[] = {
    //  c     k     p     alpha
    { 1.0f, 0.8f, 2.0f, 0.0012f },  // ALU
    { 1.5f, 1.2f, 0.5f, 0.0008f },  // CACHE
    { 2.0f, 0.5f, 0.2f, 0.0005f },  // MEMORY
    { 0.8f, 1.5f, 0.1f, 0.0006f },  // INTERCONNECT
};

static const float T_AMBIENT = 300.0f;  // ambient / reference temperature (K)
static const float Z_AMPLIFY = 10.0f;  // amplification factor for z-displacement visualization

// A single mesh cell.
// The mesh holds two flat arrays: one for current state, one as write buffer (double-buffering).
// Layout: 9 floats + 1 int + 1 bool = 41 bytes, padded by compiler to 44 bytes (aligned to 4).
#ifdef USE_PADDED_CELL
struct alignas(64) Cell {
#else
struct Cell {
#endif
    // Thermal state
    float T;        // current temperature (K)

    // Material properties
    float c;        // heat capacity (J / K)
    float k;        // thermal conductivity
    float p;        // power generation per timestep

    // Thermal expansion
    float alpha;    // coefficient of thermal expansion

    // 3D geometry — starts flat (z=0), z evolves each timestep
    float x;        // column center position
    float y;        // row center position
    float z;        // out-of-plane displacement (3D buckling)
    float base_size; // nominal cell side length

    CellType type;
    bool is_boundary; // boundary cells are held at T_AMBIENT

#ifdef USE_PADDED_CELL
    // Pad to exactly 64 bytes (one cache line) to eliminate false sharing.
    // 9 floats(36) + int(4) + bool(1) + compiler pad(3) = 44 bytes → need 20 more.
    char _cache_pad[20];
#endif
};
