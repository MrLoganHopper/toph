from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,Query,Response
from sqlalchemy import select,func,delete
from app.api.dependencies import require_farm_member,require_farm_admin
from app.services.auth_service import Context,recheck
from app.services.primitives import now
from app.services import catalog_service as service
from app.db.session import transaction
from app.schemas.contracts import Named,Page,CatalogInput,TagInput,FieldInput,FieldUpdate,FieldDetail,GeoCollection
router=APIRouter(prefix='/api/v1/farms/{farm_id}',tags=['Catalogs and fields'])

def catalog_table(kind):
    from app.models import tables
    return getattr(tables,kind)

def install_catalog(kind):
    def get_catalog(cursor:str|None=None,limit:int=Query(100,ge=1,le=100),ctx:Context=Depends(require_farm_member)):
        table=catalog_table(kind)
        with transaction() as conn:
            recheck(conn,ctx)
            where=table.c.farm_id==ctx.farm_id
            return service.page(conn,select(table.c.id,table.c.name).where(where),select(func.count()).select_from(table).where(where),[kind,str(ctx.farm_id)],cursor,limit,table.c.id)
    def create_catalog(data:CatalogInput,ctx:Context=Depends(require_farm_admin)):
        table=catalog_table(kind);identifier=uuid4()
        with transaction() as conn:
            recheck(conn,ctx,admin=True)
            conn.execute(table.insert().values(id=identifier,farm_id=ctx.farm_id,name=data.name))
            return {'id':identifier,'name':data.name}
    def update_catalog(identifier:UUID,data:CatalogInput,ctx:Context=Depends(require_farm_admin)):
        table=catalog_table(kind)
        with transaction() as conn:
            recheck(conn,ctx,admin=True);service.require_resource(conn,table,ctx.farm_id,identifier)
            conn.execute(table.update().where(table.c.farm_id==ctx.farm_id,table.c.id==identifier).values(name=data.name,updated_at=now()))
            return {'id':identifier,'name':data.name}
    def delete_catalog(identifier:UUID,ctx:Context=Depends(require_farm_admin)):
        table=catalog_table(kind)
        with transaction() as conn:
            recheck(conn,ctx,admin=True);service.require_resource(conn,table,ctx.farm_id,identifier)
            conn.execute(delete(table).where(table.c.farm_id==ctx.farm_id,table.c.id==identifier))
        return Response(status_code=204)
    for fn in (get_catalog,create_catalog,update_catalog,delete_catalog):fn.__name__=fn.__name__+'_'+kind
    router.add_api_route('/'+kind,get_catalog,methods=['GET'],response_model=Page[Named])
    router.add_api_route('/'+kind,create_catalog,methods=['POST'],response_model=Named,status_code=201)
    # Names in OpenAPI are the exact identifiers from the contract.
    from functools import wraps
    # A signature alias lets shared code keep the same parallel CRUD semantics.
    import inspect
    param=kind[:-3]+'y_id' if kind=='activities' else 'fertilizer_id'
    for fn,method,model,status in [(update_catalog,'PATCH',Named,200),(delete_catalog,'DELETE',None,204)]:
        sig=inspect.signature(fn)
        # FastAPI Path alias preserves the contract path without dynamically executing source.
        from fastapi import Path
        from typing import Annotated
        params=[p.replace(annotation=Annotated[UUID,Path(alias=param)]) if p.name=='identifier' else p for p in sig.parameters.values()]
        fn.__signature__=sig.replace(parameters=params)
        router.add_api_route('/'+kind+'/{'+param+'}',fn,methods=[method],response_model=model,status_code=status)

install_catalog('activities');install_catalog('fertilizers')

@router.get('/tags',response_model=Page[Named])
def tags(cursor:str|None=None,limit:int=Query(100,ge=1,le=100),ctx:Context=Depends(require_farm_member)):
    table=catalog_table('tags')
    with transaction() as conn:
        recheck(conn,ctx);where=table.c.farm_id==ctx.farm_id
        return service.page(conn,select(table.c.id,table.c.name).where(where),select(func.count()).select_from(table).where(where),['tags',str(ctx.farm_id)],cursor,limit,table.c.id)

@router.post('/tags',response_model=Named,status_code=201)
def add_tag(data:TagInput,ctx:Context=Depends(require_farm_admin)):
    table=catalog_table('tags');identifier=uuid4()
    with transaction() as conn:
        recheck(conn,ctx,admin=True);conn.execute(table.insert().values(id=identifier,farm_id=ctx.farm_id,name=data.name))
    return {'id':identifier,'name':data.name}

