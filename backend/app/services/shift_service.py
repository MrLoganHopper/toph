from sqlalchemy import select,func
from app.errors import not_found,AppError
from app.services.catalog_service import require_resource,validate_refs

def shift_statement():
    from app.models.tables import shifts as s,users as u,fields as f,activities as a,fertilizers as z
    join=s.join(u,u.c.id==s.c.employee_id).outerjoin(f,(f.c.id==s.c.field_id)&(f.c.farm_id==s.c.farm_id)).outerjoin(a,(a.c.id==s.c.activity_id)&(a.c.farm_id==s.c.farm_id)).outerjoin(z,(z.c.id==s.c.fertilizer_id)&(z.c.farm_id==s.c.farm_id))
    return select(s,u.c.name.label('employee_name'),f.c.name.label('field_name'),a.c.name.label('activity_name'),z.c.name.label('fertilizer_name')).select_from(join)

def view(row):
    return {'id':row['id'],'employee':{'id':row['employee_id'],'name':row['employee_name']},'start_at':row['start_at'],'end_at':row['end_at'],
        **{key:{'id':row[key+'_id'],'name':row[key+'_name']} if row[key+'_id'] else None for key in ('field','activity','fertilizer')}}

def get_shift(conn,farm_id,identifier):
    from app.models.tables import shifts
    row=conn.execute(shift_statement().where(shifts.c.farm_id==farm_id,shifts.c.id==identifier)).mappings().first()
    if not row:not_found()
    return view(row)

def validate_shift(conn,farm_id,values):
    from app.models.tables import memberships,users
    allowed=conn.execute(select(memberships.c.id).join(users,users.c.id==memberships.c.user_id).where(memberships.c.farm_id==farm_id,
        memberships.c.user_id==values['employee_id'],memberships.c.role=='worker',memberships.c.is_enabled.is_(True),users.c.is_enabled.is_(True))).first()
    if not allowed:not_found()
    validate_refs(conn,farm_id,values)
    if values['end_at']<=values['start_at']:raise AppError(422,'INVALID_SCHEDULE','End time must follow start time.')
