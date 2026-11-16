"""Knowledge library administration; never accessible to learner accounts."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.knowledge import KnowledgeDocument
from app.services import knowledge_library as library
from app.services.knowledge_parser import MAX_BYTES

router = APIRouter(dependencies=[Depends(require_roles('admin'))])


class EditMaterial(BaseModel):
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=2000)
    enabled: bool

    @field_validator('title')
    @classmethod
    def meaningful_title(cls, value):
        if not value.strip():
            raise ValueError('请填写资料名称')
        return value.strip()


@router.get('')
def list_materials(db: Session = Depends(get_db)):
    return [library.public(d) for d in db.query(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())]


@router.post('', status_code=201)
def upload_material(file: Annotated[UploadFile, File()], title: Annotated[str, Form(max_length=160)] = '',
        description: Annotated[str, Form(max_length=2000)] = '', password: Annotated[str, Form(max_length=256)] = '',
        enabled: Annotated[bool, Form()] = True, db: Session = Depends(get_db)):
    try:
        data = file.file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, '单份资料不能超过 40 MB。')
        return library.add(db, file.filename or '', data, title, description, password, enabled)
    finally:
        file.file.close()


@router.get('/{identifier}')
def material_detail(identifier: str, db: Session = Depends(get_db)):
    return library.public(library.find(db, identifier), True)


@router.put('/{identifier}')
def edit_material(identifier: str, body: EditMaterial, db: Session = Depends(get_db)):
    return library.edit(db, identifier, **body.model_dump())


@router.delete('/{identifier}')
def delete_material(identifier: str, revision: int = Query(ge=1), db: Session = Depends(get_db)):
    return library.remove(db, identifier, revision)


@router.get('/{identifier}/download')
def download_material(identifier: str, db: Session = Depends(get_db)):
    doc = library.find(db, identifier)
    path = library.file_path(doc)
    if not path.is_file():
        raise HTTPException(404, '资料文件不可用，请重新上传。')
    return FileResponse(path, filename=doc.filename, media_type='application/octet-stream')
