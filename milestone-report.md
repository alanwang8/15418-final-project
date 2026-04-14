# Milestone Report: Dynamic Thermo-Elastic Mesh Simulation for Parallel Systems

**Team:** Alan Wang, Allison Chen  
**Course:** CMU 15-418/618 — Parallel Computer Architecture and Programming  
**Date:** April 14, 2026  
**Project URL:** https://alanwang8.github.io/15418-final-project/

---

## Updated Schedule

The table below reflects our actual progress and revised half-week plan through the end of the semester.

| Dates | Task | Owner | Status |
|-------|------|-------|--------|
| Mar 23–25 | Finalize design and submit proposal | Both | ✅ Done |
| Mar 26–28 | Implement `Cell` and `Mesh` data structures; serial heat diffusion skeleton | Allison | ✅ Done |
| Mar 29–31 | Verify heat diffusion correctness on small examples; add floorplan patterns | Allison | ✅ Done |
| Apr 1–3 | Implement temperature-dependent geometry update (thermal expansion); add 3D z-displacement per instructor feedback | Allison | ✅ Done |
| Apr 4–7 | Add OpenMP parallel loops (static scheduling); double-buffering for race-free updates | Alan | ✅ Done |
| Apr 8–10 | Add dynamic scheduling variant; CLI for thread/pattern/schedule control; CSV timing output | Alan | ✅ Done |
| Apr 11–14 | **Milestone:** Measure initial speedups; generate heatmaps and speedup charts; write milestone report | Both | ✅ Done |
| Apr 15–17 | Refine 3D conductance model; investigate false sharing and cache line alignment | Allison | 🔄 Next |
| Apr 18–21 | Profile load imbalance under hotspot patterns; compare static vs. dynamic scheduling experimentally | Alan | ⏳ Pending |
| Apr 22–24 | Run full benchmark sweep on GHC lab machines: 500×500 mesh, patterns ×{1,2,4,8,16} threads | Both | ⏳ Pending |
| Apr 25–27 | Analyze results; identify bottlenecks; generate final plots and heatmap animations | Alan | ⏳ Pending |
| Apr 28–30 | Write final report (~10 pages); prepare poster (8 pages); code cleanup | Both | ⏳ Pending |
| May 1 | **Poster session** — 15-418: 8:30–11:30am | Both | ⏳ Pending |

---

## Work Completed

We have a fully functional parallel simulator built from scratch in C++17 with OpenMP. The implementation has three main components: a mesh data structure, a thermal update engine, and a 3D geometry update.

**Mesh and data structures.** The mesh is represented as a flat row-major array of `Cell` structs, where each cell stores: temperature *T*, heat capacity *c*, thermal conductivity *k*, power generation *p*, coefficient of thermal expansion *α*, and a full 3D position (*x*, *y*, *z*). Cell types (ALU, Cache, Memory, Interconnect) carry distinct default thermal and mechanical properties — for example, ALU cells have higher power generation and thermal expansion coefficients than memory cells. We implemented four floorplan configurations to exercise different workload distributions: a uniform cache array (baseline), a single central ALU hotspot (Hotspot-1), four quadrant ALU clusters with interconnect strips between them (Hotspot-4, modeled after a realistic multicore chip layout), and a random assignment pattern. Neighbor connectivity uses a 4-connected structured grid stored as precomputed index lists, avoiding pointer indirection during the hot update loop.

**Thermal simulation.** The thermal update follows an explicit finite-difference discretization of the 2D heat equation. At each timestep, every interior cell's temperature is updated as:

```
T_i^new = T_i + Δt · (p_i + Σ_{j∈N(i)} k_ij · (T_j − T_i)) / c_i
```

where `k_ij = min(k_i, k_j) / dist3D(i, j)` — conductance scales inversely with the 3D Euclidean distance between cell centers, so the geometry directly modulates heat flow. Boundary cells are held at ambient temperature (300 K) to act as heat sinks. We use **double-buffering**: all reads come from the current temperature array while writes go to a separate buffer, which is swapped atomically at the end of each step. This eliminates all race conditions without requiring per-cell locks and ensures every cell updates from the same consistent global snapshot.

**3D geometry update (buckling).** Per instructor feedback, we extended the model beyond a flat 2D plane to support out-of-plane deformation. After each thermal step, each cell's *z*-coordinate is updated:

```
z_i = α_i · (T_i − T_ref) · base_size · Z_amplify
```

Hot cells rise above the chip plane while cool cells remain near *z* = 0. This is physically motivated by shape-memory alloy behavior: local expansion creates a dome-like buckle profile in hot regions. Crucially, the updated *z* positions change `dist3D(i,j)` — and therefore `k_ij` — in the next timestep, creating a genuine thermomechanical feedback loop. We use a *Z_amplify* factor of 10× to make the displacement visible in output visualizations while remaining numerically stable.

