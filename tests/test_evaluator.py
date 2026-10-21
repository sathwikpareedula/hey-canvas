import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evaluate import evaluate, retrieval_metrics, extract_xy, check_rule

class EvaluatorTests(unittest.TestCase):
    def test_missing_is_not_run(self):
        result=evaluate([{'id':'a','category':'x','checks':[],'expected_source_ids':[],'forbidden_source_ids':[],'course_id':'c'}],[])
        self.assertEqual(result[0]['status'],'NOT_RUN')
    def test_correct_response(self):
        case={'id':'a','category':'x','checks':[{'type':'contains_all','values':['2.1']}], 'expected_source_ids':['s1'],'forbidden_source_ids':['s2'],'course_id':'c'}
        result=evaluate([case],[{'case_id':'a','answer':'Read 2.1','source_ids':['s1'],'course_id':'c'}])
        self.assertEqual(result[0]['status'],'PASS')
    def test_wrong_source_fails(self):
        case={'id':'a','category':'x','checks':[], 'expected_source_ids':['s1'],'forbidden_source_ids':['s2'],'course_id':'c'}
        self.assertEqual(evaluate([case],[{'case_id':'a','answer':'ok','source_ids':['s2']}])[0]['status'],'FAIL')
    def test_missing_sources_not_verified(self):
        case={'id':'a','category':'x','checks':[], 'expected_source_ids':[],'forbidden_source_ids':[],'course_id':'c'}
        self.assertEqual(evaluate([case],[{'case_id':'a','answer':'ok'}])[0]['status'],'NOT_VERIFIED')
    def test_wrong_window_fails(self):
        case={'id':'a','category':'x','checks':[{'type':'date_window','value':'2026-10-01/2026-10-31'}], 'expected_source_ids':[],'forbidden_source_ids':[],'course_id':'c'}
        self.assertEqual(evaluate([case],[{'case_id':'a','answer':'Nothing due today','source_ids':[],'normalized_window':'2026-10-18'}])[0]['status'],'FAIL')
    def test_unreported_window_not_verified(self):
        case={'id':'a','category':'x','checks':[{'type':'date_window','value':'2026-10-01/2026-10-31'}], 'expected_source_ids':[],'forbidden_source_ids':[],'course_id':'c'}
        self.assertEqual(evaluate([case],[{'case_id':'a','answer':'ok','source_ids':[]}])[0]['status'],'NOT_VERIFIED')
    def test_internal_leak(self):
        self.assertFalse(check_rule({'type':'no_internal_leak'},'ROUTING_EVIDENCE foo')[0])
    def test_numerical(self):
        self.assertEqual(extract_xy('x = 2, y = 3'),(2.,3.))
        self.assertFalse(check_rule({'type':'numeric_pair','x':2,'y':3},'x = 5, y = 3')[0])
    def test_retrieval_metrics(self):
        m=retrieval_metrics([{'id':'a','expected_source_ids':['a','b']}],[{'case_id':'a','source_ids':['a','c']}])
        self.assertAlmostEqual(m['micro_precision'],0.5)
        self.assertAlmostEqual(m['micro_recall'],0.5)
    def test_duplicate_fails(self):
        case={'id':'a','category':'x','checks':[], 'expected_source_ids':[],'forbidden_source_ids':[],'course_id':'c'}
        self.assertEqual(evaluate([case],[{'case_id':'a','answer':'ok','source_ids':[]},{'case_id':'a','answer':'ok','source_ids':[]}])[0]['status'],'FAIL')
if __name__=='__main__': unittest.main()
