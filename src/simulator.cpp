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
    precomputeConductance();
}

// ---------------------------------------------------------------------------
// Precompute conductances: cond_[i*4+n] = min(ki,kj) / dist3D(i,j)
// Called once at construction (k is constant; z=0 so geometry is flat).
// ---------------------------------------------------------------------------
void Simulator::precomputeConductance() {
    const int N = mesh_.totalCells();
    const auto& cells = mesh_.cells;
    auto& cond = mesh_.cond_;

#ifdef _OPENMP
    #pragma omp parallel for schedule(static) num_threads(cfg_.nthreads)
#endif
    for (int i = 0; i < N; i++) {
        const Cell& ci = cells[i];
        const NeighborList& nl = mesh_.neighbors[i];
        for (int n = 0; n < 4; n++) {
            int j = nl.idx[n];
            if (j < 0 || n >= nl.count) {
                cond[i*4 + n] = 0.0f;
                continue;
            }
            const Cell& cj = cells[j];
            float dx = ci.x - cj.x;
            float dy = ci.y - cj.y;
            float dz = ci.z - cj.z;
            float d = std::sqrt(dx*dx + dy*dy + dz*dz);
            if (d < 1e-6f) d = 1e-6f;
            cond[i*4 + n] = std::min(ci.k, cj.k) / d;
        }
    }
}

// ---------------------------------------------------------------------------
// Thermal update — serial
// Reads T_flat[i/j], writes T_buf[i], then swaps T_flat <-> T_buf.
// ---------------------------------------------------------------------------
void Simulator::stepThermalSerial() {
    const int N = mesh_.totalCells();
    const float dt = cfg_.dt;
    const auto& cells = mesh_.cells;
    const float* T = mesh_.T_flat.data();
    const float* cond = mesh_.cond_.data();
    auto& buf = mesh_.T_buf;

    for (int i = 0; i < N; i++) {
        const Cell& ci = cells[i];
        if (ci.is_boundary) {
            buf[i] = T_AMBIENT;
            continue;
        }

        float Ti = T[i];
        float flux = ci.p;
        const NeighborList& nl = mesh_.neighbors[i];
        for (int n = 0; n < nl.count; n++) {
            int j = nl.idx[n];
            if (j < 0) continue;
            flux += cond[i*4 + n] * (T[j] - Ti);
        }
        buf[i] = Ti + dt * flux / ci.c;
    }

    std::swap(mesh_.T_flat, mesh_.T_buf);
}

// ---------------------------------------------------------------------------
// Thermal update — OpenMP parallel
// ---------------------------------------------------------------------------
void Simulator::stepThermalOMP() {
#ifdef _OPENMP
    const int N = mesh_.totalCells();
    const float dt = cfg_.dt;
    const auto& cells = mesh_.cells;
    auto& buf = mesh_.T_buf;
    const float* cond = mesh_.cond_.data();
    const int chunk = cfg_.dynamic_chunk;
    const bool track = cfg_.track_threads;
    const bool dynamic_sched = cfg_.dynamic_schedule;

    #pragma omp parallel num_threads(cfg_.nthreads)
    {
        int tid = omp_get_thread_num();
        double t_start = track ? omp_get_wtime() : 0.0;
        const float* T = mesh_.T_flat.data();

        if (dynamic_sched) {
            #pragma omp for schedule(dynamic, chunk)
            for (int i = 0; i < N; i++) {
                const Cell& ci = cells[i];
                if (ci.is_boundary) { buf[i] = T_AMBIENT; continue; }
                float Ti = T[i];
                float flux = ci.p;
                const NeighborList& nl = mesh_.neighbors[i];
                for (int n = 0; n < nl.count; n++) {
                    int j = nl.idx[n];
                    if (j < 0) continue;
                    flux += cond[i*4 + n] * (T[j] - Ti);
                }
                buf[i] = Ti + dt * flux / ci.c;
            }
        } else {
            #pragma omp for schedule(static)
            for (int i = 0; i < N; i++) {
                const Cell& ci = cells[i];
                if (ci.is_boundary) { buf[i] = T_AMBIENT; continue; }
                float Ti = T[i];
                float flux = ci.p;
                const NeighborList& nl = mesh_.neighbors[i];
                for (int n = 0; n < nl.count; n++) {
                    int j = nl.idx[n];
                    if (j < 0) continue;
                    flux += cond[i*4 + n] * (T[j] - Ti);
                }
                buf[i] = Ti + dt * flux / ci.c;
            }
        }

        if (track) {
            double elapsed = (omp_get_wtime() - t_start) * 1000.0;
            thread_thermal_acc_[tid] += elapsed;
        }
    }

    std::swap(mesh_.T_flat, mesh_.T_buf);

#else
    stepThermalSerial();
#endif
}

