"""DESTRUCTIVE: reset farm_app only in an explicitly authorized disposable *_test DB."""
import os,sys
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
value=os.environ.get('TEST_DATABASE_URL')
if not value or os.environ.get('TOPH_TEST_RESET')!='YES':
    sys.exit('Set TEST_DATABASE_URL and TOPH_TEST_RESET=YES for an isolated test database.')
url=make_url(value)
if not (url.database or '').endswith('_test'):
    sys.exit('Refusing to reset: the database name must end in _test.')
# This script intentionally does not use a production/default DATABASE_URL.
engine=create_engine(url.set(drivername='postgresql+psycopg'),connect_args={'prepare_threshold':None},hide_parameters=True)
with engine.begin() as conn:conn.execute(text('DROP SCHEMA IF EXISTS farm_app CASCADE'))
engine.dispose()
print('Disposable test application schema reset.')
