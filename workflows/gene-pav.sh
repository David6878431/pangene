#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need bwa samtools bedtools python3
stage gene-pav
cp "$PAN_FASTA" pan.fa; bwa index pan.fa
for sample in "${SAMPLES[@]}"; do
  bwa mem -t "$THREADS" -R "@RG\\tID:$sample\\tSM:$sample" pan.fa "$WORKDIR/qc/$sample.1.fq.gz" "$WORKDIR/qc/$sample.2.fq.gz" |
    samtools view -u -q "$MIN_MAPQ" -F 2308 |
    samtools sort -@ "$THREADS" -m "$SORT_MEMORY" -o "$sample.bam" -
  bedtools genomecov -ibam "$sample.bam" -bg > "$sample.depth.bed"
  python3 "$DATA" depth --input "$sample.depth.bed" --output "$sample.covered.bed" --min-depth "$MIN_DEPTH"
  bedtools coverage -a "$PAN_GENES_BED" -b "$sample.covered.bed" > "$sample.coverage.tsv"
done
python3 "$DATA" coverage --directory "$PWD" --samples "$(sample_csv)" --min-coverage "$GENE_COVERAGE" --prefix genes