// ---------------------------------------------------------------------------
// Geometry update — serial
// Reads T_flat[i], writes cells[i].z.
// ---------------------------------------------------------------------------
void Simulator::stepGeometrySerial() {
    const int N = mesh_.totalCells();
    const float* T = mesh_.T_flat.data();
    for (int i = 0; i < N; i++) {
        Cell& c = mesh_.cells[i];
        float dT = T[i] - T_AMBIENT;
        c.z = c.alpha * dT * c.base_size * Z_AMPLIFY;
    }
}

// ---------------------------------------------------------------------------
// Geometry update — OpenMP parallel
// ---------------------------------------------------------------------------
void Simulator::stepGeometryOMP() {
#ifdef _OPENMP
    const int N = mesh_.totalCells();
    const float* T = mesh_.T_flat.data();
    #pragma omp parallel for schedule(static) num_threads(cfg_.nthreads)
    for (int i = 0; i < N; i++) {
        Cell& c = mesh_.cells[i];
        float dT = T[i] - T_AMBIENT;
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
    if (cfg_.flat_mode) return;
    if (cfg_.use_openmp && cfg_.nthreads > 1)
        stepGeometryOMP();
    else
        stepGeometrySerial();
}

// ---------------------------------------------------------------------------
// Memory bandwidth probe (STREAM-style triad)
// ---------------------------------------------------------------------------
double Simulator::measureBandwidthGBs() const {
    using Clock = std::chrono::high_resolution_clock;
    using ds    = std::chrono::duration<double>;

    const int N = mesh_.totalCells();
    const int rep = 5;
    std::vector<float> a(N, 1.0f), b(N, 2.0f), c(N, 0.5f);
    const float scalar = 1.3f;

    for (int i = 0; i < N; i++) a[i] = b[i] * scalar + c[i];

    auto t0 = Clock::now();
    for (int r = 0; r < rep; r++)
        for (int i = 0; i < N; i++) a[i] = b[i] * scalar + c[i];
    auto t1 = Clock::now();

    double sec = ds(t1 - t0).count();
    double bytes = (double)rep * N * 12.0;
    return bytes / sec / 1e9;
}

// ---------------------------------------------------------------------------
// Full simulation run with timing
// ---------------------------------------------------------------------------
SimResult Simulator::run() {
    SimResult result{};
    result.thread_stats.resize(cfg_.nthreads);

    std::fill(thread_thermal_acc_.begin(), thread_thermal_acc_.end(), 0.0);

    using Clock = std::chrono::high_resolution_clock;
    using ms = std::chrono::duration<double, std::milli>;

    auto t_total_start = Clock::now();

    for (int step = 0; step < cfg_.steps; step++) {
        auto t0 = Clock::now();
        stepThermal();
        auto t1 = Clock::now();
        result.thermal_ms += ms(t1 - t0).count();

        stepGeometry();
        auto t2 = Clock::now();
        result.geometry_ms += ms(t2 - t1).count();
    }

    result.total_ms = ms(Clock::now() - t_total_start).count();

    for (int t = 0; t < cfg_.nthreads; t++)
        result.thread_stats[t].thermal_ms = thread_thermal_acc_[t];

    // Final stats read from T_flat (authoritative after ping-pong)
    const float* T = mesh_.T_flat.data();
    float T_max = T_AMBIENT, T_sum = 0.0f;
    const int N = mesh_.totalCells();
    for (int i = 0; i < N; i++) {
        if (T[i] > T_max) T_max = T[i];
        T_sum += T[i];
    }
    result.T_max  = T_max;
    result.T_mean = T_sum / N;

    if (!cfg_.heatmap_out.empty())
        dumpHeatmap(cfg_.heatmap_out);

    return result;
}

// ---------------------------------------------------------------------------
// Heatmap dump: writes rows x cols CSV
// ---------------------------------------------------------------------------
void Simulator::dumpHeatmap(const std::string& path) const {
    std::ofstream f(path);
    if (!f.is_open())
        throw std::runtime_error("Cannot open heatmap output: " + path);
    f << "row,col,T,z,type\n";
    const float* T = mesh_.T_flat.data();
    for (int r = 0; r < mesh_.rows; r++)
        for (int c = 0; c < mesh_.cols; c++) {
            int i = mesh_.idx(r, c);
            const Cell& cell = mesh_.cells[i];
            f << r << ',' << c << ',' << T[i] << ',' << cell.z
              << ',' << static_cast<int>(cell.type) << '\n';
        }
}
