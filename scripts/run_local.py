"""Run both local servers in the foreground. Ctrl+C stops the child processes."""
from pathlib import Path
import os,shutil,subprocess,sys,time
root=Path(__file__).resolve().parents[1]
python=root/'backend/.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
if not python.exists() or not npm or not (root/'frontend/node_modules').exists():sys.exit('First run: python scripts/setup_local.py --seed')
children=[]
try:
    children.append(subprocess.Popen([str(python),'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],cwd=root/'backend'))
    children.append(subprocess.Popen([npm,'run','dev'],cwd=root/'frontend'))
    print('\nOpen http://localhost:5173 . Keep this terminal open. Ctrl+C stops both servers.',flush=True)
    while all(process.poll() is None for process in children):time.sleep(.5)
    failed=next((p.returncode for p in children if p.poll() is not None),1)
    sys.exit(failed or 0)
except KeyboardInterrupt:pass
finally:
    for child in children:
        if child.poll() is None:child.terminate()
    for child in children:
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:child.kill()
