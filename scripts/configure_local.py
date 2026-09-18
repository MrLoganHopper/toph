"""Create local-only environment files. Existing files are never overwritten."""
from pathlib import Path
from urllib.parse import quote
import argparse,getpass,json,secrets,sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--managed',action='store_true',help='Prompt for a development PostgreSQL provider instead of local Docker.')
args=parser.parse_args()
paths=[ROOT/'backend/.env',ROOT/'frontend/.env']+([] if args.managed else [ROOT/'.env'])
existing=[str(p.relative_to(ROOT)) for p in paths if p.exists()]
if existing:sys.exit('Refusing to overwrite: '+', '.join(existing)+'. Edit those files directly or back them up first.')
if args.managed:
    db=getpass.getpass('Development runtime transaction-pooler URL (hidden): ').strip()
    migration=getpass.getpass('Development migration direct/session URL (hidden): ').strip()
    if not db.startswith(('postgresql://','postgresql+psycopg://')) or not migration.startswith(('postgresql://','postgresql+psycopg://')):sys.exit('Use PostgreSQL connection URLs copied from your provider.')
    schema=input('Installed PostGIS schema [public]: ').strip() or 'public'
else:
    password=secrets.token_urlsafe(32)
    db=migration=f'postgresql+psycopg://postgres:{quote(password,safe="")}@localhost:5432/toph'
    schema='public';(ROOT/'.env').write_text('POSTGRES_PASSWORD='+password+'\n')
backend=(ROOT/'backend/.env.example').read_text()
values={'APP_ENV':'development','DATABASE_URL':db,'MIGRATION_DATABASE_URL':migration,'POSTGIS_SCHEMA':schema,
 'COOKIE_SECURE':'false','CSRF_SECRET':secrets.token_urlsafe(48),'RATE_LIMIT_SECRET':secrets.token_urlsafe(48),
 'APP_ORIGINS':json.dumps(['http://localhost:5173','http://127.0.0.1:5173'])}
lines=[]
for line in backend.splitlines():
    key=line.split('=',1)[0]
    lines.append(key+'='+values[key] if key in values else line)
(ROOT/'backend/.env').write_text('\n'.join(lines)+'\n')
(ROOT/'frontend/.env').write_text((ROOT/'frontend/.env.example').read_text())
for p in paths:
    try:p.chmod(0o600)
    except OSError:pass
print('Local .env files created. Credentials were not printed. Add provider keys to backend/.env and your map style to frontend/.env.')
