"""Initial, frozen v1 schema. This snapshot must never be imported from live models."""
from alembic import op
from sqlalchemy import text
from app.config import settings
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None
"""The complete relational model; SQLAlchemy Core avoids accidental ORM serialization."""
from sqlalchemy import (MetaData, Table, Column, String, Text, Boolean, DateTime, Integer, BigInteger,
                        Numeric, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Index, func)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry

metadata = MetaData(schema='farm_app', naming_convention={
    'ix': 'ix_%(table_name)s_%(column_0_name)s', 'uq': 'uq_%(table_name)s_%(column_0_N_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s', 'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s'})


def ident():
    return Column('id', UUID(as_uuid=True), primary_key=True)


def farm_id():
    return Column('farm_id', UUID(as_uuid=True), ForeignKey('farms.id'), nullable=False)


def timestamps(updated=True):
    cols = [Column('created_at', DateTime(timezone=True), nullable=False, server_default=func.now())]
    if updated:
        cols.append(Column('updated_at', DateTime(timezone=True), nullable=False, server_default=func.now()))
    return cols


farms = Table('farms', metadata, ident(), Column('name', String(120), nullable=False),
              Column('timezone', String(100), nullable=False), *timestamps(),
              CheckConstraint("length(trim(name)) > 0", name='name_nonblank'))
users = Table('users', metadata, ident(), Column('username', String(40), nullable=False, unique=True),
              Column('name', String(120), nullable=False), Column('password_hash', Text, nullable=False),
              Column('must_change_password', Boolean, nullable=False, server_default='false'),
              Column('is_enabled', Boolean, nullable=False, server_default='true'), *timestamps(),
              CheckConstraint("username ~ '^[a-z0-9][a-z0-9._-]{2,39}$'", name='username_format'),
              CheckConstraint('length(trim(name)) > 0', name='name_nonblank'))
memberships = Table('farm_memberships', metadata, ident(), farm_id(),
                    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), nullable=False),
                    Column('role', String(10), nullable=False),
                    Column('is_enabled', Boolean, nullable=False, server_default='true'), *timestamps(),
                    UniqueConstraint('farm_id', 'user_id'), UniqueConstraint('farm_id', 'id'),
                    CheckConstraint("role IN ('admin','worker')", name='role'))
Index('ix_memberships_user', memberships.c.user_id)
sessions = Table('auth_sessions', metadata, ident(),
                 Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), nullable=False),
                 Column('token_hash', String(64), nullable=False, unique=True), *timestamps(False),
                 Column('expires_at', DateTime(timezone=True), nullable=False),
                 CheckConstraint('expires_at > created_at', name='expiry'))
Index('ix_sessions_user', sessions.c.user_id)
Index('ix_sessions_expiry', sessions.c.expires_at)
fields = Table('fields', metadata, ident(), farm_id(), Column('name', String(120), nullable=False),
               Column('geometry', Geometry('MULTIPOLYGON', srid=4326, spatial_index=True), nullable=False),
               *timestamps(), UniqueConstraint('farm_id', 'id'),
               CheckConstraint('length(trim(name)) > 0', name='name_nonblank'),
               CheckConstraint('NOT ST_IsEmpty(geometry) AND ST_IsValid(geometry)', name='valid_geometry'),
               CheckConstraint('ST_NDims(geometry)=2 AND ST_SRID(geometry)=4326 AND ST_NPoints(geometry)<=1000', name='geometry_size'),
               CheckConstraint('ST_XMin(Box3D(geometry)) >= -180 AND ST_XMax(Box3D(geometry)) <= 180 '
                               'AND ST_YMin(Box3D(geometry)) >= -90 AND ST_YMax(Box3D(geometry)) <= 90', name='bounds'))


def catalog(name, length=100, updated=True):
    table = Table(name, metadata, ident(), farm_id(), Column('name', String(length), nullable=False),
                  *timestamps(updated), UniqueConstraint('farm_id', 'id'),
                  CheckConstraint('length(trim(name)) > 0', name='name_nonblank'))
    Index(f'uq_{name}_farm_name', table.c.farm_id, func.lower(table.c.name), unique=True)
    return table