**OpenMP parallelization.** Both the thermal update loop and the geometry update loop are parallelized with `#pragma omp parallel for`. The implicit barrier at the end of each parallel region ensures the geometry step never begins before all thermal writes are complete, preserving correctness across timesteps. We support two scheduling strategies selectable at runtime: static partitioning (round-robin block assignment, best for uniform workloads) and dynamic scheduling with configurable chunk size (for imbalanced hotspot scenarios). Thread count is controlled via CLI flag (`--threads N`), and all timing uses `std::chrono::high_resolution_clock` with separate accounting for the thermal and geometry phases.

---

## Goals and Deliverables Assessment

We believe we are on track to deliver all **Must Achieve** goals by April 30. The table below gives a precise status:

| Deliverable | Status | Notes |
|-------------|--------|-------|
| 2D/3D mesh simulator | ✅ Complete | Full 3D (*x,y,z*) positions; *z* evolves each step |
| Coupled thermo-elastic deformation | ✅ Complete | Buckling feeds back into conductance |
| OpenMP parallel implementation | ✅ Complete | Static + dynamic; up to 16 threads |
| Performance evaluation (initial) | ✅ Complete | Speedup measured on dev machine; GHC sweep pending |
| Full benchmark suite on GHC | 🔄 Scheduled Apr 22–24 | 500×500 mesh, 1–16 threads, all patterns |
| Load balance analysis | 🔄 Scheduled Apr 18–21 | Per-thread timing, static vs. dynamic |
| Dynamic scheduling comparison | 🔄 Scheduled Apr 18–21 | Will quantify benefit under hotspot workloads |
| Heatmap + speedup visualizations | ✅ Preliminary | SVG heatmaps and speedup charts generated |
| Animated mesh visualization | ⏳ Nice-to-have | Frame-by-frame dump implemented; GIF assembly pending |

No goals have been dropped. The 3D extension was added based on instructor feedback and is already implemented.

---

## Preliminary Results

### Experimental Setup

All results below were collected on a development machine (Intel multi-core CPU). We will run the authoritative benchmark suite on GHC lab machines (`ghcXX.ghc.andrew.cmu.edu`, 8 physical cores, 16 logical) during April 22–24. Each configuration was run 3 times and averaged to reduce noise. Mesh: 100×100 cells, 200 timesteps, Δt = 0.01, static OpenMP scheduling unless noted.

### Correctness Validation

We verified parallel correctness by comparing the final temperature arrays of the serial and 8-thread OpenMP runs on identical inputs. Both produce T_max = 309.999 K and T_mean = 300.748 K for the Hotspot-1 configuration (100×100, 100 steps). The double-buffering scheme eliminates race conditions entirely — no per-cell locking is required because each thread reads only from the previous step's buffer and writes only to the next step's buffer.

As a secondary check, we verified qualitative thermal behavior: the Hotspot-1 pattern produces a Gaussian-like radial plume centered on the ALU cluster, consistent with the expected diffusion kernel. The Hotspot-4 pattern shows four symmetric plumes with elevated temperatures along the interconnect strips between quadrants.

### Speedup Results

| Threads | Pattern | Avg Time (ms) | Speedup | Parallel Efficiency |
|---------|---------|--------------|---------|---------------------|
| 1 | Uniform | 35.3 | 1.00× | 100% |
| 2 | Uniform | 14.3 | 2.46× | 99% |
| 4 | Uniform | 7.5 | 4.71× | 95% |
| 8 | Uniform | 4.4 | **8.09×** | 81% |
| 1 | Hotspot-1 | 27.9 | 1.00× | 100% |
| 2 | Hotspot-1 | 14.4 | 1.94× | 97% |
| 4 | Hotspot-1 | 7.6 | 3.69× | 92% |
| 8 | Hotspot-1 | 4.5 | **6.16×** | 77% |

### Analysis

**Uniform workload** achieves near-linear speedup up to 4 threads (4.71×, 95% efficient) and super-linear speedup at 8 threads (8.09×, 81% efficient). The super-linear result at 2 and 8 threads likely reflects cache effects: a 100×100 mesh fits in ~160 KB for float temperatures, comfortably within a single core's L2 cache. When distributed across 8 cores, each thread operates on ~20 KB — fitting entirely in L1 cache (typically 32 KB), yielding a cache-related bonus on top of the parallelism benefit.

**Hotspot-1 workload** shows consistently lower speedup (6.16× vs 8.09× at 8 threads). Even though the structured grid assigns equal numbers of cells per thread under static scheduling, cells near the hot center have larger temperature gradients — and therefore larger conductance variations — resulting in slightly more arithmetic per update. This creates subtle load imbalance. We expect dynamic scheduling to partially recover this loss; that experiment is planned for April 18–21.

