import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from monitor import load_baseline


class JsonBaselineTests(unittest.TestCase):
    def test_duplicate_members_at_all_levels(self):
        for text in ('{"errors":["gap"],"errors":[]}', '{"files":{"a":{},"a":{}}}', '{"files":{"a":{"size":1,"size":2}}}'):
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'baseline.json'
                path.write_text(text)
                with self.subTest(text=text), self.assertRaisesRegex(ValueError,'Duplicate baseline JSON key'):
                    load_baseline(path)

    def test_repeated_fields_in_separate_records_are_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'baseline.json'
            value={'files':{'a':{'size':1},'b':{'size':2}}}
            path.write_text(json.dumps(value))
            self.assertEqual(load_baseline(path),value)

    def test_cli_duplicate_baseline_exits_two_without_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'watched';root.mkdir()
            baseline=Path(directory)/'baseline.json'
            baseline.write_text('{"errors":["gap"],"errors":[]}')
            result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'monitor.py'),'check',str(root),str(baseline)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(result.stdout,'')
            self.assertIn('Duplicate baseline JSON key',result.stderr)
            self.assertNotIn('Traceback',result.stderr)
