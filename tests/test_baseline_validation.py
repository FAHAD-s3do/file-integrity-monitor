import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from monitor import compare, snapshot, validate_snapshot


class BaselineValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'watched'
        self.root.mkdir()
        (self.root / 'file').write_text('stable')
        self.saved = snapshot(self.root)

    def test_snapshot_accepts_generated_data(self):
        self.assertIs(validate_snapshot(self.saved), self.saved)

    def test_unsafe_file_paths_are_rejected(self):
        for path in ('../escape', '/absolute', 'folder/../file', 'folder\\file', '.'):
            malformed = copy.deepcopy(self.saved)
            malformed['files'] = {path: next(iter(self.saved['files'].values()))}
            with self.subTest(path=path), self.assertRaises(ValueError):
                compare(malformed, self.saved)

    def test_invalid_file_records_are_rejected(self):
        invalid = (
            None,
            {'sha256': 'xyz', 'size': 6, 'mode': 0o644},
            {'sha256': '0' * 64, 'size': -1, 'mode': 0o644},
            {'sha256': '0' * 64, 'size': 6, 'mode': 0o10000},
        )
        for record in invalid:
            malformed = copy.deepcopy(self.saved)
            malformed['files']['file'] = record
            with self.subTest(record=record), self.assertRaises(ValueError):
                compare(malformed, self.saved)

    def test_invalid_coverage_fields_are_rejected(self):
        for field, value in (('errors', 'none'), ('errors', [1]), ('skipped', None), ('skipped', ['../unknown'])):
            malformed = copy.deepcopy(self.saved)
            malformed[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                compare(malformed, self.saved)

    def test_cli_rejects_malformed_baseline_without_traceback(self):
        baseline = Path(self.tmp.name) / 'baseline.json'
        malformed = copy.deepcopy(self.saved)
        malformed['files']['../escape'] = malformed['files'].pop('file')
        baseline.write_text(json.dumps(malformed))
        script = Path(__file__).resolve().parents[1] / 'monitor.py'
        result = subprocess.run(
            [sys.executable, str(script), 'check', str(self.root), str(baseline)],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('canonical relative POSIX paths', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
