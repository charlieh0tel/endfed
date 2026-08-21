#!/bin/sh
# D: the Richardson pair, both geometries.  Sequential so the machine
# never runs more than one sweep at a time, and nice 19 so interactive
# work always preempts it.  WORKERS defaults to 12 (sushi, 16 threads);
# set it lower on smaller machines (snaggle, 8 threads: WORKERS=6).
set -e
cd "$(dirname "$0")"
: "${WORKERS:=12}"
echo "campaign start: $(date -Is), $WORKERS workers"
for geometry in "" "--sloper"; do
  for density in 2 4; do
    echo "=== sweep $geometry --density $density: $(date -Is)"
    nice -n 19 uv run python nec4_table_sweep.py /usr/bin/nec4d42 \
      --workers "$WORKERS" --density "$density" $geometry
  done
done
echo "=== extrapolating: $(date -Is)"
uv run python extrapolate_sweep.py \
  nec4_table_sweep_d2.npz nec4_table_sweep_d4.npz \
  nec4_table_sweep_extrapolated.npz
uv run python extrapolate_sweep.py \
  nec4_table_sloper_sweep_d2.npz nec4_table_sloper_sweep_d4.npz \
  nec4_table_sloper_sweep_extrapolated.npz
echo "campaign done: $(date -Is)"
