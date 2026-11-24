-- =====================================================================
-- ARKA — AI-powered Road for Knowledge & Advancement
-- Skema database sederhana (SQLite). Bisa dipindah ke PostgreSQL/MySQL
-- dengan sedikit penyesuaian tipe data (TEXT JSON -> JSONB, dsb).
-- =====================================================================
PRAGMA foreign_keys = ON;

-- Sekolah mitra. Guru BK dan siswa terhubung ke sekolah (FR-001, FR-009)
CREATE TABLE IF NOT EXISTS schools (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    city        TEXT NOT NULL,
    invite_code TEXT NOT NULL UNIQUE,          -- kode/tautan undangan dari guru BK
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Semua pengguna: siswa, guru_bk, kepsek, admin (kontrol akses berbasis peran)
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    role           TEXT NOT NULL CHECK (role IN ('siswa','guru_bk','kepsek','admin')),
    name           TEXT NOT NULL,
    nickname       TEXT,
    email          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    birth_date     TEXT,                        -- YYYY-MM-DD (cek usia < 18)
    gender         TEXT,
    city           TEXT,
    school_id      INTEGER REFERENCES schools(id),   -- NULL = "Sekolah belum terdaftar"
    grade          TEXT,                        -- '10' / '11' / '12'
    class_name     TEXT,                        -- mis. 'XI IPA 1'
    interests      TEXT NOT NULL DEFAULT '[]',  -- JSON array minat awal
    concern        TEXT,
    status         TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('pending_consent','active','rejected','deleted')),
    onboarded      INTEGER NOT NULL DEFAULT 0,
    notif_enabled  INTEGER NOT NULL DEFAULT 1,
    pseudo_id      TEXT NOT NULL UNIQUE,        -- ID pseudonim untuk event analitik
    last_active_at TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    deleted_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_school ON users(school_id, role, status);

-- Persetujuan orang tua/wali (FR-002, GR2, UU PDP Pasal 25)
CREATE TABLE IF NOT EXISTS consents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token          TEXT NOT NULL UNIQUE,        -- tautan persetujuan
    code           TEXT NOT NULL,               -- kode verifikasi 6 digit
    parent_name    TEXT NOT NULL,
    parent_contact TEXT NOT NULL,               -- email/telepon orang tua
    policy_version TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','approved','rejected','expired','superseded')),
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    expires_at     TEXT NOT NULL,               -- 7 hari
    decided_at     TEXT
);

-- Pengerjaan asesmen; satu baris per percobaan (simpan & lanjutkan, riwayat) (FR-003, FR-004)
CREATE TABLE IF NOT EXISTS assessment_attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    test_key      TEXT NOT NULL CHECK (test_key IN ('minat','bakat','kepribadian','nilai')),
    answers       TEXT NOT NULL DEFAULT '{}',   -- JSON {item_id: 1..5}
    current_index INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress','completed')),
    result        TEXT,                         -- JSON hasil skor
    started_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    completed_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON assessment_attempts(user_id, test_key, status);

-- Career Roadmap (FR-005, FR-011)
CREATE TABLE IF NOT EXISTS roadmaps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    data        TEXT NOT NULL,                  -- JSON rekomendasi jurusan, profesi, skill + alasan
    is_saved    INTEGER NOT NULL DEFAULT 0,
    is_current  INTEGER NOT NULL DEFAULT 1,
    based_on    TEXT NOT NULL,                  -- daftar asesmen yang dipakai
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    saved_at    TEXT
);
CREATE TABLE IF NOT EXISTS roadmap_steps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    roadmap_id  INTEGER NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    period      TEXT NOT NULL,
    tasks       TEXT NOT NULL DEFAULT '[]',     -- JSON [{text, done}]
    done        INTEGER NOT NULL DEFAULT 0,
    done_at     TEXT
);

