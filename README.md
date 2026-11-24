# ARKA — AI-powered Road for Knowledge & Advancement

Web ARKA yang **tampilannya sama persis dengan prototipe** (arkai-nine.vercel.app), tetapi sudah berjalan sungguhan dengan **backend Flask + database SQLite**.
Semua data (akun, asesmen, roadmap, chat, mentoring, data siswa untuk guru BK) tersimpan di database, bukan data palsu seperti di prototipe.

---

## 1. Cara menjalankan (VS Code)

1. Ekstrak zip, lalu di VS Code pilih **File → Open Folder…** → folder `arka`.
2. Buka terminal: **Terminal → New Terminal**.
3. Jalankan:
   ```bash
   cd backend
   pip install flask
   python app.py
   ```
   (Mac: `pip3` dan `python3`.)
4. Buka **http://localhost:5000** di browser.

Database `arka.db` dan data contoh dibuat otomatis saat pertama kali dijalankan. Untuk mengulang dari awal: `python seed.py`.

### Akun demo (password semua: `arka1234`)

| Peran | Email |
|---|---|
| Siswa | `arya@siswa.id` |
| Guru BK | `bk@harapan.sch.id` |
| Kepala Sekolah | `kepsek@harapan.sch.id` (melihat dashboard & laporan BK) |

Tombol **"Lihat sebagai Guru BK / Siswa"** di sidebar (sama seperti prototipe) berpindah ke akun demo di atas. Tombol ini hanya aktif di mode demo (`ARKA_DEMO=1`, default). Matikan dengan `ARKA_DEMO=0` sebelum dipakai sungguhan.

Atau buat akun sendiri lewat **Daftar Gratis** → pilih peran → isi onboarding 3 langkah.
Siswa dan guru BK yang mengetik **nama sekolah yang sama** saat onboarding otomatis terhubung, sehingga siswa itu muncul di dashboard guru BK tersebut.

---

## 2. Struktur folder

```
arka/
├── backend/
│   ├── app.py          # REST API + penyaji frontend
│   ├── engine.py       # penilaian asesmen, profil, roadmap, skor kesiapan, AI Companion, deteksi krisis
│   ├── data.py         # bank soal 4 asesmen + database profesi, jurusan, beasiswa
│   ├── db.py           # koneksi SQLite
│   ├── schema.sql      # skema database
│   ├── seed.py         # data contoh (2 sekolah, 40 siswa, 4 mentor, dst.)
│   └── requirements.txt
├── index.py          # titik masuk untuk Vercel
├── requirements.txt  # dependensi untuk Vercel
├── vercel.json
└── public/        # frontend (nama "public" wajib untuk Vercel)
    ├── index.html
    ├── template.html   # TEMPLATE ASLI prototipe (semua halaman), bagian statis disambungkan ke data
    ├── css/app.css     # gaya global asli prototipe
    ├── img/logo.png    # logo prototipe
    └── js/
        ├── runtime.js  # mesin render template (sc-if, sc-for, {{ }}, onclick, style-hover)
        └── logic.js    # logika halaman (diadaptasi dari kelas Component prototipe) + panggilan API
```

**Cara kerjanya:** prototipe dibuat dengan format template `sc-if` / `sc-for` / `{{ nilai }}`. Template aslinya dipakai apa adanya (`template.html`), dirender oleh `runtime.js`. Kelas logikanya (`logic.js`) masih memakai nama state dan halaman yang sama dengan prototipe. Bedanya, semua angka dan daftar sekarang diambil dari `/api/...`.

Mau mengubah tampilan? Edit `public/template.html` (HTML biasa dengan style inline). Mau mengubah data atau aksi? Edit `public/js/logic.js` (fungsi `load()` dan `renderVals()`).

---

## 3. Halaman & sumber datanya

