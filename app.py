"""
ARKA — backend API (Flask + SQLite)

Jalankan:  python app.py   ->  http://localhost:5000
Akun demo dibuat oleh seed.py (lihat README).
"""
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, date
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session, abort
from werkzeug.security import check_password_hash, generate_password_hash

import db as dbm
from db import q, x
import engine
from data import TESTS, RIASEC

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "public"   # di Vercel folder public/ disajikan langsung oleh CDN
POLICY_VERSION = "v1.0-2026-11"
DEMO_MODE = os.environ.get("ARKA_DEMO", "1") == "1"   # tampilkan kotak surat simulasi

app = Flask(__name__, static_folder=None)


ON_VERCEL = bool(os.environ.get("VERCEL"))


def _secret_key():
    if os.environ.get("ARKA_SECRET"):
        return os.environ["ARKA_SECRET"]
    if ON_VERCEL:   # sistem file Vercel read-only; set ARKA_SECRET di Project Settings agar login stabil
        return "arka-demo-secret-ganti-dengan-ARKA_SECRET"
    f = Path(__file__).with_name(".secret_key")
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


app.config.update(SECRET_KEY=_secret_key(), SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=timedelta(days=7),
                  JSON_SORT_KEYS=False)
app.teardown_appcontext(dbm.close_db)

# ================================================================= helpers

def now():
    return datetime.now().isoformat(timespec="seconds")


def err(msg, code=400, **extra):
    return jsonify({"error": msg, **extra}), code


def age_of(birth):
    try:
        b = date.fromisoformat(birth)
    except (TypeError, ValueError):
        return None
    t = date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    u = q("SELECT * FROM users WHERE id=? AND status!='deleted'", (uid,), one=True)
    return u


def log_event(user, name):
    """Event analitik: hanya ID pseudonim, jenis, waktu (Bab 7)."""
    x("INSERT INTO events(pseudo_id, event) VALUES(?,?)", (user["pseudo_id"], name))


def audit(actor, action, target, allowed):
    x("INSERT INTO audit_log(actor_id, action, target, allowed, ip) VALUES(?,?,?,?,?)",
      (actor["id"] if actor else None, action, target, 1 if allowed else 0, request.remote_addr))


def send_mail(to, subject, body, link=None):
    """Mode demo: simpan ke outbox. Produksi: ganti dengan layanan email/WA."""
    x("INSERT INTO outbox(to_contact, subject, body, link) VALUES(?,?,?,?)", (to, subject, body, link))


def need(*roles, active=False):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                return err("Silakan masuk dulu.", 401)
            if roles and u["role"] not in roles:
                audit(u, f"{request.method} {request.path}", "role", False)
                return err("Akses ditolak untuk peran ini.", 403)
            if active and u["status"] != "active":
                return err("Fitur terkunci sampai persetujuan orang tua/wali tercatat.", 423,
                           reason="consent")
            x("UPDATE users SET last_active_at=? WHERE id=?", (now(), u["id"]))
            return fn(u, *a, **kw)
        return wrapper
    return deco


def public_user(u):
    school = q("SELECT id,name,city,invite_code FROM schools WHERE id=?", (u["school_id"],), one=True) if u["school_id"] else None
    out = {k: u[k] for k in ("id", "role", "name", "nickname", "email", "birth_date", "gender", "city",
                             "grade", "class_name", "interests", "concern", "status", "onboarded", "notif_enabled")}
    out["school"] = school
    out["age"] = age_of(u["birth_date"])
    if u["role"] == "siswa" and u["status"] == "pending_consent":
        c = q("SELECT parent_name,parent_contact,expires_at,created_at FROM consents WHERE student_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
              (u["id"],), one=True)
        out["consent"] = c
        out["consent_expired"] = bool(c and c["expires_at"] < now())
    return out

# ----------------------------------------------------------- data siswa

def completed_results(uid):
    """Hasil terbaru per asesmen yang selesai."""
    rs = q("""SELECT test_key, result, completed_at FROM assessment_attempts
              WHERE user_id=? AND status='completed' ORDER BY completed_at""", (uid,))
    out = {}
    for r in rs:
        out[r["test_key"]] = r["result"]
    return out


def last_completion(uid):
    r = q("SELECT MAX(completed_at) AS m FROM assessment_attempts WHERE user_id=? AND status='completed'", (uid,), one=True)
    return r["m"] if r else None


def all_careers():
    return q("SELECT * FROM careers")


def all_majors():
    return q("SELECT * FROM majors")


def current_roadmap(uid):
    r = q("SELECT * FROM roadmaps WHERE user_id=? AND is_current=1 ORDER BY id DESC LIMIT 1", (uid,), one=True)
    if not r:
        return None
    steps = q("SELECT * FROM roadmap_steps WHERE roadmap_id=? ORDER BY idx", (r["id"],))
    tasks = [t for s in steps for t in s["tasks"]]
    r["steps"] = steps
    r["progress"] = round(sum(1 for t in tasks if t["done"]) / len(tasks) * 100) if tasks else 0
    r["based_on"] = json.loads(r["based_on"])
    return r


def student_stats(u):
    res = completed_results(u["id"])
    rd = current_roadmap(u["id"])
    pct = (rd["progress"] / 100) if rd else 0
    score = engine.readiness(len(res), bool(rd and rd["is_saved"]), pct, u["last_active_at"])
    tags = engine.priority_tags(score, len(res), u["last_active_at"])
    return res, rd, score, tags

# ================================================================= static

