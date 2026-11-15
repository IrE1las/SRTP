"""Student-facing wording and document figures, separate from source/grading data."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

PRESENTATION_PATH = Path(__file__).resolve().parents[4] / 'ai_design/station/chapter_question_presentation.json'
FIGURES = {
    'images/fig1-5.png': '实例站场图1（图1-5）',
    'images/fig1-6.png': '实例站场图2（图1-6）',
    'images/fig1-7.png': '实例站场图3（图1-7）',
    'images/ppt-L01-p60.png': '列车进路示意图',
    'images/ppt-L02-p22.png': '偏极继电器磁化路径图',
    'images/ppt-L02-p74.png': '继电器电路图',
    'images/ppt-L06-p37.png': '信号设备移设示意图',
    'images/ppt-L07-p12.png': '道岔类型示意图',
}


@lru_cache(maxsize=1)
def load_presentations():
    try:
        data = json.loads(PRESENTATION_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if data.get('version') != 1:
        return {}
    return {item['id']: item for item in data.get('questions', [])}


def present_question(question):
    """Only apply a rewrite to the exact reviewed source version; never mutate it."""
    fields = ('id', 'chapter', 'kind', 'stem', 'options', 'answer', 'answer_status')
    signature = hashlib.sha256(json.dumps({key: question.get(key) for key in fields},
        ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    entry = load_presentations().get(question.get('id'), {})
    if (entry.get('signature') != signature
            or entry.get('original_images', []) != (question.get('images') or [])):
        entry = {}
    raw_images = entry.get('images', question.get('images', []))
    images = [dict(src='/chapter-bank/' + name, alt=FIGURES[name])
              for name in dict.fromkeys(raw_images) if name in FIGURES]
    return dict(stem=entry.get('stem', question.get('stem', '')), images=images)
