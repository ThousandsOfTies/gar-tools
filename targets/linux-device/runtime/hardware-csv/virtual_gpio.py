"""Expose gpio-sim at canonical CSV chip paths without rewriting the CSV.

Only the named configfs gpio-sim instance and aliases to its own chips are
managed. An occupied canonical device path is never replaced.
"""
import argparse
import csv
import json
from pathlib import Path
import re
import time


def plan(directory):
    groups={}
    used=set()
    with (Path(directory)/'gpio.csv').open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            chip=row['chip'];line=int(row['line'])
            if not re.fullmatch(r'/dev/gpiochip\d+',chip) or not 0<=line<=4095:
                raise ValueError('Invalid canonical GPIO chip/line')
            if (chip,line) in used:
                raise ValueError('Duplicate canonical GPIO line')
            used.add((chip,line))
            groups[chip]=max(groups.get(chip,0),line+1)
    return [{'device':chip,'num_lines':count} for chip,count in sorted(groups.items())]


def alias(expected,actual):
    if not actual.is_char_device():
        raise ValueError('gpio-sim device is unavailable')
    if expected==actual or expected.is_symlink() and expected.resolve()==actual:
        return
    if expected.exists() or expected.is_symlink():
        raise ValueError(f'Refusing to replace an occupied device path: {expected}')
    expected.symlink_to(actual.name)


def cleanup(rows,device):
    if not device.exists():
        return
    banks=sorted(device.glob('gpio-bank*'))
    actual={Path('/dev')/(bank/'chip_name').read_text().strip() for bank in banks}
    for row in rows:
        expected=Path(row['device'])
        if expected.is_symlink() and expected.resolve() in actual:
            expected.unlink()
    (device/'live').write_text('0')
    for bank in banks:
        bank.rmdir()
    device.rmdir()


def ensure(rows,device):
    if device.exists():
        banks=sorted(device.glob('gpio-bank*'))
        counts=[int((bank/'num_lines').read_text()) for bank in banks]
        if counts!=[row['num_lines'] for row in rows]:
            cleanup(rows,device)
    device.mkdir(exist_ok=True)
    created=(device/'live').read_text().strip()!='1'
    if created:
        for index,row in enumerate(rows):
            bank=device/f'gpio-bank{index}';bank.mkdir(exist_ok=True)
            (bank/'num_lines').write_text(str(row['num_lines']))
            (bank/'label').write_text(device.name)
        (device/'live').write_text('1')
    try:
        result=[]
        for index,row in enumerate(rows):
            actual=Path('/dev')/(device/f'gpio-bank{index}'/'chip_name').read_text().strip()
            deadline=time.monotonic()+3
            while not actual.exists() and time.monotonic()<deadline:
                time.sleep(.02)
            alias(Path(row['device']),actual)
            result.append({**row,'virtual_device':str(actual)})
        return result
    except Exception:
        if created:
            cleanup(rows,device)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hardware',type=Path,required=True)
    parser.add_argument('--instance',required=True)
    parser.add_argument('--cleanup',action='store_true')
    parser.add_argument('--plan',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',args.instance):
        raise ValueError('Invalid gpio-sim instance')
    rows=plan(args.hardware)
    device=Path('/sys/kernel/config/gpio-sim')/args.instance
    if args.plan:
        print(json.dumps(rows))
    elif args.cleanup:
        cleanup(rows,device)
    else:
        print(json.dumps(ensure(rows,device)))


if __name__=='__main__':
    main()
