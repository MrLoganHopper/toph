"""Set the frontend reverse proxy without embedding credentials."""
from pathlib import Path
from urllib.parse import urlsplit
import sys,json
if len(sys.argv)!=2:sys.exit('Usage: python scripts/set_backend_origin.py https://YOUR-BACKEND.vercel.app')
origin=sys.argv[1].rstrip('/');parts=urlsplit(origin)
if parts.scheme!='https' or not parts.netloc or parts.path or parts.query or parts.fragment or parts.username:sys.exit('Use a stable HTTPS origin without a path, query or credentials.')
p=Path(__file__).resolve().parents[1]/'frontend/vercel.json';data=json.loads(p.read_text())
data['rewrites']=[{'source':'/api/:path*','destination':origin+'/api/:path*'},{'source':'/(.*)','destination':'/index.html'}]
p.write_text(json.dumps(data,indent=2)+'\n');print('Updated frontend/vercel.json. Commit this change and redeploy the frontend.')
