#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need masurca cd-hit-est seqkit
stage independent-assembly
assemblies=()
for sample in "${SAMPLES[@]}"; do
  mkdir "$sample"; pushd "$sample"
  masurca -t "$THREADS" -i "$WORKDIR/unmapped/$sample/unmapped.1.fq.gz,$WORKDIR/unmapped/$sample/unmapped.2.fq.gz"
  seqkit seq -m "$MIN_CONTIG" CA/primary.genome.scf.fasta | sed "s/^>/>$sample::/" > assembly.fa
  popd; assemblies+=("$sample/assembly.fa")
done
cat "${assemblies[@]}" > all.fa
cd-hit-est -i all.fa -o novel.fa -c "$CLUSTER_IDENTITY" -T "$THREADS" -M "$CLUSTER_MEMORY_MB"
