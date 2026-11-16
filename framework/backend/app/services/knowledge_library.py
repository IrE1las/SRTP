"""Persist managed sources; only enabled text is exposed to the chapter tutor."""
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import update, delete

from app.models.knowledge import KnowledgeDocument, KnowledgeMigration
from app.services import knowledge_parser as parser

ROOT = Path(__file__).resolve().parents[4]
STORAGE = ROOT / '.runtime/knowledge-library/documents'
BUILTIN = ROOT / 'ai_design/ai/knowledge/计算机联锁基础知识.docx'


def file_path(doc):
    if doc.builtin:
        return BUILTIN
    # Neither a client-supplied name nor a path from a document enters a file path.
    try:
        identifier = str(UUID(doc.id))
    except ValueError:
        raise HTTPException(404, '资料不存在') from None
    root = STORAGE.resolve()
    target = root / (identifier + '.' + doc.format)
    if target.is_symlink() or not target.resolve().is_relative_to(root):
        raise HTTPException(404, '资料文件不可用')
    return target


def public(doc, preview=False):
    chars = sum(len(p['text']) for p in doc.pages)
    result = {key: getattr(doc, key) for key in ('id', 'title', 'description', 'filename', 'format', 'size',
              'enabled', 'revision', 'created_at', 'updated_at', 'warnings', 'builtin')}
    result.update(page_count=len(doc.pages), text_chars=chars,
                  sparse_pages=sum(len(p['text'].strip()) < 30 for p in doc.pages),
                  status='ready' if chars else 'needs_text',
                  unit='段' if doc.format in {'docx', 'txt', 'md'} else '页')
    if preview:
        result['pages'] = doc.pages
    return result


def find(db, identifier):
    doc = db.get(KnowledgeDocument, identifier)
    if doc is None:
        raise HTTPException(404, '资料不存在或已删除')
    return doc


def add(db, filename, data, title='', description='', password='', enabled=True):
    suffix = Path(filename.replace('\\', '/')).suffix.lower()
    clean_name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', filename.replace('\\', '/').split('/')[-1])[:190]
    title = title.strip() or Path(clean_name).stem
    if not title or len(title) > 160 or len(description) > 2000:
        raise HTTPException(422, '资料名称为 1—160 字，说明最多 2000 字。')
    try:
        clean = parser.prepare(data, suffix, password)
        pages, warnings = parser.extract(clean, suffix)
    except parser.MaterialError as failure:
        raise HTTPException(422, str(failure)) from None
    digest = hashlib.sha256(clean).hexdigest()
    duplicate = db.query(KnowledgeDocument).filter_by(sha256=digest).first()
    if duplicate:
        raise HTTPException(409, f'这份文件已在资料库中：{duplicate.title}')
    doc = KnowledgeDocument(id=str(uuid4()), title=title, description=description.strip(), filename=clean_name,
        format=suffix[1:], size=len(clean), sha256=digest, pages=pages, warnings=warnings,
        builtin=False, enabled=enabled)
    STORAGE.mkdir(parents=True, exist_ok=True)
    target = file_path(doc)
    try:
        with target.open('xb') as stream:
            stream.write(clean)
        db.add(doc)
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    return public(doc, True)


def edit(db, identifier, revision, title, description, enabled):
    find(db, identifier)
    changed = db.execute(update(KnowledgeDocument).where(KnowledgeDocument.id == identifier,
        KnowledgeDocument.revision == revision).values(title=title.strip(), description=description.strip(),
        enabled=enabled, revision=revision + 1, updated_at=datetime.now(timezone.utc)),
        execution_options={'synchronize_session': False})
    if not changed.rowcount:
        db.rollback()
        raise HTTPException(409, '资料已在其他页面更新，请刷新后重试。')
    db.commit()
    db.expire_all()
    return public(find(db, identifier), True)


def remove(db, identifier, revision):
    doc = find(db, identifier)
    path, builtin = file_path(doc), doc.builtin
    # Commit removal first: a file cleanup failure must never leave it retrievable.
    changed = db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id == identifier,
        KnowledgeDocument.revision == revision), execution_options={'synchronize_session': False})
    if not changed.rowcount:
        db.rollback()
        raise HTTPException(409, '资料已更新，请刷新后再删除。')
    db.commit()
    if not builtin:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return {'message': '已从资料库移除；本地副本清理失败，请联系维护人员清理。'}
    return {'message': '已从资料库删除。已有对话引用保留，后续回答不再检索这份资料。'}


def adopt_builtin(db):
    """One-time migration. A deleted source must never reappear after restart."""
    key = 'initial-teaching-source-v1'
    if db.get(KnowledgeMigration, key):
        return
    if BUILTIN.exists():
        data = BUILTIN.read_bytes()
        pages, warnings = parser.extract(data, '.docx')
        db.add(KnowledgeDocument(id=str(uuid4()), title=BUILTIN.stem, description='项目原有的计算机联锁基础资料。',
            filename=BUILTIN.name, format='docx', size=len(data), sha256=hashlib.sha256(data).hexdigest(),
            builtin=True, pages=pages, warnings=warnings, enabled=True))
    db.add(KnowledgeMigration(key=key))
    db.commit()


def candidates(db):
    result = []
    for doc in db.query(KnowledgeDocument).filter_by(enabled=True).order_by(KnowledgeDocument.created_at, KnowledgeDocument.id):
        for page in doc.pages:
            text = page['text'].strip()
            for offset in range(0, len(text), 650):
                result.append({'label': f'{doc.title}，{page["location"]}', 'text': text[offset:offset + 800]})
    return result
