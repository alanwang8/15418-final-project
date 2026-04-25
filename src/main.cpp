#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <stdexcept>
#include <cstdlib>
#include <chrono>
#include "mesh.h"
#include "simulator.h"

static void printUsage(const char* prog) {
    std::cerr
        << "Usage: " << prog << " [options]\n"
        << "  --size <N>          NxN mesh (default 100)\n"
        << "  --rows <R>          rows (overrides --size)\n"
        << "  --cols <C>          cols (overrides --size)\n"
        << "  --threads <T>       OpenMP thread count (default 1)\n"
        << "  --steps <S>         timesteps (default 500)\n"
        << "  --dt <dt>           timestep size (default 0.01)\n"
        << "  --pattern <P>       uniform|hotspot1|hotspot4|random (default uniform)\n"
        << "  --schedule <S>      static|dynamic (default static)\n"
        << "  --chunk <C>         dynamic schedule chunk size (default 64)\n"
        << "  --serial            force serial (no OpenMP)\n"
        << "  --flat              skip geometry update (2D-only, z stays 0)\n"
        << "  --track-threads     record per-thread timing (printed with --verbose)\n"
        << "  --bandwidth         measure and print memory bandwidth then exit\n"
        << "  --output <file>     append CSV timing row to file\n"
        << "  --heatmap <file>    dump final T/z grid as CSV\n"
        << "  --seed <N>          RNG seed for random pattern (default 42)\n"
        << "  --verbose           print progress\n";
}

static FloorplanPattern parsePattern(const std::string& s) {
    if (s == "uniform")   return FloorplanPattern::UNIFORM;
    if (s == "hotspot1")  return FloorplanPattern::HOTSPOT_1;
    if (s == "hotspot4")  return FloorplanPattern::HOTSPOT_4;
    if (s == "random")    return FloorplanPattern::RANDOM;
    throw std::invalid_argument("Unknown pattern: " + s);
}

