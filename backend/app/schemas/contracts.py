from datetime import datetime, timedelta
from typing import Annotated, Generic, Literal, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, field_validator, model_validator
from app.services.primitives import username,password,timezone,validate_geometry,now

class Model(BaseModel):
    model_config=ConfigDict(extra='forbid')

Name=Annotated[str,Field(min_length=1,max_length=120)]
CatalogName=Annotated[str,Field(min_length=1,max_length=100)]
class Named(Model):
    id:UUID
    name:str
class Farm(Named):
    timezone:str
    created_at:datetime
    updated_at:datetime
class User(Named):
    username:str
    must_change_password:bool
class Membership(Model):
    id:UUID
    role:Literal['admin','worker']
    is_enabled:bool
    farm:Farm
class AuthResult(Model):
    user:User
    memberships:list[Membership]
    csrf_token:str
    must_change_password:bool
class LoginInput(Model):
    username:str=Field(min_length=1,max_length=40)
    password:str=Field(min_length=1,max_length=128)
    @field_validator('username')
    @classmethod
    def login_name(cls,v): return username(v)
class PasswordChange(Model):
    current_password:str=Field(min_length=1,max_length=128)
    new_password:str=Field(min_length=12,max_length=128)
class FarmUpdate(Model):
    name:Name|None=None
    timezone:str|None=None
    @field_validator('name')
    @classmethod
    def nonblank(cls,v):
        if v is not None and not v.strip(): raise ValueError('Name is required.')
        return v.strip() if v else v
    @field_validator('timezone')
    @classmethod
    def valid_zone(cls,v): return timezone(v) if v is not None else v
    @model_validator(mode='after')
    def changed(self):
        if not self.model_fields_set or any(getattr(self,k) is None for k in self.model_fields_set): raise ValueError('Provide a non-null update.')
        return self
class CatalogInput(Model):
    name:CatalogName
    @field_validator('name')
    @classmethod
    def clean(cls,v):
        if not v.strip():raise ValueError('A name is required.')
        return v.strip()
class TagInput(CatalogInput):
    name:str=Field(min_length=1,max_length=80)
class FieldInput(Model):
    name:Name
    geometry:dict
    @field_validator('geometry')
    @classmethod
    def valid_geometry(cls,v):return validate_geometry(v)
    @field_validator('name')
    @classmethod
    def clean(cls,v):
        if not v.strip():raise ValueError('A field name is required.')
        return v.strip()
class FieldUpdate(Model):
    name:Name|None=None
    geometry:dict|None=None
    @field_validator('geometry')
    @classmethod
    def valid_geometry(cls,v):return validate_geometry(v) if v is not None else v
    @field_validator('name')
    @classmethod
    def clean(cls,v):
        if v is not None and not v.strip(): raise ValueError('A field name is required.')
        return v.strip() if v else v
    @model_validator(mode='after')
    def changed(self):
        if not self.model_fields_set or any(getattr(self,k) is None for k in self.model_fields_set):raise ValueError('Provide a non-null update.')
        return self
class FieldDetail(Named):
    geometry:dict
    created_at:datetime
    updated_at:datetime
class GeoCollection(Model):
    type:Literal['FeatureCollection']='FeatureCollection'
    features:list[dict]
    farm_bbox:list[float]|None
    next_cursor:str|None
class Member(Model):
    id:UUID
    user_id:UUID
    name:str
    username:str
    role:Literal['admin','worker']
    is_enabled:bool
class MemberInput(Model):
    name:Name
    username:str
    role:Literal['admin','worker']='worker'
    @field_validator('username')
    @classmethod
    def clean_username(cls,v):return username(v)
    @field_validator('name')
    @classmethod
    def clean_name(cls,v):
        if not v.strip():raise ValueError('Name is required.')
        return v.strip()
class MemberCreated(Model):
    member:Member
    temporary_password:str
class MemberUpdate(Model):
    role:Literal['admin','worker']|None=None
    is_enabled:bool|None=None
    @model_validator(mode='after')
    def changed(self):
        if not self.model_fields_set or any(getattr(self,k) is None for k in self.model_fields_set):raise ValueError('Provide a non-null update.')
        return self
class PasswordReset(Model):
    temporary_password:str
    must_change_password:Literal[True]=True
class ShiftInput(Model):
    employee_id:UUID
    start_at:AwareDatetime
    end_at:AwareDatetime
    field_id:UUID|None=None
    activity_id:UUID|None=None
    fertilizer_id:UUID|None=None
    @model_validator(mode='after')
    def ordered(self):
        if self.end_at<=self.start_at:raise ValueError('End time must follow start time.')
        return self
class ShiftUpdate(Model):
    employee_id:UUID|None=None
    start_at:AwareDatetime|None=None
    end_at:AwareDatetime|None=None
    field_id:UUID|None=None
    activity_id:UUID|None=None
    fertilizer_id:UUID|None=None
    @model_validator(mode='after')
    def changed(self):
        if not self.model_fields_set:raise ValueError('Provide an update.')
        if any(getattr(self,k) is None for k in ('employee_id','start_at','end_at') if k in self.model_fields_set):raise ValueError('Employee and times cannot be null.')
        if self.start_at and self.end_at and self.end_at<=self.start_at:raise ValueError('End time must follow start time.')
        return self
