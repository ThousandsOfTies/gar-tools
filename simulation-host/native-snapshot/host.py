"""Execute checksum snapshots on a prepared virtual Linux host; never compile."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request


def verify(root):
    checks=json.loads((root/'simulator-manifest.json').read_text())
    return all((root/name).is_file() and hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in checks.items())


def extract(archive,output):
    with tarfile.open(archive) as stream:
        members=stream.getmembers();names=set()
        for member in members:
            path=Path(member.name)
            if path.is_absolute() or '..' in path.parts or member.name in names or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe snapshot archive member')
            names.add(member.name)
        if sum(m.size for m in members)>1024**3:
            raise ValueError('Snapshot is too large')
        stream.extractall(output,filter='data')
    checks=json.loads((output/'simulator-manifest.json').read_text())
    files={str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}
    if files!=set(checks)|{'simulator-manifest.json'} or not verify(output):
        raise ValueError('Snapshot inventory/checksum mismatch')


def require_host():
    if Path('/var/lib/gar/simulation-host-ready').read_text().strip()!='gar-vagrant-2':
        raise ValueError('A prepared GAR virtual host is required')
    if Path('/sys/class/dmi/id/product_name').read_text().strip()!='VirtualBox':
        raise ValueError('This runtime is qualified for VirtualBox only')


def unit(name):
    if not re.fullmatch('[a-z][a-z0-9-]{0,31}',name):raise ValueError('Invalid service name')
    return 'gar-snapshot-'+name+'.service'


def settings(root):
    data=json.loads((root/'product.json').read_text())
    return data,data['simulation']['snapshot']


def execute(values,**kwargs):
    return subprocess.run(values,check=True,**kwargs)


def stop(root):
    _,config=settings(root)
    for service in reversed(config['services']):
        if Path('/etc/systemd/system',unit(service['name'])).exists():
            execute(['systemctl','stop',unit(service['name'])])


def deploy(root,archive,build_id,digest,product):
    require_host()
    if not re.fullmatch('[a-z][a-z0-9-]{0,63}',product) or root!=Path('/var/lib/gar/snapshots')/product:
        raise ValueError('Invalid snapshot destination')
    if not re.fullmatch('[A-Za-z0-9_-]{10,100}',build_id):raise ValueError('Invalid build ID')
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=digest:raise ValueError('Transfer checksum mismatch')
    marker=Path('/var/lib/gar/native-snapshot-owner')
    if marker.exists() and marker.read_text().strip()!=product:
        raise ValueError('Virtual host belongs to another Product')
    root.parent.mkdir(parents=True,exist_ok=True)
    user=pwd.getpwnam(os.environ['SUDO_USER'])
    with tempfile.TemporaryDirectory(prefix='.deploy-',dir=root.parent) as temporary:
        temporary=Path(temporary);next_root=temporary/'app';next_root.mkdir()
        extract(archive,next_root)
        data,_=settings(next_root)
        if data['id']!=product:raise ValueError('Product identity mismatch')
        (next_root/'.gar').mkdir()
        (next_root/'.gar/build-id').write_text(build_id+'\n')
        (next_root/'.gar/owner.json').write_text(json.dumps({'user':user.pw_name,'uid':user.pw_uid,'gid':user.pw_gid}))
        (next_root/'.gar/build.env').write_text('GAR_BUILD_ID='+build_id+'\n')
        if (root/'.gar/private').is_dir():shutil.copytree(root/'.gar/private',next_root/'.gar/private')
        for path in [next_root,*next_root.rglob('*')]:os.chown(path,user.pw_uid,user.pw_gid)
        if root.exists():
            stop(root)
            root.rename(temporary/'previous')
        next_root.rename(root)
    marker.write_text(product+'\n')


def expanded(root,value):
    return value.replace('{root}',str(root)).replace('{host}',str(root/'.gar-host/host.py'))


def start(root):
    require_host()
    if not verify(root):raise ValueError('Deployed snapshot changed; rebuild/redeploy before starting')
    _,config=settings(root)
    owner=json.loads((root/'.gar/owner.json').read_text())
    for service in config['services']:
        name=unit(service['name'])
        command=[expanded(root,v) for v in service['command']]
        if not command or any('\n' in value or '\0' in value for value in command):raise ValueError('Invalid service command')
        dependencies=' '.join(unit(item) for item in service.get('requires',[]))
        lines=['[Unit]','Description=GAR snapshot '+service['name']]
        if dependencies:lines+=['After='+dependencies,'Requires='+dependencies]
        lines+=['[Service]','Type='+('notify' if service['name']=='devices' else 'simple'),
                'User='+('root' if service.get('root') else owner['user']),
                'WorkingDirectory='+str(root),'EnvironmentFile='+str(root/'.gar/build.env')]
        environment={'GAR_HW_SIM_SOCK':'/run/gar/hw_sim.sock','GAR_RUNTIME_DIR':'/run/gar',**service.get('environment',{})}
        environment['PYTHONDONTWRITEBYTECODE']='1'
        for key,path in service.get('optional_files',{}).items():
            if Path(expanded(root,path)).is_file():environment[key]=path
        for key,value in environment.items():
            if not re.fullmatch('[A-Z_][A-Z0-9_]*',key):raise ValueError('Invalid environment name')
            lines.append('Environment='+json.dumps(key+'='+expanded(root,value)).replace('%','%%'))
        for values in service.get('prepare',[]):
            lines.append('ExecStartPre='+' '.join(json.dumps(expanded(root,v)).replace('%','%%') for v in values))
        lines+=['ExecStart='+' '.join(json.dumps(v).replace('%','%%') for v in command),
                'Restart=on-failure','RestartSec=2','KillMode=control-group','TimeoutStartSec=45']
        Path('/etc/systemd/system',name).write_text('\n'.join(lines)+'\n')
    execute(['systemctl','daemon-reload'])
    for service in config['services']:execute(['systemctl','start',unit(service['name'])])


def devices(root):
    require_host()
    _,config=settings(root);hardware=root/config['hardware']
    runtime=root/'sources/gar-tools/targets/linux-device/runtime'
    sys.path.insert(0,str(runtime/'hardware-csv'))
    import virtual_gpio
    owner=json.loads((root/'.gar/owner.json').read_text())
    directory=Path('/run/gar');directory.mkdir(exist_ok=True);os.chown(directory,owner['uid'],owner['gid'])
    os.environ['GAR_HARDWARE_DIR']=str(hardware)
    children=[];rows=[];instance=Path('/sys/kernel/config/gpio-sim/gar-snapshot')
    def launch(values):children.append(subprocess.Popen([str(v) for v in values]))
    def wait_file(path):
        deadline=time.monotonic()+20
        while not Path(path).exists():
            if any(p.poll() is not None for p in children) or time.monotonic()>deadline:raise RuntimeError('Virtual device did not become ready: '+str(path))
            time.sleep(.05)
        os.chown(path,owner['uid'],owner['gid'])
    def interrupted(*_):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,interrupted)
    try:
        if (hardware/'gpio.csv').exists():
            rows=virtual_gpio.plan(hardware);virtual_gpio.ensure(rows,instance)
            for row in rows:os.chown(row['device'],owner['uid'],owner['gid']);os.chmod(row['device'],0o660)
        if config.get('bridge'):
            launch(['/usr/bin/python3',runtime/'web-bridge/bridge.py']);wait_file('/run/gar/hw_sim.sock')
        if (hardware/'spi.csv').exists():
            with (hardware/'gpio.csv').open() as stream:gpio=list(csv.DictReader(stream))
            dc=next(row['line'] for row in gpio if row['name']=='lcd_dc')
            with (hardware/'spi.csv').open() as stream:
                for row in csv.DictReader(stream):
                    if Path(row['dev']).exists():raise ValueError('Refusing an occupied SPI path')
                    launch([root/'build/cuse_spi_gc9a01','-f','-s','--devname='+row['dev'].removeprefix('/dev/'),'--dc-line='+dc]);wait_file(row['dev']);os.chmod(row['dev'],0o660)
        if (hardware/'i2c.csv').exists():
            with (hardware/'i2c.csv').open() as stream:
                for row in csv.DictReader(stream):
                    if not re.fullmatch('/dev/i2c-[0-9]+',row['dev']):raise ValueError('Invalid I2C path')
                    if Path(row['dev']).exists():raise ValueError('Refusing an occupied I2C path')
                    launch([root/'build/cuse_i2c','-f','--devname='+row['dev'].removeprefix('/dev/')]);wait_file(row['dev']);os.chmod(row['dev'],0o660)
        execute(['systemd-notify','--ready'])
        while all(p.poll() is None for p in children):time.sleep(.2)
        raise RuntimeError('A virtual device process exited')
    finally:
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        if rows:virtual_gpio.cleanup(rows,instance)


def diagnostic(root):
    _,config=settings(root);expected=(root/'.gar/build-id').read_text().strip();services={}
    for service in config['services']:
        name=unit(service['name'])
        value=subprocess.run(['systemctl','show',name,'-p','MainPID','--value'],capture_output=True,text=True)
        pid=int(value.stdout.strip() or '0')
        active=subprocess.run(['systemctl','is-active','--quiet',name]).returncode==0
        try:matches=('GAR_BUILD_ID='+expected).encode() in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
        except OSError:matches=False
        services[name]={'active':active,'pid':pid,'buildIdMatch':matches}
    try:
        with urllib.request.urlopen(config['health_url'],timeout=5) as response:health=json.load(response)
    except Exception as error:health={'ok':False,'error':str(error)}
    verified=verify(root)
    panel=services[unit(config['health_service'])]
    ok=verified and all(s['active'] and s['buildIdMatch'] for s in services.values()) and health.get('buildId')==expected and health.get('ok',True) is True and health.get('pid')==panel['pid']
    if config.get('require_app_build'):ok=ok and health.get('appBuildId')==expected
    return {'ok':ok,'snapshotVerified':verified,'deployedBuildId':expected,'runningBuildId':health.get('buildId'),
            'services':services,'health':health}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['deploy','start','stop','devices','diag','log'])
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--archive',type=Path);parser.add_argument('--build-id');parser.add_argument('--sha256');parser.add_argument('--product')
    args=parser.parse_args();root=args.root.resolve()
    if args.action=='deploy':deploy(root,args.archive,args.build_id,args.sha256,args.product)
    elif args.action=='start':start(root)
    elif args.action=='stop':stop(root)
    elif args.action=='devices':devices(root)
    elif args.action=='diag':print(json.dumps(diagnostic(root)))
    else:
        _,config=settings(root)
        execute(['journalctl',*[value for s in config['services'] for value in ['-u',unit(s['name'])]],'-n','80','--no-pager'])


if __name__=='__main__':main()
