import importlib,os,sys,tempfile
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
temp = tempfile.mkdtemp(prefix='portfolio-test-')
os.environ['APP_DB']=str(Path(temp)/'test.db')
if 'main' in sys.modules: del sys.modules['main']
from main import app
client=TestClient(app)

def test_health():
    r=client.get('/api/health')
    assert r.status_code==200 and r.json()['ok']

def test_initial_list():
    r=client.get('/api/items')
    assert r.status_code==200 and isinstance(r.json(),list)

def test_summary():
    r=client.get('/api/summary')
    assert r.status_code==200 and isinstance(r.json(),list)


# v0.3 regression tests
def test_deal_stage_history_and_pipeline():
    d=client.post('/api/items',json={'company':'Example Ltd','value':1000,'probability':40}).json()
    assert client.patch(f"/api/items/{d['id']}",params={'stage':'Proposal'}).status_code==200
    assert client.patch(f"/api/items/{d['id']}",params={'stage':'Won'}).status_code==200
    events=client.get(f"/api/deals/{d['id']}/history").json()
    assert len(events)==2 and events[0]['new_stage']=='Won'
    pipeline=client.get('/api/pipeline').json()
    assert any(x['stage']=='Won' and x['deals']>=1 for x in pipeline)
    assert client.patch(f"/api/items/{d['id']}",params={'stage':'Invalid'}).status_code==422

