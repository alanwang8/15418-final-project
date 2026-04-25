# Running on PSC Bridges-2 for Large-Scale Experiments

PSC (Pittsburgh Supercomputing Center) Bridges-2 RM nodes have **128 physical cores** per
node, enabling scaling experiments impossible on GHC (max 8–16 physical cores). This lets
you measure speedup from 1 to 128 OpenMP threads on a single node.

## Prerequisites

- Access to Bridges-2 via your CMU/XSEDE/ACCESS account
- The `sim` and `sim_padded` binaries built on Bridges-2 (not cross-compiled on GHC)

---

## Step 1: Connect to Bridges-2

```bash
ssh <andrew_id>@bridges2.psc.edu
```

If you don't have an account, request one via [ACCESS](https://allocations.access-ci.org/
) (formerly XSEDE) with your CMU email.

---

## Step 2: Copy Project Files

From your **local machine** or GHC:

```bash
# From local machine:
scp -r /afs/andrew.cmu.edu/usr22/<andrew_id>/private/15418/project/ \
    <andrew_id>@bridges2.psc.edu:~/15418-project/

# Or from GHC (faster):
ssh ghc<NN>.ghc.andrew.cmu.edu  # log into a GHC machine first
scp -r ~/private/15418/project/ <andrew_id>@bridges2.psc.edu:~/15418-project/
```

---

## Step 3: Load Modules and Build on Login Node

```bash
# On Bridges-2 login node:
cd ~/15418-project
module load gcc/10.2.0

# Build parallel + serial + padded binaries
make all padded

# Verify:
./sim --size 50 --steps 10 --pattern hotspot1 --threads 4 --verbose
```

> **Important:** Always build on the login node (not inside a SLURM job) to avoid
> occupying compute resources for compilation.

---

## Step 4: Submit the Benchmark Job

```bash
cd ~/15418-project
mkdir -p results/psc_heatmaps

# Submit to RM partition (128-core regular memory nodes):
sbatch scripts/run_psc.sh

# Monitor your job:
squeue -u $USER
```

The job requests 1 full node exclusively for 2 hours. Typical runtime: 30–60 minutes
for a full 1000×1000 sweep (4 patterns × 2 schedules × 8 thread counts × 3 trials).

---

## Step 5: Monitor Output

```bash
# Live log (job output streams here):
tail -f results/psc_<jobid>.out

# Or check job status:
scontrol show job <jobid>
```

---

## Step 6: Retrieve Results to Local Machine

```bash
# From your local machine:
scp <andrew_id>@bridges2.psc.edu:~/15418-project/results/psc_benchmark.csv \
    /afs/andrew.cmu.edu/usr22/<andrew_id>/private/15418/project/results/

scp -r <andrew_id>@bridges2.psc.edu:~/15418-project/results/psc_heatmaps/ \
    /afs/andrew.cmu.edu/usr22/<andrew_id>/private/15418/project/results/
```

---

## Step 7: Generate Plots

```bash
cd /afs/andrew.cmu.edu/usr22/<andrew_id>/private/15418/project
python3 scripts/visualize.py --all-psc
```

This generates all speedup curves, scheduling comparisons, load balance charts,
and 3D isometric views from the PSC data into `results/`.

---

## PSC-Specific Notes

| Setting | Value |
|---------|-------|
| Partition | `RM` (regular memory) |
| Cores per node | 128 physical (AMD EPYC) |
| Memory | 256 GB |
| Max walltime | `--quickdev` slot: 30 min; `RM`: 48 hrs |
| Storage | Home dir: 10 GB; Ocean/scratch: unlimited |

### NUMA topology on RM nodes

Bridges-2 RM uses dual-socket EPYC processors (2 × 64 cores). At high thread counts
(≥ 64), you cross NUMA boundaries. You may observe a speedup plateau or slight dip
at 64→128 threads due to inter-socket memory traffic. Set `OMP_PROC_BIND=close` to
keep threads on the same socket at low counts:

```bash
export OMP_PROC_BIND=close OMP_PLACES=cores
./sim --threads 64 --size 1000 --pattern hotspot4 --steps 500
```

The `run_psc.sh` script sets `OMP_NUM_THREADS` automatically for each config.

### If job times out

Reduce `STEPS` from 500 to 200 in `run_psc.sh`, or use only sizes 500 (not 1000),
or reduce `TRIALS` from 3 to 1.

---

## Comparing GHC vs PSC Results

After collecting both datasets:

```bash
# On local machine:
python3 scripts/visualize.py \
    --speedup results/ghc_benchmark.csv   # generates GHC plots

python3 scripts/visualize.py \
    --speedup results/psc_benchmark.csv   # generates PSC plots
```

Key differences to highlight in the report:
1. **Raw speedup at 8–16 threads:** Should match GHC (validates reproducibility)
2. **64-thread speedup:** Not possible on GHC; shows whether the algorithm continues scaling
3. **128-thread behavior:** Likely hits memory bandwidth ceiling or NUMA effects
4. **Dynamic vs static at 128 threads:** More interesting than at 8 threads
