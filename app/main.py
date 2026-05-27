"""
Minimal FastAPI service for DevOps challenge.
- /health : liveness (always returns 200 if process is up)
- /ready  : readiness (returns 200 only if DB is reachable)
- /items  : POST to insert, GET to list
"""
import os
import time
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("app")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

app = FastAPI(title="DevOps Challenge API")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, connect_timeout=3,
    )


@app.on_event("startup")
def init_db():
    # Retry loop — DB pod may still be coming up.
    for attempt in range(30):
        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS items "
                    "(id SERIAL PRIMARY KEY, name TEXT NOT NULL, "
                    "created_at TIMESTAMP DEFAULT NOW())"
                )
                conn.commit()
            log.info("DB initialized")
            return
        except Exception as e:
            log.warning(f"DB not ready (attempt {attempt+1}/30): {e}")
            time.sleep(2)
    log.error("DB init failed after 30 attempts — continuing; /ready will fail")


class Item(BaseModel):
    name: str


@app.get("/health")
def health():
    # Liveness — just confirms the process is alive.
    return {"status": "ok"}


@app.get("/ready")
def ready():
    # Readiness — confirms the app can serve traffic (DB reachable).
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB unreachable: {e}")


@app.get("/items")
def list_items():
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, name, created_at FROM items ORDER BY id DESC LIMIT 50")
        return cur.fetchall()


@app.post("/items")
def add_item(item: Item):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO items (name) VALUES (%s) RETURNING id", (item.name,))
        new_id = cur.fetchone()[0]
        conn.commit()
    return {"id": new_id, "name": item.name}
