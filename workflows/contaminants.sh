#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need blastn seqkit python3
stage contaminants
blastn -query "$NOVEL_FASTA" -db "$NT_DATABASE" -taxidlist "$EXCLUDE_TAXIDS" -task megablast -outfmt '6 qseqid pident qcovs staxids bitscore' -max_target_seqs 5 -num_threads "$THREADS" -evalue "$BLAST_EVALUE" > hits.tsv
awk -v identity="$CONTAM_IDENTITY" -v coverage="$CONTAM_COVERAGE" '$2>=identity && $3>=coverage{print $1}' hits.tsv | sort -u > removed.ids.txt
if [[ -s removed.ids.txt ]]; then seqkit grep -v -f removed.ids.txt "$NOVEL_FASTA" > novel.final.fa; else cp "$NOVEL_FASTA" novel.final.fa; fi
