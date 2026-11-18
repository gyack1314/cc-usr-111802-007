"""验证观测元数据约束与跨指标联读结论。"""
import json,unittest
from pathlib import Path
from climate_analysis.evidence import connect,receive
from climate_analysis.report import generate
from climate_analysis.lineup import (coverage_fit,FIT_EXACT,FIT_NESTED,FIT_NONE,
  covariation,evaluate_claims,gaps,common_window,indicators)
DATA=json.loads((Path(__file__).resolve().parents[1]/'data/example.json').read_text(encoding='utf8'))
def load():
 db=connect(':memory:')
 for doc in DATA['documents']:receive(db,doc)
 return db
class Metadata(unittest.TestCase):
 def test_observation_requires_metadata(self):
  doc=json.loads(json.dumps(DATA['documents'][0]))
  del doc['records'][0]['payload']['published_at']
  db=connect(':memory:')
  with self.assertRaises(ValueError):receive(db,doc)
 def test_unknown_revision_status_rejected(self):
  doc=json.loads(json.dumps(DATA['documents'][0]))
  doc['records'][0]['payload']['revision_status']='guess'
  db=connect(':memory:')
  with self.assertRaises(ValueError):receive(db,doc)
 def test_period_order_rejected(self):
  doc=json.loads(json.dumps(DATA['documents'][0]))
  doc['records'][0]['payload']['period_start']='2026-07-01'
  db=connect(':memory:')
  with self.assertRaises(ValueError):receive(db,doc)
class Coverage(unittest.TestCase):
 def test_fit(self):
  self.assertEqual(coverage_fit('global','global'),FIT_EXACT)
  self.assertEqual(coverage_fit('global','global_ocean'),FIT_NESTED)
  self.assertEqual(coverage_fit('ocean_0_700m','ocean_700_2000m'),FIT_NONE)
class Lineup(unittest.TestCase):
 def setUp(self):self.db=load()
 def tearDown(self):self.db.close()
 def test_common_window_intersects_period_unions(self):
  grouped=indicators(self.db,DATA['known_at'][0])
  window=common_window(grouped)
  self.assertEqual(window,{'period_start':'2026-06-01','period_end':'2026-06-30'})
 def test_covariation_is_not_causal(self):
  view=covariation(self.db,DATA['known_at'][1])
  self.assertTrue(view['co_moving'])
  self.assertFalse(view['causal_claim_supported'])
  self.assertEqual(set(view['directions']),{'energy','ocean_heat','sea_level'})
 def test_claim_blocked_by_preliminary_at_first_known_at(self):
  verdicts={c['id']:c for c in evaluate_claims(self.db,DATA['known_at'][0])}
  self.assertEqual(verdicts['claim-1']['verdict'],'暂不支持-初步值')
  self.assertTrue(any(b['type']=='preliminary' for b in verdicts['claim-1']['blockers']))
  # 深层产品 8 月才发布：第一时点是缺口而非弱证据
  self.assertEqual(verdicts['claim-2']['verdict'],'证据缺口')
 def test_claim_supported_after_revision_and_release(self):
  verdicts={c['id']:c for c in evaluate_claims(self.db,DATA['known_at'][1])}
  self.assertEqual(verdicts['claim-1']['verdict'],'证据支持')
  self.assertFalse(verdicts['claim-1']['causal_claim_supported'])
  self.assertEqual(verdicts['claim-2']['verdict'],'证据支持')
 def test_nested_coverage_kept_as_caveat(self):
  verdicts={c['id']:c for c in evaluate_claims(self.db,DATA['known_at'][1])}
  self.assertTrue(any(c['type']=='nested_coverage' for c in verdicts['claim-1']['caveats']))
 def test_gaps_report_lag_and_revision_wait(self):
  summary=gaps(self.db,DATA['known_at'][0])
  kinds={(item['metric'],item['type']) for item in summary['items']}
  self.assertIn(('energy','awaiting_revision'),kinds)
  self.assertIn(('ocean_heat','publication_lag'),kinds)
 def test_report_embeds_lineup_and_fingerprint(self):
  report=generate(self.db,DATA['known_at'][0])
  self.assertIn('lineup',report)
  self.assertEqual(len(report['fingerprint']),64)
if __name__=='__main__':unittest.main()
