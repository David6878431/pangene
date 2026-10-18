#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need bowtie2 bowtie2-build samtools masurca seqkit
stage iterative-assembly
ref="$WORKDIR/prepare/$REFERENCE/genome.fa"; file "$ref"
: > novel.fa
for sample in "${SAMPLES[@]}"; do
  unmap_reads "$sample" "$ref" "$PWD/$sample.map"
  mkdir "$sample.asm"; pushd "$sample.asm"
  masurca -t "$THREADS" -i "$WORKDIR/iterative-assembly/$sample.map/unmapped.1.fq.gz,$WORKDIR/iterative-assembly/$sample.map/unmapped.2.fq.gz"
  seqkit seq -m "$MIN_CONTIG" CA/primary.genome.scf.fasta | sed "s/^>/>$sample::/" > novel.fa
  cat "$ref" novel.fa > merged.fa
  ref="$PWD/merged.fa"
  cat novel.fa >> "$WORKDIR/iterative-assembly/novel.fa"
  popd
done
