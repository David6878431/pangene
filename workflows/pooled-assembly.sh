#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need megahit seqkit
stage pooled-assembly
one=(); two=()
for sample in "${SAMPLES[@]}"; do
  file "$WORKDIR/unmapped/$sample/unmapped.1.fq.gz"; file "$WORKDIR/unmapped/$sample/unmapped.2.fq.gz"
  one+=("$WORKDIR/unmapped/$sample/unmapped.1.fq.gz"); two+=("$WORKDIR/unmapped/$sample/unmapped.2.fq.gz")
done
(IFS=,; megahit -1 "${one[*]}" -2 "${two[*]}" -t "$THREADS" -m "$MEGAHIT_MEMORY" --min-contig-len "$MIN_CONTIG" -o assembly)
seqkit seq -m "$MIN_CONTIG" assembly/final.contigs.fa > novel.fa
