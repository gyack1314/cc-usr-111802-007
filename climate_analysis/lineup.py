"""跨指标联读：辨别可同时比较的证据、不能支持的因果判断与缺口。

三条曲线（地球能量失衡、海洋热含量、海平面上升）即使同向，也只是同一
已知时点上的共变，不构成因果链。本模块对每条观测保留观测期间、发布时点、
修订状态与空间覆盖，只在共同观测窗口、覆盖适配且非初步值的条件下比较，
并把不满足条件的部分显式记为缺口而不是静默剔除。
"""
from datetime import datetime
from .evidence import records

# 空间覆盖层级：父节点完全包含子节点覆盖范围。
COVERAGE_TREE={
  'global':('global_ocean',),
  'global_ocean':('ocean_0_700m','ocean_700_2000m'),
  'ocean_0_700m':(),
  'ocean_700_2000m':(),
}
FIT_EXACT='exact';FIT_NESTED='nested';FIT_NONE='none'
VERDICT_SUPPORTED='证据支持'
VERDICT_PRELIMINARY='暂不支持-初步值'
VERDICT_COVERAGE='暂不支持-覆盖不足'
VERDICT_PERIOD='暂不支持-期间不重叠'
VERDICT_MISSING='证据缺口'

def _date(value):
  return datetime.fromisoformat(value).date()

def coverage_fit(required, actual):
  """要求覆盖与实际覆盖的适配关系：一致、层级包含或不兼容。"""
  if required==actual:return FIT_EXACT
  if required in COVERAGE_TREE and actual in COVERAGE_TREE:
    def contains(outer, inner):
      if outer==inner:return True
      return any(contains(child,inner) for child in COVERAGE_TREE[outer])
    if contains(required,actual) or contains(actual,required):return FIT_NESTED
  return FIT_NONE

def _indicator(obs):
  p=obs['payload']
  return {
    'id':obs['id'],'metric':p['metric'],'region':p['region'],'unit':p['unit'],
    'value':p['value'],'period_start':p['period_start'],'period_end':p['period_end'],
    'published_at':p['published_at'],'revision_status':p['revision_status'],
    'spatial_coverage':p['spatial_coverage'],'revision':obs['revision'],
    'source_sha256':obs['source']['sha256'],
    'received_at':obs['source']['received_at'],
  }

def indicators(db,known_at):
  """按指标归集观测，并保留每项观测的期间、发布时点、修订与覆盖。"""
  grouped={}
  for obs in records(db,'observation',known_at):
    grouped.setdefault(obs['payload']['metric'],[]).append(_indicator(obs))
  for rows in grouped.values():
    rows.sort(key=lambda item:(item['period_start'],item['id'],item['revision']))
  return grouped

def common_window(grouped):
  """各指标观测期间并集的交集；任一指标缺数据则无共同窗口。"""
  if not grouped:return None
  spans=[]
  for rows in grouped.values():
    starts=[_date(r['period_start']) for r in rows]
    ends=[_date(r['period_end']) for r in rows]
    spans.append((min(starts),max(ends)))
  left=max(span[0] for span in spans);right=min(span[1] for span in spans)
  if right<left:return None
  return {'period_start':left.isoformat(),'period_end':right.isoformat()}

def _overlaps(row,window):
  return window is not None and _date(row['period_start'])<=_date(window['period_end']) \
    and _date(row['period_end'])>=_date(window['period_start'])

def _pick(group,window,scope,require_match):
  """在共同窗口内为某指标选覆盖适配最优的观测。"""
  candidates=[r for r in group if _overlaps(r,window)]
  scored=[]
  for row in candidates:
    fit=coverage_fit(scope,row['spatial_coverage'])
    if fit==FIT_NONE:continue
    if require_match and fit!=FIT_EXACT:continue
    rank={FIT_EXACT:0,FIT_NESTED:1}[fit]
    scored.append((rank,row['published_at'],row))
  if not scored:return None
  # 覆盖适配优先（exact 优于 nested），同档内按记录标识确定性选取
  scored.sort(key=lambda item:(item[0],item[2]['id']))
  return scored[0][2]

def covariation(db,known_at):
  """共同窗口内各指标参照偏离的符号共变；共变不等于因果。"""
  grouped=indicators(db,known_at);window=common_window(grouped)
  references=records(db,'reference',known_at)
  used={};signs={}
  for metric,group in grouped.items():
    pick=_pick(group,window,'global',False)
    if pick is None:continue
    matches=[r for r in references if all(r['payload'][k]==pick[k] for k in ('metric','region','unit'))]
    if not matches:continue
    used[metric]=pick['id']
    signs[metric]=('上升' if pick['value']-matches[-1]['payload']['value']>0 else '下降或持平')
  distinct=set(signs.values())
  return {'window':window,'used_observations':used,'directions':signs,
    'co_moving':len(distinct)==1 and len(signs)>1,
    'causal_claim_supported':False,
    'note':'同向共变只描述同一窗口的符号一致，不能据此断言指标间存在因果链'}

