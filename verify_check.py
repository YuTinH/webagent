#!/usr/bin/env python3
import json, os, argparse
STATE = 'env/state.json'
def load_env():
    return json.load(open(STATE,'r',encoding='utf-8')) if os.path.exists(STATE) else {}
def contains(sub,sup):
    if isinstance(sub,dict):
        return all(k in sup and contains(v, sup[k]) for k,v in sub.items())
    if isinstance(sub,list):
        return all(any(contains(x,y) for y in sup) for x in sup) if isinstance(sup,list) else False
    return sub==sup
def missing(sub,sup,prefix=''):
    out=[]
    if isinstance(sub,dict):
        for k,v in sub.items():
            if k not in sup: out.append(prefix+k)
            else: out += missing(v, sup[k], prefix+k+'.')
    elif isinstance(sub,list):
        for i,x in enumerate(sub):
            if not isinstance(sup,list) or not any(contains(x,y) for y in sup): out.append(prefix+f'[{i}]')
    else:
        if sub!=sup: out.append(prefix.rstrip('.'))
    return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('task_id'); a=ap.parse_args()
    exp = json.load(open(os.path.join('env', f'{a.task_id}_expected.json'),'r',encoding='utf-8'))
    env = load_env(); ok = contains(exp, env)
    print('CHECK', a.task_id, '=>', 'PASS' if ok else 'FAIL')
    if not ok:
        for m in missing(exp, env): print('  missing:', m)
if __name__=='__main__': main()
