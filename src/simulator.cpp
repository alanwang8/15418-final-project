#include "simulator.h"
#include <cmath>
#include <fstream>
#include <chrono>
#include <numeric>
#include <algorithm>
#include <stdexcept>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

Simulator::Simulator(Mesh& mesh, const SimConfig& cfg)
    : mesh_(mesh), cfg_(cfg),
      thread_thermal_acc_(cfg.nthreads, 0.0)
{
}

// ---------------------------------------------------------------------------
// Helper: 3D Euclidean distance between two cells
// ---------------------------------------------------------------------------
static inline float dist3D(const Cell& a, const Cell& b) {
    float dx = a.x - b.x;
    float dy = a.y - b.y;
    float dz = a.z - b.z;
    return std::sqrt(dx*dx + dy*dy + dz*dz);
}

// ---------------------------------------------------------------------------
// Thermal update — serial
// Reads cells[i].T, writes mesh_.T_buf[i], then swaps.
// Formula: T_i^new = T_i + dt*(p_i + Σ k_ij*(T_j - T_i)) / c_i
// where k_ij = min(k_i, k_j) / dist3D(i,j)
// ---------------------------------------------------------------------------
void Simulator::stepThermalSerial() {
    const int N = mesh_.totalCells();
    const float dt = cfg_.dt;
    const auto& cells = mesh_.cells;
    auto& buf = mesh_.T_buf;

    for (int i = 0; i < N; i++) {
        const Cell& ci = cells[i];
        if (ci.is_boundary) {
            buf[i] = T_AMBIENT;
            continue;
        }

        float flux = ci.p;
        const NeighborList& nl = mesh_.neighbors[i];
        for (int n = 0; n < nl.count; n++) {
            int j = nl.idx[n];
            if (j < 0) continue;
            const Cell& cj = cells[j];
            float d = dist3D(ci, cj);
            if (d < 1e-6f) d = 1e-6f;
            float kij = std::min(ci.k, cj.k) / d;
            flux += kij * (cj.T - ci.T);
        }
        buf[i] = ci.T + dt * flux / ci.c;
    }

    // Swap buffer into cells
    for (int i = 0; i < N; i++)
        mesh_.cells[i].T = buf[i];
}

// ---------------------------------------------------------------------------
// Thermal update — OpenMP parallel
// When cfg_.track_threads is set, records per-thread wall time in
// thread_thermal_acc_ (accumulated across all calls).
// ---------------------------------------------------------------------------
void Simulator::stepThermalOMP() {
#ifdef _OPENMP
    const int N = mesh_.totalCells();
    const float dt = cfg_.dt;
    const auto& cells = mesh_.cells;
    auto& buf = mesh_.T_buf;
    const int chunk = cfg_.dynamic_chunk;
    const bool track = cfg_.track_threads;
    const bool dynamic_sched = cfg_.dynamic_schedule;

    #pragma omp parallel num_threads(cfg_.nthreads)
    {
        int tid = omp_get_thread_num();
        double t_start = track ? omp_get_wtime() : 0.0;

        if (dynamic_sched) {
            #pragma omp for schedule(dynamic, chunk)
            for (int i = 0; i < N; i++) {
                const Cell& ci = cells[i];
                if (ci.is_boundary) { buf[i] = T_AMBIENT; continue; }
                float flux = ci.p;
                const NeighborList& nl = mesh_.neighbors[i];
                for (int n = 0; n < nl.count; n++) {
                    int j = nl.idx[n];
                    if (j < 0) continue;
                    const Cell& cj = cells[j];
                    float d = dist3D(ci, cj);
                    if (d < 1e-6f) d = 1e-6f;
                    float kij = std::min(ci.k, cj.k) / d;
                    flux += kij * (cj.T - ci.T);
                }
                buf[i] = ci.T + dt * flux / ci.c;
            }
        } else {
            #pragma omp for schedule(static)
            for (int i = 0; i < N; i++) {
                const Cell& ci = cells[i];
                if (ci.is_boundary) { buf[i] = T_AMBIENT; continue; }
                float flux = ci.p;
                const NeighborList& nl = mesh_.neighbors[i];
                for (int n = 0; n < nl.count; n++) {
                    int j = nl.idx[n];
                    if (j < 0) continue;
                    const Cell& cj = cells[j];
                    float d = dist3D(ci, cj);
                    if (d < 1e-6f) d = 1e-6f;
                    float kij = std::min(ci.k, cj.k) / d;
                    flux += kij * (cj.T - ci.T);
                }
                buf[i] = ci.T + dt * flux / ci.c;
            }
        }

        if (track) {
            double elapsed = (omp_get_wtime() - t_start) * 1000.0;
            // Atomic accumulation into per-thread slot (no race: each thread
            // writes only to its own slot)
            thread_thermal_acc_[tid] += elapsed;
        }
    }

    // Swap: write T_buf back to cells (also parallelized)
    #pragma omp parallel for schedule(static) num_threads(cfg_.nthreads)
    for (int i = 0; i < N; i++)
        mesh_.cells[i].T = buf[i];

#else
    stepThermalSerial();
#endif
}

