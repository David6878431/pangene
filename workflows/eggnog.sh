#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need emapper.py
stage eggnog
args=(); [[ -z "$TAX_SCOPE" ]] || args+=(--tax_scope "$TAX_SCOPE")
emapper.py -i "$PROTEIN_FASTA" --itype proteins -o eggnog -m diamond --cpu "$THREADS" --data_dir "$EGGNOG_DB" --dmnd_db "$EGGNOG_DB/eggnog_proteins.dmnd" "${args[@]}"
