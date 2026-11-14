"""Export the independent native route table with original line references."""
import argparse
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'framework'/'backend'))
from app.services.simulation_console.reference_station import reference_station_package


def export(output):
    package=reference_station_package()
    output.mkdir(parents=True,exist_ok=True)
    (output/'native-route-table.json').write_text(json.dumps({
        'source':package['source'],'provenance':package['provenance'],
        'counts':package['counts'],'routes':package['routes'],
    },ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    with (output/'原软件进路恢复表.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['进路编号','原进路名称','原文件行号','按钮顺序','道岔要求','接近区段',
                         '内方区段顺序','基本段','重建初始显示','超限绝缘检查','原始定义','备注'])
        for route in package['routes']:
            points=' '.join(sid+('反位' if pos else '定位') for sid,pos in route['switches'].items())
            writer.writerow([route['id'],route['name'],route['source_row'],
                             ' → '.join(route['button_sequence']),points,route['approach_section'],
                             ' → '.join(route['sections']),' '.join(route['subroutes']),route['aspect'],
                             json.dumps(route['clearance_checks'],ensure_ascii=False),route['source_raw'],
                             '；'.join(route['warnings']+route['reasons'])])
    print(f"Exported {len(package['routes'])} original definitions to {output}")


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    export(parser.parse_args().output)
