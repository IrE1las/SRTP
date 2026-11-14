"""Reproduce read-only radare2 analysis; keep generated output local."""
import argparse
import hashlib
import json
from pathlib import Path

# Recovered readers and the route-token parser, not guessed symbol names.
FUNCTIONS = {
    'document_init':0x412370, 'geometry_dispatch':0x412ea0,
    'switch_reader':0x4069a0, 'shunt_reader':0x404140,
    'train_reader':0x4098d0, 'track_reader':0x4088f0,
    'switchless_reader':0x4298f0, 'insulation_reader':0x41ee10,
    'text_reader':0x41ef70, 'route_loader':0x4197a0,
    'route_token_parser':0x424d30,
}


def reverse(executable, output, target='sdm'):
    import r2pipe
    output.mkdir(parents=True,exist_ok=True)
    functions = FUNCTIONS if target=='sdm' else {
        'station_loader':0x6e5140, 'signal_reader':0x6e7330, 'point_reader':0x6e77d0,
        'additional_protection_reader':0x6e7f80,
        'clearance_reader':0x6e8310, 'departure_output_reader':0x6e9360,
        'straight_control_reader':0x6e9dd0, 'lu_control_reader':0x6ea010,
        'through_control_reader':0x6ea290,
    }
    evidence={'sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),'target':target,'functions':{}}
    r=r2pipe.open(str(executable),flags=['-2','-e','scr.color=0'])
    try:
        r.cmd('aaa')
        for name,address in functions.items():
            info=r.cmdj(f'afij @ {address}')
            if not info or info[0]['addr']!=address:
                raise ValueError(f'Expected reader function not found: {name}')
            evidence['functions'][name]=info[0]
            (output/f'{name}.pseudo.c').write_text(r.cmd(f'pdc @ {address}'),encoding='utf-8')
            (output/f'{name}.asm').write_text(r.cmd(f'pdf @ {address}'),encoding='utf-8')
        (output/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    finally:
        r.quit()
    print(f'Analyzed {len(functions)} functions; target executable was never run.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('executable',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--target',choices=['sdm','liansuo'],default='sdm')
    args=parser.parse_args()
    reverse(args.executable,args.output,args.target)