-- AI Career Companion: sesi & pesan (memori percakapan) (FR-006, FR-007, FR-020, M4)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic      TEXT,
    started_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    last_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sender      TEXT NOT NULL CHECK (sender IN ('user','ai')),
    text        TEXT NOT NULL,
    sources     TEXT NOT NULL DEFAULT '[]',     -- JSON sumber database karier
    kind        TEXT NOT NULL DEFAULT 'normal' CHECK (kind IN ('normal','offtopic','crisis','error')),
    model       TEXT,                           -- versi model / 'rules-v1'
    feedback    TEXT CHECK (feedback IN ('helpful','inaccurate')),
    review_status TEXT,                         -- 'queued' bila ditandai tidak akurat
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_msgs_user ON chat_messages(user_id, created_at);

-- Catatan konseling guru BK, hanya terlihat oleh penulisnya (FR-015)
CREATE TABLE IF NOT EXISTS counseling_notes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    counselor_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    text         TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Database karier terkurasi (D5): profesi & program studi
CREATE TABLE IF NOT EXISTS careers (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    field     TEXT NOT NULL,
    riasec    TEXT NOT NULL,                    -- kode Holland 2 huruf, mis. 'IA'
    talents   TEXT NOT NULL DEFAULT '[]',       -- JSON kecerdasan pendukung
    values_   TEXT NOT NULL DEFAULT '[]',       -- JSON nilai kerja pendukung
    salary    TEXT,
    description TEXT NOT NULL,
    skills    TEXT NOT NULL DEFAULT '[]',
    majors    TEXT NOT NULL DEFAULT '[]',       -- JSON nama program studi terkait
    outlook   TEXT,
    source    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS majors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    field       TEXT NOT NULL,
    riasec      TEXT NOT NULL,
    talents     TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL,
    subjects    TEXT NOT NULL DEFAULT '[]',     -- mapel pendukung di SMA
    campuses    TEXT NOT NULL DEFAULT '[]',
    source      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scholarships (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    provider    TEXT NOT NULL,
    level       TEXT NOT NULL,
    description TEXT NOT NULL,
    source      TEXT NOT NULL
);

-- Survei kejelasan arah karier (M5)
CREATE TABLE IF NOT EXISTS clarity_surveys (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    phase      TEXT NOT NULL CHECK (phase IN ('baseline','followup')),
    score      INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Permintaan hapus akun & data (FR-010)
CREATE TABLE IF NOT EXISTS deletion_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    code         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','confirmed')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    confirmed_at TEXT,
    purge_after  TEXT                            -- data dihapus permanen paling lambat 30 hari
);

-- Event instrumentasi (Bab 7): hanya ID pseudonim, jenis event, waktu
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pseudo_id  TEXT NOT NULL,
    event      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_events ON events(event, created_at);

-- Audit log akses data sensitif (NFR keamanan, GR1)
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id   INTEGER,
    action     TEXT NOT NULL,
    target     TEXT,
    allowed    INTEGER NOT NULL,
    ip         TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Kotak surat simulasi (pengganti email/SMS sungguhan di mode demo)
CREATE TABLE IF NOT EXISTS outbox (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    to_contact TEXT NOT NULL,
    subject    TEXT NOT NULL,
    body       TEXT NOT NULL,
    link       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Mentoring 1-on-1 (halaman Mentoring di prototipe)
CREATE TABLE IF NOT EXISTS mentors (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    role     TEXT NOT NULL,
    company  TEXT NOT NULL,
    field    TEXT NOT NULL,
    rating   REAL NOT NULL DEFAULT 5.0,
    price    INTEGER NOT NULL,
    bio      TEXT
);
CREATE TABLE IF NOT EXISTS mentor_bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mentor_id   INTEGER NOT NULL REFERENCES mentors(id),
    date        TEXT NOT NULL,
    time        TEXT NOT NULL,
    payment     TEXT,
    status      TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed','done','cancelled')),
    notes       TEXT,
    rating      INTEGER,
    review      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
