"""Managed library access, extraction, decryption, and retrieval lifecycle."""
import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import msoffcrypto
import pytest
from pypdf import PdfWriter
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.models.knowledge import KnowledgeDocument
from app.services import knowledge_library as lib, knowledge_parser as parser, chapter_ai_materials as materials

BASE = '/api/admin/knowledge'


@pytest.fixture()
def library_client(client, monkeypatch, tmp_path):
    from main import app
    monkeypatch.setattr(lib, 'STORAGE', tmp_path / 'sources')
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role='admin', is_active=True)
    yield client, app


def post(client, text='轨道电路用于检查区段占用与空闲。', **fields):
    return client.post(BASE, files={'file': ('轨道电路.md', text.encode(), 'text/plain')}, data=fields)


def pptx(slides, order=None):
    """Minimal package with intentionally shuffled physical slide names."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        ids = order or list(range(1, len(slides) + 1))
        z.writestr('ppt/presentation.xml', '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst>' + ''.join(f'<p:sldId id="{i+255}" r:id="r{i}"/>' for i in ids) + '</p:sldIdLst></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels', '<Relationships>' + ''.join(f'<Relationship Id="r{i}" Target="slides/slide{i}.xml"/>' for i in range(1,len(slides)+1)) + '</Relationships>')
        for i, text in enumerate(slides, 1):
            z.writestr(f'ppt/slides/slide{i}.xml', f'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:sld>')
    return output.getvalue()


def test_all_routes_are_admin_only(library_client):
    client, app = library_client
    for role in ('student', 'teacher'):
        app.dependency_overrides[get_current_user] = lambda role=role: SimpleNamespace(id=2, role=role)
        responses = [client.get(BASE), post(client), client.get(BASE+'/unknown'),
                     client.get(BASE+'/unknown/download'), client.delete(BASE+'/unknown?revision=1'),
                     client.put(BASE+'/unknown', json={'title':'x','description':'','enabled':False,'revision':1})]
        assert all(r.status_code == 403 for r in responses)
    app.dependency_overrides.pop(get_current_user)
    assert client.get(BASE).status_code == 401


def test_upload_edit_disable_delete_retrieval_and_restart(library_client, db_session, monkeypatch):
    client, _ = library_client
    monkeypatch.setattr(materials, 'SessionLocal', sessionmaker(bind=db_session.get_bind()))
    response = post(client)
    assert response.status_code == 201, response.text
    doc = response.json()
    identifier = doc['id']
    assert doc['pages'][0]['location'] == '第1段'
    assert materials.retrieve('轨道电路检查')[0]['label'] == '轨道电路，第1段'
    assert materials.retrieve('今天天气怎么样') == []
    assert client.get(f'{BASE}/{identifier}/download').content == '轨道电路用于检查区段占用与空闲。'.encode()
    assert post(client).status_code == 409
    changed = client.put(f'{BASE}/{identifier}', json={'revision':1,'title':'联锁原理','description':'教学资料','enabled':False})
    assert changed.status_code == 200
    assert materials.retrieve('轨道电路检查') == []
    assert client.delete(f'{BASE}/{identifier}?revision=1').status_code == 409
    assert client.put(f'{BASE}/{identifier}', json={'revision':1,'title':'旧页面','enabled':True}).status_code == 409
    updated = client.put(f'{BASE}/{identifier}', json={'revision':2,'title':'联锁原理','description':'教学资料','enabled':True}).json()
    assert materials.retrieve('轨道电路检查')[0]['label'] == '联锁原理，第1段'
    assert client.delete(f'{BASE}/{identifier}?revision={updated["revision"]}').status_code == 200
    db_session.expire_all()
    assert db_session.get(KnowledgeDocument, identifier) is None
    assert not list(lib.STORAGE.iterdir())
    assert client.get(f'{BASE}/{identifier}').status_code == 404
    assert materials.retrieve('轨道电路检查') == []


def test_builtin_removal_is_not_reimported_and_original_is_preserved(db_session):
    lib.adopt_builtin(db_session)
    doc = db_session.query(KnowledgeDocument).filter_by(builtin=True).one()
    original = lib.BUILTIN.read_bytes()
    lib.remove(db_session, doc.id, doc.revision)
    lib.adopt_builtin(db_session)
    assert db_session.query(KnowledgeDocument).count() == 0
    assert lib.BUILTIN.read_bytes() == original


def test_slide_order_comes_from_presentation_and_empty_slides_remain_locatable():
    pages, warnings = parser.extract(pptx(['道岔锁闭', '', '进路建立'], [3, 1, 2]), '.pptx')
    assert [p['text'] for p in pages] == ['进路建立', '道岔锁闭', '']
    assert [p['location'] for p in pages] == ['第1页', '第2页', '第3页']
    assert any('电路连线' in warning for warning in warnings)


def test_encrypted_pptx_is_saved_without_password_and_bad_password_saves_nothing(library_client):
    client, _ = library_client
    plain = pptx(['进路锁闭后开放信号'])
    encrypted = io.BytesIO()
    # Library encryption expects OOXML content types even though extraction only uses slides.
    valid = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(plain)) as original, zipfile.ZipFile(valid, 'w') as z:
        for name in original.namelist(): z.writestr(name, original.read(name))
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>')
        # msoffcrypto's synthetic encryption writer requires a regular (>=4KB) OLE stream.
        z.writestr('fixture-padding.bin', b'x' * 5000)
    msoffcrypto.OfficeFile(io.BytesIO(valid.getvalue())).encrypt('test-password-only', encrypted)
    for password in ('', 'wrong'):
        result = client.post(BASE, files={'file':('course.pptx',encrypted.getvalue())},data={'password':password})
        assert result.status_code == 422
        assert 'test-password-only' not in result.text and 'wrong' not in result.text
    assert not lib.STORAGE.exists()
    result = client.post(BASE, files={'file':('course.pptx',encrypted.getvalue())},data={'password':'test-password-only'})
    assert result.status_code == 201, result.text
    saved = client.get(f'{BASE}/{result.json()["id"]}/download').content
    assert zipfile.is_zipfile(io.BytesIO(saved))
    assert 'test-password-only' not in result.text


def test_encrypted_pdf_is_decrypted_and_image_only_file_is_not_claimed_as_readable():
    writer = PdfWriter(); writer.add_blank_page(width=200,height=200); writer.encrypt('test-only')
    stream = io.BytesIO(); writer.write(stream)
    with pytest.raises(parser.MaterialError): parser.prepare(stream.getvalue(),'.pdf','bad')
    plain = parser.prepare(stream.getvalue(), '.pdf', 'test-only')
    pages,warnings = parser.extract(plain,'.pdf')
    assert len(pages)==1 and pages[0]['text']==''
    assert any('未提取到' in w for w in warnings)


def test_rejects_broken_wrong_format_oversized_and_blank_name(library_client, monkeypatch):
    client, _ = library_client
    assert client.post(BASE,files={'file':('bad.pptx',b'broken')}).status_code == 422
    assert client.post(BASE,files={'file':('old.ppt',b'legacy')}).status_code == 422
    assert client.post(BASE,files={'file':('bad.md',b'\xff')}).status_code == 422
    from app.api import knowledge
    monkeypatch.setattr(knowledge, 'MAX_BYTES', 5)
    assert post(client).status_code == 413
    assert not lib.STORAGE.exists()


def test_document_path_is_generated_not_taken_from_uploaded_filename(library_client):
    client, _ = library_client
    r = client.post(BASE,files={'file':('../../outside.md','联锁关系'.encode())})
    assert r.status_code == 201
    assert r.json()['filename'] == 'outside.md'
    assert [p.name for p in lib.STORAGE.iterdir()] == [r.json()['id'] + '.md']


def test_word_uses_paragraphs_not_invented_pages():
    output = io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>道岔</w:t></w:r><w:r><w:t>表示</w:t></w:r></w:p></w:body></w:document>')
    pages,_ = parser.extract(output.getvalue(),'.docx')
    assert pages == [{'number':1,'location':'第1段','text':'道岔表示','images':0}]


def test_tutor_receives_current_managed_sources_and_real_locations(db_session, tmp_path, monkeypatch):
    from app.services import chapter_ai_tutor as tutor
    monkeypatch.setattr(lib, 'STORAGE', tmp_path / 'sources')
    monkeypatch.setattr(materials, 'SessionLocal', sessionmaker(bind=db_session.get_bind()))
    uploaded = lib.add(db_session, '教师课件.pptx', pptx(['轨道电路用于检查区段占用与空闲。']))
    observed = []
    def provider(system, payload, max_tokens=2200):
        observed.append(payload['sources'])
        ids = [s['id'] for s in payload['sources']]
        return {'scope':'related','answer':'检查区段占用与空闲。','source_ids':ids,'general_knowledge':False}
    monkeypatch.setattr(tutor, 'provider', provider)
    payload = {'question':{'stem':'轨道电路检查什么？'},'result':{'explanation':'检查区段占用。'}}
    answer = tutor.generate(payload, [], '', True)
    assert answer['sources'][1]['label'] == '教师课件，第1页'
    lib.edit(db_session, uploaded['id'],1,'教师课件','',False)
    answer = tutor.generate(payload, [], '', True)
    assert [s['id'] for s in answer['sources']] == [1]
    assert observed[-1] == [{'id':1,'label':'本题标准解析','text':'检查区段占用。'}]
