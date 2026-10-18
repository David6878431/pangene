#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need bowtie2 bowtie2-build samtools
stage unmapped
for sample in "${SAMPLES[@]}"; do
  unmap_reads "$sample" "$WORKDIR/prepare/$REFERENCE/genome.fa" "$PWD/$sample"
done
