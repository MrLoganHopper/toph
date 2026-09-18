"""Read-only application smoke test through the real frontend origin."""
from urllib.parse import urlsplit
import argparse,getpass,sys
import httpx
p=argparse.ArgumentParser(description=__doc__);p.add_argument('origin');a=p.parse_args();origin=a.origin.rstrip('/')
url=urlsplit(origin)
if url.scheme not in ('http','https') or not url.netloc or url.path:sys.exit('Supply the frontend origin, without a path.')
username=input('Administrator username: ');password=getpass.getpass('Password: ')
with httpx.Client(base_url=origin,timeout=30,follow_redirects=False,headers={'Origin':origin}) as client:
    missing=client.get('/api/v1/not-a-route');assert missing.status_code==404 and 'application/json' in missing.headers.get('content-type',''), 'API rewrite returned HTML or the wrong status.'
    response=client.post('/api/v1/auth/login',json={'username':username,'password':password});response.raise_for_status();auth=response.json();csrf=auth['csrf_token'];client.headers['X-CSRF-Token']=csrf
    try:
        assert not auth['must_change_password'],'Change the temporary password in the browser first.'
        me=client.get('/api/v1/me');me.raise_for_status();assert me.json()['user']['id']==auth['user']['id'];assert 'no-store' in me.headers['cache-control']
        membership=next(m for m in auth['memberships'] if m['role']=='admin');base='/api/v1/farms/'+membership['farm']['id']
        for endpoint in ('bootstrap','dashboard','logs?limit=2','fields/geojson?limit=1','activities','fertilizers','members'):
            result=client.get(base+'/'+endpoint);result.raise_for_status();assert 'application/json' in result.headers['content-type'];assert 'no-store' in result.headers['cache-control'];print('PASS',endpoint)
        route=client.get('/admin/'+membership['farm']['id']+'/dashboard');assert route.status_code==200 and 'text/html' in route.headers.get('content-type',''), 'SPA route refresh failed.'
        print('PASS nested frontend route; session cookies; API rewrite; JSON errors; safe cache headers.')
    finally:
        logout=client.post('/api/v1/auth/logout');logout.raise_for_status()
    assert client.get('/api/v1/me').status_code==401
print('PASS logout revocation. Live voice, S3 upload, and phone playback still require the browser checklist.')
