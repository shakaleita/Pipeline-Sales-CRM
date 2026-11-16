"""Insert optional synthetic demonstration records (safe to rerun)."""
from fastapi.testclient import TestClient
from main import app

SEEDS = [{'company': 'Northwind Analytics', 'contact': 'Jane Example', 'value': 14000, 'stage': 'Qualified', 'owner': 'Alex', 'probability': 55}, {'company': 'Acme Studio', 'contact': 'Sam Example', 'value': 9000, 'stage': 'Proposal', 'owner': 'Jordan', 'probability': 70}]
client=TestClient(app)
if client.get('/api/items').json():
    print('Existing records found; skipping seed.')
else:
    for record in SEEDS:
        result=client.post('/api/items',json=record)
        result.raise_for_status()
    print('Added',len(SEEDS),'synthetic sample records.')
