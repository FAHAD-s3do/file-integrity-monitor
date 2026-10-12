import tempfile
import unittest
from pathlib import Path
from monitor import snapshot,compare
class Tests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);(self.root/'a').write_text('old')
 def tearDown(self):self.tmp.cleanup()
 def test_unchanged(self):
  s=snapshot(self.root);r=compare(s,snapshot(self.root));self.assertFalse(r['modified']);self.assertTrue(r['complete'])
 def test_modified_added_removed(self):
  s=snapshot(self.root);(self.root/'a').unlink();(self.root/'b').write_text('new');r=compare(s,snapshot(self.root));self.assertEqual(r['removed'],['a']);self.assertEqual(r['added'],['b'])
 def test_content_change(self):
  s=snapshot(self.root);(self.root/'a').write_text('new');self.assertEqual(compare(s,snapshot(self.root))['modified'],['a'])
 def test_mode_change(self):
  s=snapshot(self.root);(self.root/'a').chmod(0o700);self.assertEqual(compare(s,snapshot(self.root))['modified'],['a'])
 def test_symlink_not_followed(self):
  (self.root/'link').symlink_to('/etc/passwd');r=snapshot(self.root);self.assertNotIn('link',r['files']);self.assertIn('link',r['skipped'])
 def test_errors_do_not_prove_removal(self):
  s=snapshot(self.root);n=dict(s,files={},errors=['unreadable']);r=compare(s,n);self.assertEqual(r['removed'],[]);self.assertEqual(r['unresolved_absences'],['a'])
 def test_root_mismatch(self):
  s=snapshot(self.root)
  with self.assertRaises(ValueError):compare(s,dict(s,root='/different'))
