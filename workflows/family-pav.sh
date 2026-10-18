#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need python3
stage family-pav
args=(); [[ -z "$UNASSIGNED_TSV" ]] || args+=(--unassigned "$UNASSIGNED_TSV")
python3 "$DATA" orthopav --input "$ORTHOGROUPS_TSV" --samples "$(sample_csv)" --prefix families --softcore "$SOFTCORE" --permutations "$PERMUTATIONS" --seed "$SEED" "${args[@]}"