Index('uq_fields_farm_name', fields.c.farm_id, func.lower(fields.c.name), unique=True)
activities = catalog('activities')
fertilizers = catalog('fertilizers')
tags = catalog('tags', 80, False)


def activity_refs():
    return [Column('field_id', UUID(as_uuid=True)), Column('activity_id', UUID(as_uuid=True)),
            Column('fertilizer_id', UUID(as_uuid=True)),
            ForeignKeyConstraint(['farm_id','field_id'], ['fields.farm_id','fields.id']),
            ForeignKeyConstraint(['farm_id','activity_id'], ['activities.farm_id','activities.id']),
            ForeignKeyConstraint(['farm_id','fertilizer_id'], ['fertilizers.farm_id','fertilizers.id'])]


shifts = Table('shifts', metadata, ident(), farm_id(), Column('employee_id', UUID(as_uuid=True), nullable=False),
               *activity_refs(), Column('start_at', DateTime(timezone=True), nullable=False),
               Column('end_at', DateTime(timezone=True), nullable=False), *timestamps(),
               UniqueConstraint('farm_id','id'), UniqueConstraint('farm_id','id','employee_id'),
               ForeignKeyConstraint(['farm_id','employee_id'], ['farm_memberships.farm_id','farm_memberships.user_id']),
               CheckConstraint('end_at > start_at', name='time_order'))
Index('ix_shifts_employee_time', shifts.c.farm_id, shifts.c.employee_id, shifts.c.start_at, shifts.c.end_at)
recordings = Table('recordings', metadata, ident(), farm_id(), Column('employee_id', UUID(as_uuid=True), nullable=False),
                   Column('client_submission_id', UUID(as_uuid=True), nullable=False),
                   Column('payload_hash', String(64), nullable=False), Column('object_key', Text, nullable=False, unique=True),
                   Column('object_version_id', Text), Column('content_type', String(100), nullable=False),
                   Column('size_bytes', BigInteger, nullable=False), Column('duration_ms', Integer, nullable=False),
                   Column('transcript', JSONB, nullable=False), Column('waveform_peaks', JSONB(none_as_null=True)),
                   Column('interview_version', String(40), nullable=False),
                   Column('recorded_at', DateTime(timezone=True), nullable=False),
                   Column('uploaded_at', DateTime(timezone=True)), *timestamps(False),
                   UniqueConstraint('farm_id','id'), UniqueConstraint('farm_id','id','employee_id'),
                   UniqueConstraint('farm_id','employee_id','client_submission_id'),
                   ForeignKeyConstraint(['farm_id','employee_id'], ['farm_memberships.farm_id','farm_memberships.user_id']),
                   CheckConstraint('size_bytes > 0 AND size_bytes <= 26214400', name='size'),
                   CheckConstraint('duration_ms > 0 AND duration_ms <= 600000', name='duration'),
                   CheckConstraint("jsonb_typeof(transcript)='array' AND jsonb_array_length(transcript)>0", name='transcript'),
                   CheckConstraint("waveform_peaks IS NULL OR (jsonb_typeof(waveform_peaks)='array' AND jsonb_array_length(waveform_peaks)<=512)", name='peaks'),
                   CheckConstraint('(uploaded_at IS NULL) = (object_version_id IS NULL)', name='upload_receipt'))
Index('ix_recordings_farm_time', recordings.c.farm_id, recordings.c.recorded_at)
logs = Table('logs', metadata, ident(), farm_id(), Column('employee_id', UUID(as_uuid=True), nullable=False),
             Column('recording_id', UUID(as_uuid=True), nullable=False, unique=True), Column('shift_id', UUID(as_uuid=True)),
             *activity_refs(), Column('summary', Text, nullable=False), Column('answers', JSONB, nullable=False),
             Column('extraction_confidence', Numeric(5,4)), Column('extractor_model', String(100), nullable=False),
             Column('extraction_version', String(40), nullable=False), Column('submission_hash', String(64), nullable=False),
             Column('recorded_at', DateTime(timezone=True), nullable=False), *timestamps(False),
             UniqueConstraint('farm_id','id'),
             ForeignKeyConstraint(['farm_id','employee_id'], ['farm_memberships.farm_id','farm_memberships.user_id']),
             ForeignKeyConstraint(['farm_id','recording_id','employee_id'], ['recordings.farm_id','recordings.id','recordings.employee_id']),
             ForeignKeyConstraint(['farm_id','shift_id','employee_id'], ['shifts.farm_id','shifts.id','shifts.employee_id']),
             CheckConstraint('length(trim(summary))>0', name='summary_nonblank'),
             CheckConstraint('extraction_confidence IS NULL OR (extraction_confidence>=0 AND extraction_confidence<=1)', name='confidence'))
