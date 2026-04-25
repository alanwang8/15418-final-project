#!/usr/bin/env bash
# run_benchmarks.sh — sweep thread counts, mesh sizes, patterns, and schedules.
# Run this from the project root after building with `make all`.
# Results are written to results/benchmark.csv.
#
# Usage:
#   bash scripts/run_benchmarks.sh [--quick] [--full]
#
#   --quick   Small sweep (100x100 only, fewer patterns) for fast iteration
#   --full    Full sweep including 500x500 and 1000x1000 meshes (default on GHC)

set -euo pipefail

BINARY="./sim"
OUTFILE="results/benchmark.csv"
HEATMAP_DIR="results/heatmaps"
TRIALS=3   # average over this many runs

# Parse flags
QUICK=false
FULL=false
for arg in "$@"; do
    case $arg in
        --quick) QUICK=true ;;
        --full)  FULL=true  ;;
    esac
done

if $QUICK; then
    SIZES=(100)
    PATTERNS=(uniform hotspot1)
    THREADS=(1 2 4 8)
    SCHEDULES=(static)
    STEPS=200
elif $FULL; then
    SIZES=(100 500 1000)
    PATTERNS=(uniform hotspot1 hotspot4 random)
    THREADS=(1 2 4 8 16)
    SCHEDULES=(static dynamic)
    STEPS=500
else
    # Default: GHC machine sweep
    SIZES=(100 500)
    PATTERNS=(uniform hotspot1 hotspot4 random)
    THREADS=(1 2 4 8 16)
    SCHEDULES=(static dynamic)
    STEPS=500
fi

mkdir -p results "$HEATMAP_DIR"

echo "=== Benchmark sweep starting at $(date) ==="
echo "  Binary : $BINARY"
echo "  Output : $OUTFILE"
echo "  Sizes  : ${SIZES[*]}"
echo "  Threads: ${THREADS[*]}"
echo "  Patterns: ${PATTERNS[*]}"
echo "  Schedules: ${SCHEDULES[*]}"
echo "  Steps  : $STEPS"
echo "  Trials : $TRIALS"
echo ""

# Remove old results file so header is fresh
rm -f "$OUTFILE"

total_runs=$(( ${#SIZES[@]} * ${#THREADS[@]} * ${#PATTERNS[@]} * ${#SCHEDULES[@]} ))
run_count=0

for size in "${SIZES[@]}"; do
for pattern in "${PATTERNS[@]}"; do
for sched in "${SCHEDULES[@]}"; do
for threads in "${THREADS[@]}"; do

    run_count=$((run_count + 1))
    echo -n "[$run_count/$total_runs] size=${size} threads=${threads} pattern=${pattern} sched=${sched} ... "

    # Run TRIALS times and accumulate times
    total_time=0.0
    for trial in $(seq 1 $TRIALS); do
        output=$("$BINARY" \
            --size "$size" \
            --threads "$threads" \
            --steps "$STEPS" \
            --pattern "$pattern" \
            --schedule "$sched" \
            --output "$OUTFILE")
        # Parse total_ms from stdout line "total_ms=X thermal_ms=Y ..."
        t=$(echo "$output" | grep -oP 'total_ms=\K[0-9.]+')
        total_time=$(echo "$total_time + $t" | bc -l)
    done
    avg_time=$(echo "$total_time / $TRIALS" | bc -l)
    printf "avg=%.2f ms\n" "$avg_time"

done
done
done
done

# Also dump heatmaps for the interesting patterns at 100x100
echo ""
echo "=== Dumping heatmaps for visualization ==="
for pattern in uniform hotspot1 hotspot4; do
    "$BINARY" --size 100 --steps "$STEPS" --pattern "$pattern" --threads 8 \
        --heatmap "${HEATMAP_DIR}/heatmap_${pattern}.csv" >/dev/null
    echo "  Wrote ${HEATMAP_DIR}/heatmap_${pattern}.csv"
done

echo ""
echo "=== Benchmark sweep complete at $(date) ==="
echo "Results written to $OUTFILE"
echo "Heatmaps written to $HEATMAP_DIR/"
