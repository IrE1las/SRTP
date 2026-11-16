"""Extract document text with real slide/page locations; never executes document content."""
import io
import posixpath
import re
import zipfile
from xml.etree import ElementTree as ET

import msoffcrypto
from pypdf import PdfReader, PdfWriter

MAX_BYTES = 40 * 1024 * 1024
MAX_PAGES = 1500
MAX_TEXT = 2_000_000
FORMATS = {'.pptx', '.pdf', '.docx', '.txt', '.md'}
DRAWING = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
WORD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


class MaterialError(ValueError):
    pass


def prepare(data, suffix, password=''):
    """Return an unencrypted source. Passwords only live in this request's memory."""
    if suffix not in FORMATS:
        raise MaterialError('支持 PPTX、PDF、DOCX、TXT 和 Markdown；旧版 PPT 请在 PowerPoint 中另存为 PPTX 后上传。')
    if not data or len(data) > MAX_BYTES:
        raise MaterialError('文件不能为空，单份资料不能超过 40 MB。')
    if suffix in {'.pptx', '.docx'} and not zipfile.is_zipfile(io.BytesIO(data)):
        try:
            office = msoffcrypto.OfficeFile(io.BytesIO(data))
            if not office.is_encrypted():
                raise MaterialError('文件格式与扩展名不符，请重新另存后上传。')
            if not password:
                raise MaterialError('文件已加密，请填写打开密码。')
            office.load_key(password=password, verify_password=True)
            output = io.BytesIO()
            office.decrypt(output, verify_integrity=True)
            data = output.getvalue()
        except MaterialError:
            raise
        except msoffcrypto.exceptions.InvalidKeyError:
            raise MaterialError('密码不正确，请核对文件的打开密码。') from None
        except Exception:
            raise MaterialError('无法读取加密文件，请核对密码，或另存为无密码文件再上传。') from None
    if suffix == '.pdf':
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                if not password or not reader.decrypt(password):
                    raise MaterialError('PDF 已加密，请填写正确的打开密码。')
                if len(reader.pages) > MAX_PAGES:
                    raise MaterialError('单份资料最多支持 1500 页，请拆分后上传。')
                writer = PdfWriter()
                writer.append_pages_from_reader(reader)
                output = io.BytesIO()
                writer.write(output)
                data = output.getvalue()
        except MaterialError:
            raise
        except Exception:
            raise MaterialError('PDF 无法读取，请检查文件是否完整。') from None
    if len(data) > MAX_BYTES:
        raise MaterialError('解密后的文件超过 40 MB，请拆分后上传。')
    return data


def _xml(archive, name):
    info = archive.getinfo(name)
    if info.file_size > 8_000_000:
        raise MaterialError('文件中的单页内容过大，请拆分后上传。')
    return ET.fromstring(archive.read(info))


def _paragraphs(root, namespace):
    # Reading only text nodes avoids counting XML metadata and preserves table/group text.
    return '\n'.join(''.join(n.text or '' for n in p.iter(namespace + 't'))
                     for p in root.iter(namespace + 'p')).strip()


def extract(data, suffix):
    pages, warnings = [], []
    try:
        if suffix in {'.docx', '.pptx'}:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos = z.infolist()
                if len(infos) > 20000 or sum(i.file_size for i in infos) > 250_000_000:
                    raise MaterialError('文件展开后过大，请拆分后上传。')
                if suffix == '.docx':
                    root = _xml(z, 'word/document.xml')
                    pages = [{'number': i, 'location': f'第{i}段', 'text': _paragraphs(p, WORD), 'images': 0}
                             for i, p in enumerate(root.iter(WORD + 'p'), 1)]
                    # DOCX has no reliable pagination until rendered; do not invent page numbers.
                    warnings.append('Word 按原文段落定位；分页随字体和排版变化，不标注页码。')
                else:
                    root = _xml(z, 'ppt/presentation.xml')
                    rels = _xml(z, 'ppt/_rels/presentation.xml.rels')
                    targets = {r.attrib['Id']: r.attrib.get('Target', '') for r in rels
                               if r.attrib.get('TargetMode') != 'External'}
                    pns = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
                    rns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
                    slides = list(root.iter(pns + 'sldId'))
                    if len(slides) > MAX_PAGES:
                        raise MaterialError('单份课件最多支持 1500 页，请拆分后上传。')
                    for i, slide in enumerate(slides, 1):
                        target = targets[slide.attrib[rns + 'id']]
                        name = posixpath.normpath(posixpath.join('ppt', target)) if not target.startswith('/') else target.lstrip('/')
                        if not name.startswith('ppt/slides/'):
                            raise MaterialError('课件幻灯片引用无效。')
                        slide_root = _xml(z, name)
                        pages.append({'number': i, 'location': f'第{i}页', 'text': _paragraphs(slide_root, DRAWING),
                                      'images': sum(1 for _ in slide_root.iter(DRAWING + 'blip'))})
                    warnings.append('已提取幻灯片文字；图片内文字、电路连线及动画过程尚未识别，AI 不据此猜测。')
        elif suffix == '.pdf':
            reader = PdfReader(io.BytesIO(data))
            if len(reader.pages) > MAX_PAGES:
                raise MaterialError('单份资料最多支持 1500 页，请拆分后上传。')
            for i, page in enumerate(reader.pages, 1):
                pages.append({'number': i, 'location': f'第{i}页', 'text': (page.extract_text() or '').strip(), 'images': 0})
            warnings.append('PDF 仅提取可复制文字，扫描页及图内文字尚未识别。')
        else:
            try:
                text = data.decode('utf-8-sig')
            except UnicodeDecodeError:
                raise MaterialError('文本文件请使用 UTF-8 编码保存后上传。') from None
            pages = [{'number': i, 'location': f'第{i}段', 'text': p.strip(), 'images': 0}
                     for i, p in enumerate(re.split(r'\n\s*\n', text), 1)]
        if len(pages) > 20000 or sum(len(p['text']) for p in pages) > MAX_TEXT:
            raise MaterialError('可检索文字过多，请按章节拆分后上传。')
        if not any(p['text'] for p in pages):
            warnings.append('未提取到可检索文字，请补充文字版或 OCR 文稿后重新上传。')
        return pages, warnings
    except MaterialError:
        raise
    except Exception:
        raise MaterialError('资料解析失败，请确认文件格式正确且未损坏。') from None
