"""Run all installed checks, preserving a nonzero exit code if any fail."""
from pathlib import Path
import argparse,os,subprocess,sys
root=Path(__file__).resolve().parents[1];npm='npm.cmd' if os.name=='nt' else 'npm'
checks=[('Backend tests',[sys.executable,'-m','pytest'],root/'backend'),('API contract',[sys.executable,str(root/'scripts/export_openapi.py')],root),('TypeScript',[npm,'run','typecheck'],root/'frontend'),('Frontend lint',[npm,'run','lint'],root/'frontend'),('Frontend unit tests',[npm,'test'],root/'frontend'),('Production build',[npm,'run','build'],root/'frontend')]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--require-db',action='store_true');args=parser.parse_args()
failed=[]
if args.require_db and not os.environ.get('TEST_DATABASE_URL'):failed.append('PostGIS integration database missing')
for name,command,cwd in checks:
    print('\n=== '+name+' ===',flush=True)
    try:code=subprocess.run(command,cwd=cwd,check=False).returncode
    except OSError as exc:print(exc);code=1
    if code:failed.append(name)
print('\nChecks failing or blocked: '+(', '.join(failed) if failed else 'none'))
if not os.environ.get('TEST_DATABASE_URL'):print('PostGIS integration tests require TEST_DATABASE_URL; skipped tests are not passes.')
sys.exit(bool(failed))
