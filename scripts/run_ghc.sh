#!/usr/bin/env bash
# run_ghc.sh — Full benchmark sweep for GHC lab machines.
#
# GHC machines have 8 physical cores (16 logical with HT). Run this script
# from the project root after `make all padded`.
#
# Usage:
#   bash scripts/run_ghc.sh [--quick] [--full]
#
#   (no flag) — Standard sweep: 100×100 and 500×500, 1-16 threads, all patterns
#   --quick   — Small sweep only (100×100, 2 patterns, static) for fast iteration
#   --full    — Adds 1000×1000 and skips nothing

set -euo pipefail

BINARY="./sim"
BINARY_PADDED="./sim_padded"
OUTFILE="results/ghc_benchmark.csv"
HEATMAP_DIR="results/heatmaps"
TRIALS=3
STEPS=500

QUICK=false; FULL=false
for arg in "$@"; do
    case $arg in --quick) QUICK=true ;; --full) FULL=true ;; esac
done

if $QUICK; then
    SIZES=(100); PATTERNS=(uniform hotspot1); THREADS=(1 2 4 8); SCHEDULES=(static); STEPS=200
elif $FULL; then
    SIZES=(100 500 1000); PATTERNS=(uniform hotspot1 hotspot4 random)
    THREADS=(1 2 4 8 16); SCHEDULES=(static dynamic)
else
    SIZES=(100 500); PATTERNS=(uniform hotspot1 hotspot4 random)
    THREADS=(1 2 4 8 16); SCHEDULES=(static dynamic)
fi

mkdir -p results "$HEATMAP_DIR"
rm -f "$OUTFILE"

echo "=== GHC Benchmark Sweep — $(date) ==="
echo "  Machine : $(hostname)"
echo "  CPUs    : $(nproc) logical ($(nproc --all) total)"
echo "  Output  : $OUTFILE"
echo "  Sizes   : ${SIZES[*]}"
echo "  Threads : ${THREADS[*]}"
echo "  Patterns: ${PATTERNS[*]}"
echo "  Sched   : ${SCHEDULES[*]}"
echo "  Steps   : $STEPS (avg over $TRIALS trials)"
echo ""

total_runs=$(( ${#SIZES[@]} * ${#THREADS[@]} * ${#PATTERNS[@]} * ${#SCHEDULES[@]} ))
run_count=0

# ---- Main parallel scaling sweep -----------------------------------------
for size in "${SIZES[@]}"; do
for pattern in "${PATTERNS[@]}"; do
for sched in "${SCHEDULES[@]}"; do
for threads in "${THREADS[@]}"; do
    run_count=$((run_count + 1))
    echo -n "[$run_count/$total_runs] size=${size} threads=${threads} pattern=${pattern} sched=${sched} ... "

    total_time=0.0
    for trial in $(seq 1 $TRIALS); do
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

# ---- Per-thread load balance tracking (hotspot patterns, select configs) ---
echo ""
echo "=== Per-thread load balance (hotspot4, 500×500 if available) ==="
for pattern in hotspot4 hotspot1; do
    size=500
    if [[ ! " ${SIZES[*]} " =~ " ${size} " ]]; then size=100; fi
    for threads in 4 8 16; do
        [[ ! " ${THREADS[*]} " =~ " ${threads} " ]] && continue
        for sched in static dynamic; do
            [[ ! " ${SCHEDULES[*]} " =~ " ${sched} " ]] && continue
            echo -n "  load-balance: size=${size} threads=${threads} pattern=${pattern} sched=${sched} ... "
            "$BINARY" \
                --size "$size" --threads "$threads" \
                --steps "$STEPS" --pattern "$pattern" \
                --schedule "$sched" \
                --track-threads \
                --output "$OUTFILE" \
                --verbose 2>&1 | grep -E "thread [0-9]:" | sed 's/^\[sim\] /  /' || true
            echo "done"
        done
    done
done

# ---- False sharing: padded vs unpadded (500×500) --------------------------
if [ -f "$BINARY_PADDED" ]; then
    echo ""
    echo "=== False-sharing experiment: padded vs unpadded (500×500, static) ==="
    echo "  (columns padded=0 vs padded=1 in CSV)"
    for threads in 1 4 8 16; do
        [[ ! " ${THREADS[*]} " =~ " ${threads} " ]] && continue
        echo -n "  unpadded threads=${threads} ... "
        for trial in $(seq 1 $TRIALS); do
            "$BINARY" --size 500 --threads "$threads" --steps "$STEPS" \
                --pattern uniform --schedule static --output "$OUTFILE" > /dev/null
        done
        echo -n "done  |  padded threads=${threads} ... "
        for trial in $(seq 1 $TRIALS); do
            "$BINARY_PADDED" --size 500 --threads "$threads" --steps "$STEPS" \
                --pattern uniform --schedule static --output "$OUTFILE" > /dev/null
        done
        echo "done"
    done
else
    echo ""
    echo "=== Skipping padded experiment (sim_padded not found; run: make padded) ==="
fi

# ---- Flat vs 3D comparison (hotspot1, 500×500) ----------------------------
echo ""
echo "=== Flat vs 3D comparison (hotspot1, 500×500 or 100×100) ==="
cmp_size=500
if [[ ! " ${SIZES[*]} " =~ " ${cmp_size} " ]]; then cmp_size=100; fi
for threads in 1 8; do
    [[ ! " ${THREADS[*]} " =~ " ${threads} " ]] && continue
    echo -n "  3D  threads=${threads} ... "
    "$BINARY" --size "$cmp_size" --threads "$threads" --steps "$STEPS" \
        --pattern hotspot1 --schedule static \
        --heatmap "${HEATMAP_DIR}/heatmap_3d_hotspot1.csv" \
        --output "$OUTFILE" > /dev/null
    echo -n "done  |  flat threads=${threads} ... "
    "$BINARY" --size "$cmp_size" --threads "$threads" --steps "$STEPS" \
        --pattern hotspot1 --schedule static --flat \
        --heatmap "${HEATMAP_DIR}/heatmap_flat_hotspot1.csv" \
        --output "$OUTFILE" > /dev/null
    echo "done"
done

# ---- Bandwidth probe -------------------------------------------------------
echo ""
echo "=== Memory bandwidth probe ==="
"$BINARY" --size 500 --bandwidth
echo ""

# ---- Heatmap dumps for visualization -------------------------------------
echo "=== Dumping heatmaps for visualization (500×500 or 100×100) ==="
hm_size=500
if [[ ! " ${SIZES[*]} " =~ " ${hm_size} " ]]; then hm_size=100; fi
for pattern in uniform hotspot1 hotspot4 random; do
    out="${HEATMAP_DIR}/heatmap_${pattern}.csv"
    echo -n "  ${pattern} (${hm_size}×${hm_size}) ... "
    "$BINARY" --size "$hm_size" --steps "$STEPS" --pattern "$pattern" \
        --threads 8 --heatmap "$out" > /dev/null
    echo "done → $out"
done

echo ""
echo "=== Sweep complete — $(date) ==="
echo "Results: $OUTFILE"
echo ""
echo "Next: python3 scripts/visualize.py --all-ghc"
