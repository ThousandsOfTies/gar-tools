"""Derive built-in MCU resource selection from the common parts/wiring CSVs."""
from product import csv_rows, inside


def derive(product):
    settings = product.data['hardware']['binding_csv']
    parts = csv_rows(inside(product.root, settings['components']))
    identifiers = [row['component_id'] for row in parts]
    board = settings['board_component']
    if board not in identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError('Embedded component IDs must be unique and include the board')
    connections = csv_rows(inside(product.root, settings['connections']))
    displays, buttons = [], []
    resources = product.profile['resources']
    for row in connections:
        if row['source'] != board or row['target'] not in identifiers:
            raise ValueError('Embedded resource selection must connect the board to a declared part')
        resource = row['source_pin']
        if row['signal'] == 'display':
            if resource != resources['display']['id']:
                raise ValueError('Display CSV resource is outside the board profile')
            displays.append(resource)
        elif row['signal'] == 'button':
            if resource not in resources['buttons'] or resource in buttons:
                raise ValueError('Button CSV resource is missing or selected twice')
            buttons.append(resource)
        else:
            raise ValueError('Embedded binding CSV supports explicit display/button selections only')
    if len(displays) != 1 or not buttons:
        raise ValueError('Embedded binding CSV requires one display and at least one button')
    return {'schema_version': 1, 'display': displays[0], 'buttons': buttons,
            'orientation': resources['display']['orientation']}