// ---------------------------------------------------------------------------
// Geometry update — serial
// z_i = alpha_i * (T_i - T_ref) * base_size * Z_AMPLIFY
// Models 3D out-of-plane buckling: hot cells rise above the original plane.
// This updated z then feeds back into dist3D() in the next thermal step,
// slightly increasing conductance between elevated neighbors.
// ---------------------------------------------------------------------------
void Simulator::stepGeometrySerial() {
    const int N = mesh_.totalCells();
    for (int i = 0; i < N; i++) {
        Cell& c = mesh_.cells[i];
        float dT = c.T - T_AMBIENT;
        c.z = c.alpha * dT * c.base_size * Z_AMPLIFY;
    }
}

// ---------------------------------------------------------------------------
// Geometry update — OpenMP parallel
// ---------------------------------------------------------------------------
void Simulator::stepGeometryOMP() {
#ifdef _OPENMP
    const int N = mesh_.totalCells();
    #pragma omp parallel for schedule(static) num_threads(cfg_.nthreads)
    for (int i = 0; i < N; i++) {
        Cell& c = mesh_.cells[i];
        float dT = c.T - T_AMBIENT;
        c.z = c.alpha * dT * c.base_size * Z_AMPLIFY;
    }
#else
    stepGeometrySerial();
#endif
}

// ---------------------------------------------------------------------------
// Public single-step wrappers
// ---------------------------------------------------------------------------
void Simulator::stepThermal() {
    if (cfg_.use_openmp && cfg_.nthreads > 1)
        stepThermalOMP();
    else
        stepThermalSerial();
}

void Simulator::stepGeometry() {
    if (cfg_.flat_mode) return;  // skip geometry in flat mode (z stays 0)
    if (cfg_.use_openmp && cfg_.nthreads > 1)
        stepGeometryOMP();
    else
        stepGeometrySerial();
}

// ---------------------------------------------------------------------------
// Memory bandwidth probe (STREAM-style)
// Allocates a temporary array sized to the mesh and performs a timed
// triad (a[i] = b[i] * scalar + c[i]).  Returns GB/s (read+write).
// ---------------------------------------------------------------------------
double Simulator::measureBandwidthGBs() const {
    using Clock = std::chrono::high_resolution_clock;
    using ds    = std::chrono::duration<double>;

    const int N = mesh_.totalCells();
    const int rep = 5;
    std::vector<float> a(N, 1.0f), b(N, 2.0f), c(N, 0.5f);
    const float scalar = 1.3f;

    // Warm up caches
    for (int i = 0; i < N; i++) a[i] = b[i] * scalar + c[i];

    auto t0 = Clock::now();
    for (int r = 0; r < rep; r++)
        for (int i = 0; i < N; i++) a[i] = b[i] * scalar + c[i];
    auto t1 = Clock::now();

    double sec = ds(t1 - t0).count();
    // Bytes per iteration: read b (4B) + read c (4B) + write a (4B) = 12B per element
    double bytes = (double)rep * N * 12.0;
    return bytes / sec / 1e9;
}

// ---------------------------------------------------------------------------
// Full simulation run with timing
// ---------------------------------------------------------------------------
SimResult Simulator::run() {
    SimResult result{};
    result.thread_stats.resize(cfg_.nthreads);

    // Reset per-thread accumulators
    std::fill(thread_thermal_acc_.begin(), thread_thermal_acc_.end(), 0.0);

    using Clock = std::chrono::high_resolution_clock;
    using ms = std::chrono::duration<double, std::milli>;

    auto t_total_start = Clock::now();

    for (int step = 0; step < cfg_.steps; step++) {
        // --- Thermal update ---
        auto t0 = Clock::now();
        stepThermal();
        auto t1 = Clock::now();
        result.thermal_ms += ms(t1 - t0).count();

        // --- Geometry update (skipped in flat mode) ---
        stepGeometry();
        auto t2 = Clock::now();
        result.geometry_ms += ms(t2 - t1).count();
    }

    result.total_ms = ms(Clock::now() - t_total_start).count();

    // Copy per-thread stats
    for (int t = 0; t < cfg_.nthreads; t++)
        result.thread_stats[t].thermal_ms = thread_thermal_acc_[t];

    // Compute final stats
    float T_max = T_AMBIENT, T_sum = 0.0f;
    for (const auto& c : mesh_.cells) {
        T_max = std::max(T_max, c.T);
        T_sum += c.T;
    }
    result.T_max  = T_max;
    result.T_mean = T_sum / mesh_.totalCells();

    if (!cfg_.heatmap_out.empty())
        dumpHeatmap(cfg_.heatmap_out);

    return result;
}

// ---------------------------------------------------------------------------
// Heatmap dump: writes rows x cols CSV of temperatures + z-displacements
// Format: row,col,T,z,type
// ---------------------------------------------------------------------------
void Simulator::dumpHeatmap(const std::string& path) const {
    std::ofstream f(path);
    if (!f.is_open())
        throw std::runtime_error("Cannot open heatmap output: " + path);
    f << "row,col,T,z,type\n";
    for (int r = 0; r < mesh_.rows; r++)
        for (int c = 0; c < mesh_.cols; c++) {
            const Cell& cell = mesh_.at(r, c);
            f << r << ',' << c << ',' << cell.T << ',' << cell.z
              << ',' << static_cast<int>(cell.type) << '\n';
        }
}
