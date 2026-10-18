#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need masurca minimap2 cd-hit-est python3
stage map-to-pan
ref="$WORKDIR/prepare/$REFERENCE/genome.fa"; file "$ref"
assemblies=()
for sample in "${SAMPLES[@]}"; do
  mkdir "$sample"; pushd "$sample"
  masurca -t "$THREADS" -i "$WORKDIR/qc/$sample.1.fq.gz,$WORKDIR/qc/$sample.2.fq.gz"
  minimap2 -x "$ASM_PRESET" -t "$THREADS" "$ref" CA/primary.genome.scf.fasta > alignments.paf
  python3 "$DATA" novel --fasta CA/primary.genome.scf.fasta --paf alignments.paf --prefix "$sample" --min-length "$MIN_CONTIG" --max-coverage "$MAX_REF_COVERAGE"
  popd; assemblies+=("$sample/$sample.novel.fa")
done
cat "${assemblies[@]}" > all.fa
cd-hit-est -i all.fa -o novel.fa -c "$CLUSTER_IDENTITY" -T "$THREADS" -M "$CLUSTER_MEMORY_MB"
