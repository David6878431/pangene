#!/usr/bin/env bash
set -Eeuo pipefail
source "${WORKFLOW_CONFIG:?Run through the Python CLI so configuration is validated}"
ASSETS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DATA="$ASSETS/data.py"
export LC_ALL=C
die() { echo "ERROR: $*" >&2; exit 2; }
need() { local tool; for tool in "$@"; do command -v "$tool" >/dev/null || die "Missing executable: $tool"; done; }
file() { [[ -s "$1" ]] || die "Missing or empty input: $1"; }
stage() {
  mkdir -p "$WORKDIR"
  local target="$WORKDIR/$1"
  [[ ! -e "$target" ]] || die "Stage output exists: $target. Choose a new workdir or explicitly archive that stage directory before rerunning."
  mkdir "$target"; cd "$target"
}
prep() {
  need python3 agat_sp_keep_longest_isoform.pl gffread
  local sample="$1" destination="$2"
  mkdir -p "$destination"
  python3 - "$sample" "${GENOME[$sample]}" "$destination/genome.fa" <<'PY'
import gzip, shutil, sys
source = gzip.open(sys.argv[2], 'rb') if sys.argv[2].endswith('.gz') else open(sys.argv[2], 'rb')
with source, open(sys.argv[3], 'wb') as out:
    shutil.copyfileobj(source, out)
PY
  python3 - "${GFF[$sample]}" "$destination/input.gff3" <<'PY'
import gzip, shutil, sys
source = gzip.open(sys.argv[1], 'rb') if sys.argv[1].endswith('.gz') else open(sys.argv[1], 'rb')
with source, open(sys.argv[2], 'wb') as out:
    shutil.copyfileobj(source, out)
PY
  agat_sp_keep_longest_isoform.pl --gff "$destination/input.gff3" -o "$destination/longest.gff3"
  gffread "$destination/longest.gff3" -g "$destination/genome.fa" -x "$destination/transcripts.cds.fa" -y "$destination/transcripts.pep.fa"
  local kind
  for kind in cds pep; do
    python3 "$DATA" normalize --gff "$destination/longest.gff3" --input "$destination/transcripts.$kind.fa" --sample "$sample" --output "$destination/$sample.$kind.fa" --mapping "$destination/$kind.ids.tsv"
  done
}
sample_csv() { local IFS=,; echo "${SAMPLES[*]}"; }
unmap_reads() {
  local sample="$1" ref="$2" output="$3"
  mkdir -p "$output"
  bowtie2-build --threads "$THREADS" "$ref" "$output/ref"
  bowtie2 -p "$THREADS" -x "$output/ref" -1 "$WORKDIR/qc/$sample.1.fq.gz" -2 "$WORKDIR/qc/$sample.2.fq.gz" |
    samtools view -u -f 12 -F 256 |
    samtools sort -n -@ "$THREADS" -m "$SORT_MEMORY" -o "$output/unmapped.names.bam" -
  samtools fastq -@ "$THREADS" -n -1 "$output/unmapped.1.fq.gz" -2 "$output/unmapped.2.fq.gz" -0 /dev/null -s "$output/singletons.fq.gz" "$output/unmapped.names.bam"
}
