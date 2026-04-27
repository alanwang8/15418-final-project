#pragma once
#include "mesh.h"
#include <vector>
#include <string>

// Per-thread timing data for load-balance analysis
struct ThreadStats {
    double thermal_ms;   // time spent in thermal update
    double geometry_ms;  // time spent in geometry update
};

// Configuration for a simulation run
struct SimConfig {
    int    steps       = 500;
    float  dt          = 0.01f;
    int    nthreads    = 1;
    bool   use_openmp  = true;
    bool   dynamic_schedule = false; // false = static, true = dynamic
    int    dynamic_chunk    = 64;
    int    stats_interval   = 0;     // dump stats every N steps (0 = only at end)
    bool   flat_mode   = false;      // if true, skip geometry update (z stays 0; 2D-only conductance)
    bool   track_threads = false;    // collect per-thread wall-time stats
    int    cond_interval    = 0;     // kept for CLI compat; unused in run loop
    std::string heatmap_out;         // path to dump final T grid CSV; empty = skip
};

// Timing results for one complete run
struct SimResult {
    double total_ms;            // wall clock for all steps
    double thermal_ms;          // cumulative thermal update time
    double geometry_ms;         // cumulative geometry update time
    float  T_max;               // max temperature at end
    float  T_mean;              // mean temperature at end
    std::vector<ThreadStats> thread_stats; // per-thread breakdown (OpenMP only)
};

class Simulator {
public:
    explicit Simulator(Mesh& mesh, const SimConfig& cfg);

    // Run the full simulation. Returns timing + stats.
    SimResult run();

    // Measure approximate memory bandwidth using a streaming array benchmark.
    // Returns estimated read+write bandwidth in GB/s.
    double measureBandwidthGBs() const;

    // Single-step accessors for debugging/visualization
    void stepThermal();
    void stepGeometry();

private:
    Mesh&       mesh_;
    SimConfig   cfg_;

    // Per-thread cumulative wall times (accumulated across all steps)
    std::vector<double> thread_thermal_acc_;

    void stepThermalSerial();
    void stepThermalOMP();
    void stepGeometrySerial();
    void stepGeometryOMP();
    void precomputeConductance();

    void dumpHeatmap(const std::string& path) const;
};
