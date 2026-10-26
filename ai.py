"""Gemini first; if anything goes wrong, fall back to the built-in parsers. Never raises."""
import os, re, json, httpx
from collections import Counter

URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

def _gemini(prompt):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        r = httpx.post(URL.format(os.getenv("GEMINI_MODEL") or "gemini-2.5-flash-lite"),
                       headers={"x-goog-api-key": key},
                       json={"contents": [{"parts": [{"text": prompt}]}],
                             "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}},
                       timeout=25)
        r.raise_for_status()
        return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    except Exception:
        return None

def _strs(v):
    return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else None

# ---------- prioritize ----------
P = """Sort these notes into tasks. Return ONLY JSON:
{{"summary":"one calm sentence","high":["..."],"medium":["..."],"low":["..."]}}
Use short imperative task wording. high = urgent or important and due soon.
Notes:
{t}"""
HI = re.compile(r"urgent|asap|today|tonight|deadline|due|tomorrow|must|important|immediately|submit|pay", re.I)
LO = re.compile(r"maybe|someday|sometime|eventually|if time|optional|when free|later|might", re.I)

def _basic_priority(text):
    parts = re.split(r"[\n;]+|(?<=[.!?])\s+", text)
    items = [re.sub(r"^[\s\-\*\u2022\d\.\)]+", "", p).strip().rstrip(".") for p in parts]
    items = [i for i in items if len(i) > 2]
    hi = [i for i in items if HI.search(i)]
    lo = [i for i in items if i not in hi and LO.search(i)]
    me = [i for i in items if i not in hi and i not in lo]
    return {"summary": f"{len(items)} things noted, {len(hi)} need attention first.",
            "high": hi, "medium": me, "low": lo, "engine": "basic"}

def prioritize(text):
    d = _gemini(P.format(t=text))
    if isinstance(d, dict) and isinstance(d.get("summary"), str):
        hi, me, lo = _strs(d.get("high")), _strs(d.get("medium")), _strs(d.get("low"))
        if None not in (hi, me, lo):
            return {"summary": d["summary"], "high": hi, "medium": me, "low": lo, "engine": "ai"}
    return _basic_priority(text)

# ---------- summarize ----------
S = """Summarize the text. Return ONLY JSON:
{{"summary":"2-4 sentence summary","key_points":["3-6 short points"]}}
Text:
{t}"""
STOP = set("the a an and or but of to in on for with is are was were be been it this that as at by from not have has had they you we i he she his her their our your its into than then so if".split())

def _basic_summary(text):
    sents = [s.strip() for s in re.split(r"(?<=[.!?\u0964])\s+|\n+", text) if len(s.split()) > 3]
    if not sents:
        return {"summary": text[:300], "key_points": [], "engine": "basic"}
    freq = Counter(w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOP)
    score = lambda s: sum(freq[w] for w in re.findall(r"[a-z']+", s.lower())) / (len(s.split()) ** 0.6)
    top = sorted(range(len(sents)), key=lambda i: -score(sents[i]))
    return {"summary": " ".join(sents[i] for i in sorted(top[:3])),
            "key_points": [sents[i][:200] for i in sorted(top[:5])], "engine": "basic"}

def summarize(text):
    d = _gemini(S.format(t=text))
    if isinstance(d, dict) and isinstance(d.get("summary"), str) and _strs(d.get("key_points")) is not None:
        return {"summary": d["summary"], "key_points": _strs(d["key_points"]), "engine": "ai"}
    return _basic_summary(text)
