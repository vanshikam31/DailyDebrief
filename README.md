# Daily Debrief

Prioritize tasks, summarize long text, and keep a private daily journal.
FastAPI + SQLAlchemy + one static page. AI via Gemini (free key), with a built-in fallback that never crashes the site.

## Run locally
```bash
# Windows:  python -m venv venv && venv\Scripts\activate
# Mac/Linux: python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
uvicorn main:app --reload
```
Open http://localhost:8000 (API docs: /docs). Without a Gemini key it runs in basic mode with local SQLite.

## API
| Method | Path | Auth |
|---|---|---|
| POST | /api/prioritize `{text}` | no |
| POST | /api/summarize `{text}` | no |
| POST | /api/auth/register, /api/auth/login `{email,password}` | no |
| GET | /api/auth/me | yes |
| GET/POST/DELETE | /api/saved | yes |
| GET | /api/journal, /api/journal/{YYYY-MM-DD} | yes |
| PUT | /api/journal/{YYYY-MM-DD} `{mood,content,gratitude}` | yes |

## Deploy free (Render + Neon)
1. Neon.tech: create a free Postgres project, copy the connection string.
2. Push to GitHub, then Render > New > Web Service > this repo > Free.
   Build `pip install -r requirements.txt`, Start `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Environment: `DATABASE_URL` (Neon string), `GEMINI_API_KEY`, `SECRET_KEY` (long random string).
4. Custom domain: Render > Settings > Custom Domains, add the DNS record Render shows you.
