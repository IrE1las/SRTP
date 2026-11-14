"""Lossless, repeatable import of the teacher-reviewed original-station table.

The runtime demonstration table cannot express the source's conditional groups
or typography. Keep source cells and character formatting intact for future exam
logic rather than interpreting them as runtime locks during import.
"""

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.shunting_route import ShuntingDataset, ShuntingRoute

DATASET_KEY = 'original-station-shunting'
STATION_KEY = 'original-photo-station'
SOURCE_FIELDS = {
    '进路号码', '方向', '进路', '进路方式', '排列进路按下按钮', '确定运行方向道岔',
    '信号机名称', '信号机显示', '表示器', '道岔', '敌对信号', '轨道区段',
    '迎面进路(列车)', '迎面进路(调车)', '其他联锁',
}


def validate_payload(payload: dict[str, Any]) -> None:
    if payload.get('schema_version') != 1 or payload.get('dataset_key') != DATASET_KEY:
        raise ValueError('不支持的数据集或版本')
    if payload.get('station_key') != STATION_KEY:
        raise ValueError('数据必须关联原始图车站')
    source = payload.get('source', {})
    if source.get('reviewed') is not True or not source.get('review_confirmation'):
        raise ValueError('缺少人工核对完成的明确确认记录')
    if len(source.get('workbook_sha256', '')) != 64:
        raise ValueError('缺少核对稿文件校验值')
    topology = payload.get('station_topology', {})
    if {t['id'] for t in topology.get('tracks', [])} != {'5', 'III', 'I', 'II', '4'}:
        raise ValueError('原始图五股道站场关联不一致')
    rows = payload.get('routes', [])
    numbers = [row.get('route_number') for row in rows]
    if any(type(n) is not int for n in numbers) or sorted(numbers) != list(range(20, 55)):
        raise ValueError('必须完整包含唯一的 20—54 号进路')
    for row in rows:
        fields = row.get('fields', {})
        if set(fields) != SOURCE_FIELDS or fields['进路号码'] != row['route_number']:
            raise ValueError('原表字段或进路号码不一致')
        for key in SOURCE_FIELDS - {'进路号码'}:
            if fields[key] is not None and not isinstance(fields[key], str):
                raise ValueError(f'{row["route_number"]} 号字段 {key} 必须保留为文本或空值')
        for key in ['方向', '进路', '排列进路按下按钮', '信号机名称', '信号机显示', '道岔', '敌对信号', '轨道区段']:
            if not fields[key]:
                raise ValueError(f'{row["route_number"]} 号缺少 {key}')
        if not fields['方向'].startswith('由') or '|23/25|' in fields['道岔']:
            raise ValueError('方向或已确认的大括号格式不正确')
        rich_text = row.get('rich_text', {})
        if set(rich_text) != {key for key, value in fields.items() if isinstance(value, str)}:
            raise ValueError('原文字段的字符格式记录不完整')
        for key, runs in rich_text.items():
            if ''.join(run['text'] for run in runs) != fields[key]:
                raise ValueError(f'{row["route_number"]} 号 {key} 原文与字符格式不一致')
            if any(run['vertical_align'] not in ('baseline', 'subscript', 'superscript') for run in runs):
                raise ValueError('无效的角标格式')
        if not row.get('provenance', {}).get('excel_row'):
            raise ValueError('缺少原工作表行号')


def import_reviewed_routes(db: Session, payload: dict[str, Any]) -> dict[str, int]:
    """Validate everything before mutation; the caller owns commit/rollback."""
    validate_payload(payload)
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    dataset = db.query(ShuntingDataset).filter_by(dataset_key=DATASET_KEY).one_or_none()
    values = {key: payload[key] for key in ['station_key', 'station_name', 'station_topology', 'source']}
    values['content_sha256'] = digest
    if dataset is None:
        dataset = ShuntingDataset(dataset_key=DATASET_KEY, **values)
        db.add(dataset)
        db.flush()
    else:
        for key, value in values.items():
            setattr(dataset, key, value)
    existing = {r.route_number:r for r in db.query(ShuntingRoute).filter_by(dataset_id=dataset.id).all()}
    if set(existing) - set(range(20, 55)):
        raise ValueError('数据集中存在本次范围外进路，未执行删除或覆盖')
    inserted = updated = 0
    for row in payload['routes']:
        fields = row['fields']
        values = {
            'route_type':'shunting', 'origin_label':fields['方向'][1:],
            'route_name':fields['方向'] + fields['进路'] + '调车进路',
            'fields':fields, 'rich_text':row['rich_text'], 'provenance':row['provenance'],
        }
        record = existing.get(row['route_number'])
        if record is None:
            db.add(ShuntingRoute(dataset_id=dataset.id, route_number=row['route_number'], **values))
            inserted += 1
        elif any(getattr(record, key) != value for key, value in values.items()):
            for key, value in values.items():
                setattr(record, key, value)
            updated += 1
    db.flush()
    return {'dataset_id':dataset.id, 'inserted':inserted, 'updated':updated, 'total':len(payload['routes'])}
