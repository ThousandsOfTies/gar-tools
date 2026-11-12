"""Compatibility frontend: use GAR's configured host and captured artifacts."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import webbrowser


def commands(action):
    if action in ('open','up'):
        return [('sim','start','host'),('sim','start')]
    if action=='stop':return [('sim','stop'),('sim','stop','host')]
    if action=='start':return [('sim','start','host'),('sim','start')]
    if action=='verify':return [('product','run','verify-simulation')]
    if action in ('build','deploy','status','diag','log','prepare'):return [('sim',action)]
    if action=='logs':return [('sim','log')]
    if action=='test':return [('product','run','verify-simulation')]
    raise ValueError('Use the configured local panel; this legacy action is not a GAR snapshot operation')


def main(root=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=root is None)
    parser.add_argument('action');args=parser.parse_args();root=Path(root or args.root).resolve()
    entry=shutil.which('gar')
    if not entry:
        candidate=root.parent/'GAR/GaplessAgentRuntime/scripts'/('gar.cmd' if os.name=='nt' else 'gar')
        if not candidate.is_file():raise SystemExit('Install GAR and register this Product workspace first')
        entry=str(candidate)
    for operation in commands(args.action):
        command=[entry,*operation,'--workspace','Local/'+root.name]
        result=subprocess.run(command,cwd=root,check=False)
        if result.returncode:return result.returncode
    if args.action=='open':
        data=json.loads((root/'product.json').read_text(encoding='utf-8'))
        panel=next(s for s in data['simulation']['snapshot']['services'] if s['name']=='panel')
        webbrowser.open('http://127.0.0.1:'+panel['environment']['GAR_PANEL_PORT'])
    return 0


if __name__=='__main__':raise SystemExit(main())
