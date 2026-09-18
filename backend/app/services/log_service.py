import json
from datetime import datetime
from uuid import UUID
from sqlalchemy import select,func,exists,or_,tuple_
from app.config import settings
from app.errors import AppError,not_found
from app.services.auth_service import recheck
from app.services.primitives import range_bounds,now,cursor_decode,cursor_encode

def joined_statement():
    from app.models.tables import logs as l,users as u,fields as f,activities as a,fertilizers as z,shifts as s
    joined=l.join(u,u.c.id==l.c.employee_id).outerjoin(f,(f.c.id==l.c.field_id)&(f.c.farm_id==l.c.farm_id)).outerjoin(a,(a.c.id==l.c.activity_id)&(a.c.farm_id==l.c.farm_id)).outerjoin(z,(z.c.id==l.c.fertilizer_id)&(z.c.farm_id==l.c.farm_id)).outerjoin(s,(s.c.id==l.c.shift_id)&(s.c.farm_id==l.c.farm_id)&(s.c.employee_id==l.c.employee_id))
    return select(l,u.c.name.label('employee_name'),f.c.name.label('field_name'),a.c.name.label('activity_name'),z.c.name.label('fertilizer_name'),s.c.start_at.label('shift_start'),s.c.end_at.label('shift_end')).select_from(joined),joined

def predicates(conn,ctx,filters,default='all',as_of=None):
    from app.models.tables import farms,logs as l,users as u,fields as f,activities as a,fertilizers as z,tags as t,log_tags as lt
    role=recheck(conn,ctx);where=[l.c.farm_id==ctx.farm_id]
    zone=conn.execute(select(farms.c.timezone).where(farms.c.id==ctx.farm_id)).scalar_one()
    start,end=(filters.from_,filters.to) if filters.from_ is not None else range_bounds(filters.range or default,zone,as_of)
    if start is not None:where.extend([l.c.recorded_at>=start,l.c.recorded_at<end])
    who=ctx.user_id if role!='admin' else filters.employee_id
    if who is not None:where.append(l.c.employee_id==who)
    for key in ('field_id','activity_id','fertilizer_id'):
        if getattr(filters,key):where.append(l.c[key]==getattr(filters,key))
    if filters.tag_id:
        where.append(exists(select(1).where(lt.c.farm_id==ctx.farm_id,lt.c.log_id==l.c.id,lt.c.tag_id==filters.tag_id)))
    if filters.q.strip():
        q=filters.q.strip()
        tag_match=exists(select(1).select_from(lt.join(t,(t.c.id==lt.c.tag_id)&(t.c.farm_id==lt.c.farm_id))).where(lt.c.farm_id==ctx.farm_id,lt.c.log_id==l.c.id,t.c.name.icontains(q,autoescape=True)))
        where.append(or_(u.c.name.icontains(q,autoescape=True),f.c.name.icontains(q,autoescape=True),a.c.name.icontains(q,autoescape=True),z.c.name.icontains(q,autoescape=True),l.c.summary.icontains(q,autoescape=True),tag_match))
    fingerprint={'farm':str(ctx.farm_id),'user':str(ctx.user_id),'role':role,'default':default,
                 'filters':filters.model_dump(mode='json',by_alias=True,exclude={'cursor','limit'})}
    return where,fingerprint,zone

def tags_for(conn,ctx,log_ids):
    from app.models.tables import tags,log_tags
    result={identifier:[] for identifier in log_ids}
    if not log_ids:return result
    for r in conn.execute(select(log_tags.c.log_id,tags.c.id,tags.c.name).join(tags,(tags.c.id==log_tags.c.tag_id)&(tags.c.farm_id==log_tags.c.farm_id)).where(log_tags.c.farm_id==ctx.farm_id,log_tags.c.log_id.in_(log_ids)).order_by(tags.c.name)).mappings():
        result[r['log_id']].append({'id':r['id'],'name':r['name']})
    return result

def item(row,tags):
    return {'id':row['id'],'recorded_at':row['recorded_at'],'employee':{'id':row['employee_id'],'name':row['employee_name']},
        **{key:{'id':row[key+'_id'],'name':row[key+'_name']} if row[key+'_id'] else None for key in ('activity','fertilizer','field')},
        'scheduled_shift':{'id':row['shift_id'],'start_at':row['shift_start'],'end_at':row['shift_end']} if row['shift_id'] else None,
        'summary_preview':row['summary'][:240]+('...' if len(row['summary'])>240 else ''),
        'extraction_confidence':float(row['extraction_confidence']) if row['extraction_confidence'] is not None else None,'tags':tags}

