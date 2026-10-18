#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need minimap2 syri
stage syri
ref="$WORKDIR/prepare/$REFERENCE/genome.fa"; file "$ref"
for sample in "${SAMPLES[@]}"; do
  [[ "$sample" != "$REFERENCE" ]] || continue
  query="$WORKDIR/prepare/$sample/genome.fa"; file "$query"
  minimap2 -ax "$ASM_PRESET" --eqx -t "$THREADS" "$ref" "$query" > "$sample.sam"
  syri -c "$sample.sam" -r "$ref" -q "$query" -F S --nc "$THREADS" --prefix "$sample."
done