int main(int argc, char* argv[]) {
    int size     = 100;
    int rows_arg = 0, cols_arg = 0;
    int nthreads = 1;
    int steps    = 500;
    float dt     = 0.01f;
    std::string pattern_str = "uniform";
    std::string schedule_str = "static";
    int chunk    = 64;
    bool serial  = false;
    bool flat_mode = false;
    bool track_threads = false;
    bool do_bandwidth = false;
    std::string output_file;
    std::string heatmap_file;
    unsigned seed = 42;
    bool verbose = false;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        auto nextArg = [&]() -> std::string {
            if (i + 1 >= argc) throw std::invalid_argument("Missing value for " + arg);
            return argv[++i];
        };
        if      (arg == "--size")          size         = std::stoi(nextArg());
        else if (arg == "--rows")          rows_arg     = std::stoi(nextArg());
        else if (arg == "--cols")          cols_arg     = std::stoi(nextArg());
        else if (arg == "--threads")       nthreads     = std::stoi(nextArg());
        else if (arg == "--steps")         steps        = std::stoi(nextArg());
        else if (arg == "--dt")            dt           = std::stof(nextArg());
        else if (arg == "--pattern")       pattern_str  = nextArg();
        else if (arg == "--schedule")      schedule_str = nextArg();
        else if (arg == "--chunk")         chunk        = std::stoi(nextArg());
        else if (arg == "--serial")        serial       = true;
        else if (arg == "--flat")          flat_mode    = true;
        else if (arg == "--track-threads") track_threads = true;
        else if (arg == "--bandwidth")     do_bandwidth = true;
        else if (arg == "--output")        output_file  = nextArg();
        else if (arg == "--heatmap")       heatmap_file = nextArg();
        else if (arg == "--seed")          seed         = (unsigned)std::stoul(nextArg());
        else if (arg == "--verbose")       verbose      = true;
        else if (arg == "--help" || arg == "-h") { printUsage(argv[0]); return 0; }
        else { std::cerr << "Unknown argument: " << arg << "\n"; printUsage(argv[0]); return 1; }
    }

    int R = rows_arg ? rows_arg : size;
    int C = cols_arg ? cols_arg : size;
    FloorplanPattern pattern = parsePattern(pattern_str);
    bool dynamic_sched = (schedule_str == "dynamic");

    if (verbose) {
        std::cerr << "[sim] " << R << "x" << C << " mesh, "
                  << nthreads << " thread(s), " << steps << " steps, "
                  << "pattern=" << pattern_str
                  << ", schedule=" << schedule_str
                  << (flat_mode ? ", flat" : ", 3D") << "\n";
#ifdef USE_PADDED_CELL
        std::cerr << "[sim] Cell layout: PADDED (64-byte aligned, sizeof(Cell)=" << sizeof(Cell) << ")\n";
#else
        std::cerr << "[sim] Cell layout: DEFAULT (sizeof(Cell)=" << sizeof(Cell) << ")\n";
#endif
    }

    Mesh mesh(R, C, 1.0f);
    mesh.initFloorplan(pattern, seed);

    SimConfig cfg;
    cfg.steps            = steps;
    cfg.dt               = dt;
    cfg.nthreads         = nthreads;
    cfg.use_openmp       = !serial;
    cfg.dynamic_schedule = dynamic_sched;
    cfg.dynamic_chunk    = chunk;
    cfg.flat_mode        = flat_mode;
    cfg.track_threads    = track_threads;
    cfg.heatmap_out      = heatmap_file;

    Simulator sim(mesh, cfg);

    // --bandwidth: measure streaming bandwidth and exit
    if (do_bandwidth) {
        double bw = sim.measureBandwidthGBs();
        std::cout << "bandwidth_GBs=" << bw << "\n";
        if (verbose)
            std::cerr << "[sim] Streaming bandwidth: " << bw << " GB/s\n";
        return 0;
    }

    SimResult result = sim.run();

    if (verbose) {
        std::cerr << "[sim] Done. Total=" << result.total_ms << " ms"
                  << "  thermal=" << result.thermal_ms << " ms"
                  << "  geometry=" << result.geometry_ms << " ms"
                  << "  T_max=" << result.T_max << " K"
                  << "  T_mean=" << result.T_mean << " K\n";
        if (track_threads && nthreads > 1) {
            std::cerr << "[sim] Per-thread thermal ms (cumulative over " << steps << " steps):\n";
            double total = 0.0;
            for (int t = 0; t < nthreads; t++) total += result.thread_stats[t].thermal_ms;
            double avg = total / nthreads;
            for (int t = 0; t < nthreads; t++) {
                double ms_t = result.thread_stats[t].thermal_ms;
                std::cerr << "  thread " << t << ": " << ms_t << " ms"
                          << "  (" << (ms_t / avg * 100.0) << "% of avg)\n";
            }
        }
    }

    // Print summary to stdout for easy parsing
    std::cout << "total_ms="     << result.total_ms
              << " thermal_ms="  << result.thermal_ms
              << " geometry_ms=" << result.geometry_ms
              << " T_max="       << result.T_max
              << " T_mean="      << result.T_mean
              << "\n";

    // Append CSV row to output file
    if (!output_file.empty()) {
        bool write_header = false;
        {
            std::ifstream check(output_file);
            write_header = !check.good();
        }
        std::ofstream f(output_file, std::ios::app);
        if (!f.is_open()) {
            std::cerr << "Warning: cannot open output file " << output_file << "\n";
        } else {
            if (write_header)
                f << "threads,rows,cols,pattern,schedule,steps,dt,flat,padded,"
                  << "total_ms,thermal_ms,geometry_ms,T_max,T_mean\n";
#ifdef USE_PADDED_CELL
            const char* padded_str = "1";
#else
            const char* padded_str = "0";
#endif
            f << nthreads << ',' << R << ',' << C << ','
              << pattern_str << ',' << schedule_str << ','
              << steps << ',' << dt << ','
              << (flat_mode ? 1 : 0) << ',' << padded_str << ','
              << result.total_ms << ',' << result.thermal_ms << ','
              << result.geometry_ms << ',' << result.T_max << ',' << result.T_mean << '\n';

            // Append per-thread stats as separate rows if tracked
            if (track_threads && nthreads > 1) {
                for (int t = 0; t < nthreads; t++) {
                    f << "thread_stat," << t << ',' << result.thread_stats[t].thermal_ms << '\n';
                }
            }
        }
    }

    return 0;
}
