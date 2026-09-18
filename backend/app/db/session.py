from contextlib import contextmanager
from functools import lru_cache
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.config import settings
from app.errors import missing_config, AppError

@lru_cache(maxsize=2)
def engine(operator=False):
    cfg=settings()
    url=cfg.migration_database_url if operator else cfg.database_url
    missing_config(**{'MIGRATION_DATABASE_URL' if operator else 'DATABASE_URL':url})
    parsed=make_url(url)
    if parsed.drivername not in ('postgres','postgresql','postgresql+psycopg'):
        raise AppError(503,'DATABASE_CONFIGURATION','Use a PostgreSQL connection URL.')
    parsed=parsed.set(drivername='postgresql+psycopg')
    args={'prepare_threshold':None,'connect_timeout':8}
    if cfg.app_env in ('production','preview'):
        ssl=parsed.query.get('sslmode','require')
        if ssl not in ('require','verify-ca','verify-full'):
            raise AppError(503,'DATABASE_CONFIGURATION','Production database connections must use TLS.')
        parsed=parsed.update_query_dict({'sslmode':ssl})
    return create_engine(parsed,connect_args=args,pool_size=cfg.db_pool_size,max_overflow=0,pool_timeout=8,pool_pre_ping=True,pool_recycle=300,hide_parameters=True)

@contextmanager
def transaction(operator=False):
    with engine(operator).begin() as conn:
        # SET LOCAL survives only this transaction, including in a transaction pooler.
        schema=settings().postgis_schema
        conn.execute(text(f'SET LOCAL search_path TO farm_app, "{schema}", public'))
        conn.execute(text("SET LOCAL statement_timeout = '12000ms'"))
        conn.execute(text("SET LOCAL lock_timeout = '5000ms'"))
        yield conn
