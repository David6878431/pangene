#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need maker fasta_merge gff3_merge
stage annotate
cp "$MAKER_OPTS" maker_opts.ctl; cp "$MAKER_BOPTS" maker_bopts.ctl; cp "$MAKER_EXE" maker_exe.ctl
# Evidence paths in .ctl must be absolute and visible inside the selected executor.
maker -cpus "$THREADS" maker_opts.ctl maker_bopts.ctl maker_exe.ctl
file "$MAKER_INDEX"
fasta_merge -d "$MAKER_INDEX" -o novel
gff3_merge -d "$MAKER_INDEX" -o novel.gff3
