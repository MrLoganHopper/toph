from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.main import app
schema=app.openapi();output=root/'docs/openapi.json';output.write_text(json.dumps(schema,indent=2)+'\n')
contract=json.loads((root/'docs/api_contract.json').read_text())
missing=[(e['method'],e['path']) for e in contract['endpoints'] if e['method'].lower() not in schema['paths'].get(e['path'],{})]
if missing:raise SystemExit('Missing contract routes: '+repr(missing))
print(f'Generated actual FastAPI OpenAPI. All {len(contract["endpoints"])} contract routes are present.')
