"""保留已知时点报告，比较区域判断变化。

报告是已知时点的不可变快照：所有联读、主张与缺口结论都固定在该时点可见
的证据版次上，并由指纹封存；后续修订只生成新时点报告，不能改写旧报告。
"""
import hashlib,json
from .metrics import compare
from .context import decide
from .lineup import covariation,evaluate_claims,gaps
def generate(db,known_at):
 measures=compare(db,known_at);decisions=[decide(db,known_at,row) for row in measures]
 out={'known_at':known_at,'measurements':measures,'decisions':decisions,
   'lineup':{'covariation':covariation(db,known_at),
     'claims':evaluate_claims(db,known_at),'gaps':gaps(db,known_at)}}
 out['fingerprint']=hashlib.sha256(json.dumps(out,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 return out
def difference(a,b):
 old={r['id']:r for r in a['decisions']};new={r['id']:r for r in b['decisions']}
 return {'before':a['fingerprint'],'after':b['fingerprint'],
   'changed':sorted(k for k in old.keys()&new.keys() if old[k]!=new[k]),
   'added':sorted(new.keys()-old.keys()),'removed':sorted(old.keys()-new.keys())}
