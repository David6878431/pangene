#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need vg bgzip tabix bcftools
stage graph-call
for suffix in gbz min dist snarls; do file "$GRAPH_PREFIX.$suffix"; done
vcfs=()
for sample in "${SAMPLES[@]}"; do
  vg giraffe -Z "$GRAPH_PREFIX.gbz" -m "$GRAPH_PREFIX.min" -d "$GRAPH_PREFIX.dist" -f "${READ1[$sample]}" -f "${READ2[$sample]}" -N "$sample" -t "$THREADS" > "$sample.gam"
  vg pack -x "$GRAPH_PREFIX.gbz" -g "$sample.gam" -Q "$MIN_MAPQ" -o "$sample.pack" -t "$THREADS"
  vg call "$GRAPH_PREFIX.gbz" -r "$GRAPH_PREFIX.snarls" -k "$sample.pack" -a -t "$THREADS" -s "$sample" > "$sample.vcf"
  bgzip "$sample.vcf"; tabix -p vcf "$sample.vcf.gz"; vcfs+=("$sample.vcf.gz")
done
if [[ ${#vcfs[@]} -eq 1 ]]; then cp "${vcfs[0]}" all.vcf.gz; else bcftools merge --threads "$THREADS" -m all -Oz -o all.vcf.gz "${vcfs[@]}"; fi
tabix -p vcf all.vcf.gz
