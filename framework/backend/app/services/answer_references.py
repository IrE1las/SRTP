"""Local-source references with explicit limits; not automatic essay answers."""
import hashlib
import json

LABELS = {
    'supported': '参考答案（现有资料可支持）',
    'partial': '参考解答（部分内容待核实）',
    'missing': '资料不足，暂不能给出标准答案',
}


def load_references(root):
    data = json.loads((root / 'ai_design/station/report_answer_references.json').read_text(encoding='utf8'))
    if data['version'] != 1:
        raise ValueError('参考答案版本不支持')
    source_paths = set()
    for source in data['sources']:
        path = (root / source['path']).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError('参考答案资料须位于项目内')
        if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise ValueError('参考答案依据已变化，须先复核解答')
        source_paths.add(source['path'])
    refs = {}
    for item in data['entries']:
        key = (item['question'], item['field'])
        if key in refs or item['status'] not in LABELS or not item['answer'] or not item['analysis']:
            raise ValueError('参考答案条目不完整或重复')
        if item['status'] != 'supported' and not item['missing']:
            raise ValueError('未核实答案须明确资料缺口')
        if not item['sources'] or any(s['path'] not in source_paths for s in item['sources']):
            raise ValueError('参考答案缺少本地来源')
        refs[key] = item
    return refs


def explanation_text(item):
    parts = [LABELS[item['status']], item['answer'], '解析：' + item['analysis']]
    if item['missing']:
        parts.append('尚缺依据：' + item['missing'])
    return '\n\n'.join(parts)
