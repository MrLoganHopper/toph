"""Create/rotate one restricted database login after migrations. No password is printed."""
from pathlib import Path
import getpass,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import settings
from app.db.session import engine
from psycopg import sql
secret=getpass.getpass('New toph_runtime database password (at least 24 characters): ')
if len(secret)<24:sys.exit('Use a unique random password of at least 24 characters.')
if secret!=getpass.getpass('Repeat password: '):sys.exit('Passwords differ.')
cfg=settings()
with engine(operator=True).connect() as conn:
    raw=conn.connection.driver_connection
    with raw.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_namespace WHERE nspname='farm_app'")
        if not cursor.fetchone():sys.exit('Run Alembic migrations first.')
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='toph_runtime'")
        if not cursor.fetchone():cursor.execute('CREATE ROLE toph_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION')
        cursor.execute('ALTER ROLE toph_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT')
        cursor.execute("SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='toph_runtime')")
        if cursor.fetchone():sys.exit('The runtime role belongs to another database role. Remove unintended inherited/SET ROLE privileges before using it.')
        cursor.execute(sql.SQL('ALTER ROLE toph_runtime PASSWORD {}').format(sql.Literal(secret)))
        cursor.execute('GRANT USAGE ON SCHEMA farm_app TO toph_runtime')
        cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO toph_runtime').format(sql.Identifier(cfg.postgis_schema)))
        cursor.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA farm_app TO toph_runtime')
        cursor.execute('REVOKE ALL ON TABLE farm_app.alembic_version FROM toph_runtime')
    conn.commit()
print('Restricted role configured. Use its password only in the backend runtime database URL. Keep migration credentials separate.')
