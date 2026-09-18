import json
from uuid import UUID,uuid4
from sqlalchemy import select,func,delete
from app.config import settings
from app.errors import AppError,not_found
from app.services.primitives import cursor_encode,cursor_decode,now

def named(conn,table,farm_id):
    return [dict(r) for r in conn.execute(select(table.c.id,table.c.name).where(table.c.farm_id==farm_id).order_by(func.lower(table.c.name),table.c.id)).mappings()]

def require_resource(conn,table,farm_id,identifier):
    row=conn.execute(select(table).where(table.c.farm_id==farm_id,table.c.id==identifier)).mappings().first()
    if row is None:not_found()
    return dict(row)

def page(conn,stmt,count_stmt,scope,cursor,limit,id_column):
    if cursor:
        values=cursor_decode(cursor,scope,settings().csrf_secret)
        try:
            if len(values)!=1:raise ValueError()
            marker=UUID(values[0])
        except (TypeError,ValueError) as exc:raise AppError(422,'INVALID_CURSOR','Invalid catalog cursor.') from exc
        stmt=stmt.where(id_column>marker)
    rows=[dict(r) for r in conn.execute(stmt.order_by(id_column).limit(limit+1)).mappings()]
    more=len(rows)>limit;rows=rows[:limit]
    next_cursor=cursor_encode([str(rows[-1]['id'])],scope,settings().csrf_secret) if more else None
    return {'items':rows,'total_matching':conn.execute(count_stmt).scalar_one(),'next_cursor':next_cursor}

def field_detail(conn,farm_id,identifier):
    from app.models.tables import fields
    row=conn.execute(select(fields.c.id,fields.c.name,fields.c.created_at,fields.c.updated_at,func.ST_AsGeoJSON(fields.c.geometry).label('geometry')).where(fields.c.farm_id==farm_id,fields.c.id==identifier)).mappings().first()
    if not row:not_found()
    out=dict(row);out['geometry']=json.loads(out['geometry']);return out

def valid_field_geometry(conn,geometry):
    geom=func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)),4326)
    if not conn.execute(select(func.ST_IsValid(geom))).scalar_one():
        raise AppError(422,'INVALID_GEOMETRY','The polygon intersects itself or has invalid rings.')
    return geom

def validate_refs(conn,farm_id,values):
    from app.models.tables import fields,activities,fertilizers
    for key,table in [('field_id',fields),('activity_id',activities),('fertilizer_id',fertilizers)]:
        if values.get(key):require_resource(conn,table,farm_id,values[key])

def member_view(conn,farm_id,identifier):
    from app.models.tables import memberships,users
    row=conn.execute(select(memberships.c.id,memberships.c.user_id,memberships.c.role,memberships.c.is_enabled,users.c.name,users.c.username).join(users,users.c.id==memberships.c.user_id).where(memberships.c.farm_id==farm_id,memberships.c.id==identifier)).mappings().first()
    if not row:not_found()
    return dict(row)
