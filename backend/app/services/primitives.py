import base64
import calendar
import hashlib
import hmac
import json
import math
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from argon2 import PasswordHasher
from app.errors import AppError

PASSWORDS=PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1)

def now(): return datetime.now(dt_timezone.utc)

def username(value):
    value=value.strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,39}',value):
        raise ValueError('Username must have 3-40 lowercase letters, digits, dots, underscores, or hyphens.')
    return value

def password(value):
    if not isinstance(value,str) or not 12<=len(value)<=128:
        raise ValueError('Password must contain 12-128 characters.')
    return value

def timezone(value):
    try: ZoneInfo(value)
    except (ZoneInfoNotFoundError,ValueError,TypeError) as exc:
        raise ValueError('Use a valid IANA timezone, such as America/Los_Angeles.') from exc
    return value

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=lambda v:v.isoformat() if isinstance(v,datetime) else str(v))

def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def mac(secret,value): return hmac.new(secret.encode(),value.encode(),hashlib.sha256).hexdigest()

def cursor_encode(values,fingerprint,secret):
    payload=base64.urlsafe_b64encode(canonical({'v':1,'values':values,'fp':digest(canonical(fingerprint))}).encode()).decode().rstrip('=')
    return payload+'.'+mac(secret,payload)

def cursor_decode(value,fingerprint,secret):
    try:
        if not value or len(value)>3000: raise ValueError()
        payload,signature=value.split('.')
        if not hmac.compare_digest(mac(secret,payload),signature): raise ValueError()
        parsed=json.loads(base64.b64decode(payload+'='*(-len(payload)%4),altchars=b'-_',validate=True))
        if parsed['v']!=1 or parsed['fp']!=digest(canonical(fingerprint)): raise ValueError()
        if not isinstance(parsed['values'],list): raise ValueError()
        return parsed['values']
    except (ValueError,KeyError,TypeError,UnicodeDecodeError) as exc:
        raise AppError(422,'INVALID_CURSOR','This pagination cursor is invalid or belongs to different filters. Start from the first page.') from exc

def range_bounds(preset,zone,as_of=None):
    stamp=as_of or now(); local=stamp.astimezone(ZoneInfo(zone))
    today=local.replace(hour=0,minute=0,second=0,microsecond=0)
    if preset=='all': return None,None
    if preset=='last_day': return stamp-timedelta(hours=24),stamp
    if preset=='last_week': return stamp-timedelta(days=7),stamp
    if preset=='last_month': return stamp-timedelta(days=30),stamp
    if preset=='today': start,end=today,today+timedelta(days=1)
    elif preset=='this_week':
        start=today-timedelta(days=today.weekday());end=start+timedelta(days=7)
    elif preset=='this_month':
        start=today.replace(day=1)
        end=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
    else: raise AppError(422,'INVALID_RANGE','Choose a supported date range.')
    return start.astimezone(dt_timezone.utc),end.astimezone(dt_timezone.utc)

def validate_geometry(geometry):
    """Validate GeoJSON structure; PostGIS also checks polygon topology on write."""
    if not isinstance(geometry,dict) or set(geometry)-{'type','coordinates'}:
        raise ValueError('Supply a GeoJSON geometry with type and coordinates.')
    kind=geometry.get('type'); coords=geometry.get('coordinates')
    if kind not in ('Polygon','MultiPolygon') or not isinstance(coords,list) or not coords:
        raise ValueError('A nonempty Polygon or MultiPolygon is required.')
    polys=[coords] if kind=='Polygon' else coords
    count=0
    for poly in polys:
        if not isinstance(poly,list) or not poly: raise ValueError('Polygon needs at least one ring.')
        for ring in poly:
            if not isinstance(ring,list) or len(ring)<4 or ring[0]!=ring[-1]: raise ValueError('Each ring needs at least four positions and must be closed.')
            for point in ring:
                if not isinstance(point,list) or len(point)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in point):
                    raise ValueError('Use finite, two-dimensional longitude/latitude positions.')
                if not -180<=point[0]<=180 or not -90<=point[1]<=90: raise ValueError('Coordinates are outside WGS84 bounds.')
                count+=1
    if count>1000: raise ValueError('At most 1,000 positions are allowed per field.')
    return {'type':'MultiPolygon','coordinates':polys}
