"""初步值修订后的结论影响分析。

原报告是已知时点的不可变快照，新数字不能回写旧报告。本模块比较两个时点
各自的报告与证据谱系，把依赖记录分为：修订（版次变化）、新增、未变，并
逐项标注原结论失去依据还是仍成立。
"""
from .evidence import lineage
from .lineup import evaluate_claims

def _record_index(db,known_at):
  index={}
  for family in lineage(db,'observation',known_at):
    for row in family:
      index[(row['payload']['metric'],row['id'])]=row
  return index

def record_changes(db,before_at,after_at):
  """观测版次在两个时点之间的变化，含修订状态迁移与量值变化。"""
  old=_record_index(db,before_at);new=_record_index(db,after_at);changes=[]
  for key in sorted(set(old)|set(new)):
    before=old.get(key);after=new.get(key)
    if before is None:
      changes.append({'metric':key[0],'record_id':key[1],'kind':'added',
        'revision_after':after['revision'],'status_after':after['payload']['revision_status']})
    elif after is None:
      changes.append({'metric':key[0],'record_id':key[1],'kind':'withdrawn',
        'revision_before':before['revision']})
    elif after['revision']!=before['revision']:
      changes.append({'metric':key[0],'record_id':key[1],'kind':'revised',
        'revision_before':before['revision'],'revision_after':after['revision'],
        'status_before':before['payload']['revision_status'],
        'status_after':after['payload']['revision_status'],
        'value_before':before['payload']['value'],'value_after':after['payload']['value']})
    else:
      changes.append({'metric':key[0],'record_id':key[1],'kind':'unchanged',
        'revision':after['revision'],'status':after['payload']['revision_status']})
  return changes

def _decision_map(report):
  return {row['id']:row for row in report['decisions']}

def decision_impact(db,before_report,after_report,before_at,after_at):
  """单期区域判断：依据被修订则原判断失去依据，否则仍成立。"""
  before=_decision_map(before_report);after=_decision_map(after_report)
  changes={(c['record_id']):c for c in record_changes(db,before_at,after_at)}
  out=[]
  for rid in sorted(set(before)|set(after)):
    old=before.get(rid);new=after.get(rid);change=changes.get(rid)
    if old is None:
      standing='新增判断'
    elif change is not None and change['kind']=='revised':
      standing='失去依据-依据记录已修订'
    elif new is None:
      standing='失去依据-判断不再产生'
    elif new.get('status')!=old.get('status'):
      standing='结论变化-规则或参照更新'
    else:
      standing='仍成立-依据记录未修订'
    out.append({'id':rid,'before_status':old.get('status') if old else None,
      'after_status':new.get('status') if new else None,
      'record_change':change['kind'] if change else None,'standing':standing})
  return out

def claim_impact(db,before_report,after_report,before_at,after_at):
  """简报主张：重新核验，并区分修订推翻、缺口补齐与仍成立。"""
  old={row['id']:row for row in evaluate_claims(db,before_at)}
  new={row['id']:row for row in evaluate_claims(db,after_at)}
  revised={c['record_id'] for c in record_changes(db,before_at,after_at) if c['kind']=='revised'}
  out=[]
  for cid in sorted(set(old)|set(new)):
    previous=old.get(cid);current=new.get(cid)
    touched=bool(previous and revised.intersection(previous.get('used_observations',[])))
    if previous and previous['verdict']!='证据支持' and current and current['verdict']=='证据支持':
      standing='获得依据-原缺口已补齐'
    elif touched and previous and current and previous['verdict']!=current['verdict']:
      standing='原结论失去依据-初步值修订后核验结果改变'
    elif touched:
      standing='仍成立但已按修订值重新核验'
    elif previous and current and previous['verdict']==current['verdict']:
      standing='仍成立-依据记录未修订'
    else:
      standing='状态变化'
    out.append({'id':cid,'before_verdict':previous['verdict'] if previous else None,
      'after_verdict':current['verdict'] if current else None,'standing':standing,
      'before_used':previous.get('used_observations',[]) if previous else [],
      'after_used':current.get('used_observations',[]) if current else []})
  return out

def assess(db,before_report,after_report,before_at,after_at):
  return {
    'before_fingerprint':before_report['fingerprint'],
    'after_fingerprint':after_report['fingerprint'],
    'record_changes':record_changes(db,before_at,after_at),
    'decision_impact':decision_impact(db,before_report,after_report,before_at,after_at),
    'claim_impact':claim_impact(db,before_report,after_report,before_at,after_at),
    'immutability':'原报告指纹独立保留，修订只产生新时点报告，不回写旧数字',
  }
