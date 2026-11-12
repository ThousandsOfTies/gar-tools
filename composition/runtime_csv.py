"""Package one authored CSV dataset and its runtime reader for either Linux path."""
import shutil

from product import csv_rows, inside


def references(product):
    relative = product.data['launch'].get('hardware_environment_csv')
    if not relative:
        return product.data['launch'].get('hardware_environment', {})
    rows = csv_rows(inside(product.root, relative))
    result = {}
    for row in rows:
        variable = row['variable']
        if variable in result or row['table'] not in ('gpio', 'spi'):
            raise ValueError('Duplicate variable or unsupported hardware runtime table')
        result[variable] = {key: row[key] for key in ('table', 'name', 'field')}
    if not result:
        raise ValueError('Hardware environment CSV must not be empty')
    return result


def install(product, application):
    if not product.data['launch'].get('hardware_environment_csv'):
        return
    directory = application / 'hardware'
    directory.mkdir()
    for name in ('gpio.csv', 'spi.csv'):
        shutil.copyfile(product.hardware / name, directory / name)
    shutil.copyfile(inside(product.root, product.data['launch']['hardware_environment_csv']), directory / 'environment.csv')
    loader = inside(product.components['tools'], 'targets/linux-device/runtime/hardware-csv')
    shutil.copytree(loader, application / 'hardware-csv')
