from dotenv import load_dotenv
load_dotenv()

import os, re, json, time, secrets, datetime as dt
from collections import defaultdict, deque
import bcrypt, jwt
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select, desc

import ai
from db import Base, engine, Session, User, Journal, Saved

SECRET = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
Base.metadata.create_all(engine)
app = FastAPI(title="Daily Debrief")

# ---------- helpers ----------
hits = defaultdict(deque)
def limit(request: Request):
    ip = (request.headers.get("x-forwarded-for") or request.client.host).split(",")[0].strip()
    q, t = hits[ip], time.time()
    while q and t - q[0] > 60: q.popleft()
    if len(q) >= 20: raise HTTPException(429, "Too many requests. Try again in a minute.")
    q.append(t)

def make_token(uid):
    exp = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=14)
    return jwt.encode({"sub": str(uid), "exp": exp}, SECRET, algorithm="HS256")

def current_user(request: Request):
    h = request.headers.get("authorization", "")
    if not h.startswith("Bearer "): raise HTTPException(401, "Please log in.")
    try: uid = int(jwt.decode(h[7:], SECRET, algorithms=["HS256"])["sub"])
    except Exception: raise HTTPException(401, "Session expired. Please log in again.")
    with Session() as s: u = s.get(User, uid)
    if not u: raise HTTPException(401, "Please log in.")
    return u

# ---------- auth ----------
class Creds(BaseModel):
    email: str
    password: str
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@app.post("/api/auth/register", dependencies=[Depends(limit)])
def register(c: Creds):
    email = c.email.strip().lower()
    if not EMAIL.match(email) or len(email) > 255: raise HTTPException(400, "Enter a valid email.")
    if not 8 <= len(c.password.encode()) <= 72: raise HTTPException(400, "Password must be 8 to 72 characters.")
    with Session() as s:
        if s.scalar(select(User).where(User.email == email)): raise HTTPException(400, "That email is already registered.")
        u = User(email=email, pw_hash=bcrypt.hashpw(c.password.encode(), bcrypt.gensalt()).decode())
        s.add(u); s.commit()
        return {"token": make_token(u.id), "email": u.email}

@app.post("/api/auth/login", dependencies=[Depends(limit)])
def login(c: Creds):
    with Session() as s:
        u = s.scalar(select(User).where(User.email == c.email.strip().lower()))
    if not u or not bcrypt.checkpw(c.password.encode()[:72], u.pw_hash.encode()):
        raise HTTPException(401, "Incorrect email or password.")
    return {"token": make_token(u.id), "email": u.email}

@app.get("/api/auth/me")
def me(u: User = Depends(current_user)): return {"email": u.email}

# ---------- tools (guests allowed) ----------
class TextIn(BaseModel):
    text: str

def check(t):
    t = t.strip()
    if len(t.split()) < 3: raise HTTPException(400, "Add at least a few words first.")
    return t[:8000]

@app.post("/api/prioritize", dependencies=[Depends(limit)])
def prioritize(b: TextIn): return ai.prioritize(check(b.text))

@app.post("/api/summarize", dependencies=[Depends(limit)])
def summarize(b: TextIn): return ai.summarize(check(b.text))

# ---------- saved (login) ----------
class SaveIn(BaseModel):
    kind: str
    title: str
    input_text: str
    result: dict

@app.post("/api/saved")
def save(b: SaveIn, u: User = Depends(current_user)):
    if b.kind not in ("prioritize", "summarize"): raise HTTPException(400, "Bad kind.")
    with Session() as s:
        r = Saved(user_id=u.id, kind=b.kind, title=b.title[:120], input_text=b.input_text[:8000],
                  result=json.dumps(b.result)[:20000])
        s.add(r); s.commit()
        return {"id": r.id}

@app.get("/api/saved")
def saved(u: User = Depends(current_user)):
    with Session() as s:
        rows = s.scalars(select(Saved).where(Saved.user_id == u.id).order_by(desc(Saved.id)).limit(100)).all()
        return [{"id": r.id, "kind": r.kind, "title": r.title, "result": json.loads(r.result)} for r in rows]

@app.delete("/api/saved/{sid}")
def unsave(sid: int, u: User = Depends(current_user)):
    with Session() as s:
        r = s.get(Saved, sid)
        if r and r.user_id == u.id: s.delete(r); s.commit()
    return {"ok": True}

# ---------- journal (login) ----------
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
class JIn(BaseModel):
    mood: int = 0
    content: str = ""
    gratitude: str = ""

def day_ok(d):
    if not DAY.match(d): raise HTTPException(400, "Bad date.")
    return d

@app.get("/api/journal")
def jlist(u: User = Depends(current_user)):
    with Session() as s:
        rows = s.scalars(select(Journal).where(Journal.user_id == u.id).order_by(desc(Journal.day)).limit(60)).all()
        return [{"day": r.day, "mood": r.mood, "preview": (r.content or r.gratitude)[:90]}
                for r in rows if (r.content or r.gratitude or r.mood)]

@app.get("/api/journal/{day}")
def jget(day: str, u: User = Depends(current_user)):
    with Session() as s:
        r = s.scalar(select(Journal).where(Journal.user_id == u.id, Journal.day == day_ok(day)))
        return {"mood": r.mood, "content": r.content, "gratitude": r.gratitude} if r else {"mood": 0, "content": "", "gratitude": ""}

@app.put("/api/journal/{day}")
def jput(day: str, b: JIn, u: User = Depends(current_user)):
    with Session() as s:
        r = s.scalar(select(Journal).where(Journal.user_id == u.id, Journal.day == day_ok(day)))
        if not r: r = Journal(user_id=u.id, day=day); s.add(r)
        r.mood, r.content, r.gratitude = max(0, min(5, b.mood)), b.content[:20000], b.gratitude[:5000]
        s.commit()
    return {"ok": True}

# ---------- static ----------
@app.get("/api/health")
def health(): return {"ok": True, "ai": bool(os.getenv("GEMINI_API_KEY"))}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index(): return FileResponse("static/index.html")
