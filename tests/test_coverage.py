import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from monitor import compare, snapshot


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'watched'
        self.root.mkdir()
        (self.root/'file').write_text('stable')
        self.saved=snapshot(self.root)

    def test_baseline_skip_prevents_complete_verdict(self):
        old=dict(self.saved,skipped=['previously-unreadable-link'])
        result=compare(old,self.saved)
        self.assertFalse(result['complete'])
        self.assertFalse(result['baseline_complete'])
        self.assertTrue(result['current_complete'])
        self.assertEqual(result['baseline_skipped'],old['skipped'])

    def test_baseline_error_is_exposed(self):
        old=dict(self.saved,errors=['collection failed'])
        result=compare(old,self.saved)
        self.assertFalse(result['complete'])
        self.assertEqual(result['baseline_errors'],['collection failed'])

    def test_current_skip_without_absence_is_incomplete(self):
        result=compare(self.saved,dict(self.saved,skipped=['link']))
        self.assertFalse(result['complete'])
        self.assertFalse(result['current_complete'])
        self.assertEqual(result['unresolved_absences'],[])

    def test_known_changes_remain_visible_with_baseline_gap(self):
        old=dict(self.saved,skipped=['link'])
        (self.root/'file').write_text('changed')
        result=compare(old,snapshot(self.root))
        self.assertEqual(result['modified'],['file'])
        self.assertFalse(result['complete'])

    def run_cli(self, action, baseline):
        script=Path(__file__).resolve().parents[1]/'monitor.py'
        return subprocess.run([sys.executable,str(script),action,str(self.root),str(baseline)],capture_output=True,text=True)

    def test_cli_current_skip_exits_two_without_removals(self):
        baseline=Path(self.tmp.name)/'baseline.json'
        baseline.write_text(json.dumps(self.saved))
        (self.root/'link').symlink_to(self.root/'file')
        result=self.run_cli('check',baseline)
        self.assertEqual(result.returncode,2)
        report=json.loads(result.stdout)
        self.assertFalse(report['complete'])
        self.assertEqual(report['unresolved_absences'],[])

    def test_cli_saved_skip_stays_incomplete_after_link_removed(self):
        baseline=Path(self.tmp.name)/'baseline.json'
        (self.root/'link').symlink_to(self.root/'file')
        self.assertEqual(self.run_cli('baseline',baseline).returncode,0)
        (self.root/'link').unlink()
        result=self.run_cli('check',baseline)
        self.assertEqual(result.returncode,2)
        self.assertEqual(json.loads(result.stdout)['baseline_skipped'],['link'])

    def test_cli_complete_unchanged_and_changed_exit_codes(self):
        baseline=Path(self.tmp.name)/'baseline.json'
        baseline.write_text(json.dumps(self.saved))
        self.assertEqual(self.run_cli('check',baseline).returncode,0)
        (self.root/'file').write_text('changed')
        self.assertEqual(self.run_cli('check',baseline).returncode,1)
