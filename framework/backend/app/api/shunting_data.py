"""Teacher access to the reviewed original-station shunting answer source."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.shunting_route import ShuntingDataset, ShuntingRoute
from app.services.shunting_data import DATASET_KEY

router = APIRouter(dependencies=[Depends(require_roles('teacher', 'admin'))])


def _dataset(db: Session) -> ShuntingDataset:
    dataset = db.query(ShuntingDataset).filter_by(dataset_key=DATASET_KEY).one_or_none()
    if dataset is None:
        raise HTTPException(404, '尚未导入原始图车站调车联锁表')
    return dataset


@router.get('/dataset')
def dataset_info(db: Session = Depends(get_db)) -> dict[str, Any]:
    dataset = _dataset(db)
    return {
        'dataset_key':dataset.dataset_key, 'station_key':dataset.station_key,
        'station_name':dataset.station_name, 'station_topology':dataset.station_topology,
        'source':dataset.source, 'content_sha256':dataset.content_sha256,
        'route_count':db.query(ShuntingRoute).filter_by(dataset_id=dataset.id).count(),
    }


@router.get('/routes')
def list_shunting_routes(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    dataset = _dataset(db)
    routes = db.query(ShuntingRoute).filter_by(dataset_id=dataset.id).order_by(ShuntingRoute.route_number).all()
    return [{'route_number':r.route_number, 'route_type':r.route_type, 'origin_label':r.origin_label,
             'route_name':r.route_name} for r in routes]


@router.get('/routes/{route_number}')
def shunting_route_detail(route_number: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    dataset = _dataset(db)
    route = db.query(ShuntingRoute).filter_by(dataset_id=dataset.id, route_number=route_number).one_or_none()
    if route is None:
        raise HTTPException(404, '调车进路不存在')
    return {
        'dataset_key':dataset.dataset_key, 'station_key':dataset.station_key,
        'route_number':route.route_number, 'route_type':route.route_type,
        'fields':route.fields, 'rich_text':route.rich_text, 'provenance':route.provenance,
    }
