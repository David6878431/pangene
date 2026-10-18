#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

stage prepare
mkdir proteins
for sample in "${SAMPLES[@]}"; do
  prep "$sample" "$PWD/$sample"
  cp "$sample/$sample.pep.fa" "proteins/$sample.fa"
done
