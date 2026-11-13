import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from report import CHAPTERS,SIGNS,make_pdf
class Core(unittest.TestCase):
 def test_questions(self):
  self.assertEqual(len(CHAPTERS),30)
  self.assertEqual(sum(len(x['choices']) for x in CHAPTERS),131)
 def test_pdf(self):
  answers=[next(iter(c['choices'])) for c in CHAPTERS]
  self.assertTrue(make_pdf(answers,None,'TSD-TEST').startswith(b'%PDF'))
 def test_bad_answer(self):
  with self.assertRaises(ValueError):make_pdf(['x']*30)
if __name__=='__main__':unittest.main()
