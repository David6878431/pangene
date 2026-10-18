#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need cactus-pangenome
stage graph-build
: > genomes.txt
for sample in "${SAMPLES[@]}"; do
  printf '%s\t%s\n' "$sample" "$WORKDIR/prepare/$sample/genome.fa" >> genomes.txt
done
mkdir tmp
cactus-pangenome ./jobstore genomes.txt --outDir graph --outName pangenome --reference "$REFERENCE" --binariesMode local --maxCores "$THREADS" --maxMemory "$CACTUS_MEMORY" --mgCores "$THREADS" --mapCores "$THREADS" --consCores "$THREADS" --indexCores "$THREADS" --gbz full --gfa full --vcf full --giraffe full --workDir "$PWD/tmp"
