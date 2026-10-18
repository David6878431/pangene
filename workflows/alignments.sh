#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need nucmer delta-filter show-coords delta2vcf
stage alignments
ref="$WORKDIR/prepare/$REFERENCE/genome.fa"; file "$ref"
for sample in "${SAMPLES[@]}"; do
  [[ "$sample" != "$REFERENCE" ]] || continue
  query="$WORKDIR/prepare/$sample/genome.fa"; file "$query"
  nucmer --maxmatch -t "$THREADS" -p "$sample" "$ref" "$query"
  delta-filter -1 -i "$MIN_IDENTITY" -l "$MIN_ALIGNMENT" "$sample.delta" > "$sample.1delta"
  delta-filter -m -i "$MIN_IDENTITY" -l "$MIN_ALIGNMENT" "$sample.delta" > "$sample.mdelta"
  show-coords -Tclrd "$sample.1delta" > "$sample.1coords"
  show-coords -Tclrd "$sample.mdelta" > "$sample.mcoords"
  delta2vcf < "$sample.1delta" > "$sample.variants.raw.vcf"
done
# Raw delta2vcf dialects differ across MUMmer versions; do not fabricate genotypes or merge missing calls as reference.
