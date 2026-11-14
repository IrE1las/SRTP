"""Recover the SDM station format confirmed against native reader functions.

Type dispatcher: 0x412ea0; switch: 0x4069a0; shunt: 0x404140;
train: 0x4098d0; track: 0x4088f0/0x4298f0; joint: 0x41ee10.
Reads reference files only. No executable loading or COM registration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def integer(self):
        if self.pos + 4 > len(self.data):
            raise ValueError(f"Truncated integer at {self.pos}")
        value = struct.unpack_from('<i', self.data, self.pos)[0]
        self.pos += 4
        return value

    def values(self, count):
        return [self.integer() for _ in range(count)]

    def string(self):
        length = self.integer()
        if not 0 <= length <= 128:
            raise ValueError(f"Invalid string length {length} at {self.pos}")
        return bytes(self.integer() & 255 for _ in range(length)).decode('gb18030')

    def points(self):
        count = self.integer()
        if not 0 <= count <= 256:
            raise ValueError(f"Invalid point count {count} at {self.pos}")
        return [self.values(2) for _ in range(count)]


def decode_geometry(data):
    reader, records, blocks = Reader(data), [], []
    while reader.pos < len(data):
        block_offset = reader.pos
        kind, count = reader.values(2)
        if kind not in {0, 1, 2, 3, 4, 501, 502} or not 0 <= count <= 512:
            raise ValueError(f"Unrecognized block {kind}/{count} at {block_offset}")
        blocks.append({'type': kind, 'count': count, 'offset': block_offset})
        for _ in range(count):
            item = {'type': kind, 'offset': reader.pos}
            if kind == 501:
                item.update(shape=reader.integer(), length=reader.integer(), center=reader.values(2),
                            endpoints=[reader.values(2), reader.values(2)], polygon=reader.points())
            else:
                item['name'] = reader.string()
                if kind == 2:
                    item['section'] = reader.string()
                    item['group'] = reader.string() if reader.integer() else None
                    item.update(mode=reader.integer(), label=reader.values(2), point=reader.values(2),
                                branches=[reader.points() for _ in range(3)], shape=reader.values(6))
                    item['extra'] = {'name': reader.string(), 'value': reader.integer()} if reader.integer() else None
                    item['flag'] = reader.integer()
                elif kind in {3, 4}:
                    item.update(label=reader.values(2), points=reader.points(), mode=reader.integer())
                elif kind in {0, 1}:
                    item['fields'] = reader.values(25)
                else:
                    item.update(point=reader.values(2), color=reader.integer())
            records.append(item)
    assert reader.pos == len(data), 'Geometry must consume the complete binary file'
    return {'bytes_consumed': reader.pos, 'blocks': blocks, 'records': records}


def decode_routes(data):
    result, kind = [], 'shunt'
    for number, raw in enumerate(data.decode('gb18030').splitlines(), 1):
        text = raw.split(';', 1)[0].strip()
        if not text:
            continue
        if text in {'SHUNTSECTION:', 'TRAINSECTION:'}:
            kind = 'train' if text == 'TRAINSECTION:' else 'shunt'
            continue
        match = re.fullmatch(r'([^=]+)=\s*\[([^]]+)\]\s*(.*)', text)
        if not match:
            raise ValueError(f'Unrecognized route syntax on line {number}: {text}')
        name, buttons, body = match.groups()
        result.append({'name': name.strip(), 'kind': kind, 'line': number,
                       'buttons': [b.strip() for b in buttons.split(',')],
                       'tokens': [b.strip() for b in body.split(',') if b.strip()], 'raw': raw})
    return result


def decode_topology(data):
    """Keep every named block, including mixed-case controls without Name fields.

    Splitting only on uppercase headers merges AutoBlock/ZXJ_Control into the
    preceding COUPLE record and silently destroys the original station rules.
    """
    entries, blocks = {}, []
    current = None
    for number, raw in enumerate(data.decode('gb18030').splitlines(), 1):
        text = raw.split(';', 1)[0].strip()
        header = re.fullmatch(r'([A-Za-z][A-Za-z0-9_]*_\d+):', text)
        if header:
            current = {'id': header[1], 'line': number, 'fields': {}}
            blocks.append(current)
        elif current is not None and '=' in text:
            key, value = text.split('=', 1)
            current['fields'][key.strip()] = value.strip()
    for block in blocks:
        fields = block['fields']
        if fields.get('Name'):
            if fields['Name'] in entries:
                raise ValueError(f'Duplicate topology object: {fields["Name"]}')
            entries[fields['Name']] = fields
    return entries, blocks


def import_station(source, output, assets):
    files = {name: (source/'SDM'/name).read_bytes() for name in ['SWJDATA.dat', 'Route.txt', 'Code.txt', 'Config.txt']}
    geometry = decode_geometry(files['SWJDATA.dat'])
    topology = (source/'联锁机'/'STADATA.TXT').read_bytes()
    entries, controls = decode_topology(topology)
    package = {'provenance': {'format': 'SDM native station data',
                             'sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
                             'topology_sha256': hashlib.sha256(topology).hexdigest()},
               'geometry': geometry, 'routes': decode_routes(files['Route.txt']), 'topology': entries,
               'topology_blocks': controls,
               'config': files['Config.txt'].decode('gb18030')}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    # Reuse bitmap resources as browser-compatible PNG files, recording each origin.
    from PIL import Image
    assets.mkdir(parents=True, exist_ok=True)
    manifest = []
    for folder in ['BITMAP', 'MenuBitmap']:
        dest = assets/folder.lower()
        dest.mkdir(exist_ok=True)
        for image in sorted((source/'SDM'/folder).glob('*')):
            if image.suffix.lower() != '.bmp':
                continue
            target = dest/(image.stem+'.png')
            with Image.open(image) as im:
                converted = im.convert('RGBA')
                if folder == 'MenuBitmap':
                    # Native toolbar images use RGB magenta as the transparency key.
                    converted.putdata([(r,g,b,0 if (r,g,b)==(255,0,255) else a)
                                       for r,g,b,a in converted.getdata()])
                converted.save(target)
            manifest.append({'source': f'SDM/{folder}/{image.name}', 'output': f'{folder.lower()}/{target.name}',
                             'sha256': hashlib.sha256(image.read_bytes()).hexdigest()})
    (assets/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'blocks': geometry['blocks'], 'bytes': geometry['bytes_consumed'],
                      'routes': len(package['routes']), 'assets': len(manifest)}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--assets', type=Path, required=True)
    args = parser.parse_args()
    import_station(args.source, args.output, args.assets)
