import csv
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
MODULE = next(p.name for p in (ROOT / 'src').iterdir() if p.is_dir() and (p / 'cli.py').exists())
cli = importlib.import_module(MODULE + '.cli')
spec = importlib.util.spec_from_file_location('bio_data', ROOT / 'workflows' / 'data.py')
bio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bio)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def put(self, name, content):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8', newline='\n')
        return target

    def helper(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(ROOT / 'workflows/data.py'), *map(str, args)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def config(self, extra='', samples=None, docker=''):
        self.put('samples.tsv', samples or 'sample\tgenome\tgff\tread1\tread2\nA\t/data/a.fa\t/data/a.gff3\t/data/a.1.fq\t/data/a.2.fq\nB\t/data/b.fa\t/data/b.gff3\t/data/b.1.fq\t/data/b.2.fq\n')
        return self.put('config.toml', '[pipeline]\nSAMPLES_TSV="samples.tsv"\n' + extra + '\n[docker]\nhost_workdir="results"\nhost_data="data"\n' + docker)

    def test_duplicate_samples_rejected(self):
        path = self.config(samples='sample\nA\nA\n')
        with self.assertRaisesRegex(cli.ConfigError, 'duplicate'):
            cli.Config(path)

    def test_unknown_keys_numeric_bounds_and_mounts(self):
        for setting, message in [('THREAD=2', 'Unknown'), ('THREADS=0', 'numeric'),
                                 ('SOFTCORE=1.1', 'numeric'), ('THREADS=true', 'numeric'),
                                 ('PERMUTATIONS=2.5', 'numeric')]:
            with self.subTest(setting=setting), self.assertRaisesRegex(cli.ConfigError, message):
                cli.Config(self.config(setting))
        with self.assertRaisesRegex(cli.ConfigError, 'Overlapping'):
            cli.Config(self.config(docker='host_database="data/nested"'))

    def test_docker_paths_and_required_inputs(self):
        with self.assertRaisesRegex(cli.ConfigError, 'absolute POSIX'):
            cli.Config(self.config('ORTHOGROUPS_TSV="relative.tsv"'))
        config = cli.Config(self.config())
        stage = 'family-pav' if MODULE.startswith('pangene_') else 'pav'
        with self.assertRaisesRegex(cli.ConfigError, 'ORTHOGROUPS_TSV'):
            config.validate([stage])
        with self.assertRaisesRegex(cli.ConfigError, 'Missing sample input'):
            config.validate(['prepare'], check_files=True)

    def test_shell_data_is_quoted_not_executed(self):
        marker = self.root / 'injected'
        config = cli.Config(self.config('TAX_SCOPE="$(touch injected); value"'))
        self.assertIn("TAX_SCOPE='$(touch injected); value'", config.shell())
        self.assertFalse(marker.exists())
        argv = cli.command(config, 'prepare', '/tmp/safe config.sh')
        self.assertIsInstance(argv, list)
        self.assertIn('WORKFLOW_CONFIG=/opt/config.sh', argv)
        self.assertTrue(any('dst=/data,readonly' in arg for arg in argv))
        self.assertFalse(any('--privileged' == arg for arg in argv))

    def test_dry_run_has_no_side_effects(self):
        path = self.config()
        with patch.object(cli, 'run', side_effect=AssertionError('must not execute')):
            self.assertEqual(cli.main(['run','prepare','--config',str(path),'--dry-run']), 0)
        self.assertFalse((self.root / 'results').exists())
        self.assertFalse((self.root / ('.' + cli.NAME)).exists())

    def test_init_preserves_existing_user_files(self):
        self.assertEqual(cli.main(['init', str(self.root)]), 0)
        original = (self.root / 'config.toml').read_bytes()
        self.assertEqual(cli.main(['init', str(self.root)]), 2)
        self.assertEqual((self.root / 'config.toml').read_bytes(), original)

    def test_failure_stops_later_stages_and_records_status(self):
        path = self.config(samples='sample\nA\n')
        config = cli.Config(path, 'local')
        stages = {'first': {'description':'fixture'}, 'later': {'description':'fixture'}}
        def fake_command(config, stage, *args):
            return [sys.executable, '-c', 'import sys; print("fixture"); sys.exit(7)' if stage == 'first' else 'raise AssertionError("later ran")']
        with patch.object(cli, 'STAGES', stages), patch.object(cli, 'command', fake_command):
            with self.assertRaisesRegex(cli.ConfigError, 'failed \(7\)'):
                cli.run(config, ['first','later'], sys.executable)
        report = next((self.root / ('.' + cli.NAME) / 'runs').glob('*/run.json'))
        metadata = json.loads(report.read_text())
        self.assertEqual(metadata['status'], 'failed')
        self.assertEqual([s['stage'] for s in metadata['stages']], ['first'])
        self.assertEqual(metadata['stages'][0]['returncode'], 7)
        self.assertIn('fixture', Path(metadata['stages'][0]['log']).read_text())

    def test_gff_exact_parent_mapping_preserves_underscores(self):
        gff = self.put('in.gff3', 'chr1\t.\tgene\t1\t9\t.\t+\t.\tID=gene_a_1\nchr1\t.\tmRNA\t1\t9\t.\t+\t.\tID=tx_1;Parent=gene_a_1\n')
        fa = self.put('in.fa', '>tx_1\nMKT\n')
        self.helper('normalize','--gff',gff,'--input',fa,'--output',self.root/'out.fa','--mapping',self.root/'ids.tsv','--sample','Sample_A')
        self.assertEqual(list(bio.fasta(self.root/'out.fa')), [('Sample_A::gene_a_1','MKT')])
        self.assertEqual(bio.table(self.root/'ids.tsv')[0]['transcript'], 'tx_1')

    def test_hmmer_model_coverage_and_zero_based_domains(self):
        # 90/100 model positions, protein alignment 2..4. Correct coverage is model, not protein span.
        dom = self.put('hits.txt', 'A::g - 6 MODEL - 100 1e-20 50 0 1 1 1e-10 1e-10 40 0 1 90 2 4 1 5 0.99 desc\n')
        self.helper('hmmer','--input',dom,'--prefix',self.root/'A','--coverage','.9')
        rows = bio.table(self.root/'A.domains.tsv')
        self.assertEqual((rows[0]['start0'], rows[0]['end']), ('1','4'))
        proteins = self.put('pep.fa', '>A::g\nABCDEF\n>A::g10\nXXXXXX\n')
        confirmed = self.put('confirmed.txt','A::g\n')
        self.helper('finalize','--confirmed',confirmed,'--candidates',self.root/'A.candidates.txt','--proteins',proteins,'--domains',self.root/'A.domains.tsv','--prefix',self.root/'final')
        self.assertEqual(list(bio.fasta(self.root/'final.domains.fa'))[0][1], 'BCD')
        self.assertEqual(len(list(bio.fasta(self.root/'final.pep.fa'))), 1)
        self.put('confirmed.txt', 'A::g10\n')
        self.helper('finalize','--confirmed',confirmed,'--candidates',self.root/'A.candidates.txt','--proteins',proteins,'--domains',self.root/'A.domains.tsv','--prefix',self.root/'bad', expected=2)

    def test_empty_confirmed_list_is_valid_absence(self):
        self.helper('finalize','--confirmed',self.put('confirmed',''),'--candidates',self.put('candidate',''),
                    '--proteins',self.put('pep','>A::g\nMKT\n'),'--domains',self.put('domains','id\tstart0\tend\tmodel\n'),
                    '--prefix',self.root/'none')
        self.assertEqual((self.root/'none.pep.fa').read_text(), '')

    def test_pav_first_record_singletons_and_reproducible_curves(self):
        groups = self.put('groups.tsv', 'Orthogroup\tA\tB\nOG1\tA::g1, A::g10\tB::g1\nOG2\tA::g2\t\n')
        single = self.put('unassigned.tsv', 'Orthogroup\tA\tB\nOG3\t\tB::g3\n')
        for prefix in ['one','two']:
            self.helper('orthopav','--input',groups,'--unassigned',single,'--samples','A,B','--prefix',self.root/prefix,'--permutations','3')
        counts = bio.table(self.root/'one.counts.tsv')
        self.assertEqual([r['group'] for r in counts], ['OG1','OG2','OG3'])
        self.assertEqual(counts[0]['A'], '2')
        self.assertEqual(counts[0]['class'], 'core')
        self.assertEqual(counts[2]['class'], 'private')
        self.assertEqual((self.root/'one.curves.tsv').read_bytes(), (self.root/'two.curves.tsv').read_bytes())
        selected = self.put('selected', 'A::g1\n')
        self.helper('orthopav','--input',groups,'--samples','A,B','--selected',selected,'--prefix',self.root/'select')
        self.assertEqual(bio.table(self.root/'select.counts.tsv')[0]['A'], '1')
        self.assertEqual(bio.table(self.root/'select.counts.tsv')[0]['B'], '0')

    def test_vcf_info_end_indels_and_breakend_anchors(self):
        vcf = self.put('sv.vcf', '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\nchr1\t10\tv1\tN\t<DEL>\t.\tPASS\tSVTYPE=DEL;X=1;END=20\nchr1\t30\t.\tACG\tA\t.\tPASS\t.\nchr1\t40\tbnd\tN\tN]chr2:50]\t.\tPASS\tSVTYPE=BND\n')
        self.helper('intervals','--input',vcf,'--output',self.root/'out.bed')
        rows = [line.split('\t') for line in (self.root/'out.bed').read_text().splitlines()]
        self.assertEqual(rows[0][:4], ['chr1','9','20','v1'])
        self.assertEqual(rows[1][1:3], ['29','32'])
        self.assertEqual(rows[2][1:3], ['39','40'])

    def test_novel_paf_overlap_is_not_double_counted(self):
        fa = self.put('contigs.fa', '>c\n' + 'A'*100 + '\n')
        paf = self.put('contigs.paf', 'c\t100\t0\t15\t+\tr\t100\t0\t15\t15\t15\t60\nc\t100\t5\t20\t+\tr\t100\t20\t35\t15\t15\t60\n')
        self.helper('novel','--fasta',fa,'--paf',paf,'--prefix',self.root/'new','--min-length','50','--max-coverage','.2')
        self.assertEqual(bio.table(self.root/'new.coverage.tsv')[0]['covered_bases'], '20')
        self.assertEqual(len(list(bio.fasta(self.root/'new.novel.fa'))),1)

    def test_expression_exact_ids_and_coexpression(self):
        expression = self.put('expr.tsv','gene\ts1\ts2\ts3\ng1\t1\t2\t3\ng10\t3\t2\t1\nconstant\t2\t2\t2\n')
        selected = self.put('ids','g1\n')
        self.helper('matrix','--input',expression,'--ids',selected,'--output',self.root/'subset.tsv')
        self.assertEqual([r['gene'] for r in bio.table(self.root/'subset.tsv')], ['g1'])
        self.helper('coexpression','--input',expression,'--ids',selected,'--output',self.root/'edges.tsv')
        edges = bio.table(self.root/'edges.tsv')
        self.assertEqual(len(edges),1)
        self.assertEqual(float(edges[0]['pearson_r']),-1)

    def test_codon_pair_filter_preserves_reading_frame(self):
        aligned = self.put('codons.fa','>a\nATGA--GCCNNN\n>b\nATGAAAGCTAAA\n')
        self.helper('axt','--input',aligned,'--output',self.root/'out.axt','--name','pair1')
        self.assertEqual((self.root/'out.axt').read_text(),'pair1\nATGGCC\nATGGCT\n\n')

    @unittest.skipUnless(os.environ.get('BASH_FOR_TEST'), 'Set BASH_FOR_TEST for real Bash integration')
    def test_real_bash_stage_uses_generated_config_and_bundled_helper(self):
        bash = os.environ['BASH_FOR_TEST']
        python = Path(sys.executable).as_posix()
        wrappers = self.root / 'bin'
        wrappers.mkdir()
        self.put('bin/python3', '#!/usr/bin/sh\nexec ' + shlex.quote(python) + ' "$@"\n')
        if os.name != 'nt':
            (wrappers/'python3').chmod(0o755)
        if MODULE.startswith('pangene_'):
            stage = 'family-pav'
            input_file = self.put('groups.tsv', 'Orthogroup\tA\tB\nOG1\tA::g\tB::g\n')
            extra = 'ORTHOGROUPS_TSV=' + json.dumps(input_file.as_posix())
            expected = 'families.pav.tsv'
        else:
            stage = 'expression'
            matrix = self.put('expr.tsv', 'gene\tx\ty\tz\ng1\t1\t2\t3\ng10\t3\t2\t1\n')
            genes = self.put('ids', 'g1\n')
            extra = 'EXPRESSION_TSV=' + json.dumps(matrix.as_posix()) + '\nEXPRESSION_IDS=' + json.dumps(genes.as_posix())
            expected = 'family.expression.tsv'
        config = cli.Config(self.config(extra), 'local')
        with patch.dict(os.environ, {'PATH': str(wrappers) + os.pathsep + os.environ['PATH']}):
            cli.run(config, [stage], bash)
        output = self.root/'results'/stage/expected
        self.assertTrue(output.is_file())
        if stage == 'expression':
            self.assertEqual([r['gene'] for r in bio.table(output)], ['g1'])
        else:
            self.assertEqual(bio.table(output)[0], {'group':'OG1', 'A':'1', 'B':'1'})
        # A second invocation must reject an existing output directory.
        with patch.dict(os.environ, {'PATH': str(wrappers) + os.pathsep + os.environ['PATH']}):
            with self.assertRaisesRegex(cli.ConfigError, 'failed'):
                cli.run(config, [stage], bash)


if __name__ == '__main__':
    unittest.main()