| Halaman (sama dengan prototipe) | Yang sekarang sungguhan |
|---|---|
| Landing, Daftar, Masuk | Akun tersimpan, password di-hash, pilihan peran Siswa / Guru BK / Kepala Sekolah |
| Onboarding 3 langkah | Data diri, sekolah, kelas, minat, dan kekhawatiran disimpan; sekolah dicocokkan ke tabel `schools` |
| Dashboard siswa | Skor karier dihitung dari data, sesi terakhir, milestone (asesmen, roadmap, booking mentor, profesi dilihat), notifikasi & rekomendasi AI, aktivitas terbaru |
| AI Companion & Riwayat | Jawaban berdasarkan profil & database karier, mengingat topik sebelumnya, menolak topik di luar karier, **layar bantuan krisis** (Healing119 · 119 ext. 8), sesi baru setelah jeda 30 menit |
| Asesmen, pengerjaan tes, hasil | 4 tes dengan butir berbeda (minat RIASEC, bakat, kepribadian, nilai karier); jawaban tersimpan per klik (bisa lanjut lain waktu); hasil, kampus relevan, dan profesi cocok dihitung dari jawaban |
| Career Roadmap & detail | Dibuat otomatis setelah 2 asesmen, checklist bisa dicentang, progres tersimpan, tombol **Perbarui** membuat ulang dari asesmen terbaru |
| Mentoring (cari, profil, booking, sesi, ringkasan) | Mentor dari database, booking tersimpan (tanggal tidak boleh lewat), catatan sesi & ulasan tersimpan. *Pembayaran & video call masih simulasi.* |
| Direktori Karir & detail | Profesi dari database, diurutkan menurut kecocokan, pencarian berfungsi |
| Dashboard Guru BK | Siswa satu sekolah saja, skor, status asesmen, tag prioritas, perhatian prioritas, pencarian, jumlah mentoring bulan ini |
| Profil Siswa (BK) | Ringkasan AI otomatis, hasil asesmen nyata, **catatan konseling tersimpan** (hanya terlihat oleh guru penulisnya). Guru BK sekolah lain ditolak (403) dan dicatat di audit log |
| Laporan Kelas | Distribusi skor & minat dari data nyata, tanpa nama; kelompok <10 siswa disembunyikan; **Ekspor PDF** lewat cetak browser |
| Pengaturan | Nama & email akun yang login, jumlah asesmen selesai |

---

## 4. Database (ringkas)

```
schools 1──* users (role: siswa | guru_bk | kepsek | admin)
users 1──* assessment_attempts      jawaban (JSON), posisi terakhir, hasil
users 1──* roadmaps 1──* roadmap_steps   rekomendasi + alasan, checklist
users 1──* chat_sessions 1──* chat_messages   memori percakapan, sumber, feedback
users 1──* mentor_bookings *──1 mentors       booking, catatan sesi, ulasan
users(siswa) 1──* counseling_notes *──1 users(guru_bk)
careers, majors, scholarships        database karier
events, audit_log                    instrumentasi (ID pseudonim) & log akses data siswa
consents, deletion_requests, outbox  tersedia di API (persetujuan ortu, hapus akun), belum dipakai di tampilan prototipe
```

---

## 5. AI sungguhan (opsional)

Tanpa API key, Companion memakai mesin aturan offline. Untuk memakai LLM, set salah satu variabel di bawah sebelum `python app.py`. Bila penyedia utama gagal atau melewati 10 detik, sistem otomatis pindah ke cadangan.
```bash
export OPENAI_API_KEY=...     # utama
export GEMINI_API_KEY=...     # cadangan
```

---

## 6. Catatan jujur (beda dengan PRD)

Tampilan mengikuti prototipe, jadi beberapa hal di PRD **belum tampil di UI** walaupun API-nya sudah ada:
- **Persetujuan orang tua** (FR-002) dan **hapus akun** (FR-010): endpoint `/api/consent/*` dan `/api/account/delete/*` sudah ada, tetapi belum ada halamannya di prototipe.
- **Pilihan peran Guru BK saat daftar** terbuka untuk umum, mengikuti prototipe. Di produksi, akun guru BK sebaiknya dibuat atau diverifikasi oleh sekolah.
- **Teks marketing di landing** (mis. "Platform AI Karir #1", "0 kompetitor", testimoni, harga Premium) masih teks asli prototipe dan belum sesuai PRD (V1 gratis selama pilot).
- Butir asesmen masih versi demo yang lebih pendek; isi final perlu ditinjau psikolog mitra.
- Pembayaran mentoring, video call, login Google, dan notifikasi masih simulasi.

---

## 7. Deploy ke Vercel

1. Upload folder `arka` (isi folder ini, bukan zip-nya) ke repository GitHub baru.
2. Buka **vercel.com/new**, login dengan GitHub, lalu **Import** repository itu.
3. Biarkan semua pengaturan default (Framework terdeteksi: Flask). Buka **Environment Variables**, tambahkan:
   - `ARKA_SECRET` = teks acak panjang (misalnya `arka-kelompok5-2026-rahasia`), supaya login tidak sering ter-logout.
4. Klik **Deploy**. Setelah selesai, kamu mendapat link `https://nama-proyek.vercel.app`.

⚠️ **Penting soal database di Vercel:** Vercel tidak punya penyimpanan file permanen. Database SQLite disimpan di `/tmp` dan **bisa kembali ke data contoh** setiap kali server "tidur" (biasanya setelah beberapa menit tidak dipakai). Akun demo selalu ada, tetapi akun dan data baru bisa hilang.
Cocok untuk **presentasi atau demo**. Kalau butuh data permanen, pakai database online (misalnya Neon/Vercel Postgres atau Turso, tetapi kode `db.py` perlu diubah) atau hosting dengan disk permanen (Render, PythonAnywhere).