@router.get('/fields',response_model=Page[Named])
def fields(cursor:str|None=None,limit:int=Query(100,ge=1,le=100),ctx:Context=Depends(require_farm_member)):
    table=catalog_table('fields')
    with transaction() as conn:
        recheck(conn,ctx);where=table.c.farm_id==ctx.farm_id
        return service.page(conn,select(table.c.id,table.c.name).where(where),select(func.count()).select_from(table).where(where),['fields',str(ctx.farm_id)],cursor,limit,table.c.id)

@router.get('/fields/geojson',response_model=GeoCollection)
def geojson(cursor:str|None=None,limit:int=Query(50,ge=1,le=50),field_id:UUID|None=None,ctx:Context=Depends(require_farm_member)):
    import json
    table=catalog_table('fields')
    with transaction() as conn:
        recheck(conn,ctx)
        base=table.c.farm_id==ctx.farm_id;where=base if field_id is None else base&(table.c.id==field_id)
        result = service.page(
    conn,
    select(
        table.c.id,
        table.c.name,
        func.extensions.ST_AsGeoJSON(table.c.geometry).label("geometry"),
    ).where(where),
    select(func.count()).select_from(table).where(where),
    ["geojson", str(ctx.farm_id), str(field_id)],
    cursor,
    limit,
    table.c.id,
)
        box = conn.execute(
    select(
        func.extensions.ST_XMin(
            func.extensions.ST_Envelope(
                func.extensions.ST_Collect(table.c.geometry)
            )
        ),
        func.extensions.ST_YMin(
            func.extensions.ST_Envelope(
                func.extensions.ST_Collect(table.c.geometry)
            )
        ),
        func.extensions.ST_XMax(
            func.extensions.ST_Envelope(
                func.extensions.ST_Collect(table.c.geometry)
            )
        ),
        func.extensions.ST_YMax(
            func.extensions.ST_Envelope(
                func.extensions.ST_Collect(table.c.geometry)
            )
        ),
    ).where(base)
).one()
        features=[{'type':'Feature','id':str(r['id']),'properties':{'id':str(r['id']),'name':r['name']},'geometry':json.loads(r['geometry'])} for r in result['items']]
        return {'type':'FeatureCollection','features':features,'farm_bbox':list(box) if box[0] is not None else None,'next_cursor':result['next_cursor']}

@router.get('/fields/{field_id}',response_model=FieldDetail)
def get_field(field_id:UUID,ctx:Context=Depends(require_farm_member)):
    with transaction() as conn:recheck(conn,ctx);return service.field_detail(conn,ctx.farm_id,field_id)

@router.post('/fields',response_model=FieldDetail,status_code=201)
def add_field(data:FieldInput,ctx:Context=Depends(require_farm_admin)):
    table=catalog_table('fields');identifier=uuid4()
    with transaction() as conn:
        recheck(conn,ctx,admin=True);geom=service.valid_field_geometry(conn,data.geometry)
        conn.execute(table.insert().values(id=identifier,farm_id=ctx.farm_id,name=data.name,geometry=geom))
        return service.field_detail(conn,ctx.farm_id,identifier)

@router.patch('/fields/{field_id}',response_model=FieldDetail)
def edit_field(field_id:UUID,data:FieldUpdate,ctx:Context=Depends(require_farm_admin)):
    table=catalog_table('fields');values=data.model_dump(exclude_unset=True)
    with transaction() as conn:
        recheck(conn,ctx,admin=True);service.require_resource(conn,table,ctx.farm_id,field_id)
        if 'geometry' in values:values['geometry']=service.valid_field_geometry(conn,values['geometry'])
        conn.execute(table.update().where(table.c.farm_id==ctx.farm_id,table.c.id==field_id).values(**values,updated_at=now()))
        return service.field_detail(conn,ctx.farm_id,field_id)

@router.delete('/fields/{field_id}',status_code=204)
def remove_field(field_id:UUID,ctx:Context=Depends(require_farm_admin)):
    table=catalog_table('fields')
    with transaction() as conn:
        recheck(conn,ctx,admin=True);service.require_resource(conn,table,ctx.farm_id,field_id)
        conn.execute(delete(table).where(table.c.farm_id==ctx.farm_id,table.c.id==field_id))
