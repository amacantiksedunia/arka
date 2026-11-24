"""
Membuat database baru berisi data contoh.
    python seed.py          -> hapus arka.db lama & buat ulang
Semua akun demo memakai kata sandi: arka1234
"""
import json
import random
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

import db as dbm
import engine
from data import CAREERS, MAJORS, SCHOLARSHIPS, SRC, TESTS

PASSWORD = "arka1234"
rnd = random.Random(42)


def ts(days_ago=0, hours_ago=0):
    return (datetime.now() - timedelta(days=days_ago, hours=hours_ago)).isoformat(timespec="seconds")


def answers_for(test_key, high_dims):
    """Jawaban sintetis: dimensi pilihan cenderung 4-5, lainnya 1-3."""
    out = {}
    for it in TESTS[test_key]["items"]:
        out[it["id"]] = rnd.choice([4, 5, 5]) if it["dim"] in high_dims else rnd.choice([1, 2, 2, 3, 3])
    return out


ARCHETYPES = [
    # minat, bakat, kepribadian, nilai
    (["I", "A"], ["spasial", "logis"], ["I", "N", "T", "P"], ["kreativitas", "pendapatan"]),
    (["I", "R"], ["logis", "intrapersonal"], ["I", "S", "T", "J"], ["pendapatan", "kemandirian"]),
    (["S", "I"], ["interpersonal", "logis"], ["E", "S", "F", "J"], ["dampak", "keamanan"]),
    (["E", "A"], ["interpersonal", "linguistik"], ["E", "N", "F", "P"], ["kemandirian", "kreativitas"]),
    (["C", "E"], ["logis"], ["I", "S", "T", "J"], ["keamanan", "pendapatan"]),
    (["A", "S"], ["linguistik", "spasial"], ["E", "N", "F", "P"], ["kreativitas", "dampak"]),
    (["R", "I"], ["naturalis", "kinestetik"], ["I", "S", "T", "P"], ["dampak", "keamanan"]),
    (["S", "R"], ["kinestetik", "interpersonal"], ["E", "S", "F", "J"], ["kolaborasi", "dampak"]),
]

FIRST = ["Arya", "Dina", "Rafi", "Maya", "Bagas", "Laras", "Nadia", "Fajar", "Citra", "Dimas", "Eka", "Gilang",
         "Hana", "Irfan", "Jihan", "Kevin", "Lutfi", "Mega", "Nico", "Olivia", "Putri", "Raka", "Salsa", "Tegar",
         "Umi", "Vino", "Wulan", "Yoga", "Zahra", "Bima", "Alya", "Reza", "Sinta", "Tio", "Ayu", "Fikri", "Gita"]
LAST = ["Pratama", "Safitri", "Hidayat", "Putri", "Wicaksono", "Sari", "Nugroho", "Ramadhan", "Lestari",
        "Saputra", "Kurniawan", "Anggraini", "Firmansyah", "Maharani", "Setiawan", "Wijaya"]