class Shift(Model):
    id:UUID
    employee:Named
    start_at:datetime
    end_at:datetime
    field:Named|None
    activity:Named|None
    fertilizer:Named|None
class ShiftSummary(Model):
    id:UUID
    start_at:datetime
    end_at:datetime
class Turn(Model):
    speaker:Literal['assistant','worker']
    text:str=Field(min_length=1,max_length=16000)
    offset_ms:int=Field(ge=0,le=600000)
    @field_validator('text')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():raise ValueError('Empty transcript turn.')
        return v
class RecordingInput(Model):
    client_submission_id:UUID
    content_type:Literal['audio/webm','audio/mp4','audio/ogg']
    size_bytes:int=Field(gt=0,le=26214400)
    duration_ms:int=Field(gt=0,le=600000)
    recorded_at:AwareDatetime
    interview_version:Literal['interview-v1']
    transcript:list[Turn]=Field(min_length=1,max_length=500)
    waveform_peaks:list[Annotated[float,Field(ge=0,le=1,allow_inf_nan=False)]]|None=Field(default=None,max_length=512)
    @model_validator(mode='after')
    def valid_recording(self):
        if not any(t.speaker=='worker' for t in self.transcript):raise ValueError('A worker transcript is required.')
        if any(t.offset_ms>self.duration_ms for t in self.transcript):raise ValueError('Transcript offset exceeds recording duration.')
        if self.recorded_at>now()+timedelta(minutes=5):raise ValueError('Recording time is too far in the future.')
        if self.recorded_at<now()-timedelta(days=365):raise ValueError('Recording is over one year old.')
        return self
class RecordingReceipt(Model):
    id:UUID
    recorded_at:datetime
    uploaded_at:datetime|None
    linked_log_id:UUID|None
class RecordingDetail(RecordingReceipt):
    content_type:str
    size_bytes:int
    duration_ms:int
    transcript:list[Turn]
    waveform_peaks:list[float]|None
    interview_version:str
class UploadAuthorization(Model):
    url:str
    method:Literal['POST']='POST'
    fields:dict[str,str]
    expires_at:datetime
    max_size_bytes:int
class AudioAuthorization(Model):
    url:str
    expires_at:datetime
    content_type:str
    duration_ms:int
class LogCreate(Model):
    recording_id:UUID
    shift_id:UUID|None # Explicit null is meaningful for idempotency.
class Answers(Model):
    details:str|None
    issues:str|None
class Extraction(Model):
    summary:str=Field(min_length=1,max_length=10000)
    field_id:str|None
    activity_id:str|None
    fertilizer_id:str|None
    answers:Answers
    extraction_confidence:float|None=Field(ge=0,le=1,allow_inf_nan=False)
    @field_validator('summary')
    @classmethod
    def nonblank(cls,v):
        if not v.strip():raise ValueError('Summary is empty.')
        return v.strip()
class RecordingView(Model):
    id:UUID
    content_type:str
    duration_ms:int
    waveform_peaks:list[float]|None
    transcript:list[Turn]
    interview_version:str
class LogItem(Model):
    id:UUID
    recorded_at:datetime
    employee:Named
    activity:Named|None
    fertilizer:Named|None
    field:Named|None
    scheduled_shift:ShiftSummary|None
    summary_preview:str
    extraction_confidence:float|None
    tags:list[Named]
class LogDetail(LogItem):
    summary:str
    answers:Answers
    recording:RecordingView
    field_geometry:dict|None
T=TypeVar('T')
class Page(Model,Generic[T]):
    items:list[T]
    total_matching:int
    next_cursor:str|None
class LogFilters(Model):
    range:Literal['today','this_week','this_month','all','last_day','last_week','last_month']|None=None
    from_:AwareDatetime|None=Field(default=None,alias='from')
    to:AwareDatetime|None=None
    employee_id:UUID|None=None
    field_id:UUID|None=None
    activity_id:UUID|None=None
    fertilizer_id:UUID|None=None
    tag_id:UUID|None=None
    q:str=Field(default='',max_length=200)
    sort:Literal['recorded_at']='recorded_at'
    direction:Literal['asc','desc']='desc'
    limit:int=Field(25,ge=1,le=100)
    cursor:str|None=Field(default=None,max_length=3000)
    @model_validator(mode='after')
    def dates(self):
        if (self.from_ is None)!=(self.to is None):raise ValueError('Both from and to are required.')
        if self.range and self.from_ is not None:raise ValueError('Use a preset or explicit dates, not both.')
        if self.from_ is not None and self.from_>=self.to:raise ValueError('End must follow start.')
        return self
class DashboardMetrics(Model):
    recordings_today:int
    scheduled_workers_now:int
    average_extraction_confidence:float|None
    confidence_sample_size:int
class DashboardResult(Model):
    as_of:datetime
    timezone:str
    metrics:DashboardMetrics
    metric_scopes:dict[str,str]
    logs:Page[LogItem]
class Bootstrap(Model):
    user:User
    farm:Farm
    membership:Member
    fields:list[Named]
    activities:list[Named]
    fertilizers:list[Named]
    shifts:list[Shift]
    workers:list[Named]
    tags:list[Named]
class RealtimeInput(Model):
    shift_id:UUID|None=None
class RealtimeSecret(Model):
    client_secret:str
    expires_at:int
    model:str
    interview_version:str
