"""Operator commands. Run with MIGRATION_DATABASE_URL, never from an HTTP route."""
import argparse
import getpass
import os
from datetime import timedelta
from uuid import UUID, uuid4
from sqlalchemy import select,delete,func
from app.config import settings
from app.db.session import transaction
from app.models.tables import farms,users,memberships,fields,activities,fertilizers,tags,shifts,recordings,logs,log_tags,sessions,rate_buckets
from app.services.primitives import PASSWORDS,password,username,timezone,now,canonical,digest


def ask_password(label='Password'): 
    value=getpass.getpass(label+': ')
    password(value)
    if value!=getpass.getpass('Repeat password: '):
        raise ValueError('Passwords do not match.')
    return value


def create_farm():
    name=input('Farm name: ').strip()
    zone=timezone(input('IANA timezone [America/Los_Angeles]: ').strip() or 'America/Los_Angeles')
    full_name=input('First admin full name: ').strip()
    login=username(input('Admin username: '))
    if not name or not full_name:
        raise ValueError('Farm and admin names are required.')
    hashed=PASSWORDS.hash(ask_password())
    fid,uid=uuid4(),uuid4()
    with transaction(operator=True) as conn:
        conn.execute(farms.insert().values(id=fid,name=name,timezone=zone))
        conn.execute(users.insert().values(id=uid,name=full_name,username=login,password_hash=hashed))
        conn.execute(memberships.insert().values(id=uuid4(),farm_id=fid,user_id=uid,role='admin'))
    print(f'Created farm {fid} and admin {login}. Log in through the frontend.')


