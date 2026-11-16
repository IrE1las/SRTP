"""Small, local teaching-material retriever. Never searches the question bank."""
import math
import re
from collections import Counter
from pathlib import Path
from app.core.database import SessionLocal
from app.services.knowledge_library import candidates as managed_candidates

ROOT = Path(__file__).resolve().parents[4]
RULES_FILE = ROOT / 'ai_design/station/interlocking_rules.md'


def terms(text):
    text = text.casefold()
    result = re.findall(r'[a-z0-9]+', text)
    for run in re.findall(r'[\u4e00-\u9fff]+', text):
        result.extend(run[i:i + 2] for i in range(len(run) - 1))
    return Counter(result)


def retrieve(query, limit=3):
    # Resolve current enable/delete state for every new answer, never scan unmanaged files.
    with SessionLocal() as db:
        candidates = managed_candidates(db)
    for chunk in candidates:
        chunk['terms'] = terms(chunk['text'])
    query_terms = terms(query)
    frequencies = Counter(term for chunk in candidates for term in chunk['terms'])
    ranked = []
    for chunk in candidates:
        score = sum(math.log(1 + len(candidates) / frequencies[term]) * min(count, 2)
                    for term, count in chunk['terms'].items() if term in query_terms)
        if score > 0:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [{'id': index, 'label': chunk['label'], 'text': chunk['text']}
            for index, (_, chunk) in enumerate(ranked[:limit], 2)]


def internal_rules():
    try:
        return RULES_FILE.read_text(encoding='utf-8-sig')[:30000]
    except OSError:
        return ''