def main():
    if dbm.DB_PATH.exists():
        dbm.DB_PATH.unlink()
    c = dbm.connect()
    dbm.init_schema(c)

    for name, field, riasec, talents, values, salary, desc, skills, majors, outlook in CAREERS:
        c.execute("""INSERT INTO careers(name,field,riasec,talents,values_,salary,description,skills,majors,outlook,source)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                  (name, field, riasec, json.dumps(talents), json.dumps(values), salary, desc,
                   json.dumps(skills), json.dumps(majors), outlook, SRC))
    for name, field, riasec, talents, desc, subjects, campuses in MAJORS:
        c.execute("""INSERT INTO majors(name,field,riasec,talents,description,subjects,campuses,source)
                     VALUES(?,?,?,?,?,?,?,?)""",
                  (name, field, riasec, json.dumps(talents), desc, json.dumps(subjects), json.dumps(campuses), SRC))
    for name, prov, level, desc in SCHOLARSHIPS:
        c.execute("INSERT INTO scholarships(name,provider,level,description,source) VALUES(?,?,?,?,?)",
                  (name, prov, level, desc, "Ringkasan tim ARKA; cek laman resmi penyelenggara"))

    for nm, role, co, field, rating, price, bio in [
        ("Rizky Aditya, S.Psi", "Career Counselor", "Tokopedia", "Teknologi", 4.9, 75000, "Konselor karier yang membantu siswa memetakan minat dan pilihan jurusan teknologi."),
        ("Dr. Sari Wulandari", "HR Director", "Unilever", "Bisnis", 4.8, 120000, "Berpengalaman merekrut lulusan baru; fokus pada persiapan karier dan wawancara."),
        ("Budi Santoso, M.Kom", "Senior Engineer", "Gojek", "Teknologi", 4.7, 100000, "Software engineer yang membimbing siswa memulai belajar pemrograman."),
        ("Anisa Rahma, S.Ds", "Lead Designer", "Bukalapak", "Desain", 4.9, 85000, "Desainer produk; spesialis review portofolio desain untuk masuk DKV."),
    ]:
        c.execute("INSERT INTO mentors(name,role,company,field,rating,price,bio) VALUES(?,?,?,?,?,?,?)", (nm, role, co, field, rating, price, bio))

    sA = c.execute("INSERT INTO schools(name,city,invite_code) VALUES(?,?,?)",
                   ("SMA Harapan Bangsa", "Malang", "HARAPAN-MLG")).lastrowid
    sB = c.execute("INSERT INTO schools(name,city,invite_code) VALUES(?,?,?)",
                   ("SMA Nusantara", "Surabaya", "NUSANTARA-SBY")).lastrowid

    pw = generate_password_hash(PASSWORD)

    def user(role, name, email, school, **kw):
        cols = {"role": role, "name": name, "email": email, "password_hash": pw, "school_id": school,
                "status": "active", "onboarded": 1, "pseudo_id": secrets.token_hex(8), **kw}
        k = ",".join(cols)
        return c.execute(f"INSERT INTO users({k}) VALUES({','.join('?' * len(cols))})", tuple(cols.values())).lastrowid

    bk_a = user("guru_bk", "Ibu Sari Wulandari, S.Pd", "bk@harapan.sch.id", sA, last_active_at=ts(0, 1))
    user("kepsek", "Bpk. Budi Santoso, M.Pd", "kepsek@harapan.sch.id", sA, last_active_at=ts(1))
    user("guru_bk", "Bpk. Andi Kusuma, S.Pd", "bk@nusantara.sch.id", sB, last_active_at=ts(2))

    # --- siswa demo utama: 2 asesmen selesai, roadmap belum disimpan
    arya = user("siswa", "Arya Pratama", "arya@siswa.id", sA, birth_date="2009-03-14", grade="11",
                class_name="XI IPA 1", nickname="Arya", gender="L", city="Malang",
                interests=json.dumps(["Teknologi", "Seni & Desain"]), concern="Takut salah pilih jurusan",
                last_active_at=ts(0, 2), created_at=ts(5))
    for key, dims, d in (("minat", ["I", "A"], 3), ("bakat", ["spasial", "logis"], 2)):
        ans = answers_for(key, dims)
        c.execute("""INSERT INTO assessment_attempts(user_id,test_key,answers,current_index,status,result,started_at,completed_at)
                     VALUES(?,?,?,?,?,?,?,?)""",
                  (arya, key, json.dumps(ans), len(ans) - 1, "completed", json.dumps(engine.score_test(key, ans)), ts(d, 1), ts(d)))
    # tes kepribadian setengah jalan (contoh simpan & lanjutkan)
    part = dict(list(answers_for("kepribadian", ["I", "N", "T", "P"]).items())[:7])
    c.execute("INSERT INTO assessment_attempts(user_id,test_key,answers,current_index,started_at) VALUES(?,?,?,?,?)",
              (arya, "kepribadian", json.dumps(part), 7, ts(1)))
    c.execute("INSERT INTO consents(student_id,token,code,parent_name,parent_contact,policy_version,status,created_at,expires_at,decided_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (arya, secrets.token_urlsafe(16), "000000", "Ibu Ratna", "ratna.ortu@email.id", "v1.0-2026-11", "approved", ts(5), ts(-2), ts(5)))
    s1 = c.execute("INSERT INTO chat_sessions(user_id,topic,started_at,last_at) VALUES(?,?,?,?)",
                   (arya, "Jurusan yang cocok", ts(1), ts(1))).lastrowid
    for snd, txt in (("user", "Halo, aku suka desain dan teknologi. Jurusan apa yang cocok ya?"),
                     ("ai", "Dari hasil Tes Minat, tipe terkuatmu Investigatif dan Artistik. Jurusan yang paling cocok saat ini: Desain Komunikasi Visual, Sistem Informasi, dan Teknik Informatika. Mau aku bandingkan dua di antaranya?")):
        c.execute("INSERT INTO chat_messages(session_id,user_id,sender,text,model,created_at) VALUES(?,?,?,?,?,?)",
                  (s1, arya, snd, txt, "arka-rules-v1" if snd == "ai" else None, ts(1)))

    # --- siswa menunggu persetujuan (tidak tampil di dashboard BK)
    rid = user("siswa", "Rafi Hidayat", "rafi@siswa.id", sA, birth_date="2009-08-01", grade="11",
               class_name="XI IPA 1", status="pending_consent", onboarded=0, created_at=ts(1))
    c.execute("INSERT INTO consents(student_id,token,code,parent_name,parent_contact,policy_version,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?)",
              (rid, "demo-persetujuan-rafi", "123456", "Bpk. Hidayat", "hidayat.ortu@email.id", "v1.0-2026-11", ts(-6), ts(1)))
    c.execute("INSERT INTO outbox(to_contact,subject,body,link,created_at) VALUES(?,?,?,?,?)",
              ("hidayat.ortu@email.id", "Persetujuan data anak untuk ARKA",
               "Yth. Bpk. Hidayat,\n\nRafi Hidayat mendaftar di ARKA. Kode verifikasi: 123456\nTautan berlaku 7 hari.",
               "/#/persetujuan/demo-persetujuan-rafi", ts(1)))

    # --- siswa lain untuk dashboard & laporan
    classes = [("XI IPA 1", "11", 12), ("XII IPA 1", "12", 11), ("XI IPS 1", "11", 8), ("XII IPS 1", "12", 6)]
    used = {"Arya Pratama", "Rafi Hidayat"}
    for cls, grade, n in classes:
        for _ in range(n - (1 if cls == "XI IPA 1" else 0)):
            while True:
                nm = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
                if nm not in used:
                    used.add(nm)
                    break
            arch = rnd.choice(ARCHETYPES)
            n_done = rnd.choices([0, 1, 2, 3, 4], weights=[2, 2, 3, 2, 3])[0]
            inactive = rnd.random() < 0.2
            last = ts(rnd.randint(8, 20)) if inactive else ts(rnd.randint(0, 5), rnd.randint(0, 12))
            byear = 2009 if grade == "11" else 2008
            ints = rnd.sample(["Teknologi", "Seni & Desain", "Kesehatan", "Bisnis", "Teknik", "Sosial", "Media", "Hukum"], 2)
            sid = user("siswa", nm, nm.lower().replace(" ", ".") + "@siswa.id", sA, interests=json.dumps(ints),
                       birth_date=f"{byear}-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}", grade=grade,
                       class_name=cls, last_active_at=last, created_at=ts(rnd.randint(10, 40)))
            for key, dims in list(zip(["minat", "bakat", "kepribadian", "nilai"], arch))[:n_done]:
                ans = answers_for(key, dims)
                d = rnd.randint(1, 30)
                c.execute("""INSERT INTO assessment_attempts(user_id,test_key,answers,current_index,status,result,started_at,completed_at)
                             VALUES(?,?,?,?,?,?,?,?)""",
                          (sid, key, json.dumps(ans), len(ans) - 1, "completed",
                           json.dumps(engine.score_test(key, ans)), ts(d, 1), ts(d)))
            if n_done >= 2:
                c.commit()
                urow = dbm.row(c.execute("SELECT * FROM users WHERE id=?", (sid,)).fetchone())
                res = {r["test_key"]: json.loads(r["result"]) for r in c.execute(
                    "SELECT test_key,result FROM assessment_attempts WHERE user_id=? AND status='completed'", (sid,))}
                careers = dbm.rows(c.execute("SELECT * FROM careers").fetchall())
                majors = dbm.rows(c.execute("SELECT * FROM majors").fetchall())
                data, steps = engine.build_roadmap(urow, res, careers, majors)
                saved = rnd.random() < 0.7
                rmid = c.execute("INSERT INTO roadmaps(user_id,data,is_saved,based_on,saved_at) VALUES(?,?,?,?,?)",
                                 (sid, json.dumps(data), 1 if saved else 0, json.dumps(sorted(res)), ts(3) if saved else None)).lastrowid
                for i, s in enumerate(steps):
                    tasks = s["tasks"]
                    if i in (1, 2) and saved:
                        for t in tasks:
                            t["done"] = rnd.random() < 0.5
                    c.execute("INSERT INTO roadmap_steps(roadmap_id,idx,title,description,period,tasks,done) VALUES(?,?,?,?,?,?,?)",
                              (rmid, i, s["title"], s["description"], s["period"], json.dumps(tasks),
                               1 if all(t["done"] for t in tasks) else 0))

    # siswa sekolah B (untuk uji akses lintas sekolah / 403)
    user("siswa", "Siswa Sekolah Lain", "lain@siswa.id", sB, birth_date="2008-05-05", grade="12",
         class_name="XII IPA 2", last_active_at=ts(1))

    c.execute("INSERT INTO counseling_notes(student_id,counselor_id,text,created_at) VALUES(?,?,?,?)",
              (arya, bk_a, "Sesi awal: Arya tertarik desain & teknologi, masih ragu antara DKV dan Informatika. Tindak lanjut: minta selesaikan tes kepribadian.", ts(2)))
    c.commit()
    c.close()
    print(f"Database dibuat: {dbm.DB_PATH}")


if __name__ == "__main__":
    main()
