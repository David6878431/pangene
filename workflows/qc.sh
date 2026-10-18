#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need fastp
stage qc
for sample in "${SAMPLES[@]}"; do
  fastp -i "${READ1[$sample]}" -I "${READ2[$sample]}" -o "$sample.1.fq.gz" -O "$sample.2.fq.gz" --thread "$THREADS" --qualified_quality_phred "$QUALITY" --unqualified_percent_limit "$UNQUALIFIED" --n_base_limit "$N_BASE_LIMIT" --html "$sample.html" --json "$sample.json"
done