for name in ('employee_id','field_id','activity_id','fertilizer_id'):
    Index(f'ix_logs_farm_{name}_time', logs.c.farm_id, logs.c[name], logs.c.recorded_at.desc(), logs.c.id.desc())
Index('ix_logs_farm_time', logs.c.farm_id, logs.c.recorded_at.desc(), logs.c.id.desc())
log_tags = Table('log_tags', metadata, Column('farm_id', UUID(as_uuid=True), primary_key=True),
                 Column('log_id', UUID(as_uuid=True), primary_key=True), Column('tag_id', UUID(as_uuid=True), primary_key=True),
                 *timestamps(False), ForeignKeyConstraint(['farm_id','log_id'], ['logs.farm_id','logs.id']),
                 ForeignKeyConstraint(['farm_id','tag_id'], ['tags.farm_id','tags.id']))
Index('ix_log_tags_reverse', log_tags.c.farm_id, log_tags.c.tag_id, log_tags.c.log_id)
rate_buckets = Table('rate_limit_buckets', metadata, Column('key_hash', String(64), primary_key=True),
                     Column('bucket_start', DateTime(timezone=True), primary_key=True),
                     Column('request_count', Integer, nullable=False), Column('expires_at', DateTime(timezone=True), nullable=False),
                     CheckConstraint('request_count >= 1', name='positive_count'))
Index('ix_rate_buckets_expiry', rate_buckets.c.expires_at)


def upgrade():
    bind = op.get_bind()
    schema = settings().postgis_schema
    bind.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    bind.execute(text(f'CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA "{schema}"'))
    actual = bind.execute(text("SELECT n.nspname FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='postgis'")).scalar_one()
    if actual != schema:
        raise RuntimeError(f'PostGIS is installed in {actual}; set POSTGIS_SCHEMA to that schema and rerun.')
    bind.execute(text('CREATE SCHEMA IF NOT EXISTS farm_app'))
    bind.execute(text(f'SET LOCAL search_path TO farm_app, "{schema}", public'))
    metadata.create_all(bind=bind)
    bind.execute(text("REVOKE ALL ON SCHEMA farm_app FROM PUBLIC"))
    bind.execute(text("REVOKE ALL ON ALL TABLES IN SCHEMA farm_app FROM PUBLIC"))
    bind.execute(text("""
    DO $$ DECLARE r text; BEGIN
      FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
          EXECUTE format('REVOKE ALL ON SCHEMA farm_app FROM %I',r);
          EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA farm_app FROM %I',r);
        END IF;
      END LOOP;
    END $$;
    """))
    bind.execute(text("""
    CREATE FUNCTION farm_app.freeze_recording() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (to_jsonb(NEW)-'uploaded_at'-'object_version_id') IS DISTINCT FROM
         (to_jsonb(OLD)-'uploaded_at'-'object_version_id') THEN
        RAISE EXCEPTION 'Recording metadata is immutable' USING ERRCODE='23514';
      END IF;
      IF OLD.uploaded_at IS NOT NULL AND (NEW.uploaded_at IS DISTINCT FROM OLD.uploaded_at
          OR NEW.object_version_id IS DISTINCT FROM OLD.object_version_id) THEN
        RAISE EXCEPTION 'Recording version is immutable' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER freeze_recording_before_update BEFORE UPDATE ON farm_app.recordings
      FOR EACH ROW EXECUTE FUNCTION farm_app.freeze_recording();
    """))


def downgrade():
    bind = op.get_bind()
    bind.execute(text('DROP TRIGGER IF EXISTS freeze_recording_before_update ON farm_app.recordings'))
    bind.execute(text('DROP FUNCTION IF EXISTS farm_app.freeze_recording()'))
    metadata.drop_all(bind=bind)
