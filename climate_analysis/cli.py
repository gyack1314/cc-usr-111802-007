"""从本地合成资料形成两个已知时间的报告及修订影响。"""
import argparse,json
from pathlib import Path
from .evidence import connect,receive
from .report import generate,difference
from .revisions import assess
def _load(args):
 data=json.loads(Path(args.input).read_text(encoding='utf8'));db=connect(':memory:')
 for doc in data['documents']:receive(db,doc)
 return db,data
def main():
 p=argparse.ArgumentParser()
 p.add_argument('command',choices=['inspect','impact']);p.add_argument('input');args=p.parse_args()
 db,data=_load(args)
 a,b=[generate(db,t) for t in data['known_at']]
 if args.command=='inspect':
  print(json.dumps({'before':a,'after':b,'change':difference(a,b)},ensure_ascii=False,indent=2))
 else:
  print(json.dumps(assess(db,a,b,data['known_at'][0],data['known_at'][1]),ensure_ascii=False,indent=2))
 db.close()
if __name__=='__main__':main()