**Time breakdown:** Across all configurations, the thermal update accounts for ~93% of total runtime and the geometry (3D displacement) update for ~7%. This confirms that the geometry update adds modest overhead and validates keeping it in the critical path rather than deferring it. The geometry step is *O*(N) with no neighbor reads, making it embarrassingly parallel with no synchronization cost.

**What limits speedup at 8 threads?** Two hypotheses, to be tested with hardware profiling on GHC:
1. **Synchronization overhead:** The implicit barrier between the thermal and geometry phases stalls all threads until the last one finishes. Under static scheduling, any per-cell variation in work causes stragglers.
2. **Memory bandwidth:** As thread count increases, parallel reads from the temperature buffer may saturate the L3 cache bandwidth. At 500×500, the mesh is ~1 MB, which will no longer fit in L2 — we expect this effect to be more pronounced in the full-scale GHC experiments.

---

## Concerns and Open Questions

**1. Load imbalance at scale.** The efficiency drop from 95% at 4 threads to 81% at 8 threads for uniform workloads — where all cells should do identical work — is larger than expected. We suspect false sharing: adjacent cells in the mesh array may share cache lines, causing write invalidations when neighboring threads update their cells. We plan to measure this with `perf stat` on GHC and experiment with cache-line-aligned cell layouts or padding.

**2. Memory bandwidth at 500×500.** A 500×500 mesh has 250,000 cells; at ~80 bytes per `Cell` struct, the full array is ~20 MB — well beyond L3 on most cores. We anticipate the bandwidth bottleneck will reduce parallel efficiency significantly compared to the 100×100 results. We will report on this explicitly and discuss whether a Structure-of-Arrays layout (separating the hot field `T` from material constants that are read-only after initialization) would improve cache utilization.

**3. Dynamic scheduling overhead vs. benefit.** For the Hotspot-4 pattern, cells vary significantly in the amount of arithmetic they require (cells near hotspots have larger conductance variations). We expect dynamic scheduling to improve efficiency here, but the scheduling overhead may outweigh the benefit for smaller meshes. We will quantify the crossover point.

**4. Numerical stability at large Δt.** The explicit Euler scheme is conditionally stable: the timestep Δt must satisfy a CFL-like condition relative to the conductance and heat capacity. At higher temperatures (larger hotspots, more power), this bound tightens. We have not yet formally derived the stability condition for our heterogeneous mesh — this could become a concern if we scale power generation to produce more dramatic buckling.

---

## Poster Session Plan

At the May 1 poster session (15-418 slot, 8:30–11:30am), we plan to present:

1. **Live terminal demo:** Run the simulator live on a GHC machine, printing per-step timing statistics to show parallel scaling in real time. We will vary thread count from 1 to 8 on the spot to demonstrate speedup interactively.

2. **Printed speedup graphs:** Speedup vs. thread count for 100×100 and 500×500 meshes, comparing uniform vs. hotspot patterns and static vs. dynamic scheduling. All four curves on one chart to allow direct comparison.

3. **Heatmap prints:** Temperature distribution and 3D z-displacement maps for the Hotspot-4 pattern — the most visually interesting configuration. Side-by-side T and z maps illustrate the thermomechanical coupling.

4. **Load balance breakdown:** Bar chart of per-thread execution time under static scheduling for a hotspot workload — visualizing which threads become stragglers and how dynamic scheduling corrects this.

5. **Overhead of dynamics:** A two-bar comparison (static mesh vs. dynamic 3D mesh) showing the cost of the geometry update phase, motivating when dynamic coupling is worth the overhead.

---

## References

1. Chikhareva, M. & Vaidyanathan, R. (2023). A Thermal, Mechanical, and Materials Framework for a Shape Memory Alloy Heat Engine for Thermal Management. *Nanomaterials*, 13(15):2159.
2. Stan, M. R., Skadron, K., et al. (2003). HotSpot: a Dynamic Compact Thermal Model at the Processor-Architecture Level. *IEEE Micro* 23(4), pp. 32–46.
3. Chakkour, T., Sánchez, A. D., & Cai, X. C. (2024). Parallel Computation to Bidimensional Heat Equation using MPI/CUDA and FFTW. *Frontiers in Computer Science*, 5:1305800.
4. Walshaw, C. & Cross, M. (1999). Dynamic mesh partitioning & load-balancing for parallel computational mechanics codes. *Proc. ECCM*.

---

## Work Distribution

- **Alan Wang:** Led parallelization and performance evaluation. Designed the OpenMP parallel loops, implemented CLI and CSV timing infrastructure, wrote benchmark sweep scripts, and analyzed speedup results.
- **Allison Chen:** Led thermal model and deformation logic. Designed the `Cell`/`Mesh` data structures, implemented the serial heat diffusion engine, added the 3D geometry update (buckling), and generated heatmap visualizations.
- **Both:** Jointly designed the simulation algorithm, chose data structure layouts, debugged correctness, and co-wrote this report.

Expected credit distribution: **50% / 50%**.