def _gap_for(metric,group,window,scope,exact_metrics):
  require_match=metric in exact_metrics
  if not group:return {'metric':metric,'type':'missing_series','detail':'该指标在已知时点没有任何观测'}
  in_window=[r for r in group if _overlaps(r,window)]
  if not in_window:
    return {'metric':metric,'type':'period_gap','detail':'观测期间与共同窗口不重叠'}
  fitting=[r for r in in_window if coverage_fit(scope,r['spatial_coverage'])!=FIT_NONE]
  if not fitting:
    return {'metric':metric,'type':'coverage_gap','detail':'没有覆盖要求空间范围的产品','scope':scope}
  if require_match and not any(coverage_fit(scope,r['spatial_coverage'])==FIT_EXACT for r in fitting):
    return {'metric':metric,'type':'coverage_partial','detail':'只有层级近似覆盖，缺少精确匹配产品','scope':scope}
  prelim=[r['id'] for r in in_window if r['revision_status']=='preliminary']
  if prelim:
    return {'metric':metric,'type':'preliminary','detail':'共同窗口内只有初步值，修订后结论可能改变','observations':prelim}
  return None

def evaluate_claims(db,known_at):
  """逐条核验简报主张：期间、修订状态、覆盖、方向门槛分别给出依据。"""
  grouped=indicators(db,known_at);window=common_window(grouped)
  references=records(db,'reference',known_at);out=[]
  for claim in records(db,'claim',known_at):
    p=claim['payload'];scope=p['scope']
    exact_metrics=set(p.get('require_coverage_exact',[]))
    blockers=[];caveats=[];used=[];deltas={}
    for metric in p['metrics']:
      group=grouped.get(metric,[])
      gap=_gap_for(metric,group,window,scope,exact_metrics)
      if gap is not None:
        blockers.append(gap);continue
      pick=_pick(group,window,scope,metric in exact_metrics)
      fit=coverage_fit(scope,pick['spatial_coverage'])
      if fit==FIT_NESTED:
        caveats.append({'metric':metric,'type':'nested_coverage',
          'detail':'实际覆盖与要求范围仅层级包含，外推需谨慎',
          'scope':scope,'actual':pick['spatial_coverage']})
      if pick['revision_status']=='preliminary':
        blockers.append({'metric':metric,'type':'preliminary',
          'detail':'依据初步值，修订前不能作为确定结论','observations':[pick['id']]})
        continue
      matches=[r for r in references if all(r['payload'][k]==pick[k] for k in ('metric','region','unit'))]
      if not matches:
        blockers.append({'metric':metric,'type':'no_reference','detail':'同口径参照缺失'});continue
      delta=pick['value']-matches[-1]['payload']['value']
      deltas[metric]=delta;used.append(pick['id'])
    if blockers:
      if any(b['type'] in ('missing_series','period_gap','coverage_gap','coverage_partial') for b in blockers):
        verdict=VERDICT_MISSING
      elif any(b['type']=='preliminary' for b in blockers):
        verdict=VERDICT_PRELIMINARY
      else:
        verdict=VERDICT_COVERAGE
    elif deltas and p.get('expect_direction')=='positive' and not all(d>0 for d in deltas.values()):
      verdict=VERDICT_PERIOD;blockers.append({'type':'direction_mismatch','detail':'窗口内未全部同向'})
    else:
      verdict=VERDICT_SUPPORTED
    out.append({'id':claim['id'],'statement':p['statement'],'verdict':verdict,
      'window':window,'used_observations':used,'deltas':deltas,
      'blockers':blockers,'caveats':caveats,
      'causal_claim_supported':False if verdict==VERDICT_SUPPORTED else None,
      'sources':[claim['source']['sha256']]+[r['source_sha256']
        for metric in p['metrics'] for r in grouped.get(metric,[]) if r['id'] in used]})
  return out

def gaps(db,known_at):
  """汇总联读缺口：缺系列、期间错位、初步值、覆盖限制、发布滞后。"""
  grouped=indicators(db,known_at);window=common_window(grouped);found=[]
  for metric,group in grouped.items():
    gap=_gap_for(metric,group,window,'global',set())
    if gap is not None:found.append(gap)
    latest=max(group,key=lambda r:r['period_end'])
    if latest['revision_status']=='preliminary':
      found.append({'metric':metric,'type':'awaiting_revision',
        'detail':'最新观测仍为初步值，等待修订版','observations':[latest['id']]})
    cutoff=datetime.fromisoformat(known_at)
    lag=(cutoff.date()-_date(latest['period_end'])).days
    found.append({'metric':metric,'type':'publication_lag',
      'detail':'最新观测期间结束距已知时点的发布滞后天数','days':lag,
      'latest_period_end':latest['period_end']})
  return {'window':window,'items':found}
