#!/bin/bash
#SBATCH -p RM
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=128
#SBATCH -t 02:00:00
#SBATCH --exclusive
#SBATCH -J thermo_elastic_sweep
#SBATCH -o results/psc_%j.out
#SBATCH -e results/psc_%j.err
#
# run_psc.sh — PSC Bridges-2 RM benchmark sweep for thermo-elastic mesh sim.
#
# Uses OpenMP (not MPI). RM partition has 128 physical cores per node.
# Thread counts up to 128 for extreme scaling experiments.
#
# Build on login node FIRST (do not compile inside job):
#   module load gcc/10.2.0
#   make all padded
#
# Submit:
#   cd /path/to/project && sbatch scripts/run_psc.sh
#
# Monitor:
#   squeue -u $USER
#   tail -f results/psc_<jobid>.out
#
# Retrieve results (from local machine):
#   scp bridges2.psc.edu:~/15418-project/results/psc_benchmark.csv results/

set -e
module load gcc/10.2.0 || true  # load GCC with OpenMP support

# Locate project root: prefer $SLURM_SUBMIT_DIR, then $HOME/15418-project
CODE_DIR=""
for d in "${SLURM_SUBMIT_DIR:-}" "${HOME}/15418-project" "$(pwd)"; do
    [ -z "$d" ] && continue
    [ -f "$d/sim" ] && { CODE_DIR="$d"; break; }
done
if [ -z "$CODE_DIR" ]; then
    echo "ERROR: Cannot find sim binary."
    echo "  Build on login node: module load gcc/10.2.0 && make all padded"
    exit 1
fi
cd "$CODE_DIR"

BINARY="./sim"
BINARY_PADDED="./sim_padded"
OUTFILE="results/psc_benchmark.csv"
HEATMAP_DIR="results/psc_heatmaps"
TRIALS=3
STEPS=500

mkdir -p results "$HEATMAP_DIR"
rm -f "$OUTFILE"

echo "============================================================"
echo "PSC Bridges-2 RM — Thermo-Elastic Mesh Simulation Sweep"
echo "Job ID    : ${SLURM_JOB_ID:-local}"
echo "Node      : $(hostname)"
echo "CPU cores : $(nproc)"
echo "Working   : $(pwd)"
echo "Date      : $(date)"
echo "============================================================"
echo ""

# Thread counts up to 128 (RM has 128 physical cores)
THREADS=(1 2 4 8 16 32 64 128)

# Mesh sizes: use large sizes to stress the parallelism at high counts
SIZES=(500 1000)

PATTERNS=(uniform hotspot1 hotspot4 random)
SCHEDULES=(static dynamic)

total_runs=$(( ${#SIZES[@]} * ${#THREADS[@]} * ${#PATTERNS[@]} * ${#SCHEDULES[@]} ))
run_count=0

echo "=== Main scaling sweep (${total_runs} configs × ${TRIALS} trials) ==="
for size in "${SIZES[@]}"; do
for pattern in "${PATTERNS[@]}"; do
for sched in "${SCHEDULES[@]}"; do
for threads in "${THREADS[@]}"; do
    run_count=$((run_count + 1))
    echo -n "[$run_count/$total_runs] size=${size} T=${threads} pat=${pattern} sched=${sched} ... "

    total_time=0.0
    for trial in $(seq 1 $TRIALS); do
        # Set OMP_NUM_THREADS as well for NUMA-aware libraries
        export OMP_NUM_THREADS=$threads
        output=$("$BINARY" \
            --size "$size" \
            --threads "$threads" \
            --steps "$STEPS" \
            --pattern "$pattern" \
            --schedule "$sched" \
            --output "$OUTFILE")
        t=$(echo "$output" | grep -oP 'total_ms=\K[0-9.]+')
        total_time=$(echo "$total_time + $t" | bc -l)
    done
    avg_time=$(echo "$total_time / $TRIALS" | bc -l)
    printf "avg=%.2f ms\n" "$avg_time"

done; done; done; done

# ---- Per-thread load balance (hotspot patterns, 1000×1000) ---------------
echo ""
echo "=== Per-thread load balance (hotspot4, 1000×1000) ==="
for threads in 8 16 32 64 128; do
    for sched in static dynamic; do
        echo -n "  threads=${threads} sched=${sched} ... "
        export OMP_NUM_THREADS=$threads
        "$BINARY" \
            --size 1000 --threads "$threads" \
            --steps "$STEPS" --pattern hotspot4 \
            --schedule "$sched" \
            --track-threads \
            --output "$OUTFILE" \
            --verbose 2>&1 | grep -E "thread [0-9]|imbalance" || true
        echo "done"
    done
done

# ---- False-sharing experiment (1000×1000, padded vs unpadded) -------------
if [ -f "$BINARY_PADDED" ]; then
    echo ""
    echo "=== False-sharing experiment (1000×1000, static) ==="
    for threads in 1 8 32 64 128; do
        echo -n "  unpadded T=${threads} ... "
        for trial in $(seq 1 $TRIALS); do
            export OMP_NUM_THREADS=$threads
            "$BINARY" --size 1000 --threads "$threads" --steps "$STEPS" \
                --pattern uniform --schedule static --output "$OUTFILE" > /dev/null
        done
        echo -n "done  |  padded T=${threads} ... "
        for trial in $(seq 1 $TRIALS); do
            export OMP_NUM_THREADS=$threads
            "$BINARY_PADDED" --size 1000 --threads "$threads" --steps "$STEPS" \
                --pattern uniform --schedule static --output "$OUTFILE" > /dev/null
        done
        echo "done"
    done
fi

# ---- Flat vs 3D comparison (1000×1000) ------------------------------------
echo ""
echo "=== Flat vs 3D comparison (hotspot1, 1000×1000) ==="
for threads in 1 64; do
    echo -n "  3D  T=${threads} ... "
    export OMP_NUM_THREADS=$threads
    "$BINARY" --size 1000 --threads "$threads" --steps "$STEPS" \
        --pattern hotspot1 --schedule static \
        --heatmap "${HEATMAP_DIR}/heatmap_3d_hotspot1.csv" \
        --output "$OUTFILE" > /dev/null
    echo -n "done  |  flat T=${threads} ... "
    "$BINARY" --size 1000 --threads "$threads" --steps "$STEPS" \
        --pattern hotspot1 --schedule static --flat \
        --heatmap "${HEATMAP_DIR}/heatmap_flat_hotspot1.csv" \
        --output "$OUTFILE" > /dev/null
    echo "done"
done

# ---- Memory bandwidth probe -----------------------------------------------
echo ""
echo "=== Memory bandwidth (1000×1000 array) ==="
export OMP_NUM_THREADS=1
"$BINARY" --size 1000 --bandwidth

# ---- Heatmap dumps --------------------------------------------------------
echo ""
echo "=== Heatmap dumps (1000×1000) ==="
for pattern in uniform hotspot1 hotspot4 random; do
    echo -n "  ${pattern} ... "
    export OMP_NUM_THREADS=64
    "$BINARY" --size 1000 --steps "$STEPS" --pattern "$pattern" \
        --threads 64 --heatmap "${HEATMAP_DIR}/heatmap_${pattern}.csv" > /dev/null
    echo "done"
done

echo ""
echo "============================================================"
echo "Sweep complete — $(date)"
echo "Results: $OUTFILE"
echo "============================================================"
echo ""
echo "Generate plots (on local machine after scp):"
echo "  python3 scripts/visualize.py --all-psc"
