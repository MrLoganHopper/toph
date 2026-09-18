"""Install and initialize a development checkout. Run from any directory; no production seed."""
from pathlib import Path
import argparse,os,shutil,subprocess,sys,venv
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--managed',action='store_true',help='Use a development managed PostGIS database instead of local Docker.')
parser.add_argument('--seed',action='store_true',help='Create fictional demo accounts. Prompts for their private shared development password.')
args=parser.parse_args()
if not (3,12)<=sys.version_info[:2]<(3,14):sys.exit('Install Python 3.12 or 3.13 and rerun this command.')
def run(command,cwd=root):
    print('\n> '+' '.join(map(str,command)),flush=True)
    subprocess.run(list(map(str,command)),cwd=cwd,check=True)
try:
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not npm:sys.exit('Install Node.js 22.12+ (including npm), reopen the terminal, then rerun.')
    local_files=[root/'backend/.env',root/'frontend/.env']
    if all(p.exists() for p in local_files):print('Using existing local environment files. No credentials are overwritten.')
    elif any(p.exists() for p in local_files):sys.exit('Only one .env file exists. Complete both environment files or back them up before setup.')
    else:run([sys.executable,root/'scripts/configure_local.py']+(['--managed'] if args.managed else []))
    env_dir=root/'backend/.venv'
    if not env_dir.exists():venv.EnvBuilder(with_pip=True).create(env_dir)
    python=env_dir/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    run([python,'-m','pip','install','-r',root/'backend/requirements-dev.txt'])
    # Validate the effective configuration, including environment overrides, before writes.
    run([python,'-c',"from app.config import settings; assert settings().app_env in ('development','test'), 'setup_local refuses production/preview configuration'"],root/'backend')
    if not args.managed:
        if not shutil.which('docker'):sys.exit('Install and start Docker Desktop, or rerun with --managed for a development PostGIS database.')
        run(['docker','compose','up','-d','--wait','db'])
    run([npm,'ci' if (root/'frontend/package-lock.json').exists() else 'install'],root/'frontend')
    run([python,'-m','alembic','upgrade','head'],root/'backend')
    if args.seed:
        probe="""from app.db.session import transaction
from sqlalchemy import text
with transaction(operator=True) as conn:
    print(int(bool(conn.execute(text("SELECT 1 FROM farm_app.users WHERE username='demo.admin'" )).first())))
"""
        exists=subprocess.check_output([str(python),'-c',probe],cwd=root/'backend',text=True).strip()
        if exists=='1':print('Existing demo accounts retained, including their original passwords.')
        else:run([python,'-m','app.cli','seed'],root/'backend')
    run([npm,'run','typecheck'],root/'frontend')
    run([npm,'run','build'],root/'frontend')
    print('\nSetup completed. Start both servers with: python scripts/run_local.py')
    if not args.seed:print('Create your first farm with the virtual environment Python: cd backend; python -m app.cli create-farm')
except subprocess.CalledProcessError as error:
    sys.exit(f'\nSetup stopped at a failing command (exit {error.returncode}). Fix the reported error and rerun. No step is marked passed merely because it was attempted.')
