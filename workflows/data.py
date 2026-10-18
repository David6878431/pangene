#!/usr/bin/env python3
"""Portable data transforms; Python >=3.8, standard library only."""
import argparse
import csv
import gzip
import itertools
import json
import math
from pathlib import Path
import random
import statistics
import sys
from urllib.parse import unquote


def opened(path):
    return gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") else open(path, encoding="utf-8")


def fasta(path):
    name, parts, seen = None, [], set()
    with opened(path) as stream:
        for line in stream:
            if line.startswith(">"):
                if name is not None:
                    yield name, "".join(parts)
                name, parts = line[1:].split()[0], []
                if name in seen:
                    raise ValueError("Duplicate FASTA ID: " + name)
                seen.add(name)
            elif line.strip():
                if name is None:
                    raise ValueError("Sequence before FASTA header")
                parts.append(line.strip())
    if name is not None:
        yield name, "".join(parts)


def write_fasta(records, output):
    with open(output, "w", encoding="utf-8") as stream:
        for name, sequence in records:
            stream.write(">" + name + "\n")
            for i in range(0, len(sequence), 80):
                stream.write(sequence[i:i + 80] + "\n")


def table(path):
    with open(path, encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def write_table(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def ids(path):
    with open(path, encoding="utf-8-sig") as stream:
        result = [line.strip() for line in stream if line.strip() and not line.startswith("#")]
    if len(result) != len(set(result)):
        raise ValueError("Duplicate confirmed ID in " + str(path))
    return result


def normalize(args):
    """Use exact GFF transcript->gene relationships, preserving original IDs."""
    mapping, genes = {}, set()
    with opened(args.gff) as stream:
        for line in stream:
            if line.startswith("##FASTA"):
                break
            if line.startswith("#") or not line.strip():
                continue
            fields = line.rstrip().split("\t")
            if len(fields) != 9:
                raise ValueError("Expected GFF3, not GTF")
            attrs = dict(part.split("=", 1) for part in fields[8].split(";") if "=" in part)
            identifier = unquote(attrs.get("ID", ""))
            if fields[2] == "gene":
                genes.add(identifier)
            elif fields[2] in ("mRNA", "transcript"):
                parents = attrs.get("Parent", "").split(",")
                if len(parents) != 1 or not parents[0] or not identifier:
                    raise ValueError("Expected one gene parent per transcript")
                mapping[identifier] = unquote(parents[0])
    records, rows, seen = [], [], set()
    for transcript, sequence in fasta(args.input):
        gene = mapping.get(transcript, transcript if transcript in genes else "")
        if not gene:
            raise ValueError("FASTA transcript absent from GFF: " + transcript)
        if gene in seen:
            raise ValueError("More than one isoform for gene; keep longest first: " + gene)
        seen.add(gene)
        canonical = args.sample + "::" + gene
        records.append((canonical, sequence))
        rows.append([canonical, args.sample, gene, transcript])
    if not records:
        raise ValueError("No sequences extracted from GFF3")
    write_fasta(records, args.output)
    write_table(args.mapping, ["id", "sample", "gene", "transcript"], rows)


def hmmer(args):
    candidates = set()
    domains = []
    with open(args.input, encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("#") or not line.strip():
                continue
            f = line.split(maxsplit=22)
            if len(f) < 22:
                raise ValueError("Invalid HMMER domtblout")
            # hmmsearch: target=protein, query=HMM. i-Evalue=13, model=16/17, alignment=18/19 (1-based).
            coverage = (int(f[16]) - int(f[15]) + 1) / int(f[5])
            if float(f[12]) <= args.evalue and coverage >= args.coverage:
                start, end = int(f[17]) - 1, int(f[18])
                if not 0 <= start < end <= int(f[2]):
                    raise ValueError("Invalid HMMER protein coordinates")
                candidates.add(f[0])
                domains.append([f[0], start, end, f[3], f[12], coverage])
    Path(args.prefix + ".candidates.txt").write_text("".join(i + "\n" for i in sorted(candidates)), encoding="utf-8")
    write_table(args.prefix + ".domains.tsv", ["id", "start0", "end", "model", "i_evalue", "model_coverage"], domains)


def finalize(args):
    confirmed = ids(args.confirmed)
    candidates = set(ids(args.candidates))
    unknown = set(confirmed) - candidates
    if unknown:
        raise ValueError("Confirmed IDs are not passing candidates: " + ", ".join(sorted(unknown)))
    proteins = dict(fasta(args.proteins))
    missing = set(confirmed) - set(proteins)
    if missing:
        raise ValueError("Confirmed proteins missing: " + str(missing))
    domains = []
    for row in table(args.domains):
        if row["id"] in confirmed:
            start, end = int(row["start0"]), int(row["end"])
            domains.append((row["id"] + "::" + row["model"] + ":" + str(start + 1) + "-" + str(end),
                            proteins[row["id"]][start:end]))
    write_fasta(((i, proteins[i]) for i in confirmed), args.prefix + ".pep.fa")
    write_fasta(domains, args.prefix + ".domains.fa")
    Path(args.prefix + ".ids.txt").write_text("".join(i + "\n" for i in confirmed), encoding="utf-8")


def orthopav(args):
    samples = args.samples.split(",")
    if len(samples) != len(set(samples)):
        raise ValueError("Duplicate sample names")
    selected = set(ids(args.selected)) if args.selected else None
    rows, links, seen_groups, seen_genes = [], [], set(), set()
    for path in [args.input] + ([args.unassigned] if args.unassigned else []):
        with open(path, encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, delimiter="\t")
            header = next(reader)
            if header[1:] != samples:
                raise ValueError("Orthogroup sample columns/order must match manifest: " + str(header[1:]))
            for fields in reader:
                if len(fields) != len(header) or fields[0] in seen_groups:
                    raise ValueError("Malformed or duplicated orthogroup")
                seen_groups.add(fields[0])
                cells = [[i.strip() for i in cell.split(",") if i.strip()] for cell in fields[1:]]
                for sample, genes in zip(samples, cells):
                    for gene in genes:
                        if gene in seen_genes or not gene.startswith(sample + "::"):
                            raise ValueError("Gene duplicated or sample prefix mismatches: " + gene)
                        seen_genes.add(gene)
                if selected is not None and not any(gene in selected for genes in cells for gene in genes):
                    continue
                filtered = [[g for g in genes if selected is None or g in selected] for genes in cells]
                counts = [len(genes) for genes in filtered]
                present = sum(bool(n) for n in counts)
                category = "core" if present == len(samples) else "private" if present == 1 else (
                    "softcore" if present / len(samples) >= args.softcore else "dispensable")
                rows.append([fields[0], *counts, present, category])
                links.extend([fields[0], sample, gene] for sample, genes in zip(samples, filtered) for gene in genes)
    if selected is not None and selected - seen_genes:
        raise ValueError("Selected genes absent from orthogroups: " + str(sorted(selected - seen_genes)))
    write_table(args.prefix + ".counts.tsv", ["group", *samples, "present_samples", "class"], rows)
    write_table(args.prefix + ".pav.tsv", ["group", *samples], ([r[0], *(int(n > 0) for n in r[1:1 + len(samples)])] for r in rows))
    write_table(args.prefix + ".genes.tsv", ["group", "sample", "gene"], links)
    # Seeded permutations; counts are conditional on the provided genomes/annotation.
    rng, curves = random.Random(args.seed), []
    sets = [{r[0] for r in rows if r[1 + i] > 0} for i in range(len(samples))]
    for repeat in range(args.permutations):
        order = list(range(len(samples)))
        rng.shuffle(order)
        union, core = set(), set(sets[order[0]])
        for k, index in enumerate(order, 1):
            union |= sets[index]
            core &= sets[index]
            curves.append([repeat + 1, k, len(union), len(core)])
    write_table(args.prefix + ".curves.tsv", ["permutation", "samples", "pan", "core"], curves)


def intervals(args):
    rows = []
    with opened(args.input) as stream:
        for line in stream:
            if line.startswith("#"):
                continue
            f = line.rstrip().split("\t")
            if len(f) < 8:
                raise ValueError("VCF requires at least 8 columns")
            start = int(f[1]) - 1
            info = dict(item.split("=", 1) for item in f[7].split(";") if "=" in item)
            # Breakend remote coordinates cannot be represented as one continuous interval.
            if "[" in f[4] or "]" in f[4]:
                end, kind = start + 1, "BND_anchor"
            else:
                end = int(info["END"]) if "END" in info else start + len(f[3])
                kind = info.get("SVTYPE", "sequence")
                if "<" in f[4] and "END" not in info and kind != "INS":
                    raise ValueError("Symbolic non-insertion VCF record requires INFO/END")
            if start < 0 or end <= start:
                raise ValueError("Invalid VCF interval")
            identifier = f[2] if f[2] != "." else f[0] + ":" + f[1] + ":" + f[3] + ":" + f[4]
            rows.append([f[0], start, end, identifier, kind])
    with open(args.output, "w", encoding="utf-8", newline="") as stream:
        csv.writer(stream, delimiter="\t", lineterminator="\n").writerows(rows)


def subset(args):
    wanted = set(ids(args.ids))
    records = [(name, seq) for name, seq in fasta(args.input) if name in wanted]
    if wanted - {name for name, _ in records}:
        raise ValueError("FASTA missing selected IDs")
    write_fasta(records, args.output)


def select_matrix(args):
    wanted = set(ids(args.ids))
    with open(args.input, encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        header, rows, seen = next(reader), [], set()
        for row in reader:
            if len(row) != len(header) or row[0] in seen:
                raise ValueError("Duplicate genes or malformed matrix")
            seen.add(row[0])
            if row[0] in wanted:
                rows.append(row)
        if wanted - seen:
            raise ValueError("Selected genes absent from matrix: " + str(sorted(wanted - seen)))
    write_table(args.output, header, rows)


def coexpression(args):
    with open(args.input, encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        header = next(reader)
        rows = []
        seen = set()
        for row in reader:
            if row[0] in seen or len(row) != len(header):
                raise ValueError("Duplicate IDs or malformed expression matrix")
            seen.add(row[0])
            values = [float(x) for x in row[1:]]
            if len(values) < 3 or not all(math.isfinite(x) for x in values):
                raise ValueError("Expression requires >=3 finite numeric observations per gene")
            rows.append((row[0], values))
    wanted = set(ids(args.ids))
    if wanted - seen:
        raise ValueError("Family IDs absent from expression matrix")
    result = []
    for (a, x), (b, y) in itertools.combinations(rows, 2):
        if a not in wanted and b not in wanted:
            continue
        xm, ym = statistics.mean(x), statistics.mean(y)
        denom = math.sqrt(sum((v - xm) ** 2 for v in x) * sum((v - ym) ** 2 for v in y))
        if denom:
            r = sum((v - xm) * (w - ym) for v, w in zip(x, y)) / denom
            if abs(r) >= args.correlation:
                result.append([a, b, r, len(x)])
    write_table(args.output, ["gene_a", "gene_b", "pearson_r", "observations"], result)


def novel(args):
    alignments = {}
    with open(args.paf, encoding="utf-8") as stream:
        for line in stream:
            f = line.rstrip().split("\t")
            if len(f) < 12:
                raise ValueError("Malformed PAF")
            length, start, end = int(f[1]), int(f[2]), int(f[3])
            if not 0 <= start < end <= length:
                raise ValueError("Invalid PAF query coordinates")
            alignments.setdefault(f[0], []).append((start, end))
    selected, report = [], []
    for name, sequence in fasta(args.fasta):
        merged = []
        for start, end in sorted(alignments.get(name, [])):
            if end > len(sequence):
                raise ValueError("PAF and FASTA lengths disagree")
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        covered = sum(end - start for start, end in merged)
        fraction = covered / len(sequence) if sequence else 1
        keep = len(sequence) >= args.min_length and fraction <= args.max_coverage
        report.append([name, len(sequence), covered, fraction, int(keep)])
        if keep:
            selected.append((args.prefix + "::" + name, sequence))
    write_fasta(selected, args.prefix + ".novel.fa")
    write_table(args.prefix + ".coverage.tsv", ["contig", "length", "covered_bases", "reference_coverage", "candidate_novel"], report)


def depth(args):
    with open(args.input, encoding="utf-8") as stream, open(args.output, "w", encoding="utf-8") as output:
        for line in stream:
            f = line.rstrip().split("\t")
            if len(f) != 4:
                raise ValueError("Expected bedGraph with four columns")
            if float(f[3]) >= args.min_depth:
                output.write("\t".join(f[:3]) + "\n")


def coverage(args):
    samples, values, order = args.samples.split(","), {}, []
    for sample in samples:
        current = {}
        with open(Path(args.directory) / (sample + ".coverage.tsv"), encoding="utf-8") as stream:
            for line in stream:
                f = line.rstrip().split("\t")
                if len(f) != 8 or f[3] in current:
                    raise ValueError("Input genes must be BED4 with unique IDs")
                current[f[3]] = float(f[7])
                if not 0 <= current[f[3]] <= 1:
                    raise ValueError("Invalid bedtools coverage fraction")
        if not current:
            raise ValueError("No genes in coverage output")
        if values and set(current) != set(values):
            raise ValueError("Gene IDs differ between samples")
        if not values:
            order = list(current)
            values = {gene: [] for gene in order}
        for gene in order:
            values[gene].append(current[gene])
    write_table(args.prefix + ".coverage.tsv", ["gene", *samples], ([gene, *values[gene]] for gene in order))
    write_table(args.prefix + ".candidate_pav.tsv", ["gene", *samples],
                ([gene, *(int(x >= args.min_coverage) for x in values[gene])] for gene in order))


def pairs(args):
    proteins, cds = dict(fasta(args.proteins)), dict(fasta(args.cds))
    rows = table(args.pairs)
    seen = set()
    manifest = []
    for i, row in enumerate(rows, 1):
        a, b = row["gene_a"], row["gene_b"]
        key = tuple(sorted([a, b]))
        if a == b or key in seen:
            raise ValueError("Self-pair or duplicate gene pair")
        seen.add(key)
        if any(g not in proteins or g not in cds for g in key):
            raise ValueError("Pair ID absent from protein/CDS FASTA")
        if any(len(cds[g]) % 3 for g in key):
            raise ValueError("CDS length must be a multiple of three")
        path = Path(args.directory) / ("pair-%06d" % i)
        path.mkdir()
        write_fasta(((g, proteins[g]) for g in [a, b]), path / "pep.fa")
        write_fasta(((g, cds[g]) for g in [a, b]), path / "cds.fa")
        manifest.append([path.name, a, b])
    if not rows:
        raise ValueError("No gene pairs")
    write_table(Path(args.directory) / "pairs.tsv", ["directory", "gene_a", "gene_b"], manifest)


def axt(args):
    records = list(fasta(args.input))
    if len(records) != 2 or len(records[0][1]) != len(records[1][1]) or len(records[0][1]) % 3:
        raise ValueError("Expected a pair of equal-length codon aligned FASTA records")
    # Remove whole codons containing gaps/ambiguous bases in either member.
    one, two = [], []
    for i in range(0, len(records[0][1]), 3):
        a, b = records[0][1][i:i+3].upper(), records[1][1][i:i+3].upper()
        if set(a + b) <= set("ACGT"):
            one.append(a)
            two.append(b)
    if not one:
        raise ValueError("No complete unambiguous aligned codons")
    Path(args.output).write_text(args.name + "\n" + "".join(one) + "\n" + "".join(two) + "\n\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    definitions = {
        "normalize": (normalize, ["gff", "input", "output", "mapping", "sample"]),
        "hmmer": (hmmer, ["input", "prefix"]),
        "finalize": (finalize, ["confirmed", "candidates", "proteins", "domains", "prefix"]),
        "orthopav": (orthopav, ["input", "samples", "prefix"]),
        "intervals": (intervals, ["input", "output"]),
        "subset": (subset, ["input", "ids", "output"]),
        "matrix": (select_matrix, ["input", "ids", "output"]),
        "coexpression": (coexpression, ["input", "ids", "output"]),
        "novel": (novel, ["fasta", "paf", "prefix"]),
        "depth": (depth, ["input", "output"]),
        "coverage": (coverage, ["directory", "samples", "prefix"]),
        "pairs": (pairs, ["pairs", "proteins", "cds", "directory"]),
        "axt": (axt, ["input", "output", "name"]),
    }
    for name, (func, fields) in definitions.items():
        sub = subs.add_parser(name)
        sub.set_defaults(func=func)
        for field in fields:
            sub.add_argument("--" + field, required=True)
        if name == "hmmer":
            sub.add_argument("--evalue", type=float, default=1e-5)
            sub.add_argument("--coverage", type=float, default=.9)
        if name == "orthopav":
            sub.add_argument("--unassigned")
            sub.add_argument("--selected")
            sub.add_argument("--softcore", type=float, default=.95)
            sub.add_argument("--permutations", type=int, default=100)
            sub.add_argument("--seed", type=int, default=42)
        if name == "coexpression":
            sub.add_argument("--correlation", type=float, default=.9)
        if name == "novel":
            sub.add_argument("--min-length", type=int, default=500)
            sub.add_argument("--max-coverage", type=float, default=.2)
        if name == "depth":
            sub.add_argument("--min-depth", type=int, default=2)
        if name == "coverage":
            sub.add_argument("--min-coverage", type=float, default=.8)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, OSError, KeyError, StopIteration) as error:
        parser.exit(2, "ERROR: " + str(error) + "\n")


if __name__ == "__main__":
    main()
