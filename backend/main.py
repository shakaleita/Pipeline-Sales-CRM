APP_TITLE = 'Pipeline'
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
import sqlite3, os
from contextlib import contextmanager
from pathlib import Path

DB = Path(os.environ.get("APP_DB", str(Path(__file__).parent / "app.db")))
app = FastAPI(title=APP_TITLE, version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_methods=["*"], allow_headers=["*"])

@contextmanager
def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def rows(cursor):
    return [dict(r) for r in cursor.fetchall()]

def setup(sql):
    with db() as con:
        con.executescript(sql)

@app.get("/api/health")
def health():
    return {"ok": True, "service": APP_TITLE}


setup("""CREATE TABLE IF NOT EXISTS deals(id INTEGER PRIMARY KEY,company TEXT NOT NULL,contact TEXT NOT NULL DEFAULT '',value REAL NOT NULL CHECK(value>=0),stage TEXT NOT NULL DEFAULT 'Lead',owner TEXT NOT NULL DEFAULT '',probability INTEGER NOT NULL DEFAULT 20 CHECK(probability BETWEEN 0 AND 100));""")
setup("""CREATE TABLE IF NOT EXISTS deal_events(id INTEGER PRIMARY KEY,deal_id INTEGER NOT NULL,previous_stage TEXT NOT NULL,new_stage TEXT NOT NULL,recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(deal_id) REFERENCES deals(id))""")
class Deal(BaseModel):
    company:str
    contact:str=""
    value:float
    stage:str="Lead"
    owner:str=""
    probability:int=20
@app.get('/api/items')
def items():
    with db() as c:return rows(c.execute('SELECT * FROM deals ORDER BY id DESC'))
@app.post('/api/items',status_code=201)
def create_item(d:Deal):
    if not d.company.strip() or d.value<0 or not (0<=d.probability<=100):raise HTTPException(422,'Invalid deal')
    with db() as c:
        cur=c.execute('INSERT INTO deals(company,contact,value,stage,owner,probability) VALUES(?,?,?,?,?,?)',tuple(getattr(d,k) for k in ['company','contact','value','stage','owner','probability']))
        return dict(c.execute('SELECT * FROM deals WHERE id=?',(cur.lastrowid,)).fetchone())
@app.patch('/api/items/{item_id}')
def stage(item_id:int,stage:str):
    if stage not in ['Lead','Qualified','Proposal','Negotiation','Won','Lost']:raise HTTPException(422,'Invalid stage')
    with db() as c:
        old=c.execute('SELECT stage FROM deals WHERE id=?',(item_id,)).fetchone()
        if not old:raise HTTPException(404,'Deal not found')
        c.execute('UPDATE deals SET stage=? WHERE id=?',(stage,item_id))
        if old['stage']!=stage:
            c.execute('INSERT INTO deal_events(deal_id,previous_stage,new_stage) VALUES(?,?,?)',(item_id,old['stage'],stage))
        return {'id':item_id,'stage':stage}
@app.get('/api/summary')
def summary():
    with db() as c:
        return [{'label':'Deals','value':c.execute('SELECT COUNT(*) FROM deals').fetchone()[0]},{'label':'Pipeline value','value':round(c.execute("SELECT COALESCE(SUM(value),0) FROM deals WHERE stage NOT IN ('Lost','Won')").fetchone()[0],2)},{'label':'Weighted forecast','value':round(c.execute("SELECT COALESCE(SUM(value*probability/100),0) FROM deals WHERE stage NOT IN ('Lost','Won')").fetchone()[0],2)}]


# v0.3: deal stage timeline and filtering
@app.get('/api/deals/{deal_id}/history')
def deal_history(deal_id: int):
    with db() as con:
        if not con.execute('SELECT 1 FROM deals WHERE id=?',(deal_id,)).fetchone():
            raise HTTPException(404,'Deal not found')
        return rows(con.execute('SELECT * FROM deal_events WHERE deal_id=? ORDER BY id DESC',(deal_id,)))

@app.get('/api/pipeline')
def pipeline():
    with db() as con:
        return rows(con.execute("""SELECT stage,COUNT(*) AS deals,
            ROUND(COALESCE(SUM(value),0),2) AS value,
            ROUND(COALESCE(SUM(value * probability/100.0),0),2) AS weighted
            FROM deals GROUP BY stage ORDER BY stage"""))


from pydantic import Field
setup("""CREATE TABLE IF NOT EXISTS deal_notes(
 id INTEGER PRIMARY KEY,deal_id INTEGER NOT NULL,note TEXT NOT NULL,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(deal_id) REFERENCES deals(id));""")

class Note(BaseModel):
    note:str=Field(min_length=1,max_length=1500)

@app.get('/api/deals/{deal_id}/notes')
def deal_notes(deal_id:int):
    with db() as con:
        if not con.execute('SELECT 1 FROM deals WHERE id=?',(deal_id,)).fetchone():
            raise HTTPException(404,'Deal not found')
        return rows(con.execute('SELECT * FROM deal_notes WHERE deal_id=? ORDER BY id DESC',(deal_id,)))

@app.post('/api/deals/{deal_id}/notes',status_code=201)
def add_deal_note(deal_id:int,payload:Note):
    if not payload.note.strip():raise HTTPException(422,'Note required')
    with db() as con:
        if not con.execute('SELECT 1 FROM deals WHERE id=?',(deal_id,)).fetchone():
            raise HTTPException(404,'Deal not found')
        cur=con.execute('INSERT INTO deal_notes(deal_id,note) VALUES(?,?)',(deal_id,payload.note))
        return dict(con.execute('SELECT * FROM deal_notes WHERE id=?',(cur.lastrowid,)).fetchone())

from security import install_auth
install_auth(app,DB)
