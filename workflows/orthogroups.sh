#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need orthofinder
file "$WORKDIR/prepare/proteins/${SAMPLES[0]}.fa"
stage orthogroups
orthofinder -f "$WORKDIR/prepare/proteins" -S diamond -t "$THREADS" -a "$ORTHO_THREADS" -o "$PWD/results"
