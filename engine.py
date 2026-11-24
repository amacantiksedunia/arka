"""
Logika inti ARKA:
- penilaian asesmen  -> score_test()
- profil potensi diri -> build_profile()     (FR-004)
- skor kesiapan & tag prioritas -> readiness(), priority_tags()   (FR-008, OQ-6)
- Career Roadmap -> build_roadmap()          (FR-005)
- AI Career Companion -> companion_reply()   (FR-006, FR-007)
- ringkasan untuk guru BK -> counselor_summary()  (FR-014)

Semua aturan skor dan kata kunci krisis di sini adalah usulan tim dan WAJIB
ditinjau psikolog mitra sebelum dipakai dengan siswa nyata (PRD OQ-6, D1).
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta

from data import (PERSONALITY_DIMS, RIASEC, RIASEC_DESC, TALENTS, TESTS, VALUES)

DISCLAIMER = ("Hasil ini adalah indikasi berdasarkan jawabanmu, bukan diagnosis "
              "dan bukan penentu jurusan. Diskusikan dengan guru BK sebelum memutuskan.")

# ---------------------------------------------------------------- asesmen

def score_test(test_key, answers):
    """answers: {item_id: 1..5} -> dict hasil."""
    test = TESTS[test_key]
    buckets = {}
    for it in test["items"]:
        v = answers.get(it["id"])
        if v is None:
            continue
        buckets.setdefault(it["dim"], []).append(int(v))
    pct = {d: round((sum(v) / len(v) - 1) / 4 * 100) for d, v in buckets.items()}

    if test_key == "minat":
        ordered = sorted(RIASEC, key=lambda d: -pct.get(d, 0))
        return {"scores": {d: pct.get(d, 0) for d in RIASEC}, "top": ordered[:3],
                "code": "".join(ordered[:2]),
                "summary": f"Minat terkuatmu: {RIASEC[ordered[0]]} dan {RIASEC[ordered[1]]}."}
    if test_key == "bakat":
        ordered = sorted(TALENTS, key=lambda d: -pct.get(d, 0))
        return {"scores": {d: pct.get(d, 0) for d in TALENTS}, "top": ordered[:3],
                "summary": "Kekuatan alamimu: " + ", ".join(TALENTS[d] for d in ordered[:3]) + "."}
    if test_key == "nilai":
        ordered = sorted(VALUES, key=lambda d: -pct.get(d, 0))
        return {"scores": {d: pct.get(d, 0) for d in VALUES}, "top": ordered[:3],
                "summary": "Yang paling penting bagimu dalam bekerja: " + ", ".join(VALUES[d] for d in ordered[:3]) + "."}
    # kepribadian
    letters, dims = [], []
    for a, b, la, lb in PERSONALITY_DIMS:
        pa, pb = pct.get(a, 50), pct.get(b, 50)
        share_a = round(pa / (pa + pb) * 100) if (pa + pb) else 50
        letters.append(a if share_a >= 50 else b)
        dims.append({"left": la, "right": lb, "left_pct": share_a})
    labels = {"E": "suka berinteraksi", "I": "reflektif", "S": "praktis", "N": "imajinatif",
              "T": "logis", "F": "peduli", "J": "terencana", "P": "fleksibel"}
    return {"type": "".join(letters), "dims": dims,
            "summary": "Kecenderunganmu: " + ", ".join(labels[l] for l in letters) + "."}


def build_profile(completed):
    """completed: {test_key: result}. Butuh >= 2 asesmen (FR-004)."""
    done = list(completed)
    missing = [k for k in TESTS if k not in completed]
    if len(done) < 2:
        return {"available": False, "done": done, "missing": missing,
                "message": f"Selesaikan minimal 2 asesmen untuk membuat profil. Belum selesai: "
                           + ", ".join(TESTS[k]["name"] for k in missing) + "."}
    strengths = []
    if "minat" in completed:
        for d in completed["minat"]["top"][:2]:
            strengths.append(f"Minat {RIASEC[d]} — {RIASEC_DESC[d]}")
    if "bakat" in completed:
        strengths.append("Kecerdasan " + " & ".join(TALENTS[d] for d in completed["bakat"]["top"][:2]))
    if "nilai" in completed:
        strengths.append("Mengutamakan " + VALUES[completed["nilai"]["top"][0]].lower())
    if "kepribadian" in completed:
        strengths.append(completed["kepribadian"]["summary"])
    return {"available": True, "complete": len(missing) == 0,
            "label": "Lengkap" if not missing else "Sementara",
            "done": done, "missing": missing, "results": completed,
            "strengths": strengths, "disclaimer": DISCLAIMER}

# ---------------------------------------------------------------- kecocokan

def _riasec_fit(code, minat):
    if not minat:
        return None
    s = minat["scores"]
    return round(s.get(code[0], 0) * 0.65 + s.get(code[1], 0) * 0.35)


def _list_fit(tags, res):
    if not res or not tags:
        return None
    return round(sum(res["scores"].get(t, 0) for t in tags) / len(tags))


def match(item, completed):
    """Skor kecocokan 0-100 + alasan yang merujuk hasil asesmen."""
    parts, reasons = [], []
    rf = _riasec_fit(item["riasec"], completed.get("minat"))
    if rf is not None:
        parts.append((rf, 0.6))
        top = [d for d in item["riasec"] if completed["minat"]["scores"].get(d, 0) >= 60]
        if top:
            reasons.append("minat " + " & ".join(RIASEC[d] for d in top) + " kamu tinggi ("
                           + ", ".join(f"{completed['minat']['scores'][d]}%" for d in top) + ")")
    tf = _list_fit(item.get("talents"), completed.get("bakat"))
    if tf is not None:
        parts.append((tf, 0.25))
        strong = [t for t in item["talents"] if completed["bakat"]["scores"].get(t, 0) >= 60]
        if strong:
            reasons.append("kecerdasan " + " & ".join(TALENTS[t] for t in strong) + " menonjol")
    vf = _list_fit(item.get("values"), completed.get("nilai"))
    if vf is not None:
        parts.append((vf, 0.15))
        strong = [v for v in item.get("values", []) if v in completed["nilai"]["top"]]
        if strong:
            reasons.append("sejalan dengan nilai " + " & ".join(VALUES[v].lower() for v in strong))
    if not parts:
        return 0, []
    w = sum(p[1] for p in parts)
    return round(sum(p[0] * p[1] for p in parts) / w), reasons


def rank(items, completed):
    out = []
    for it in items:
        sc, rs = match(it, completed)
        out.append({**it, "match": sc, "reasons": rs})
    return sorted(out, key=lambda x: -x["match"])

# ---------------------------------------------------------------- roadmap

def build_roadmap(user, completed, careers, majors):
    ranked_c = rank(careers, completed)
    ranked_m = rank(majors, completed)
    top_c = [c for c in ranked_c if c["match"] >= 55][:4] or ranked_c[:3]
    top_m = [m for m in ranked_m if m["match"] >= 55][:4] or ranked_m[:3]
    note = None
    if len([c for c in ranked_c if c["match"] >= 55]) < 3:
        note = ("Database karier kami belum punya cukup profesi dengan kecocokan tinggi untuk "
                "profilmu. Rekomendasi di bawah adalah yang paling mendekati.")
    skills = []
    for c in top_c:
        for s in c["skills"]:
            if s not in skills:
                skills.append(s)
    def fmt(it):
        return {"id": it["id"], "name": it["name"], "field": it["field"], "match": it["match"],
                "reason": ("Cocok karena " + "; ".join(it["reasons"]) + ".") if it["reasons"]
                          else "Kecocokan dihitung dari kombinasi hasil asesmenmu."}
    m_names = [m["name"] for m in top_m[:3]]
    subjects = []
    for m in top_m[:3]:
        for s in m.get("subjects", []):
            if s not in subjects:
                subjects.append(s)
    grade = str(user.get("grade") or "11")
    steps = [
        ("Lengkapi Asesmen", "Kenali dirimu lewat 4 asesmen agar rekomendasi makin akurat.", "Minggu ini",
         [{"text": f"Selesaikan {TESTS[k]['name']}", "done": k in completed} for k in TESTS]),
        ("Pilih 2–3 Jurusan Target", "Bandingkan jurusan rekomendasi: " + ", ".join(m_names) + ".", "Bulan ini",
         [{"text": "Baca detail tiap jurusan di Direktori Karier", "done": False},
          {"text": "Tanya AI Companion perbedaan jurusan-jurusan itu", "done": False},
          {"text": "Diskusikan pilihanmu dengan guru BK", "done": False}]),
        ("Perkuat Mapel Pendukung", "Fokus pada " + (", ".join(subjects[:3]) or "mapel inti") + ".",
         "1 semester", [{"text": f"Targetkan nilai rapor {s} stabil/naik", "done": False} for s in subjects[:3]]
         or [{"text": "Jaga nilai rapor tetap stabil", "done": False}]),
        ("Bangun Skill & Pengalaman", "Mulai latih: " + ", ".join(skills[:3]) + ".", "6 bulan",
         [{"text": f"Ikuti kursus/ekskul terkait {skills[0]}", "done": False},
          {"text": "Buat 1 proyek kecil atau ikut lomba", "done": False},
          {"text": "Ngobrol dengan kakak kelas/alumni di bidang ini", "done": False}]),
        ("Siapkan Jalur Masuk Kampus", "Pahami SNBP, SNBT, dan jalur Mandiri kampus target.",
         "Kelas 12" if grade != "12" else "Semester ini",
         [{"text": "Cek syarat SNBP (nilai rapor) di laman resmi SNPMB", "done": False},
          {"text": "Latihan soal UTBK rutin", "done": False},
          {"text": "Catat jadwal pendaftaran kampus target", "done": False}]),
        ("Daftar & Mulai Kuliah", "Kirim pendaftaran dan siapkan rencana beasiswa bila perlu.", "Setelah lulus",
         [{"text": "Cari beasiswa yang sesuai (lihat Direktori)", "done": False},
          {"text": "Daftar di minimal 2 jalur", "done": False}]),
    ]
    data = {"majors": [fmt(m) for m in top_m], "careers": [fmt(c) for c in top_c],
            "skills": skills[:6], "note": note, "disclaimer": DISCLAIMER,
            "generated_at": datetime.now().isoformat(timespec="seconds")}
    return data, [{"title": t, "description": d, "period": p, "tasks": tk,
                   "done": all(x["done"] for x in tk)} for t, d, p, tk in steps]

# ---------------------------------------------------------------- kesiapan & prioritas

def readiness(n_done, roadmap_saved, step_pct, last_active):
    """Skor kesiapan karier 0-100 (usulan, menunggu persetujuan psikolog — OQ-6).
    Asesmen 60 + roadmap tersimpan 10 + progres langkah 20 + aktif 7 hari 10."""
    s = n_done * 15 + (10 if roadmap_saved else 0) + round(step_pct * 20)
    if last_active and datetime.now() - _dt(last_active) <= timedelta(days=7):
        s += 10
    return min(100, s)


def priority_tags(score, n_done, last_active):
    tags = []
    if n_done == 0:
        tags.append("Belum mulai asesmen")
    if last_active is None or datetime.now() - _dt(last_active) > timedelta(days=7):
        tags.append("Tidak aktif 7 hari")
    if score < 40:
        tags.append("Perlu perhatian")
    return tags


def _dt(s):
    return datetime.fromisoformat(str(s).replace("Z", ""))

# ---------------------------------------------------------------- companion

CRISIS_PATTERNS = [
    r"bunuh\s*diri", r"ingin\s*mati", r"pengen\s*mati", r"pingin\s*mati", r"mau\s*mati(?!\s*lampu)",
    r"mengakhiri\s*hidup", r"akhiri\s*hidup", r"menyakiti\s*diri", r"nyakitin\s*diri", r"melukai\s*diri",
    r"self[\s-]*harm", r"gak\s*mau\s*hidup", r"ga\s*mau\s*hidup", r"tidak\s*ingin\s*hidup", r"nggak\s*mau\s*hidup",
    r"capek\s*hidup", r"lelah\s*hidup", r"hidup\s*gak\s*ada\s*artinya", r"mending\s*(aku|saya)\s*(mati|ga\s*ada)",
    r"silet\s*tangan", r"suicide", r"kill\s*myself",
]
CRISIS_RE = re.compile("|".join(CRISIS_PATTERNS), re.I)
HELP_LINES = [
    {"name": "Healing119 (Kemenkes) — konseling kesehatan jiwa", "contact": "Telepon 119 ekstensi 8 · healing119.id"},
    {"name": "Layanan darurat", "contact": "112"},
    {"name": "Guru BK sekolahmu", "contact": "Temui langsung atau hubungi lewat wali kelas"},
]


def is_crisis(text):
    return bool(CRISIS_RE.search(text or ""))


TOPIC_WORDS = [
    "jurusan", "kuliah", "kampus", "karir", "karier", "kerja", "profesi", "pekerjaan", "cita", "skill",
    "keterampilan", "belajar", "snbt", "snbp", "utbk", "mandiri", "beasiswa", "sekolah", "kelas", "nilai",
    "rapor", "asesmen", "tes", "minat", "bakat", "kepribadian", "roadmap", "magang", "gaji", "prospek",
    "portofolio", "sertifikat", "kursus", "lomba", "olimpiade", "ptn", "pts", "universitas", "prodi",
    "mapel", "pelajaran", "masa depan", "bingung", "lulus", "guru bk", "ortu", "orang tua", "cocok",
    "dokter", "teknik", "desain", "bisnis", "hukum", "psikolog", "programmer", "informatika", "dkv",
]
GREET_RE = re.compile(r"^\s*(hai|halo|hello|hi|hey|pagi|siang|sore|malam|assalam)", re.I)


def _find_named(text, items):
    t = text.lower()
    found = []
    for it in items:
        n = it["name"].lower()
        short = n.split(" / ")[0].split(" (")[0]
        if n in t or short in t:
            found.append(it)
    return found


def companion_reply(text, ctx):
    """Mesin aturan (offline). ctx: user, profile, ranked_careers, ranked_majors,
    history (pesan sebelumnya), roadmap, scholarships.
    Return dict(text, sources, kind)."""
    t = text.lower().strip()
    name = ctx["user"].get("nickname") or ctx["user"]["name"].split()[0]
    prof = ctx["profile"]
    rc, rm = ctx["ranked_careers"], ctx["ranked_majors"]
    sources = []

    if GREET_RE.match(t) and len(t) < 25:
        return {"text": f"Halo {name}! 👋 Aku ARKA. Mau bahas jurusan, profesi, kampus, atau langkah di roadmap-mu hari ini?",
                "sources": [], "kind": "normal"}

    on_topic = any(w in t for w in TOPIC_WORDS) or _find_named(t, rc) or _find_named(t, rm)
    if not on_topic:
        return {"text": ("Maaf, aku hanya bisa membantu soal jurusan, kuliah, karier, dan persiapan belajar. "
                         "Coba tanya misalnya: \"Jurusan apa yang cocok untukku?\" atau \"Apa bedanya Informatika dan Sistem Informasi?\""),
                "sources": [], "kind": "offtopic"}

    # Memori: profesi/jurusan yang pernah dibahas
    mentioned_c = _find_named(t, rc)
    mentioned_m = _find_named(t, rm)
    remembered = []
    if not (mentioned_c or mentioned_m):
        for m in reversed(ctx["history"][-12:]):      # topik terakhir yang dibahas siswa
            if m["sender"] == "user":
                remembered = _find_named(m["text"], rc + rm)
                if remembered:
                    break

    prof_line = ""
    if prof.get("available") and "minat" in prof["results"]:
        top = prof["results"]["minat"]["top"]
        prof_line = f"Dari hasil Tes Minat, tipe terkuatmu {RIASEC[top[0]]} dan {RIASEC[top[1]]}. "
    elif prof.get("available"):
        prof_line = "Berdasarkan profil sementaramu, "
    else:
        prof_line = ("Kamu belum punya profil (butuh minimal 2 asesmen), jadi jawabanku masih umum. ")

    # 1) perbandingan dua jurusan/profesi
    if ("beda" in t or "banding" in t or " vs " in t) and len(mentioned_m + mentioned_c) >= 2:
        a, b = (mentioned_m + mentioned_c)[:2]
        lines = [f"Perbandingan **{a['name']}** dan **{b['name']}**:"]
        for it in (a, b):
            lines.append(f"• {it['name']} — {it['description']} Kecocokan dengan profilmu: {it.get('match', 0)}%.")
            sources.append(f"{it['name']} — Database Karier ARKA")
        better = a if a.get("match", 0) >= b.get("match", 0) else b
        lines.append(f"{prof_line}Saat ini {better['name']} sedikit lebih cocok, tapi coba lihat mata kuliah dan prospeknya dulu di Direktori.")
        return {"text": "\n".join(lines), "sources": sources, "kind": "normal"}

    # 2) tanya tentang profesi / jurusan spesifik
    target = (mentioned_c + mentioned_m)[:1] or (remembered[:1] if re.search(r"\b(itu|tadi|tersebut|barusan)\b", t) else [])
    if target:
        it = target[0]
        sources.append(f"{it['name']} — Database Karier ARKA")
        if "skills" in it:   # profesi
            txt = (f"**{it['name']}** ({it['field']}): {it['description']}\n"
                   f"• Kisaran gaji awal–menengah: {it['salary']} · Prospek: {it['outlook']}\n"
                   f"• Skill utama: {', '.join(it['skills'])}\n"
                   f"• Jurusan terkait: {', '.join(it['majors'])}\n"
                   f"{prof_line}kecocokanmu dengan profesi ini {it.get('match', 0)}%.")
            if remembered and not mentioned_c:
                txt = f"Melanjutkan obrolan kita soal {it['name']} — " + txt
        else:                # jurusan
            txt = (f"**{it['name']}**: {it['description']}\n"
                   f"• Mapel pendukung di SMA: {', '.join(it['subjects'])}\n"
                   f"• Contoh kampus: {', '.join(it['campuses'][:4])}\n"
                   f"{prof_line}kecocokanmu dengan jurusan ini {it.get('match', 0)}%. "
                   "Cek syarat dan daya tampung terbaru di laman resmi kampus/SNPMB ya.")
        return {"text": txt, "sources": sources, "kind": "normal"}

    # 3) rekomendasi jurusan
    if any(w in t for w in ["jurusan", "prodi", "kuliah apa", "cocok"]):
        if not prof.get("available"):
            return {"text": prof_line + "Selesaikan Tes Minat dan satu tes lain dulu, nanti aku bisa kasih rekomendasi jurusan yang merujuk hasilmu. Mau mulai sekarang?",
                    "sources": [], "kind": "normal"}
        top = rm[:3]
        for m in top:
            sources.append(f"{m['name']} — Database Karier ARKA")
        lines = [prof_line + "Jurusan yang paling cocok untukmu saat ini:"]
        lines += [f"• {m['name']} ({m['match']}%) — " + ("; ".join(m['reasons']) or m['description']) for m in top]
        lines.append("Ingat, ini indikasi. Mau aku bandingkan dua di antaranya?")
        return {"text": "\n".join(lines), "sources": sources, "kind": "normal"}

    # 4) rekomendasi profesi / karier
    if any(w in t for w in ["profesi", "karir", "karier", "kerja", "pekerjaan", "cita"]):
        if not prof.get("available"):
            return {"text": prof_line + "Setelah 2 asesmen selesai, aku bisa urutkan profesi berdasarkan kecocokanmu.",
                    "sources": [], "kind": "normal"}
        top = rc[:3]
        for c in top:
            sources.append(f"{c['name']} — Database Karier ARKA")
        lines = [prof_line + "Profesi yang paling cocok:"]
        lines += [f"• {c['name']} ({c['match']}%) — {c['description']}" for c in top]
        return {"text": "\n".join(lines), "sources": sources, "kind": "normal"}

    # 5) beasiswa
    if "beasiswa" in t or "biaya" in t:
        sch = ctx["scholarships"][:4]
        lines = ["Beberapa beasiswa yang bisa kamu pelajari:"]
        lines += [f"• {s['name']} ({s['provider']}) — {s['description']}" for s in sch]
        lines.append("Syarat dan jadwal berubah tiap tahun, jadi selalu cek laman resmi penyelenggara.")
        return {"text": "\n".join(lines), "sources": [f"{s['name']} — Database Karier ARKA" for s in sch], "kind": "normal"}

    # 6) jalur masuk
    if any(w in t for w in ["snbt", "snbp", "utbk", "mandiri", "daftar kampus", "masuk ptn"]):
        return {"text": ("Ada 3 jalur utama masuk PTN:\n• SNBP — berdasarkan nilai rapor & prestasi (butuh rapor stabil sejak kelas 10).\n"
                         "• SNBT — tes tertulis berbasis komputer (UTBK).\n• Mandiri — seleksi masing-masing kampus.\n"
                         "Tips: siapkan dua jalur sekaligus dan pantau info resmi di laman SNPMB. Langkah ini juga ada di roadmap-mu."),
                "sources": ["Jalur masuk PTN — ringkasan tim ARKA"], "kind": "normal"}

    # 7) skill / belajar
    if any(w in t for w in ["skill", "belajar", "keterampilan", "kursus", "portofolio"]):
        rd = ctx.get("roadmap")
        skills = (rd or {}).get("skills") or (rc[0]["skills"] if rc and prof.get("available") else [])
        if skills:
            lead = prof_line + ("Skill" if prof_line.endswith(". ") else "skill")
            return {"text": lead + " yang bisa mulai kamu latih: " + ", ".join(skills[:5]) +
                    ". Mulai dari satu dulu, misalnya ikut ekskul atau kursus gratis, lalu buat proyek kecil.",
                    "sources": [f"{rc[0]['name']} — Database Karier ARKA"] if rc else [], "kind": "normal"}

    # 8) bingung / umum
    if prof.get("available"):
        c, m = rc[0], rm[0]
        return {"text": (f"Wajar kok merasa bingung, {name}. {prof_line}arah yang bisa kamu jelajahi dulu: "
                         f"jurusan {m['name']} atau profesi {c['name']}. Mau aku jelaskan salah satunya, "
                         "atau buka langkah berikutnya di roadmap-mu?"),
                "sources": [f"{c['name']} — Database Karier ARKA", f"{m['name']} — Database Karier ARKA"], "kind": "normal"}
    return {"text": (f"Wajar kok merasa bingung, {name}. Langkah paling awal: kerjakan Tes Minat (±8 menit). "
                     "Setelah itu aku bisa bantu lebih personal."), "sources": [], "kind": "normal"}


# ---------- penyedia LLM opsional (multi-provider + fallback, FR-006 / R8)

SYSTEM_PROMPT = (
    "Kamu ARKA, AI Career Companion untuk siswa SMA/SMK Indonesia. Jawab dalam Bahasa Indonesia yang ramah dan singkat. "
    "Hanya bahas jurusan, kuliah, karier, dan persiapan belajar; tolak topik lain dengan sopan. "
    "Jangan mendiagnosis kondisi psikologis dan jangan menjamin diterima di jurusan mana pun. "
    "Rujuk profil siswa dan HANYA sebut profesi/jurusan dari daftar database yang diberikan."
)


def llm_reply(text, ctx, timeout=10):
    """Coba OpenAI lalu Gemini bila API key tersedia. Return None bila tidak ada/ gagal."""
    prof = ctx["profile"]
    db_list = [c["name"] for c in ctx["ranked_careers"][:8]] + [m["name"] for m in ctx["ranked_majors"][:8]]
    context = (f"Profil: {json.dumps({k: v for k, v in prof.items() if k in ('label', 'strengths')}, ensure_ascii=False)}\n"
               f"Database (urut kecocokan): {', '.join(db_list)}")
    hist = [{"role": "user" if m["sender"] == "user" else "assistant", "content": m["text"]} for m in ctx["history"][-10:]]
    providers = []
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")
    if os.environ.get("GEMINI_API_KEY"):
        providers.append("gemini")
    for p in providers:
        try:
            if p == "openai":
                body = {"model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                        "messages": [{"role": "system", "content": SYSTEM_PROMPT + "\n" + context}] + hist +
                                    [{"role": "user", "content": text}], "max_tokens": 400}
                req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
                                             data=json.dumps(body).encode(), method="POST",
                                             headers={"Content-Type": "application/json",
                                                      "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    out = json.load(r)["choices"][0]["message"]["content"]
                return {"text": out, "model": body["model"]}
            if p == "gemini":
                model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
                contents = [{"role": "user" if h["role"] == "user" else "model", "parts": [{"text": h["content"]}]} for h in hist]
                contents.append({"role": "user", "parts": [{"text": text}]})
                body = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT + "\n" + context}]}, "contents": contents}
                url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                       f"?key={os.environ['GEMINI_API_KEY']}")
                req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    out = json.load(r)["candidates"][0]["content"]["parts"][0]["text"]
                return {"text": out, "model": model}
        except Exception:  # noqa: BLE001 — lanjut ke penyedia cadangan
            continue
    return None

# ---------------------------------------------------------------- ringkasan BK

def counselor_summary(student, profile, roadmap, score, tags, last_data_at):
    if not profile.get("available"):
        return {"enough": False,
                "text": f"Data belum cukup: {student['name']} baru menyelesaikan "
                        f"{len(profile.get('done', []))} dari 4 asesmen. Ringkasan dibuat setelah minimal 2 asesmen selesai.",
                "last_data_at": last_data_at}
    parts = [f"{student['name']} ({student.get('class_name') or '-'}) memiliki skor kesiapan {score}/100 "
             f"dengan profil {profile['label'].lower()} ({len(profile['done'])}/4 asesmen)."]
    if profile["strengths"]:
        parts.append("Kekuatan utama: " + "; ".join(profile["strengths"][:3]) + ".")
    if roadmap:
        d = roadmap["data"]
        parts.append("Rekomendasi jurusan teratas: " + ", ".join(m["name"] for m in d["majors"][:3]) + ".")
        parts.append(f"Progres roadmap {roadmap['progress']}%" + (" (sudah disimpan)." if roadmap["is_saved"] else " (belum disimpan)."))
    else:
        parts.append("Belum membuat Career Roadmap.")
    if tags:
        parts.append("Perlu diperhatikan: " + ", ".join(tags).lower() + ".")
    if profile["missing"]:
        parts.append("Asesmen yang belum diambil: " + ", ".join(TESTS[k]["name"] for k in profile["missing"]) + ".")
    parts.append("Saran pembuka sesi: tanyakan alasan di balik minat utamanya dan apakah ia sudah membandingkan jurusan rekomendasi.")
    return {"enough": True, "text": " ".join(parts), "last_data_at": last_data_at}