def seed(secret):
    if settings().app_env=='production':
        raise ValueError('Development seed is prohibited in APP_ENV=production.')
    password(secret)
    hashed=PASSWORDS.hash(secret)
    stamp=now()
    with transaction(operator=True) as conn:
        if conn.execute(select(users.c.id).where(users.c.username=='demo.admin')).first():
            raise ValueError('Seed users already exist. Use a fresh development database. No records were changed.')
        for farm_index in range(2):
            fid=uuid4()
            conn.execute(farms.insert().values(id=fid,name='Bays Ranch' if farm_index==0 else 'Cedar Grove',timezone='America/Los_Angeles'))
            people=[]
            names=['Alex Morgan','Jordan Lee','Isaac Wang','Maya Patel','Liam Johnson','Sophia Lee','Noah Garcia','Emma Brooks','Olivia Chen','Ethan Davis']
            for index,name in enumerate(names):
                uid=uuid4()
                login=('demo.' if farm_index==0 else 'cedar.')+('admin' if index==0 else 'admin2' if index==1 else 'worker'+str(index-1))
                conn.execute(users.insert().values(id=uid,username=login,name=name,password_hash=hashed))
                conn.execute(memberships.insert().values(id=uuid4(),farm_id=fid,user_id=uid,role='admin' if index<2 else 'worker'))
                people.append(uid)
            field_ids=[]
            # Fictional demonstration geometry, not a claim about a real farm.
            for index in range(5):
                x,y=-93.10+(index%3)*0.012,41.20+(index//3)*0.012+farm_index*0.08
                shape={'type':'MultiPolygon','coordinates':[[[[x,y],[x+.01,y],[x+.01,y+.009],[x,y+.009],[x,y]]]]}
                identifier=uuid4(); field_ids.append(identifier)
                conn.execute(fields.insert().values(id=identifier,farm_id=fid,name='Field '+chr(65+index),
                    geometry=func.ST_GeomFromGeoJSON(__import__('json').dumps(shape))))
            catalogs=[]
            for table,values in [(activities,['Watering','Spraying','Harvesting','Planting','Irrigation','Scouting','Pruning','Soil work']),
                                 (fertilizers,['Compost','Nitrogen 28-0-0','Potassium sulfate']),
                                 (tags,['Equipment issue','Follow up','Irrigation'])]:
                identifiers=[]
                for name in values:
                    identifier=uuid4();identifiers.append(identifier)
                    conn.execute(table.insert().values(id=identifier,farm_id=fid,name=name))
                catalogs.append(identifiers)
            activity_ids,fertilizer_ids,tag_ids=catalogs
            for index in range(24):
                uid=people[2+index%8]; field=field_ids[index%5]; activity=activity_ids[index%8]
                fertilizer=fertilizer_ids[(index//3)%len(fertilizer_ids)] if index%3==0 else None
                captured=stamp-timedelta(hours=index*7)
                sid,rid,lid=uuid4(),uuid4(),uuid4()
                conn.execute(shifts.insert().values(id=sid,farm_id=fid,employee_id=uid,field_id=field,activity_id=activity,
                    fertilizer_id=fertilizer,start_at=captured-timedelta(hours=2),end_at=captured+timedelta(hours=3)))
                transcript=[{'speaker':'assistant','text':'What work did you do?','offset_ms':0},
                            {'speaker':'worker','text':'This is a fictional development report for a field inspection.','offset_ms':1200}]
                conn.execute(recordings.insert().values(id=rid,farm_id=fid,employee_id=uid,client_submission_id=uuid4(),
                    payload_hash=digest(canonical(transcript)),object_key=f'dev-fixture/{fid}/{rid}.webm',
                    object_version_id='development-fixture',content_type='audio/webm',size_bytes=1000,duration_ms=12000,
                    transcript=transcript,waveform_peaks=[(i%13+1)/18 for i in range(256)],interview_version='interview-v1',
                    recorded_at=captured,uploaded_at=captured+timedelta(seconds=15)))
                conn.execute(logs.insert().values(id=lid,farm_id=fid,employee_id=uid,recording_id=rid,shift_id=sid,
                    field_id=field,activity_id=activity,fertilizer_id=fertilizer,summary='Fictional development report. Inspected the assigned field and reported a small irrigation leak near the north boundary.',
                    answers={'details':'Development fixture, not actual employee work.','issues':'Example irrigation leak.'},
                    extraction_confidence=.84+(index%12)/100,extractor_model='development-fixture',extraction_version='extraction-v1',
                    submission_hash=digest(canonical({'recording_id':rid,'shift_id':sid})),recorded_at=captured))
                if index%3==0:
                    conn.execute(log_tags.insert().values(farm_id=fid,log_id=lid,tag_id=tag_ids[(index//3)%len(tag_ids)]))
    print('Seeded two fictional farms, 20 users, 10 fields, catalogs, schedules, and 48 reports.')
    print('Admin: demo.admin. Worker: demo.worker1. Password is the value you supplied. Fixture audio is intentionally unavailable.')


def attach_user():
    uid=UUID(input('Existing user UUID: '));fid=UUID(input('Farm UUID: '));role=input('Role (admin/worker): ').strip()
    if role not in ('admin','worker'):
        raise ValueError('Invalid role.')
    with transaction(operator=True) as conn:
        conn.execute(select(users.c.id).where(users.c.id==uid).with_for_update()).scalar_one()
        conn.execute(memberships.insert().values(id=uuid4(),farm_id=fid,user_id=uid,role=role))
    print('Membership created.')


def reset_password():
    login=username(input('Existing username: '));hashed=PASSWORDS.hash(ask_password('New temporary password'))
    with transaction(operator=True) as conn:
        uid=conn.execute(select(users.c.id).where(users.c.username==login).with_for_update()).scalar_one()
        conn.execute(users.update().where(users.c.id==uid).values(password_hash=hashed,must_change_password=True,updated_at=now()))
        conn.execute(delete(sessions).where(sessions.c.user_id==uid))
    print('Password reset; old sessions revoked. The user must change the temporary password.')


def maintenance(apply):
    cutoff=now()
    with transaction(operator=True) as conn:
        for table,predicate in [(sessions,sessions.c.expires_at<cutoff),(rate_buckets,rate_buckets.c.expires_at<cutoff),
            (recordings,(recordings.c.uploaded_at.is_(None))&(recordings.c.created_at<cutoff-timedelta(days=30)))]:
            count=conn.execute(select(func.count()).select_from(table).where(predicate)).scalar_one()
            print(f'{table.name}: {count} eligible rows; '+('delete' if apply else 'dry run'))
            if apply:
                conn.execute(delete(table).where(predicate))
    print('Confirmed recording metadata and all S3 audio remain untouched. Unconfirmed storage cleanup is an explicit operator task.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['create-farm','seed','attach-user','reset-password','maintenance'])
    parser.add_argument('--apply',action='store_true',help='Apply maintenance deletions.')
    parser.add_argument('--dry-run',action='store_true',help='Preview maintenance; the default.')
    args=parser.parse_args()
    try:
        if args.command=='create-farm':create_farm()
        elif args.command=='seed':seed(os.getenv('SEED_PASSWORD') or ask_password('Development seed password'))
        elif args.command=='attach-user':attach_user()
        elif args.command=='reset-password':reset_password()
        else:maintenance(args.apply and not args.dry_run)
    except Exception as exc:
        # Avoid exposing connection strings and database errors that may contain credentials.
        if isinstance(exc,ValueError):
            parser.exit(1,str(exc)+'\n')
        parser.exit(1,f'Command failed ({type(exc).__name__}). Check operator configuration and database constraints.\n')

if __name__=='__main__':
    main()
