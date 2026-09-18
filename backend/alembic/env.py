"""Explicit operator migration connection. Never runs at application startup."""
from alembic import context
from sqlalchemy import create_engine,pool,text
from sqlalchemy.engine import make_url
from app.config import settings
from app.models.tables import metadata

cfg=settings()
if not cfg.migration_database_url:
    raise RuntimeError('Set MIGRATION_DATABASE_URL to the migration-capable direct or session-pooler URL.')
url=make_url(cfg.migration_database_url).set(drivername='postgresql+psycopg')
if cfg.app_env in ('preview','production') and url.query.get('sslmode') not in ('require','verify-ca','verify-full'):
    raise RuntimeError('Migration connections require encrypted PostgreSQL in deployed environments.')
if context.is_offline_mode():
    raise RuntimeError('This spatial initialization requires an online PostGIS-capable migration connection. Use alembic upgrade head.')
engine=create_engine(url,poolclass=pool.NullPool,connect_args={'prepare_threshold':None,'connect_timeout':10},hide_parameters=True)
with engine.connect() as connection:
    # farm_app holds the version table too, outside the Supabase public Data API schema.
    connection.execute(text('CREATE SCHEMA IF NOT EXISTS farm_app'))
    connection.commit()
    context.configure(connection=connection,target_metadata=metadata,include_schemas=True,version_table_schema='farm_app',compare_type=True)
    with context.begin_transaction():context.run_migrations()
engine.dispose()
