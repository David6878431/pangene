#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"

need gffread gtfToGenePred retrieve_seq_from_fasta.pl table_annovar.pl
stage variant-annotation
gffread "$REF_GFF" -T -o ref.gtf
gtfToGenePred -genePredExt ref.gtf custom_refGene.txt
retrieve_seq_from_fasta.pl --format refGene --seqfile "$REF_FASTA" --outfile custom_refGeneMrna.fa custom_refGene.txt
table_annovar.pl "$VARIANT_VCF" "$PWD" -buildver custom -out variants -remove -protocol refGene -operation g -nastring . -vcfinput --neargene "$NEAR_GENE"
