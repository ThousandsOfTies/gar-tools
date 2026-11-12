"""Derive legacy native I2C policy objects from one authored CSV dataset.

No device is opened and no board capability is invented; the selected Product
validator still checks this object against its qualified board/profile policy.
"""
from product import csv_rows, inside
import math
import json
from pathlib import Path
import tempfile


def derive(root, data, target):
    settings=data['hardware']['i2c_contract']
    parts=csv_rows(inside(root,settings['components']))
    identifiers=[row['component_id'] for row in parts]
    if len(set(identifiers))!=len(identifiers) or settings['board_component'] not in identifiers:
        raise ValueError('I2C components require unique IDs and the selected board')
    connections=csv_rows(inside(root,settings['connections']))
    rows=csv_rows(inside(root,data['hardware']['i2c']))
    intent=csv_rows(inside(root,settings['interfaces']))
    if len(intent)!=1 or len(rows)!=1:
        raise ValueError('This native I2C policy requires exactly one interface and runtime row')
    interface=intent[0];runtime=rows[0]
    if interface['component_id'] not in identifiers or runtime['name']!=interface['runtime_name']:
        raise ValueError('I2C runtime selection differs from declared components')
    bus=int(runtime['bus']);address=int(runtime['address'],0)
    if runtime['dev']!=f'/dev/i2c-{bus}' or bus<0 or not 3<=address<=0x77:
        raise ValueError('I2C runtime bus/device/address disagree')
    pins={}
    for signal in ('SDA','SCL'):
        matches=[row for row in connections if row['source']==settings['board_component'] and
            row['target']==interface['component_id'] and row['target_pin']==signal]
        if len(matches)!=1:
            raise ValueError('Missing or ambiguous I2C wiring: '+signal)
        pins[signal]=matches[0]['source_pin']
    if pins['SDA']==pins['SCL']:
        raise ValueError('I2C requires distinct SDA/SCL pins')
    voltage=float(interface['logic_voltage_v']);frequency=int(interface['frequency_hz'])
    if not math.isfinite(voltage) or voltage<=0 or frequency<=0:
        raise ValueError('I2C voltage and frequency must be positive finite constraints')
    result={'schema_version':1,'product':settings['product'],'target':target,'interfaces':[{
        'id':interface['id'],'kind':'i2c','controller':interface['controller'],'bus':bus,
        'device':runtime['dev'],'address':hex(address),'frequency_hz':frequency,
        'logic_voltage_v':voltage,'pins':pins}]}
    if interface.get('pin_group') or interface.get('keep_rails'):
        result['preparation']={'pin_group':interface['pin_group'],
            'keep_rails':[value for value in interface['keep_rails'].split(';') if value]}
    return result


def generate(root,data,target):
    root=Path(root).resolve()
    relative='.gar/composition/i2c-binding.json'
    for item in (root/relative,*(root/relative).parents):
        if item==root:break
        if item.is_symlink() or (hasattr(item,'is_junction') and item.is_junction()):
            raise ValueError('Generated I2C binding cannot follow links')
    output=inside(root,relative,exists=False)
    binding=derive(root,data,target)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=output.parent,delete=False) as stream:
        temporary=Path(stream.name)
        json.dump(binding,stream,indent=2,allow_nan=False);stream.write('\n')
    try:temporary.replace(output)
    finally:temporary.unlink(missing_ok=True)
    return output
