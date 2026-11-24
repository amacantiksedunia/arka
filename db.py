"""Koneksi SQLite dan helper query."""
import json
import os
import sqlite3
from pathlib import Path

from flask import g

BASE_DIR = Path(__file__).resolve().parent
# Di Vercel hanya folder /tmp yang bisa ditulis (dan isinya bisa hilang saat server tidur).
_default = Path("/tmp/arka.db") if os.environ.get("VERCEL") else BASE_DIR / "arka.db"
DB_PATH = Path(os.environ.get("ARKA_DB", _default))


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_schema(conn):
    conn.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def row(r):
    """sqlite3.Row -> dict, kolom JSON otomatis di-parse."""
    if r is None:
        return None
    d = dict(r)
    for k in ("interests", "answers", "result", "data", "tasks", "sources",
              "talents", "values_", "skills", "majors", "subjects", "campuses"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except (ValueError, TypeError):
                pass
    if "values_" in d:
        d["values"] = d.pop("values_")
    return d


def rows(rs):
    return [row(r) for r in rs]


def q(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rs = cur.fetchall()
    return (row(rs[0]) if rs else None) if one else rows(rs)


def x(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid
