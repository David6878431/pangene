#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

stage prepare
GENOME[$REFERENCE]="$REF_FASTA"; GFF[$REFERENCE]="$REF_GFF"
prep "$REFERENCE" "$PWD/$REFERENCE"
