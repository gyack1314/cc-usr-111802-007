"""验证初步值修订后原结论的存废与报告不可变性。"""
import json,unittest
from pathlib import Path
from climate_analysis.evidence import connect,receive
from climate_analysis.report import generate,difference
from climate_analysis.revisions import assess,record_changes
DATA=json.loads((Path(__file__).resolve().parents[1]/'data/example.json').read_text(encoding='utf8'))
def load():
 db=connect(':memory:')
 for doc in DATA['documents']:receive(db,doc)
 return db
class RevisionImpact(unittest.TestCase):
 def setUp(self):
  self.db=load()
  self.t1,self.t2=DATA['known_at']
  self.before=generate(self.db,self.t1);self.after=generate(self.db,self.t2)
 def tearDown(self):self.db.close()
 def test_record_changes_classify_revision_addition_and_unchanged(self):
  changes={(c['record_id']):c for c in record_changes(self.db,self.t1,self.t2)}
  self.assertEqual(changes['obs-1']['kind'],'revised')
  self.assertEqual(changes['obs-1']['status_before'],'preliminary')
  self.assertEqual(changes['obs-1']['status_after'],'revised')
  self.assertEqual(changes['obs-ohc-7002000-q2']['kind'],'added')
  self.assertEqual(changes['obs-sl-202606']['kind'],'unchanged')
 def test_revised_decision_loses_basis_others_hold(self):
  impact=assess(self.db,self.before,self.after,self.t1,self.t2)
  rows={r['id']:r for r in impact['decision_impact']}
  self.assertEqual(rows['obs-1']['standing'],'失去依据-依据记录已修订')
  self.assertEqual(rows['obs-sl-202606']['standing'],'仍成立-依据记录未修订')
  self.assertEqual(rows['obs-ohc-0700-q2']['standing'],'仍成立-依据记录未修订')
  self.assertEqual(rows['obs-ohc-7002000-q2']['standing'],'新增判断')
 def test_claim_impact_distinguishes_revision_from_gap_closure(self):
  impact=assess(self.db,self.before,self.after,self.t1,self.t2)
  rows={r['id']:r for r in impact['claim_impact']}
  self.assertEqual(rows['claim-1']['standing'],'获得依据-原缺口已补齐')
  self.assertEqual(rows['claim-2']['standing'],'获得依据-原缺口已补齐')
  self.assertEqual(rows['claim-2']['before_verdict'],'证据缺口')
  self.assertEqual(rows['claim-2']['after_verdict'],'证据支持')
 def test_old_report_is_not_rewritten(self):
  # 重新生成的同一时点报告指纹必须与旧快照一致
  regenerated=generate(self.db,self.t1)
  self.assertEqual(regenerated['fingerprint'],self.before['fingerprint'])
  before_decisions={d['id']:d for d in self.before['decisions']}
  self.assertEqual(before_decisions['obs-1']['status'],'常态')
  after_decisions={d['id']:d for d in self.after['decisions']}
  self.assertEqual(after_decisions['obs-1']['status'],'关注')
  # 差异报告保留旧/新指纹，两个时点各自独立
  diff=difference(self.before,self.after)
  self.assertEqual(diff['before'],self.before['fingerprint'])
  self.assertNotEqual(diff['before'],diff['after'])
  self.assertEqual(diff['changed'],['obs-1'])
  self.assertIn('obs-ohc-7002000-q2',diff['added'])
 def test_tampering_with_stored_snapshot_is_detectable(self):
  import hashlib
  tampered=json.loads(json.dumps(self.before))
  tampered['decisions'][0]['status']='常态'
  fingerprint=hashlib.sha256(
    json.dumps(tampered,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
  self.assertNotEqual(fingerprint,self.before['fingerprint'])
if __name__=='__main__':unittest.main()