def list_logs(conn,ctx,filters,default='all',as_of=None):
    from app.models.tables import logs
    stmt,joined=joined_statement();where,fp,zone=predicates(conn,ctx,filters,default,as_of)
    total=conn.execute(select(func.count()).select_from(joined).where(*where)).scalar_one()
    stmt=stmt.where(*where)
    if filters.cursor:
        vals=cursor_decode(filters.cursor,fp,settings().csrf_secret)
        try:
            if len(vals)!=2:raise ValueError()
            stamp=datetime.fromisoformat(vals[0]);marker=UUID(vals[1])
            if stamp.tzinfo is None:raise ValueError()
        except (TypeError,ValueError) as exc:raise AppError(422,'INVALID_CURSOR','Invalid report cursor.') from exc
        pair=tuple_(logs.c.recorded_at,logs.c.id)
        stmt=stmt.where(pair<(stamp,marker) if filters.direction=='desc' else pair>(stamp,marker))
    order=[logs.c.recorded_at,logs.c.id];order=[v.desc() for v in order] if filters.direction=='desc' else order
    rows=list(conn.execute(stmt.order_by(*order).limit(filters.limit+1)).mappings());more=len(rows)>filters.limit;rows=rows[:filters.limit]
    tags=tags_for(conn,ctx,[r['id'] for r in rows])
    cursor=cursor_encode([rows[-1]['recorded_at'].isoformat(),str(rows[-1]['id'])],fp,settings().csrf_secret) if more else None
    return {'items':[item(r,tags[r['id']]) for r in rows],'total_matching':total,'next_cursor':cursor}

def detail(conn,ctx,identifier):
    from app.models.tables import logs,recordings,fields
    role=recheck(conn,ctx);stmt,_=joined_statement()
    where=[logs.c.farm_id==ctx.farm_id,logs.c.id==identifier]
    if role!='admin':where.append(logs.c.employee_id==ctx.user_id)
    row=conn.execute(stmt.where(*where)).mappings().first()
    if not row:not_found()
    recording=conn.execute(select(recordings).where(recordings.c.farm_id==ctx.farm_id,recordings.c.id==row['recording_id'])).mappings().one()
    geometry=conn.execute(select(func.ST_AsGeoJSON(fields.c.geometry)).where(fields.c.farm_id==ctx.farm_id,fields.c.id==row['field_id'])).scalar_one_or_none() if row['field_id'] else None
    out=item(row,tags_for(conn,ctx,[identifier])[identifier]);out.update(summary=row['summary'],answers=row['answers'],
        recording={k:recording[k] for k in ('id','content_type','duration_ms','waveform_peaks','transcript','interview_version')},field_geometry=json.loads(geometry) if geometry else None)
    return out

def dashboard(conn,ctx,filters):
    from app.models.tables import logs,shifts,memberships,users,farms
    recheck(conn,ctx,admin=True)
    if filters.cursor:raise AppError(422,'INVALID_CURSOR','Use the log list endpoint to request another page.')
    stamp=now();where,fp,zone=predicates(conn,ctx,filters,'this_month',stamp);stmt,joined=joined_statement()
    start,end=range_bounds('today',zone,stamp)
    today=conn.execute(select(func.count()).select_from(logs).where(logs.c.farm_id==ctx.farm_id,logs.c.recorded_at>=start,logs.c.recorded_at<end)).scalar_one()
    scheduled=conn.execute(select(func.count(func.distinct(shifts.c.employee_id))).select_from(shifts.join(memberships,(memberships.c.user_id==shifts.c.employee_id)&(memberships.c.farm_id==shifts.c.farm_id)).join(users,users.c.id==shifts.c.employee_id)).where(shifts.c.farm_id==ctx.farm_id,shifts.c.start_at<=stamp,shifts.c.end_at>stamp,memberships.c.is_enabled.is_(True),memberships.c.role=='worker',users.c.is_enabled.is_(True))).scalar_one()
    avg,count=conn.execute(select(func.avg(logs.c.extraction_confidence),func.count(logs.c.extraction_confidence)).select_from(joined).where(*where)).one()
    # Use the same explicit default on /logs so dashboard pagination fingerprints match.
    effective=filters.model_copy(update={'range':filters.range or ('this_month' if filters.from_ is None else None)})
    return {'as_of':stamp,'timezone':zone,'metrics':{'recordings_today':today,'scheduled_workers_now':scheduled,
        'average_extraction_confidence':float(avg) if avg is not None else None,'confidence_sample_size':count},
        'metric_scopes':{'recordings_today':'farm_local_today','scheduled_workers_now':'farm_schedule_at_as_of','average_extraction_confidence':'all_matching_logs'},
        'logs':list_logs(conn,ctx,effective,'all',stamp)}
