#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need minimap2 python3
stage sequence-pav
ref="$WORKDIR/prepare/$REFERENCE/genome.fa"; file "$ref"
for sample in "${SAMPLES[@]}"; do
  [[ "$sample" != "$REFERENCE" ]] || continue
  query="$WORKDIR/prepare/$sample/genome.fa"; file "$query"
  minimap2 -x "$ASM_PRESET" -t "$THREADS" "$ref" "$query" > "$sample.paf"
  python3 "$DATA" novel --fasta "$query" --paf "$sample.paf" --prefix "$sample" --min-length "$MIN_CONTIG" --max-coverage "$MAX_REF_COVERAGE"
done