@app.get("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.get("/<path:p>")
def static_files(p):
    if p.startswith("api/"):
        abort(404)
    f = FRONTEND / p
    if f.is_file():
        return send_from_directory(FRONTEND, p)
    return send_from_directory(FRONTEND, "index.html")

# ================================================================= auth & daftar

@app.get("/api/schools")
def schools():
    return jsonify(q("SELECT id, name, city FROM schools ORDER BY name"))


@app.get("/api/schools/by-invite/<code>")
def school_by_invite(code):
    s = q("SELECT id, name, city FROM schools WHERE invite_code=?", (code,), one=True)
    return jsonify(s) if s else err("Kode undangan tidak ditemukan.", 404)


def _new_consent(student, parent_name, parent_contact):
    x("UPDATE consents SET status='superseded' WHERE student_id=? AND status='pending'", (student["id"],))
    token = secrets.token_urlsafe(24)
    code = f"{secrets.randbelow(10**6):06d}"
    expires = (datetime.now() + timedelta(days=7)).isoformat(timespec="seconds")
    x("""INSERT INTO consents(student_id, token, code, parent_name, parent_contact, policy_version, expires_at)
         VALUES(?,?,?,?,?,?,?)""", (student["id"], token, code, parent_name, parent_contact, POLICY_VERSION, expires))
    link = f"/#/persetujuan/{token}"
    send_mail(parent_contact, "Persetujuan data anak untuk ARKA",
              f"Yth. {parent_name},\n\n{student['name']} mendaftar di ARKA, platform panduan karier sekolah. "
              f"Karena usianya di bawah 18 tahun, kami membutuhkan persetujuan Anda (UU PDP Pasal 25).\n\n"
              f"Buka tautan berikut dan masukkan kode verifikasi: {code}\nTautan berlaku 7 hari.",
              link)
    return token


ROLE_MAP = {"siswa": "siswa", "guru_bk": "guru_bk", "kepala_sekolah": "kepsek", "kepsek": "kepsek"}


@app.post("/api/auth/register")
def register():
    """Formulir daftar prototipe: nama, email, password, konfirmasi, daftar sebagai."""
    d = request.get_json(force=True) or {}
    name = (d.get("name") or "").strip()
    email = (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    role = ROLE_MAP.get(d.get("role") or "siswa")
    if not name or "@" not in email:
        return err("Isi nama lengkap dan email yang valid.")
    if len(pw) < 8:
        return err("Password minimal 8 karakter.")
    if d.get("confirm") is not None and d.get("confirm") != pw:
        return err("Konfirmasi password tidak sama.")
    if not role:
        return err("Peran tidak dikenal.")
    if q("SELECT 1 FROM users WHERE email=?", (email,), one=True):
        return err("Email sudah terdaftar. Silakan masuk.", 409, action="login")
    uid = x("""INSERT INTO users(role,name,email,password_hash,status,onboarded,pseudo_id)
               VALUES(?,?,?,?, 'active', 0, ?)""",
            (role, name, email, generate_password_hash(pw), secrets.token_hex(8)))
    u = q("SELECT * FROM users WHERE id=?", (uid,), one=True)
    log_event(u, "account_registered")
    session.clear()
    session.permanent = True
    session["uid"] = uid
    return jsonify({"user": public_user(u)})


@app.post("/api/auth/login")
def login():
    d = request.get_json(force=True) or {}
    u = q("SELECT * FROM users WHERE email=? AND status!='deleted'", ((d.get("email") or "").strip().lower(),), one=True)
    if not u or not check_password_hash(u["password_hash"], d.get("password") or ""):
        return err("Email atau kata sandi salah.", 401)
    if u["status"] == "rejected":
        return err("Orang tua/wali menolak persetujuan, jadi akun ini tidak aktif dan datanya akan dihapus.", 403)
    session.clear()
    session.permanent = True
    session["uid"] = u["id"]
    x("UPDATE users SET last_active_at=? WHERE id=?", (now(), u["id"]))
    if u["role"] == "guru_bk":
        log_event(u, "dashboard_opened")
    return jsonify({"user": public_user(u)})


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/me")
def me():
    u = current_user()
    return jsonify({"user": public_user(u) if u else None, "demo": DEMO_MODE})


@app.post("/api/consent/resend")
@need("siswa")
def consent_resend(u):
    d = request.get_json(silent=True) or {}
    last = q("SELECT * FROM consents WHERE student_id=? ORDER BY id DESC LIMIT 1", (u["id"],), one=True)
    pn = (d.get("parent_name") or (last and last["parent_name"]) or "").strip()
    pc = (d.get("parent_contact") or (last and last["parent_contact"]) or "").strip()
    if not pn or not pc:
        return err("Isi nama dan kontak orang tua/wali.")
    _new_consent(u, pn, pc)
    return jsonify({"ok": True})


@app.get("/api/consent/<token>")
def consent_view(token):
    c = q("SELECT * FROM consents WHERE token=?", (token,), one=True)
    if not c:
        return err("Tautan tidak ditemukan.", 404)
    s = q("SELECT name, birth_date, grade, class_name, school_id FROM users WHERE id=?", (c["student_id"],), one=True)
    sch = q("SELECT name FROM schools WHERE id=?", (s["school_id"],), one=True) if s and s["school_id"] else None
    status = c["status"]
    if status == "pending" and c["expires_at"] < now():
        status = "expired"
        x("UPDATE consents SET status='expired' WHERE id=?", (c["id"],))
    return jsonify({
        "status": status, "parent_name": c["parent_name"], "policy_version": c["policy_version"],
        "student": {"name": s["name"] if s else "-", "grade": s["grade"] if s else "-",
                    "school": sch["name"] if sch else "Sekolah belum terdaftar"},
        "data_collected": ["Nama, tanggal lahir, kelas, sekolah, email",
                           "Jawaban dan hasil 4 asesmen (minat, bakat, kepribadian, nilai karier)",
                           "Riwayat percakapan dengan AI Career Companion"],
        "who_sees": ["Anak Anda", "Guru BK sekolah anak: profil, status asesmen, dan roadmap — BUKAN isi percakapan",
                     "Kepala sekolah: hanya laporan agregat tanpa nama"],
        "rights": ["Menarik persetujuan dan menghapus akun kapan saja", "Data dihapus dari server paling lambat 30 hari setelah diminta",
                   "Data tidak dijual dan tidak dipakai untuk iklan"],
        "expires_at": c["expires_at"],
    })


@app.post("/api/consent/<token>")
def consent_decide(token):
    d = request.get_json(force=True) or {}
    c = q("SELECT * FROM consents WHERE token=?", (token,), one=True)
    if not c:
        return err("Tautan tidak ditemukan.", 404)
    if c["status"] != "pending":
        return err("Tautan ini sudah tidak berlaku.", 410)
    if c["expires_at"] < now():
        x("UPDATE consents SET status='expired' WHERE id=?", (c["id"],))
        return err("Tautan sudah kedaluwarsa. Minta anak Anda mengirim tautan baru.", 410)
    if (d.get("code") or "").strip() != c["code"]:
        return err("Kode verifikasi salah.", 400)
    decision = d.get("decision")
    if decision not in ("approve", "reject"):
        return err("Pilih Setuju atau Tolak.")
    stu = q("SELECT * FROM users WHERE id=?", (c["student_id"],), one=True)
    if decision == "approve":
        x("UPDATE consents SET status='approved', decided_at=?, parent_name=? WHERE id=?",
          (now(), (d.get("parent_name") or c["parent_name"]).strip(), c["id"]))
        x("UPDATE users SET status='active' WHERE id=?", (stu["id"],))
        log_event(stu, "consent_recorded")
    else:
        x("UPDATE consents SET status='rejected', decided_at=? WHERE id=?", (now(), c["id"]))
        purge = (datetime.now() + timedelta(days=30)).isoformat(timespec="seconds")
        x("UPDATE users SET status='rejected' WHERE id=?", (stu["id"],))
        x("INSERT INTO deletion_requests(user_id, code, status, confirmed_at, purge_after) VALUES(?,?,?,?,?)",
          (stu["id"], "-", "confirmed", now(), purge))
    return jsonify({"ok": True, "status": "approved" if decision == "approve" else "rejected"})


@app.get("/api/dev/outbox")
def outbox():
    if not DEMO_MODE:
        abort(404)
    return jsonify(q("SELECT * FROM outbox ORDER BY id DESC LIMIT 30"))

# ================================================================= onboarding & pengaturan

def school_from_name(name):
    """Cocokkan nama sekolah ketikan pengguna; buat baru bila belum ada."""
    name = (name or "").strip()
    if not name:
        return None
    r = q("SELECT id FROM schools WHERE lower(name)=lower(?)", (name,), one=True)
    if r:
        return r["id"]
    code = "".join(ch for ch in name.upper() if ch.isalnum())[:10] + "-" + secrets.token_hex(2).upper()
    return x("INSERT INTO schools(name, city, invite_code) VALUES(?,?,?)", (name, "-", code))


@app.post("/api/onboarding")
@need()
def onboarding(u):
    """Onboarding 3 langkah: data diri, sekolah, minat & kekhawatiran."""
    d = request.get_json(force=True) or {}
    interests = [i for i in (d.get("interests") or []) if isinstance(i, str)][:12]
    grade_map = {"X": "10", "XI": "11", "XII": "12"}
    grade = grade_map.get(d.get("grade") or "", d.get("grade") or None)
    class_name = " ".join(p for p in (d.get("grade"), d.get("major")) if p) or None
    school_id = school_from_name(d.get("school")) or u["school_id"]
    x("""UPDATE users SET nickname=?, birth_date=?, gender=?, city=?, school_id=?, grade=?, class_name=?,
         interests=?, concern=?, onboarded=1 WHERE id=?""",
      ((d.get("nickname") or "").strip() or None, d.get("birthDate") or None, d.get("gender") or None,
       (d.get("city") or "").strip() or None, school_id, grade, class_name,
       json.dumps(interests), d.get("concern") or None, u["id"]))
    return jsonify({"user": public_user(q("SELECT * FROM users WHERE id=?", (u["id"],), one=True))})


@app.patch("/api/settings")
@need()
def settings(u):
    d = request.get_json(force=True) or {}
    fields, vals = [], []
    for k in ("nickname", "city", "class_name"):
        if k in d:
            fields.append(f"{k}=?")
            vals.append((d[k] or "").strip() or None)
    if "notif_enabled" in d:
        fields.append("notif_enabled=?")
        vals.append(1 if d["notif_enabled"] else 0)
    if fields:
        x(f"UPDATE users SET {', '.join(fields)} WHERE id=?", (*vals, u["id"]))
    return jsonify({"user": public_user(q("SELECT * FROM users WHERE id=?", (u["id"],), one=True))})


@app.post("/api/survey")
@need("siswa", active=True)
def survey(u):
    d = request.get_json(force=True) or {}
    if d.get("score") not in (1, 2, 3, 4, 5):
        return err("Pilih skor 1–5.")
    x("INSERT INTO clarity_surveys(user_id, phase, score) VALUES(?,?,?)", (u["id"], "followup", d["score"]))
    log_event(u, "clarity_survey_answered")
    return jsonify({"ok": True})

# ================================================================= asesmen (FR-003, FR-004)

def open_attempt(uid, key):
    return q("SELECT * FROM assessment_attempts WHERE user_id=? AND test_key=? AND status='in_progress' ORDER BY id DESC LIMIT 1",
             (uid, key), one=True)


@app.get("/api/assessments")
@need("siswa", active=True)
def assessments(u):
    out = []
    for k, t in TESTS.items():
        op = open_attempt(u["id"], k)
        last = q("SELECT completed_at, result FROM assessment_attempts WHERE user_id=? AND test_key=? AND status='completed' ORDER BY completed_at DESC LIMIT 1",
                 (u["id"], k), one=True)
        out.append({"key": k, "name": t["name"], "framework": t["framework"], "desc": t["desc"],
                    "minutes": t["minutes"], "icon": t["icon"], "total": len(t["items"]),
                    "answered": len(op["answers"]) if op else 0, "in_progress": bool(op),
                    "done": bool(last), "completed_at": last["completed_at"] if last else None,
                    "summary": last["result"]["summary"] if last else None})
    return jsonify(out)


@app.get("/api/assessments/<key>")
@need("siswa", active=True)
def assessment_get(u, key):
    if key not in TESTS:
        return err("Asesmen tidak dikenal.", 404)
    op = open_attempt(u["id"], key)
    if not op:
        aid = x("INSERT INTO assessment_attempts(user_id, test_key) VALUES(?,?)", (u["id"], key))
        op = q("SELECT * FROM assessment_attempts WHERE id=?", (aid,), one=True)
        log_event(u, "assessment_started")
    t = TESTS[key]
    return jsonify({"key": key, "name": t["name"], "framework": t["framework"], "items": t["items"],
                    "answers": op["answers"], "current_index": op["current_index"], "attempt_id": op["id"]})


@app.put("/api/assessments/<key>/answers")
@need("siswa", active=True)
def assessment_save(u, key):
    if key not in TESTS:
        return err("Asesmen tidak dikenal.", 404)
    d = request.get_json(force=True) or {}
    op = open_attempt(u["id"], key)
    if not op:
        return err("Tidak ada pengerjaan aktif.", 404)
    valid_ids = {i["id"] for i in TESTS[key]["items"]}
    answers = op["answers"]
    for k, v in (d.get("answers") or {}).items():
        if k in valid_ids and v in (1, 2, 3, 4, 5):
            answers[k] = v
    idx = max(0, min(int(d.get("current_index", op["current_index"])), len(valid_ids) - 1))
    x("UPDATE assessment_attempts SET answers=?, current_index=? WHERE id=?", (json.dumps(answers), idx, op["id"]))
    return jsonify({"ok": True, "answered": len(answers)})


@app.post("/api/assessments/<key>/complete")
@need("siswa", active=True)
def assessment_complete(u, key):
    if key not in TESTS:
        return err("Asesmen tidak dikenal.", 404)
    op = open_attempt(u["id"], key)
    if not op:
        return err("Tidak ada pengerjaan aktif.", 404)
    missing = [i["id"] for i in TESTS[key]["items"] if i["id"] not in op["answers"]]
    if missing:
        return err("Masih ada butir yang belum dijawab.", 400, missing=missing)
    result = engine.score_test(key, op["answers"])
    x("UPDATE assessment_attempts SET status='completed', result=?, completed_at=? WHERE id=?",
      (json.dumps(result), now(), op["id"]))
    log_event(u, "assessment_completed")
    n = len(completed_results(u["id"]))
    if n >= 2:
        log_event(u, "profile_generated")
    return jsonify({"result": result, "completed_count": n})


@app.get("/api/assessments/<key>/result")
@need("siswa", active=True)
def assessment_result(u, key):
    rs = q("SELECT result, completed_at FROM assessment_attempts WHERE user_id=? AND test_key=? AND status='completed' ORDER BY completed_at DESC",
           (u["id"], key))
    if not rs:
        return err("Belum ada hasil.", 404)
    return jsonify({"key": key, "name": TESTS[key]["name"], "latest": rs[0], "history": rs[1:]})


@app.post("/api/assessments/<key>/retake")
@need("siswa", active=True)
def assessment_retake(u, key):
    if key not in TESTS:
        return err("Asesmen tidak dikenal.", 404)
    x("DELETE FROM assessment_attempts WHERE user_id=? AND test_key=? AND status='in_progress'", (u["id"], key))
    x("INSERT INTO assessment_attempts(user_id, test_key) VALUES(?,?)", (u["id"], key))
    log_event(u, "assessment_started")
    return jsonify({"ok": True})

# ================================================================= profil & roadmap (FR-004, FR-005, FR-011)

@app.get("/api/profile")
@need("siswa", active=True)
def profile(u):
    return jsonify(engine.build_profile(completed_results(u["id"])))


def _generate_roadmap(u):
    res = completed_results(u["id"])
    data, steps = engine.build_roadmap(u, res, all_careers(), all_majors())
    x("UPDATE roadmaps SET is_current=0 WHERE user_id=?", (u["id"],))
    rid = x("INSERT INTO roadmaps(user_id, data, based_on) VALUES(?,?,?)",
            (u["id"], json.dumps(data), json.dumps(sorted(res))))
    for i, s in enumerate(steps):
        x("INSERT INTO roadmap_steps(roadmap_id, idx, title, description, period, tasks, done) VALUES(?,?,?,?,?,?,?)",
          (rid, i, s["title"], s["description"], s["period"], json.dumps(s["tasks"]), 1 if s["done"] else 0))
    return current_roadmap(u["id"])


@app.get("/api/roadmap")
@need("siswa", active=True)
def roadmap(u):
    res = completed_results(u["id"])
    prof = engine.build_profile(res)
    if not prof["available"]:
        return jsonify({"available": False, "message": prof["message"], "missing": prof["missing"]})
    rd = current_roadmap(u["id"])
    if not rd:
        rd = _generate_roadmap(u)
    rd["outdated"] = sorted(res) != rd["based_on"]
    return jsonify({"available": True, "roadmap": rd, "profile_label": prof["label"]})


@app.post("/api/roadmap/regenerate")
@need("siswa", active=True)
def roadmap_regen(u):
    if len(completed_results(u["id"])) < 2:
        return err("Butuh minimal 2 asesmen.")
    old = current_roadmap(u["id"])
    rd = _generate_roadmap(u)
    if old:   # bawa progres tugas yang sama
        done_txt = {t["text"] for s in old["steps"] for t in s["tasks"] if t["done"]}
        for s in rd["steps"]:
            tasks = [{**t, "done": t["done"] or t["text"] in done_txt} for t in s["tasks"]]
            x("UPDATE roadmap_steps SET tasks=?, done=? WHERE id=?",
              (json.dumps(tasks), 1 if all(t["done"] for t in tasks) else 0, s["id"]))
        if old["is_saved"]:
            x("UPDATE roadmaps SET is_saved=1, saved_at=? WHERE id=?", (now(), rd["id"]))
    return jsonify({"roadmap": current_roadmap(u["id"])})


@app.post("/api/roadmap/save")
@need("siswa", active=True)
def roadmap_save(u):
    rd = current_roadmap(u["id"])
    if not rd:
        return err("Roadmap belum dibuat.", 404)
    first = not q("SELECT 1 FROM roadmaps WHERE user_id=? AND is_saved=1", (u["id"],), one=True)
    x("UPDATE roadmaps SET is_saved=1, saved_at=? WHERE id=?", (now(), rd["id"]))
    log_event(u, "roadmap_saved")
    return jsonify({"ok": True, "first": first})


@app.patch("/api/roadmap/steps/<int:sid>")
@need("siswa", active=True)
def roadmap_step(u, sid):
    s = q("""SELECT rs.* FROM roadmap_steps rs JOIN roadmaps r ON r.id=rs.roadmap_id
             WHERE rs.id=? AND r.user_id=?""", (sid, u["id"]), one=True)
    if not s:
        return err("Langkah tidak ditemukan.", 404)
    d = request.get_json(force=True) or {}
    tasks = s["tasks"]
    i = d.get("task_index")
    if isinstance(i, int) and 0 <= i < len(tasks):
        tasks[i]["done"] = bool(d.get("done"))
    all_done = all(t["done"] for t in tasks)
    x("UPDATE roadmap_steps SET tasks=?, done=?, done_at=? WHERE id=?",
      (json.dumps(tasks), 1 if all_done else 0, now() if all_done else None, sid))
    if all_done and not s["done"]:
        log_event(u, "roadmap_step_completed")
    return jsonify({"roadmap": current_roadmap(u["id"])})

# ================================================================= dashboard siswa

@app.get("/api/dashboard")
@need("siswa")
def dashboard(u):
    if u["status"] != "active":
        return jsonify({"locked": True})
    res, rd, score, _ = student_stats(u)
    last_msg = q("SELECT text, created_at FROM chat_messages WHERE user_id=? AND sender='user' ORDER BY id DESC LIMIT 1", (u["id"],), one=True)
    nexts = []
    missing = [k for k in TESTS if k not in res]
    for k in missing[:1]:
        op = open_attempt(u["id"], k)
        nexts.append({"type": "assessment", "key": k, "title": f"{'Lanjutkan' if op else 'Mulai'} {TESTS[k]['name']}",
                      "desc": f"{TESTS[k]['framework']} · ±{TESTS[k]['minutes']} menit"})
    if len(res) >= 2 and not (rd and rd["is_saved"]):
        nexts.append({"type": "roadmap", "title": "Simpan Career Roadmap pertamamu", "desc": "Rekomendasi jurusan & profesi sudah siap."})
    if rd:
        for s in rd["steps"]:
            if not s["done"]:
                nexts.append({"type": "step", "title": f"Langkah berikutnya: {s['title']}", "desc": s["description"]})
                break
    survey_due = False
    prof_at = q("SELECT MIN(completed_at) m FROM (SELECT completed_at FROM assessment_attempts WHERE user_id=? AND status='completed' ORDER BY completed_at LIMIT 2)", (u["id"],), one=True)
    if len(res) >= 2 and prof_at and prof_at["m"]:
        due = engine._dt(prof_at["m"]) + timedelta(days=28)
        answered = q("SELECT 1 FROM clarity_surveys WHERE user_id=? AND phase='followup'", (u["id"],), one=True)
        survey_due = datetime.now() >= due and not answered
    recs = []
    if res:
        for c in engine.rank(all_careers(), res)[:3]:
            recs.append({"id": c["id"], "name": c["name"], "field": c["field"], "match": c["match"]})
    return jsonify({"locked": False, "score": score, "assess_done": len(res), "assess_total": 4,
                    "missing": [{"key": k, "name": TESTS[k]["name"]} for k in missing],
                    "roadmap": {"progress": rd["progress"], "is_saved": bool(rd["is_saved"]),
                                "steps_done": sum(1 for s in rd["steps"] if s["done"]), "steps_total": len(rd["steps"])} if rd else None,
                    "last_chat": last_msg, "next": nexts[:3], "careers": recs, "survey_due": survey_due})

# ================================================================= AI Companion (FR-006, FR-007, FR-020)

def chat_context(u):
    res = completed_results(u["id"])
    rd = current_roadmap(u["id"])
    hist = q("SELECT sender, text FROM chat_messages WHERE user_id=? AND kind!='crisis' ORDER BY id DESC LIMIT 20", (u["id"],))[::-1]
    return {"user": u, "profile": engine.build_profile(res),
            "ranked_careers": engine.rank(all_careers(), res) if res else all_careers(),  # kecocokan sudah ada sejak 1 asesmen
            "ranked_majors": engine.rank(all_majors(), res) if res else all_majors(),
            "history": hist, "roadmap": rd["data"] if rd else None,
            "scholarships": q("SELECT * FROM scholarships")}


@app.get("/api/chat")
@need("siswa", active=True)
def chat_get(u):
    msgs = q("""SELECT id, session_id, sender, text, sources, kind, feedback, created_at FROM chat_messages
                WHERE user_id=? ORDER BY id DESC LIMIT 60""", (u["id"],))[::-1]
    sessions = q("""SELECT s.id, s.topic, s.started_at, s.last_at, COUNT(m.id) AS n FROM chat_sessions s
                    LEFT JOIN chat_messages m ON m.session_id=s.id WHERE s.user_id=?
                    GROUP BY s.id ORDER BY s.last_at DESC LIMIT 20""", (u["id"],))
    has_profile = len(completed_results(u["id"])) >= 2
    return jsonify({"messages": msgs, "sessions": sessions, "has_profile": has_profile})


@app.post("/api/chat")
@need("siswa", active=True)
def chat_post(u):
    d = request.get_json(force=True) or {}
    text = (d.get("text") or "").strip()[:1000]
    if not text:
        return err("Pesan kosong.")
    # sesi baru bila jeda > 30 menit (M4)
    s = q("SELECT * FROM chat_sessions WHERE user_id=? ORDER BY last_at DESC LIMIT 1", (u["id"],), one=True)
    if not s or datetime.now() - engine._dt(s["last_at"]) > timedelta(minutes=30):
        sid = x("INSERT INTO chat_sessions(user_id, topic) VALUES(?,?)", (u["id"], text[:60]))
        log_event(u, "chat_session_started")
    else:
        sid = s["id"]
    x("UPDATE chat_sessions SET last_at=? WHERE id=?", (now(), sid))

    # FR-007: sinyal krisis -> layar bantuan, tanpa saran karier, isi pesan tidak disimpan
    if engine.is_crisis(text):
        x("INSERT INTO chat_messages(session_id,user_id,sender,text,kind) VALUES(?,?,?,?,?)",
          (sid, u["id"], "user", "[pesan disembunyikan — sinyal krisis]", "crisis"))
        log_event(u, "crisis_screen_shown")
        reply = ("Terima kasih sudah cerita. Kamu tidak sendirian. Saat ini aku tidak akan membahas karier dulu — "
                 "yang paling penting adalah kamu aman. Hubungi salah satu layanan di atas, atau temui guru BK atau "
                 "orang dewasa yang kamu percaya hari ini.")
        mid = x("INSERT INTO chat_messages(session_id,user_id,sender,text,kind,model) VALUES(?,?,?,?,?,?)",
                (sid, u["id"], "ai", reply, "crisis", "safety-rules-v1"))
        return jsonify({"crisis": True, "help": engine.HELP_LINES,
                        "message": {"id": mid, "sender": "ai", "text": reply, "sources": [], "kind": "crisis"}})

    x("INSERT INTO chat_messages(session_id,user_id,sender,text) VALUES(?,?,?,?)", (sid, u["id"], "user", text))
    ctx = chat_context(u)
    ctx["history"] = ctx["history"][:-1]   # tanpa pesan barusan
    rule = engine.companion_reply(text, ctx)
    model = "arka-rules-v1"
    if rule["kind"] == "normal":
        llm = engine.llm_reply(text, ctx)
        if llm:
            rule = {**rule, "text": llm["text"]}
            model = llm["model"]
    mid = x("INSERT INTO chat_messages(session_id,user_id,sender,text,sources,kind,model) VALUES(?,?,?,?,?,?,?)",
            (sid, u["id"], "ai", rule["text"], json.dumps(rule["sources"]), rule["kind"], model))
    return jsonify({"crisis": False, "message": {"id": mid, "sender": "ai", "text": rule["text"],
                                                  "sources": rule["sources"], "kind": rule["kind"]}})


@app.post("/api/chat/<int:mid>/feedback")
@need("siswa", active=True)
def chat_feedback(u, mid):
    d = request.get_json(force=True) or {}
    v = d.get("value")
    if v not in ("helpful", "inaccurate"):
        return err("Nilai tidak valid.")
    m = q("SELECT id FROM chat_messages WHERE id=? AND user_id=? AND sender='ai'", (mid, u["id"]), one=True)
    if not m:
        return err("Pesan tidak ditemukan.", 404)
    x("UPDATE chat_messages SET feedback=?, review_status=? WHERE id=?",
      (v, "queued" if v == "inaccurate" else None, mid))
    log_event(u, "ai_feedback_given")
    return jsonify({"ok": True})

# ================================================================= direktori (FR-013)

@app.get("/api/directory")
@need("siswa", active=True)
def directory(u):
    kind = request.args.get("type", "careers")
    term = (request.args.get("q") or "").strip().lower()
    field = request.args.get("field") or ""
    res = completed_results(u["id"])
    if kind == "scholarships":
        items = q("SELECT * FROM scholarships")
        items = [s for s in items if not term or term in (s["name"] + s["description"] + s["provider"]).lower()]
        return jsonify({"items": items, "fields": [], "sorted_by_match": False})
    base = all_careers() if kind == "careers" else all_majors()
    fields = sorted({i["field"] for i in base})
    items = [i for i in base
             if (not term or term in (i["name"] + " " + i["description"] + " " + i["field"]).lower()
                 or any(term in s.lower() for s in i.get("skills", [])))
             and (not field or i["field"] == field)]
    sorted_by = len(res) >= 1
    if sorted_by:
        items = engine.rank(items, res)
    suggestions = [] if items else ["teknologi", "kesehatan", "desain", "bisnis"]
    return jsonify({"items": items, "fields": fields, "sorted_by_match": sorted_by, "suggestions": suggestions})


@app.get("/api/directory/<kind>/<int:iid>")
@need("siswa", active=True)
def directory_item(u, kind, iid):
    table = {"careers": "careers", "majors": "majors"}.get(kind)
    if not table:
        return err("Tidak dikenal.", 404)
    it = q(f"SELECT * FROM {table} WHERE id=?", (iid,), one=True)
    if not it:
        return err("Tidak ditemukan.", 404)
    res = completed_results(u["id"])
    if table == "careers":
        log_event(u, "career_viewed")
    if res:
        sc, rs = engine.match(it, res)
        it["match"], it["reasons"] = sc, rs
    if table == "careers":
        it["related_majors"] = q(f"SELECT id, name FROM majors WHERE name IN ({','.join('?' * len(it['majors']))})", it["majors"]) if it["majors"] else []
    else:
        it["related_careers"] = [c for c in all_careers() if it["name"] in c["majors"]]
    return jsonify(it)

# ================================================================= hapus akun & ekspor (FR-010)

@app.get("/api/account/export")
@need()
def account_export(u):
    data = {"akun": public_user(u),
            "asesmen": q("SELECT test_key, answers, result, status, started_at, completed_at FROM assessment_attempts WHERE user_id=?", (u["id"],)),
            "roadmap": current_roadmap(u["id"]),
            "percakapan": q("SELECT sender, text, created_at FROM chat_messages WHERE user_id=?", (u["id"],))}
    resp = jsonify(data)
    resp.headers["Content-Disposition"] = "attachment; filename=data-arka.json"
    return resp


@app.post("/api/account/delete/request")
@need()
def delete_request(u):
    code = f"{secrets.randbelow(10**6):06d}"
    x("INSERT INTO deletion_requests(user_id, code) VALUES(?,?)", (u["id"], code))
    to, who = u["email"], "kamu"
    if u["role"] == "siswa" and (age_of(u["birth_date"]) or 99) < 18:
        c = q("SELECT parent_contact FROM consents WHERE student_id=? AND status='approved' ORDER BY id DESC LIMIT 1", (u["id"],), one=True)
        if c:
            to, who = c["parent_contact"], "orang tua/wali"
    send_mail(to, "Kode konfirmasi hapus akun ARKA",
              f"Ada permintaan menghapus akun ARKA milik {u['name']}. Kode konfirmasi: {code}. "
              "Abaikan email ini bila Anda tidak memintanya.")
    return jsonify({"ok": True, "sent_to": who})


@app.post("/api/account/delete/confirm")
@need()
def delete_confirm(u):
    d = request.get_json(force=True) or {}
    r = q("SELECT * FROM deletion_requests WHERE user_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (u["id"],), one=True)
    if not r or (d.get("code") or "").strip() != r["code"]:
        return err("Kode konfirmasi salah.")
    purge = (datetime.now() + timedelta(days=30)).isoformat(timespec="seconds")
    x("UPDATE deletion_requests SET status='confirmed', confirmed_at=?, purge_after=? WHERE id=?", (now(), purge, r["id"]))
    x("UPDATE users SET status='deleted', deleted_at=? WHERE id=?", (now(), u["id"]))
    log_event(u, "account_deletion_requested")
    session.clear()
    return jsonify({"ok": True, "purge_before": purge})


def purge_due(conn):
    """Hapus permanen akun yang masa tunggunya habis (jalankan harian lewat cron)."""
    ids = [r[0] for r in conn.execute(
        "SELECT user_id FROM deletion_requests WHERE status='confirmed' AND purge_after<=?", (now(),))]
    for uid in ids:
        conn.execute("DELETE FROM users WHERE id=?", (uid,))   # CASCADE ke asesmen, chat, roadmap, catatan
    conn.commit()
    return len(ids)

# ================================================================= Guru BK (FR-008, FR-009, FR-014, FR-015)

def short_label(key, r):
    if not r:
        return None
    from data import RIASEC as RI, TALENTS as TA, VALUES as VA
    if key == "minat":
        return "-".join(RI[c] for c in r["top"][:2])
    if key == "bakat":
        return TA[r["top"][0]]
    if key == "nilai":
        return VA[r["top"][0]]
    return r.get("type")


def bk_student_or_403(u, sid):
    s = q("SELECT * FROM users WHERE id=? AND role='siswa'", (sid,), one=True)
    if not s or s["school_id"] != u["school_id"] or s["status"] != "active":
        audit(u, "open_student", f"student:{sid}", False)
        return None
    audit(u, "open_student", f"student:{sid}", True)
    return s


@app.get("/api/bk/students")
@need("guru_bk", "kepsek")
def bk_students(u):
    log_event(u, "dashboard_opened")
    cls, tag, term = request.args.get("class") or "", request.args.get("tag") or "", (request.args.get("q") or "").lower()
    students = q("SELECT * FROM users WHERE role='siswa' AND status='active' AND school_id=? ORDER BY name", (u["school_id"],))
    pending = q("SELECT COUNT(*) n FROM users WHERE role='siswa' AND status='pending_consent' AND school_id=?", (u["school_id"],), one=True)["n"]
    out = []
    for s in students:
        res, rd, score, tags = student_stats(s)
        out.append({"id": s["id"], "name": s["name"], "class_name": s["class_name"] or f"Kelas {s['grade']}",
                    "assess_done": len(res), "score": score, "tags": tags,
                    "roadmap_saved": bool(rd and rd["is_saved"]), "last_active_at": s["last_active_at"]})
    classes = sorted({o["class_name"] for o in out})
    all_tags = sorted({t for o in out for t in o["tags"]})
    total = len(out)
    stats = {"total": total, "pending_consent": pending,
             "avg_score": round(sum(o["score"] for o in out) / total) if total else 0,
             "assess_2plus": sum(1 for o in out if o["assess_done"] >= 2),
             "need_attention": sum(1 for o in out if o["tags"]),
             "no_assessment": sum(1 for o in out if o["assess_done"] == 0)}
    filtered = [o for o in out if (not cls or o["class_name"] == cls) and (not tag or tag in o["tags"])
                and (not term or term in o["name"].lower())]
    filtered.sort(key=lambda o: (-len(o["tags"]), o["score"]))
    school = q("SELECT name, invite_code FROM schools WHERE id=?", (u["school_id"],), one=True)
    return jsonify({"students": filtered, "classes": classes, "tags": all_tags, "stats": stats, "school": school})


@app.get("/api/bk/students/<int:sid>")
@need("guru_bk", "kepsek")
def bk_student(u, sid):
    s = bk_student_or_403(u, sid)
    if not s:
        return err("Akses ditolak: siswa ini bukan siswa asuhan Anda.", 403)
    log_event(u, "student_detail_opened")
    res, rd, score, tags = student_stats(s)
    prof = engine.build_profile(res)
    # FR-009: hanya profil, status asesmen, dan roadmap. Isi percakapan TIDAK dikirim.
    return jsonify({
        "student": {"id": s["id"], "name": s["name"], "class_name": s["class_name"], "grade": s["grade"],
                    "interests": s["interests"], "concern": s["concern"], "last_active_at": s["last_active_at"]},
        "score": score, "tags": tags, "profile": prof,
        "assessments": [{"key": k, "name": TESTS[k]["name"], "done": k in res,
                         "label": short_label(k, res.get(k))} for k in TESTS],
        "roadmap": {"data": rd["data"], "progress": rd["progress"], "is_saved": bool(rd["is_saved"]),
                    "steps": [{"title": st["title"], "done": bool(st["done"]), "period": st["period"]} for st in rd["steps"]]} if rd else None,
    })


@app.get("/api/bk/students/<int:sid>/summary")
@need("guru_bk", "kepsek")
def bk_summary(u, sid):
    s = bk_student_or_403(u, sid)
    if not s:
        return err("Akses ditolak.", 403)
    res, rd, score, tags = student_stats(s)
    prof = engine.build_profile(res)
    return jsonify(engine.counselor_summary(s, prof, rd, score, tags, last_completion(s["id"])))


@app.get("/api/bk/students/<int:sid>/notes")
@need("guru_bk", "kepsek")
def bk_notes(u, sid):
    if not bk_student_or_403(u, sid):
        return err("Akses ditolak.", 403)
    return jsonify(q("SELECT id, text, created_at FROM counseling_notes WHERE student_id=? AND counselor_id=? ORDER BY id DESC", (sid, u["id"])))


@app.post("/api/bk/students/<int:sid>/notes")
@need("guru_bk", "kepsek")
def bk_note_add(u, sid):
    if not bk_student_or_403(u, sid):
        return err("Akses ditolak.", 403)
    text = ((request.get_json(force=True) or {}).get("text") or "").strip()
    if not text:
        return err("Catatan kosong.")
    x("INSERT INTO counseling_notes(student_id, counselor_id, text) VALUES(?,?,?)", (sid, u["id"], text[:4000]))
    log_event(u, "counseling_note_saved")
    return jsonify(q("SELECT id, text, created_at FROM counseling_notes WHERE student_id=? AND counselor_id=? ORDER BY id DESC", (sid, u["id"])))

# ================================================================= laporan agregat (FR-018, FR-019)

MIN_GROUP = 10


@app.get("/api/report")
@need("kepsek", "guru_bk")
def report(u):
    cls = request.args.get("class") or ""
    dfrom = request.args.get("from") or "0000-01-01"
    dto = (request.args.get("to") or "9999-12-31") + "T23:59:59"
    students = q("SELECT * FROM users WHERE role='siswa' AND status='active' AND school_id=?", (u["school_id"],))
    school = q("SELECT name, city FROM schools WHERE id=?", (u["school_id"],), one=True)
    classes = sorted({s["class_name"] or f"Kelas {s['grade']}" for s in students})
    if cls:
        students = [s for s in students if (s["class_name"] or f"Kelas {s['grade']}") == cls]
    rows_ = []
    for s in students:
        done = q("""SELECT test_key, result FROM assessment_attempts WHERE user_id=? AND status='completed'
                    AND completed_at BETWEEN ? AND ?""", (s["id"], dfrom, dto))
        keys = {d["test_key"] for d in done}
        minat = next((d["result"] for d in done if d["test_key"] == "minat"), None)
        _, _, score, _ = student_stats(s)
        rows_.append({"class": s["class_name"] or f"Kelas {s['grade']}", "n_done": len(keys),
                      "interest": (s["interests"] or [None])[0],
                      "top": minat["top"][0] if minat else None, "score": score})
    n = len(rows_)
    hidden = n < MIN_GROUP
    by_class = []
    for c in sorted({r["class"] for r in rows_}):
        g = [r for r in rows_ if r["class"] == c]
        if len(g) < MIN_GROUP:
            by_class.append({"class": c, "hidden": True, "n": None})
        else:
            by_class.append({"class": c, "hidden": False, "n": len(g),
                             "pct_2plus": round(sum(1 for r in g if r["n_done"] >= 2) / len(g) * 100),
                             "avg_score": round(sum(r["score"] for r in g) / len(g))})
    out = {"school": school, "classes": classes, "min_group": MIN_GROUP, "hidden": hidden,
           "filters": {"class": cls, "from": request.args.get("from"), "to": request.args.get("to")},
           "generated_at": now(), "by_class": by_class}
    if not hidden:
        with_minat = [r for r in rows_ if r["top"]]
        out.update({
            "n": n,
            "pct_any": round(sum(1 for r in rows_ if r["n_done"] >= 1) / n * 100),
            "pct_2plus": round(sum(1 for r in rows_ if r["n_done"] >= 2) / n * 100),
            "pct_all4": round(sum(1 for r in rows_ if r["n_done"] == 4) / n * 100),
            "avg_score": round(sum(r["score"] for r in rows_) / n),
            "score_dist": [sum(1 for r in rows_ if lo <= r["score"] <= hi) for lo, hi in
                           ((0, 20), (21, 40), (41, 60), (61, 80), (81, 100))],
            "riasec": [{"code": k, "label": v, "pct": round(sum(1 for r in with_minat if r["top"] == k) / len(with_minat) * 100) if with_minat else 0}
                       for k, v in RIASEC.items()],
            "riasec_n": len(with_minat),
        })
    groups = [("Teknologi", ("Teknologi", "Teknik")), ("Bisnis", ("Bisnis", "Hukum")), ("Kesehatan", ("Kesehatan", "Olahraga")),
              ("Seni & Desain", ("Seni & Desain", "Media", "Kuliner"))]
    with_int = [r for r in rows_ if r["interest"]]
    dist = []
    for label, keys in groups:
        dist.append({"label": label, "n": sum(1 for r in with_int if r["interest"] in keys)})
    dist.append({"label": "Lainnya", "n": len(with_int) - sum(d_["n"] for d_ in dist)})
    out["interests"] = [{**d_, "pct": round(d_["n"] / len(with_int) * 100) if with_int else 0} for d_ in dist]
    out["interests_n"] = len(with_int)
    return jsonify(out)


# ================================================================= tambahan untuk alur prototipe

DEMO_ACCOUNTS = {"guru_bk": "bk@harapan.sch.id", "siswa": "arya@siswa.id"}


@app.post("/api/auth/demo-switch")
@need()
def demo_switch(u):
    """Tombol 'Lihat sebagai Guru BK / Siswa' dari prototipe. Hanya aktif di mode demo."""
    if not DEMO_MODE:
        return err("Fitur ini hanya ada di mode demo.", 403)
    to = (request.get_json(force=True) or {}).get("to")
    email = DEMO_ACCOUNTS.get(to)
    t = q("SELECT * FROM users WHERE email=?", (email,), one=True) if email else None
    if not t:
        return err("Akun demo tidak ditemukan.", 404)
    session["uid"] = t["id"]
    return jsonify({"user": public_user(t)})


@app.get("/api/activity")
@need("siswa")
def activity(u):
    """Data tambahan dashboard prototipe: aktivitas terbaru & milestone."""
    acts = []
    for r in q("SELECT test_key, completed_at FROM assessment_attempts WHERE user_id=? AND status='completed'", (u["id"],)):
        acts.append({"text": f"Menyelesaikan {TESTS[r['test_key']]['name'].lower()} ({TESTS[r['test_key']]['framework']})", "at": r["completed_at"], "kind": "assess"})
    for r in q("SELECT topic, started_at FROM chat_sessions WHERE user_id=?", (u["id"],)):
        acts.append({"text": f"Chat AI: {r['topic'] or 'sesi baru'}", "at": r["started_at"], "kind": "chat"})
    for r in q("SELECT saved_at FROM roadmaps WHERE user_id=? AND is_saved=1 AND saved_at IS NOT NULL", (u["id"],)):
        acts.append({"text": "Menyimpan Career Roadmap", "at": r["saved_at"], "kind": "roadmap"})
    for r in q("""SELECT b.created_at, m.name FROM mentor_bookings b JOIN mentors m ON m.id=b.mentor_id WHERE b.user_id=?""", (u["id"],)):
        acts.append({"text": f"Booking sesi mentoring dengan {r['name']}", "at": r["created_at"], "kind": "mentor"})
    acts.append({"text": "Mendaftar akun ARKA dan melengkapi profil", "at": u["created_at"], "kind": "join"})
    acts.sort(key=lambda a: str(a["at"]), reverse=True)
    res = completed_results(u["id"])
    rd = current_roadmap(u["id"])
    views = q("SELECT COUNT(*) n FROM events WHERE pseudo_id=? AND event='career_viewed'", (u["pseudo_id"],), one=True)["n"]
    booked = q("SELECT COUNT(*) n FROM mentor_bookings WHERE user_id=?", (u["id"],), one=True)["n"]
    milestones = [
        {"text": "Selesaikan asesmen minat", "done": "minat" in res},
        {"text": "Selesaikan asesmen bakat", "done": "bakat" in res},
        {"text": "Buat roadmap pertama", "done": bool(rd and rd["is_saved"])},
        {"text": "Booking sesi mentoring", "done": booked > 0},
        {"text": f"Eksplorasi 5 profesi ({min(views, 5)}/5)", "done": views >= 5},
    ]
    return jsonify({"activities": acts[:6], "milestones": milestones, "bookings": booked})


@app.get("/api/mentors")
@need()
def mentors(u):
    return jsonify(q("SELECT * FROM mentors ORDER BY rating DESC, id"))


@app.get("/api/mentoring/bookings")
@need("siswa")
def bookings(u):
    return jsonify(q("""SELECT b.*, m.name AS mentor_name FROM mentor_bookings b JOIN mentors m ON m.id=b.mentor_id
                        WHERE b.user_id=? ORDER BY b.id DESC""", (u["id"],)))


@app.post("/api/mentoring/bookings")
@need("siswa")
def booking_create(u):
    d = request.get_json(force=True) or {}
    m = q("SELECT * FROM mentors WHERE id=?", (d.get("mentor_id"),), one=True)
    if not m:
        return err("Mentor tidak ditemukan.", 404)
    if not d.get("date") or not d.get("time"):
        return err("Pilih tanggal dan waktu sesi.")
    if d["date"] < date.today().isoformat():
        return err("Tanggal sesi tidak boleh di masa lalu.")
    bid = x("INSERT INTO mentor_bookings(user_id, mentor_id, date, time, payment) VALUES(?,?,?,?,?)",
            (u["id"], m["id"], d["date"], d["time"], d.get("payment") or "QRIS"))
    log_event(u, "mentor_booked")
    return jsonify(q("SELECT * FROM mentor_bookings WHERE id=?", (bid,), one=True))


@app.patch("/api/mentoring/bookings/<int:bid>")
@need("siswa")
def booking_update(u, bid):
    b = q("SELECT * FROM mentor_bookings WHERE id=? AND user_id=?", (bid, u["id"]), one=True)
    if not b:
        return err("Booking tidak ditemukan.", 404)
    d = request.get_json(force=True) or {}
    x("UPDATE mentor_bookings SET status=?, notes=?, rating=?, review=? WHERE id=?",
      (d.get("status", b["status"]), d.get("notes", b["notes"]), d.get("rating", b["rating"]),
       d.get("review", b["review"]), bid))
    return jsonify(q("SELECT * FROM mentor_bookings WHERE id=?", (bid,), one=True))


@app.get("/api/bk/overview")
@need("guru_bk", "kepsek")
def bk_overview(u):
    n = q("""SELECT COUNT(*) n FROM mentor_bookings b JOIN users s ON s.id=b.user_id
             WHERE s.school_id=? AND b.created_at >= date('now','start of month')""", (u["school_id"],), one=True)["n"]
    return jsonify({"mentoring_month": n})


# ================================================================= main

def ensure_db():
    if not dbm.DB_PATH.exists():
        import seed
        seed.main()
    with dbm.connect() as c:
        dbm.init_schema(c)
        purge_due(c)


if __name__ == "__main__":
    ensure_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  ARKA berjalan di http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
