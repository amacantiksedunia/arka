/*
 * Logika halaman ARKA — diadaptasi dari kelas Component prototipe (arkai-nine.vercel.app).
 * Struktur state, nama halaman, dan nilai yang dikirim ke template SAMA dengan prototipe;
 * bedanya, data sekarang diambil dari backend (Flask + SQLite) lewat /api.
 */
'use strict';

/* ---------------- util */
async function api(path, opts = {}) {
  const o = { method: opts.method || 'GET', headers: {}, credentials: 'same-origin' };
  if (opts.body !== undefined) { o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(opts.body); }
  let res;
  try { res = await fetch('/api' + path, o); } catch (e) { throw new Error('Koneksi terputus. Coba lagi.'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) { const er = new Error(data.error || 'Terjadi kesalahan.'); er.status = res.status; er.data = data; throw er; }
  return data;
}
function toast(msg, type = 'info') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.dataset.type = type; t.classList.add('show');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), 3200);
}
function timeAgo(s) {
  if (!s) return 'belum pernah';
  const d = (Date.now() - new Date(String(s).replace(' ', 'T')).getTime()) / 1000;
  if (d < 60) return 'baru saja';
  if (d < 3600) return Math.floor(d / 60) + ' mnt lalu';
  if (d < 86400) return Math.floor(d / 3600) + ' jam lalu';
  return Math.floor(d / 86400) + ' hari lalu';
}
const fmtDate = (s) => s ? new Date(String(s).replace(' ', 'T')).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }) : '-';
const rupiah = (n) => Number(n || 0).toLocaleString('id-ID');
const todayPlus = (d) => { const t = new Date(Date.now() + d * 864e5); return t.toISOString().slice(0, 10); };

/* layar bantuan krisis (FR-007) — di luar template, tidak bisa ditutup 3 detik */
function crisisScreen(lines) {
  const root = document.getElementById('overlay');
  root.innerHTML = `<div class="ov-bg" role="dialog" aria-modal="true"><div class="ov-card">
    <div style="font-size:22px;font-weight:800;margin-bottom:8px">Kamu tidak sendirian 💜</div>
    <p style="font-size:14px;color:#4A5568;line-height:1.6;margin-bottom:14px">Sepertinya kamu sedang melalui masa yang berat. Bicara dengan orang yang terlatih bisa membantu. Hubungi salah satu layanan ini sekarang:</p>
    ${lines.map((l) => `<div style="background:#FEF2F2;border-radius:12px;padding:12px 14px;margin-bottom:8px"><div style="font-weight:700;color:#991B1B;font-size:14px">📞 ${l.name}</div><div style="font-size:13px;color:#7F1D1D">${l.contact}</div></div>`).join('')}
    <p style="font-size:12px;color:#6B7280;margin:10px 0 14px">ARKA bukan layanan konseling krisis. Jika kamu dalam bahaya, segera hubungi 112 atau orang dewasa terdekat.</p>
    <button id="ov-close" disabled style="width:100%;padding:12px;border-radius:10px;border:2px solid #E8E5F0;background:#fff;font-weight:700;cursor:pointer;font-family:inherit">Tunggu 3 detik…</button></div></div>`;
  const b = document.getElementById('ov-close'); let n = 3;
  const t = setInterval(() => { n--; if (n <= 0) { clearInterval(t); b.disabled = false; b.textContent = 'Saya mengerti, tutup'; b.focus(); } else b.textContent = `Tunggu ${n} detik…`; }, 1000);
  b.onclick = () => { root.innerHTML = ''; };
}

/* ---------------- konten statis dari prototipe */
const TEST_META = {
  minat: { desc: 'Holland RIASEC — kenali 6 tipe minat karir dan temukan bidang yang paling pas untukmu', icon: '🎯', iconBg: '#F3F0FF', barColor: 'linear-gradient(90deg,#6B4FCF,#4338CA)', diff: 'Mudah', diffColor: '#16A34A', diffBg: '#F0FDF4' },
  bakat: { desc: 'Kecerdasan Majemuk Howard Gardner — ungkap 8 jenis kecerdasan dan kekuatan alami terkuatmu', icon: '⚡', iconBg: '#FFF8E1', barColor: 'linear-gradient(90deg,#F5A623,#D97706)', diff: 'Sedang', diffColor: '#D97706', diffBg: '#FFF8E1' },
  kepribadian: { desc: '4 dimensi kepribadian — pahami cara kerja, cara mengambil keputusan, dan gaya berinteraksimu', icon: '🧠', iconBg: '#EEF2FF', barColor: 'linear-gradient(90deg,#2E5FBF,#1B3A7A)', diff: 'Sedang', diffColor: '#2E5FBF', diffBg: '#EEF2FF' },
  nilai: { desc: 'Work Values Inventory — apa yang paling penting bagimu dalam bekerja: kreativitas, keamanan, atau dampak sosial?', icon: '💎', iconBg: '#F0FDF4', barColor: 'linear-gradient(90deg,#16A34A,#15803D)', diff: 'Cepat', diffColor: '#6B4FCF', diffBg: '#F3F0FF' },
};
const RIASEC = { R: 'Realistik', I: 'Investigatif', A: 'Artistik', S: 'Sosial', E: 'Enterprising', C: 'Konvensional' };
const TALENTS = { linguistik: 'Linguistik', logis: 'Logis-Matematis', spasial: 'Visual-Spasial', kinestetik: 'Kinestetik', musikal: 'Musikal', interpersonal: 'Interpersonal', intrapersonal: 'Intrapersonal', naturalis: 'Naturalis' };
const VALUES = { kreativitas: 'Kreativitas', keamanan: 'Keamanan & Stabilitas', dampak: 'Dampak Sosial', pendapatan: 'Pendapatan & Prestise', kemandirian: 'Kemandirian', kolaborasi: 'Kerja Sama Tim' };
const BAR_COLORS = ['#6B4FCF', '#2E5FBF', '#F5A623', '#16A34A', '#9CA3AF', '#D1D5DB', '#C4B5FD', '#E5E7EB'];
const RIASEC_INFO = {
  R: ['Belajar lewat praktik langsung dan mencoba alat atau benda nyata.', 'Lapangan, bengkel, atau laboratorium dengan tugas yang konkret.', 'Terampil secara teknis, praktis, dan tahan banting.', 'pekerjaan praktis dengan alat, mesin, atau alam'],
  I: ['Belajar lewat membaca, riset, dan memecahkan soal yang menantang.', 'Lingkungan yang memberi ruang bertanya, meneliti, dan menganalisis.', 'Analitis, teliti, dan penasaran.', 'pemecahan masalah dan analisis'],
  A: ['Visual dan eksploratif — belajar paling baik lewat proyek kreatif.', 'Tim yang memberi kebebasan berkreasi dan fleksibilitas waktu.', 'Kreativitas tinggi, imajinatif, dan peka estetika.', 'ekspresi kreatif dan desain'],
  S: ['Belajar lewat diskusi dan kerja kelompok.', 'Lingkungan kolaboratif yang berdampak bagi orang lain.', 'Empati, komunikasi, dan kepedulian.', 'membantu dan bekerja dengan orang'],
  E: ['Belajar lewat praktik memimpin, presentasi, dan tantangan.', 'Lingkungan dinamis dengan target dan ruang untuk memimpin.', 'Percaya diri, persuasif, dan berani mengambil keputusan.', 'memimpin dan meyakinkan orang'],
  C: ['Belajar dengan jadwal rapi dan langkah yang jelas.', 'Lingkungan teratur dengan prosedur dan data yang jelas.', 'Teliti, terorganisir, dan dapat diandalkan.', 'keteraturan, data, dan prosedur'],
};
const CAMPUS = {
  'Universitas Brawijaya': ['UB', '#F3F0FF', '#6B4FCF'], 'ITS': ['ITS', '#FFF8E1', '#D97706', 'Institut Teknologi Sepuluh Nopember'],
  'ITB': ['ITB', '#EEF2FF', '#2E5FBF', 'Institut Teknologi Bandung'], 'UI': ['UI', '#F3F0FF', '#6B4FCF', 'Universitas Indonesia'],
  'UGM': ['UGM', '#F0FDF4', '#16A34A', 'Universitas Gadjah Mada'], 'IPB': ['IPB', '#F0FDF4', '#16A34A', 'IPB University'],
  'Universitas Airlangga': ['UNAIR', '#EEF2FF', '#2E5FBF'], 'Universitas Negeri Malang': ['UM', '#FFF8E1', '#D97706'],
  'ISI Yogyakarta': ['ISI', '#FEF2F2', '#DC2626', 'Institut Seni Indonesia Yogyakarta'], 'UNY': ['UNY', '#EEF2FF', '#2E5FBF', 'Universitas Negeri Yogyakarta'],
  'UPI': ['UPI', '#FFF8E1', '#D97706', 'Universitas Pendidikan Indonesia'], 'Unesa': ['UNESA', '#F0FDF4', '#16A34A', 'Universitas Negeri Surabaya'],
};
/* sumber belajar, tips, dan langkah lanjut per tahap roadmap (dari prototipe) */
const NODE_EXTRA = [
  { emoji: '📊', resources: [['Mulai Asesmen di ARKA', '#F3F0FF', '#6B4FCF', '📋'], ['Panduan Memahami Hasil RIASEC', '#EEF2FF', '#2E5FBF', '📖']], tip: 'Kerjakan tes saat pikiranmu segar — pagi hari adalah waktu terbaik untuk hasil yang paling akurat.', nextStep: 'assessment', nextLabel: 'Lanjutkan Asesmen' },
  { emoji: '🎓', resources: [['Smart Career Directory ARKA', '#F3F0FF', '#6B4FCF', '🔍'], ['Data Kebutuhan Kerja Indonesia 2025-2030', '#FFF8E1', '#D97706', '📈'], ['Forum Diskusi Jurusan Online', '#EEF2FF', '#2E5FBF', '💬']], tip: 'Jangan pilih jurusan hanya karena bergengsi. Pilih yang kamu minati — kamu akan jauh lebih berhasil di bidang yang kamu sukai.', nextStep: 'careerDirectory', nextLabel: 'Eksplorasi Direktori Karir' },
  { emoji: '📚', resources: [['Ruangguru — Platform Belajar Online', '#F3F0FF', '#6B4FCF', '💻'], ['Khan Academy (Matematika & Sains)', '#EEF2FF', '#2E5FBF', '🔢'], ['British Council Online (Bahasa Inggris)', '#FFF8E1', '#D97706', '🌍']], tip: 'Buat jadwal 2 jam/hari dan patuhi. Konsisten 6 bulan jauh lebih efektif dari belajar marathon seminggu sebelum ujian.', nextStep: 'chat', nextLabel: 'Minta AI Buatkan Rencana Belajar' },
  { emoji: '💼', resources: [['Google Career Certificates — Gratis', '#F3F0FF', '#6B4FCF', '🎓'], ['Behance / Dribbble (untuk desain)', '#F0FDF4', '#16A34A', '🎨'], ['Coursera — Kursus Online Terpercaya', '#EEF2FF', '#2E5FBF', '🌐']], tip: 'Satu proyek yang benar-benar bagus lebih bernilai dari sepuluh proyek setengah jadi. Pilih kualitas di atas kuantitas.', nextStep: 'mentorSearch', nextLabel: 'Cari Mentor untuk Bimbingan' },
  { emoji: '🏛️', resources: [['SNPMB — Info Resmi SNBP & SNBT', '#EEF2FF', '#2E5FBF', '🏛️'], ['Direktori Kampus & Prodi di ARKA', '#F3F0FF', '#6B4FCF', '🗂️'], ['Latihan Soal Try Out UTBK Online', '#FFF8E1', '#D97706', '📝']], tip: 'Daftar di 3 jalur sekaligus untuk memperbesar peluang. Jangan taruh semua harapan hanya di satu jalur penerimaan.', nextStep: 'chat', nextLabel: 'Diskusi Strategi Masuk Kampus' },
  { emoji: '🚀', resources: [['Glints / LinkedIn — Info Lowongan Magang', '#F3F0FF', '#6B4FCF', '💼'], ['ARKA Mentoring — Senior di Industri', '#EEF2FF', '#2E5FBF', '👨‍💼']], tip: 'Kuliah bukan hanya soal IPK tinggi. Yang lebih penting adalah siapa yang kamu kenal dan apa yang sudah nyata kamu kerjakan.', nextStep: 'mentorSearch', nextLabel: 'Temukan Mentor Industri' },
];
const DEFAULT_NODES = [
  ['Selesaikan Asesmen', 'Kenali minat dan bakat kamu', 'Sekarang'], ['Pilih Jurusan', 'Tentukan 2-3 jurusan target', 'Semester ini'],
  ['Persiapan Akademik', 'Fokus mata pelajaran kunci', '6 bulan'], ['Portofolio & Skill', 'Bangun proyek dan sertifikasi', '1 tahun'],
  ['Daftar Kampus', 'SNBP, SNBT, atau Mandiri', 'Kelas 12'], ['Kuliah & Magang', 'Mulai perjalanan karir', '2-4 tahun'],
];
const TIPS = [
  'Mulai bangun portofolio sedini mungkin! Dokumentasikan proyek sekolah, lomba, dan kegiatan ekstrakurikuler kamu. Ini akan sangat membantu saat mendaftar kuliah atau melamar magang pertama kamu nanti.',
  'Ngobrol dengan kakak kelas atau alumni yang kuliah di jurusan incaranmu. Cerita nyata mereka sering lebih jujur daripada brosur kampus.',
  'Nilai rapor dipakai untuk jalur SNBP. Jaga nilai tetap stabil sejak kelas 10 — konsistensi lebih penting daripada lonjakan di akhir.',
  'Coba ikut satu lomba atau kegiatan di luar kelas semester ini. Pengalaman kecil bisa membantumu tahu apa yang benar-benar kamu sukai.',
  'Bandingkan minimal 3 jurusan sebelum memutuskan: lihat mata kuliahnya, prospek kerja, dan kampus yang membukanya.',
];
const PAGE_TITLES = {
  dashboard: 'Dashboard', chat: 'AI Career Companion', chatHistory: 'Riwayat Chat',
  assessment: 'Asesmen', assessmentTest: 'Pengerjaan Tes', assessmentResult: 'Hasil Asesmen',
  roadmap: 'Career Roadmap', roadmapDetail: 'Detail Roadmap',
  mentorSearch: 'Cari Mentor', mentorProfile: 'Profil Mentor', mentorBooking: 'Booking Sesi',
  mentorSession: 'Sesi Mentoring', mentorPostSession: 'Ringkasan Sesi',
  bkDashboard: 'Dashboard Guru BK', bkStudentProfile: 'Profil Siswa', bkReport: 'Laporan Kelas',
  careerDirectory: 'Smart Career Directory', careerDetail: 'Detail Profesi', settings: 'Pengaturan',
};
const PUBLIC = ['landing', 'register', 'login'];
const BK_PAGES = ['bkDashboard', 'bkStudentProfile', 'bkReport'];

/* ================================================================== */
class Component extends DC.Logic {
  state = {
    page: 'landing', sidebarOpen: false, user: null, userRole: 'siswa', userName: '', userEmail: '',
    regName: '', regEmail: '', regPassword: '', regConfirm: '', regRole: 'siswa',
    loginEmail: '', loginPass: '',
    obStep: 1, nickname: '', birthDate: '', gender: '', city: '',
    school: '', grade: '', major: '', interests: [], concern: '', obDone: false,
    messages: [], sessions: [], chatInput: '', typing: false, histQ: '',
    tests: [], currentTest: '', test: null, currentQ: 0, answers: {}, result: null, resultCareers: [], resultMajors: [],
    roadmap: null, roadmapMsg: '', selNode: 0,
    mentors: [], selMentor: null, bookDate: todayPlus(3), bookTime: '10:00', booking: null, sessionNote: '', reviewText: '', mentorQ: '',
    students: [], bk: null, bkMentoring: 0, selStudent: null, studentDetail: null, bkSum: '', notes: [], noteDraft: '', bkQ: '',
    careers: [], searchQ: '', selCareer: null, careerDetail: null,
    dash: null, activity: null, report: null,
    nChat: true, nMentor: true, nAssess: true,
  };

  constructor() {
    super();
    window.addEventListener('hashchange', () => this.fromHash());
    this.boot();
  }

  async boot() {
    try { const d = await api('/me'); if (d.user) this.applyUser(d.user); } catch (e) { /* offline */ }
    this.fromHash(true);
  }

  applyUser(u) {
    this.setState({ user: u, userRole: u.role, userName: u.name, userEmail: u.email,
      nickname: u.nickname || '', birthDate: u.birth_date || '', gender: u.gender || '', city: u.city || '',
      school: u.school ? u.school.name : '', interests: u.interests || [], concern: u.concern || '' });
  }
  isBKRole(r = this.state.userRole) { return r === 'guru_bk' || r === 'kepsek'; }
  home() { return this.isBKRole() ? 'bkDashboard' : 'dashboard'; }

  /* ---------- navigasi (state + hash URL agar bisa di-refresh) */
  fromHash(first) {
    const [p, id] = (location.hash.replace(/^#\/?/, '') || 'landing').split('/');
    const page = PAGE_TITLES[p] || PUBLIC.includes(p) || p === 'onboarding' ? p : 'landing';
    this.go(page, id, true, first);
  }
  nav(p, id) { location.hash = '/' + p + (id ? '/' + id : ''); }
  async go(page, id, fromHash) {
    const u = this.state.user;
    if (!u && !PUBLIC.includes(page)) page = 'login';
    if (u && PUBLIC.includes(page)) page = u.onboarded ? this.home() : 'onboarding';
    if (u && !u.onboarded && page !== 'onboarding') page = 'onboarding';
    if (u && this.isBKRole() && !BK_PAGES.includes(page) && page !== 'settings' && page !== 'onboarding') page = 'bkDashboard';
    if (u && !this.isBKRole() && BK_PAGES.includes(page)) page = 'dashboard';
    if (this.state.page === 'mentorPostSession' && page !== 'mentorPostSession') this.saveReview();
    const wanted = '/' + page + (id ? '/' + id : '');
    if (location.hash.slice(1) !== wanted) history.replaceState(null, '', '#' + wanted);
    this.setState({ page, sidebarOpen: false });
    window.scrollTo(0, 0);
    try { await this.load(page, id); } catch (e) { if (e.status === 401) { this.setState({ user: null }); this.nav('login'); } else toast(e.message, 'error'); }
  }

  async load(page, id) {
    const S = this.state;
    switch (page) {
      case 'dashboard': {
        const [dash, activity, chat, mentors] = await Promise.all([api('/dashboard'), api('/activity'), api('/chat'), api('/mentors')]);
        this.setState({ dash, activity, sessions: chat.sessions, mentors });
        break;
      }
      case 'chat': case 'chatHistory': {
        const c = await api('/chat');
        this.setState({ messages: c.messages, sessions: c.sessions, hasProfile: c.has_profile });
        break;
      }
      case 'assessment': this.setState({ tests: await api('/assessments') }); break;
      case 'assessmentTest': {
        const key = id || S.currentTest || 'minat';
        const t = await api('/assessments/' + key);
        const first = t.items.findIndex((it) => !t.answers[it.id]);
        this.setState({ currentTest: key, test: t, answers: t.answers, currentQ: first < 0 ? t.items.length - 1 : first });
        break;
      }
      case 'assessmentResult': {
        const key = id || S.currentTest || 'minat';
        const [r, c, m] = await Promise.all([api(`/assessments/${key}/result`), api('/directory?type=careers'), api('/directory?type=majors')]);
        this.setState({ currentTest: key, result: r, resultCareers: c.items, resultMajors: m.items });
        break;
      }
      case 'roadmap': case 'roadmapDetail': {
        const r = await api('/roadmap');
        const c = r.available ? null : await api('/directory?type=careers');
        this.setState({ roadmap: r.available ? r.roadmap : null, roadmapMsg: r.message || '', selNode: id ? Number(id) : S.selNode,
          careers: c ? c.items : S.careers });
        if (r.available && !r.roadmap.is_saved) api('/roadmap/save', { method: 'POST' }).catch(() => {});
        break;
      }
      case 'mentorSearch': case 'mentorProfile': case 'mentorBooking': {
        const mentors = S.mentors.length ? S.mentors : await api('/mentors');
        this.setState({ mentors, selMentor: id ? Number(id) : (S.selMentor || (mentors[0] && mentors[0].id)) });
        break;
      }
      case 'mentorSession': case 'mentorPostSession': {
        if (!S.booking) { const b = await api('/mentoring/bookings'); if (b[0]) this.setState({ booking: b[0], selMentor: b[0].mentor_id }); }
        if (!S.mentors.length) this.setState({ mentors: await api('/mentors') });
        if (!S.dash) this.setState({ dash: await api('/dashboard') });
        break;
      }
      case 'careerDirectory': this.setState({ careers: (await api('/directory?type=careers')).items }); break;
      case 'careerDetail': {
        const cid = id || S.selCareer;
        this.setState({ selCareer: Number(cid), careerDetail: await api('/directory/careers/' + cid) });
        break;
      }
      case 'bkDashboard': {
        const [bk, ov] = await Promise.all([api('/bk/students'), api('/bk/overview')]);
        this.setState({ bk, students: bk.students, bkMentoring: ov.mentoring_month });
        break;
      }
      case 'bkStudentProfile': {
        const sid = Number(id || S.selStudent);
        this.setState({ selStudent: sid, studentDetail: null, studentError: false, bkSum: 'Menyiapkan ringkasan…', notes: [] });
        try {
          const [det, sum, notes] = await Promise.all([api('/bk/students/' + sid), api(`/bk/students/${sid}/summary`), api(`/bk/students/${sid}/notes`)]);
          this.setState({ studentDetail: det, bkSum: sum.text, notes });
        } catch (e) {
          this.setState({ bkSum: e.status === 403 ? 'Akses ditolak: siswa ini bukan siswa asuhan Anda. Percobaan ini dicatat di audit log.' : e.message, studentError: true });
        }
        break;
      }
      case 'bkReport': this.setState({ report: await api('/report') }); break;
      default:
    }
  }

  setF(f, v) { this.setState({ [f]: v }); }
  toggleInterest(i) {
    this.setState((s) => ({ interests: s.interests.includes(i) ? s.interests.filter((x) => x !== i) : [...s.interests, i] }));
  }

  /* ---------- akun */
  async register() {
    const s = this.state;
    if (!s.regName || !s.regEmail || !s.regPassword) return toast('Lengkapi nama, email, dan password.', 'error');
    if (s.regPassword !== s.regConfirm) return toast('Konfirmasi password tidak sama.', 'error');
    try {
      const d = await api('/auth/register', { method: 'POST', body: { name: s.regName, email: s.regEmail, password: s.regPassword, confirm: s.regConfirm, role: s.regRole } });
      this.applyUser(d.user);
      this.setState({ nickname: s.regName.split(' ')[0], obStep: 1, obDone: false, regPassword: '', regConfirm: '' });
      this.nav('onboarding');
    } catch (e) {
      toast(e.message, 'error');
      if (e.data && e.data.action === 'login') this.setState({ loginEmail: s.regEmail });
    }
  }
  async login() {
    const s = this.state;
    if (!s.loginEmail || !s.loginPass) return toast('Isi email dan password.', 'error');
    try {
      const d = await api('/auth/login', { method: 'POST', body: { email: s.loginEmail, password: s.loginPass } });
      this.applyUser(d.user); this.setState({ loginPass: '' });
      this.nav(d.user.onboarded ? this.home() : 'onboarding');
    } catch (e) { toast(e.message, 'error'); }
  }
  async logout() {
    await api('/auth/logout', { method: 'POST' }).catch(() => {});
    this.setState({ user: null, userRole: 'siswa', dash: null, booking: null, messages: [] });
    this.nav('landing');
  }
  async switchRole(to) {
    try { const d = await api('/auth/demo-switch', { method: 'POST', body: { to } }); this.applyUser(d.user); this.setState({ dash: null, booking: null }); this.nav(this.home()); toast(to === 'guru_bk' ? 'Masuk sebagai Guru BK (akun demo)' : 'Masuk sebagai Siswa (akun demo)'); }
    catch (e) { toast(e.message, 'error'); }
  }

  /* ---------- onboarding */
  nextOb() {
    const s = this.state;
    if (s.obStep === 1 && !s.nickname) return toast('Isi nama panggilanmu dulu ya.', 'error');
    if (s.obStep === 2 && (!s.school || !s.grade)) return toast('Isi nama sekolah dan kelas.', 'error');
    if (s.obStep < 3) return this.setState({ obStep: s.obStep + 1 });
    this.submitOnboarding();
  }
  async submitOnboarding() {
    const s = this.state;
    try {
      const d = await api('/onboarding', { method: 'POST', body: { nickname: s.nickname, birthDate: s.birthDate, gender: s.gender, city: s.city,
        school: s.school, grade: s.grade, major: s.major, interests: s.interests, concern: s.concern } });
      this.applyUser(d.user); this.setState({ obDone: true });
    } catch (e) { toast(e.message, 'error'); }
  }
  prevOb() { if (this.state.obStep > 1) this.setState((s) => ({ obStep: s.obStep - 1 })); }
  finishOb() { this.setState({ obDone: false }); this.nav(this.home()); }

  /* ---------- chat (FR-006, FR-007) */
  async sendMsg(text) {
    const txt = (text ?? this.state.chatInput).trim();
    if (!txt || this.state.typing) return;
    this.setState((s) => ({ messages: [...s.messages, { id: 'tmp' + Date.now(), sender: 'user', text: txt }], chatInput: '', typing: true }));
    try {
      const r = await api('/chat', { method: 'POST', body: { text: txt } });
      if (r.crisis) { this.setState((s) => ({ messages: s.messages.map((m, i) => i === s.messages.length - 1 ? { ...m, text: '[pesan disembunyikan]' } : m) })); crisisScreen(r.help); }
      this.setState((s) => ({ messages: [...s.messages, r.message], typing: false }));
      api('/chat').then((c) => this.setState({ sessions: c.sessions })).catch(() => {});
    } catch (e) {
      this.setState((s) => ({ messages: s.messages.slice(0, -1), chatInput: txt, typing: false }));
      toast('Coba lagi nanti. ' + e.message, 'error');
    }
  }

  /* ---------- asesmen (FR-003) */
  startTest(t) { this.nav('assessmentTest', t); }
  async answerQ(itemId, a) {
    const answers = { ...this.state.answers, [itemId]: a };
    this.setState({ answers });
    const pend = JSON.parse(localStorage.getItem('arka-pend') || '{}');
    pend[this.state.currentTest] = { ...(pend[this.state.currentTest] || {}), [itemId]: a };
    localStorage.setItem('arka-pend', JSON.stringify(pend));
    try {
      await api(`/assessments/${this.state.currentTest}/answers`, { method: 'PUT', body: { answers: pend[this.state.currentTest], current_index: this.state.currentQ } });
      delete pend[this.state.currentTest]; localStorage.setItem('arka-pend', JSON.stringify(pend));
    } catch (e) { toast('Offline — jawaban disimpan di perangkat dan dikirim saat tersambung.'); }
  }
  nextQ() { this.setState((s) => ({ currentQ: Math.min(s.currentQ + 1, (s.test?.items.length || 1) - 1) })); }
  prevQ() { this.setState((s) => ({ currentQ: Math.max(s.currentQ - 1, 0) })); }
  async finishTest() {
    const s = this.state, items = s.test.items;
    const miss = items.findIndex((it) => !s.answers[it.id]);
    if (miss >= 0) { this.setState({ currentQ: miss }); return toast(`Masih ada ${items.filter((it) => !s.answers[it.id]).length} pertanyaan yang belum dijawab.`, 'error'); }
    try {
      await api(`/assessments/${s.currentTest}/complete`, { method: 'POST' });
      toast('Asesmen selesai! 🎉'); this.nav('assessmentResult', s.currentTest);
    } catch (e) { toast(e.message, 'error'); }
  }

  /* ---------- roadmap */
  async toggleTask(stepId, idx, done) {
    if (!stepId) return toast('Selesaikan minimal 2 asesmen dulu untuk membuat roadmap personal.', 'error');
    const r = await api(`/roadmap/steps/${stepId}`, { method: 'PATCH', body: { task_index: idx, done } });
    this.setState({ roadmap: r.roadmap });
  }
  async regenRoadmap() {
    try {
      if (!this.state.roadmap) return toast('Selesaikan minimal 2 asesmen untuk membuat roadmap.', 'error');
      const r = await api('/roadmap/regenerate', { method: 'POST' });
      await api('/roadmap/save', { method: 'POST' });
      this.setState({ roadmap: r.roadmap }); toast('Roadmap diperbarui berdasarkan asesmen terbaru.');
    } catch (e) { toast(e.message, 'error'); }
  }

  /* ---------- mentoring */
  async confirmBook() {
    const s = this.state;
    try {
      const b = await api('/mentoring/bookings', { method: 'POST', body: { mentor_id: s.selMentor, date: s.bookDate, time: s.bookTime } });
      this.setState({ booking: b, sessionNote: '' }); toast('Booking berhasil! Sesi dimulai.'); this.nav('mentorSession');
    } catch (e) { toast(e.message, 'error'); }
  }
  async endSession() {
    const b = this.state.booking;
    if (b) await api(`/mentoring/bookings/${b.id}`, { method: 'PATCH', body: { status: 'done', notes: this.state.sessionNote } }).catch(() => {});
    this.setState({ reviewText: '' }); this.nav('mentorPostSession');
  }
  saveReview() {
    const b = this.state.booking;
    if (b && this.state.reviewText.trim()) api(`/mentoring/bookings/${b.id}`, { method: 'PATCH', body: { rating: 5, review: this.state.reviewText } }).then(() => toast('Ulasan tersimpan. Terima kasih!')).catch(() => {});
  }

  /* ---------- BK */
  async saveNote() {
    const s = this.state;
    if (!s.noteDraft.trim()) return toast('Catatan masih kosong.', 'error');
    try { const notes = await api(`/bk/students/${s.selStudent}/notes`, { method: 'POST', body: { text: s.noteDraft } }); this.setState({ notes, noteDraft: '' }); toast('Catatan konseling tersimpan.'); }
    catch (e) { toast(e.message, 'error'); }
  }

  /* ================================================================ nilai untuk template */
  renderVals() {
    const s = this.state;
    const pg = s.page;
    const isPublic = PUBLIC.includes(pg);
    const isOb = pg === 'onboarding';
    const isApp = !isPublic && !isOb;
    const isBK = this.isBKRole();
    const isSiswa = !isBK;
    const u = s.user || {};
    const dash = s.dash || {};
    const score = dash.score ?? 0;

    /* mentor */
    const avBg = ['linear-gradient(135deg,#6B4FCF,#2E5FBF)', 'linear-gradient(135deg,#D97706,#F5A623)', 'linear-gradient(135deg,#2E5FBF,#1B3A7A)', 'linear-gradient(135deg,#E11D48,#F43F5E)'];
    const allMentors = s.mentors.map((m, i) => ({
      id: m.id, name: m.name, role: m.role, co: m.company, rating: m.rating, price: rupiah(m.price), field: m.field,
      initial: m.name[0], avatarBg: avBg[i % avBg.length], onSelect: () => this.nav('mentorProfile', m.id),
    }));
    const mq = s.mentorQ.toLowerCase();
    const mentors = allMentors.filter((m) => !mq || (m.name + m.field + m.role + m.co).toLowerCase().includes(mq));

    /* siswa (BK) */
    const avatarBgs = ['linear-gradient(135deg,#6B4FCF,#4338CA)', 'linear-gradient(135deg,#DC2626,#EF4444)', 'linear-gradient(135deg,#2E5FBF,#1B3A7A)', 'linear-gradient(135deg,#16A34A,#15803D)', 'linear-gradient(135deg,#F59E0B,#D97706)', 'linear-gradient(135deg,#0891B2,#0E7490)'];
    const bq = s.bkQ.toLowerCase();
    const students = s.students.filter((st) => !bq || st.name.toLowerCase().includes(bq)).map((st, i) => {
      const n = st.assess_done;
      const tag = st.tags.includes('Perlu perhatian') ? 'Perlu Perhatian' : st.tags.includes('Tidak aktif 7 hari') ? 'Tidak Aktif' : st.tags.includes('Belum mulai asesmen') ? 'Belum Asesmen' : '';
      return {
        id: st.id, name: st.name, score: st.score, grade: st.class_name, last: timeAgo(st.last_active_at), tag, initial: st.name[0],
        onSelect: () => this.nav('bkStudentProfile', st.id),
        scoreColor: st.score >= 70 ? '#16A34A' : st.score >= 40 ? '#F59E0B' : '#DC2626', hasTag: !!tag,
        assessLabel: n === 4 ? 'Selesai' : n === 0 ? 'Belum' : `${n}/4`,
        assessColor: n === 4 ? '#16A34A' : '#F59E0B', assessBg: n === 4 ? '#F0FDF4' : '#FFF8E1',
        rowAvatarBg: avatarBgs[i % avatarBgs.length],
      };
    });
    const det = s.studentDetail;
    const selStudent = det ? {
      initial: det.student.name[0], name: det.student.name, grade: det.student.class_name || ('Kelas ' + (det.student.grade || '-')), score: det.score,
      scoreColor: det.score >= 70 ? '#16A34A' : det.score >= 40 ? '#F59E0B' : '#DC2626',
      assess: det.assessments.map((a) => ({ text: `${a.name.replace('Tes ', '')}: ${a.done ? a.label + ' ✓' : 'Belum selesai'}`, bg: a.done ? '#F0FDF4' : '#FFF8E1', color: a.done ? '#16A34A' : '#D97706' })),
    } : s.studentError ? { initial: '🔒', name: 'Akses ditolak', grade: 'Bukan siswa asuhan Anda', score: '-', scoreColor: '#DC2626', assess: [] }
      : { initial: '…', name: 'Memuat…', grade: '', score: '-', scoreColor: '#6B7280', assess: [] };

    /* karier */
    const sq = s.searchQ.toLowerCase();
    const mapCareer = (c) => ({ id: c.id, name: c.name, field: c.field, salary: c.salary, match: c.match ?? '—', desc: c.description, skills: c.skills || [], onSelect: () => this.nav('careerDetail', c.id) });
    const careers = s.careers.filter((c) => !sq || (c.name + c.field + c.description).toLowerCase().includes(sq)).map(mapCareer);
    const cd = s.careerDetail;
    const selCareer = cd ? { name: cd.name, field: cd.field, match: cd.match ?? '—', desc: cd.description, skills: cd.skills, salary: cd.salary } : { name: 'Memuat…', field: '', match: '—', desc: '', skills: [] };
    const topCareer = (dash.careers && dash.careers[0]) || null;

    /* roadmap */
    const rd = s.roadmap;
    const steps = rd ? rd.steps : DEFAULT_NODES.map(([title, desc, period], i) => ({ id: null, title, description: desc, period, done: false, tasks: i === 0 ? ['minat', 'bakat', 'kepribadian', 'nilai'].map((k) => ({ text: 'Selesaikan Tes ' + k[0].toUpperCase() + k.slice(1), done: false })) : [] }));
    const roadmapNodes = steps.map((n, i) => ({
      title: n.title, desc: n.description, period: n.period, done: n.done,
      onSelect: () => this.nav('roadmapDetail', i),
      borderColor: n.done ? '#16A34A' : '#E8E5F0', dotBg: n.done ? '#16A34A' : '#E8E5F0', dotColor: n.done ? '#fff' : '#9CA3AF',
      dotIcon: n.done ? '✓' : '○', titleColor: n.done ? '#16A34A' : '#1B2547',
    }));
    const ni = Math.min(s.selNode || 0, steps.length - 1);
    const node = steps[ni], ex = NODE_EXTRA[ni] || NODE_EXTRA[0];
    const partial = node.tasks.some((t) => t.done);
    const selRND = {
      emoji: ex.emoji, title: node.title, period: node.period, desc: node.description, tip: ex.tip, nextLabel: ex.nextLabel,
      statusLabel: node.done ? 'Selesai ✓' : partial ? 'Dalam Proses' : 'Belum Dimulai',
      statusColor: node.done ? '#16A34A' : partial ? '#F59E0B' : '#9CA3AF', statusBg: node.done ? '#F0FDF4' : partial ? '#FFF8E1' : '#F5F3F0',
      skills: node.tasks.map((t, j) => ({ text: t.text, bg: t.done ? '#F3F0FF' : '#FAF9F7', checkBg: t.done ? '#6B4FCF' : '#E8E5F0', checkIcon: t.done ? '✓' : '',
        textDeco: t.done ? 'line-through' : 'none', textColor: t.done ? '#9CA3AF' : '#1B2547', onToggle: () => this.toggleTask(node.id, j, !t.done) })),
      resources: ex.resources.map(([title, color, textColor, emoji]) => ({ title, color, textColor, emoji })),
      onNext: () => this.nav(ex.nextStep),
    };
    const rmDone = steps.filter((n) => n.done).length;
    const rmTop = rd ? rd.data.careers[0] : null;

    /* hasil asesmen */
    const res = this.resultVals();

    /* tes */
    const t = s.test;
    const item = t ? t.items[s.currentQ] : null;
    const scaleOpts = [1, 2, 3, 4, 5].map((n) => {
      const on = item && s.answers[item.id] === n;
      return { val: n, label: ['Sangat Tidak Setuju', 'Tidak Setuju', 'Netral', 'Setuju', 'Sangat Setuju'][n - 1], active: on,
        onClick: () => { this.answerQ(item.id, n); if (s.currentQ < t.items.length - 1) setTimeout(() => this.nextQ(), 180); },
        bg: on ? '#F3F0FF' : '#fff', border: on ? '#6B4FCF' : '#E8E5F0', dotBorder: on ? '#6B4FCF' : '#D1D5DB', textColor: on ? '#6B4FCF' : '#4A5568' };
    });
    const totalQ = t ? t.items.length : 10;
    const testProgress = t ? t.items.filter((it) => s.answers[it.id]).length : 0;
    const isLastQ = t && s.currentQ >= totalQ - 1;

    const testTypes = s.tests.map((x) => ({
      ...TEST_META[x.key], key: x.key, name: x.name, time: `${x.minutes} menit`, done: x.done,
      onStart: x.done ? () => this.nav('assessmentResult', x.key) : () => this.startTest(x.key),
      statusLabel: x.done ? '✓ Lihat Hasil' : x.in_progress ? `Lanjutkan (${x.answered}/${x.total}) →` : 'Mulai Tes →',
      btnBg: x.done ? '#F0FDF4' : 'linear-gradient(135deg,#6B4FCF,#2E5FBF)', btnColor: x.done ? '#16A34A' : '#fff',
    }));
    const assessDone = s.tests.length ? s.tests.filter((x) => x.done).length : (dash.assess_done || 0);

    /* chat */
    const msgList = [{ id: 0, sender: 'ai', text: `Halo${u.nickname ? ' ' + u.nickname : ''}! Aku ARKA, AI Career Companion kamu. Aku ingat obrolan kita sebelumnya dan menjawab berdasarkan profilmu. Cerita dong, ada apa hari ini?` }, ...s.messages].map((m) => {
      const me = m.sender === 'user';
      const src = m.sources && m.sources.length ? '\n\nSumber: ' + m.sources.join(' · ') : '';
      return { id: m.id, text: String(m.text).replace(/\*\*(.+?)\*\*/g, '$1') + src, isAI: !me, align: me ? 'flex-end' : 'flex-start',
        bg: me ? 'linear-gradient(135deg,#6B4FCF,#4338CA)' : m.kind === 'crisis' ? '#FEF2F2' : m.kind === 'offtopic' ? '#FFF8E1' : '#fff',
        txtColor: me ? '#fff' : '#1B2547', radius: me ? '18px 18px 4px 18px' : '4px 18px 18px 18px',
        shadow: me ? '0 2px 8px rgba(107,79,207,.25)' : '0 1px 4px rgba(0,0,0,.06)' };
    });
    const sesIcon = (topic) => {
      const tp = (topic || '').toLowerCase();
      if (/beasiswa|biaya/.test(tp)) return ['🏆', '#FEF2F2', 'Beasiswa'];
      if (/snbt|snbp|utbk|ujian/.test(tp)) return ['📝', '#EEF2FF', 'Ujian'];
      if (/tes|asesmen|hasil|minat/.test(tp)) return ['📊', '#FFF8E1', 'Asesmen'];
      if (/skill|portofolio|belajar/.test(tp)) return ['💼', '#F0FDF4', 'Skill'];
      if (/jurusan|kuliah|kampus|prodi/.test(tp)) return ['🎓', '#F3F0FF', 'Jurusan'];
      return ['💬', '#F3F0FF', 'Karier'];
    };
    const hq = s.histQ.toLowerCase();
    const chatSessions = s.sessions.filter((x) => !hq || (x.topic || '').toLowerCase().includes(hq)).map((x) => {
      const [icon, iconBg, tag] = sesIcon(x.topic);
      return { topic: x.topic || 'Sesi baru', date: fmtDate(x.started_at), summary: `${x.n} pesan · terakhir ${timeAgo(x.last_at)}`, icon, iconBg, tag };
    });

    /* dashboard */
    const act = s.activity || { activities: [], milestones: [] };
    const milestones = act.milestones.map((m) => ({ ...m, checkBg: m.done ? '#6B4FCF' : '#E8E5F0', checkColor: m.done ? '#fff' : '#9CA3AF', checkIcon: m.done ? '✓' : '○',
      textColor: m.done ? '#9CA3AF' : '#1B2547', textDeco: m.done ? 'line-through' : 'none', rowBg: m.done ? '#F8F7FF' : '#FAFAFA' }));
    const nextTest = (dash.missing || [])[0];
    const fieldMentor = topCareer && allMentors.find((m) => topCareer.field.includes(m.field)) || allMentors[0];
    const notifs = [
      nextTest ? { text: `${nextTest.name} kamu belum selesai — lanjutkan sekarang!`, type: 'warning' } : { text: 'Semua asesmen sudah selesai. Mantap!', type: 'success' },
      fieldMentor ? { text: `Ada mentor ${fieldMentor.field.toLowerCase()} sesuai profilmu: ${fieldMentor.name}`, type: 'info' } : null,
      dash.roadmap ? { text: `Roadmap ${dash.roadmap.is_saved ? 'tersimpan' : 'siap'} — progres ${dash.roadmap.progress}%`, type: 'success' } : { text: 'Selesaikan 2 asesmen untuk membuka Career Roadmap', type: 'info' },
    ].filter(Boolean).map((n) => ({ ...n, bg: n.type === 'warning' ? '#FFF8E1' : n.type === 'info' ? '#EEF2FF' : '#F0FDF4', dotColor: n.type === 'warning' ? '#F59E0B' : n.type === 'info' ? '#2E5FBF' : '#16A34A' }));
    const aiRecs = [
      nextTest ? { icon: '🎯', title: `Lanjutkan ${nextTest.name}`, desc: `Kamu sudah menyelesaikan ${dash.assess_done || 0} dari 4 asesmen. Lanjutkan untuk hasil yang lebih akurat!`, bg: 'linear-gradient(135deg,#F3F0FF,#E8E3FA)', titleColor: '#6B4FCF', onClick: () => this.startTest(nextTest.key) }
        : { icon: '🗺️', title: 'Buka Career Roadmap', desc: 'Semua asesmen selesai. Lihat langkah berikutnya di roadmap-mu.', bg: 'linear-gradient(135deg,#F3F0FF,#E8E3FA)', titleColor: '#6B4FCF', onClick: () => this.nav('roadmap') },
      topCareer ? { icon: '💡', title: `Eksplorasi ${topCareer.name}`, desc: `Kecocokanmu ${topCareer.match}% berdasarkan asesmen. Pelajari lebih lanjut karir ini.`, bg: 'linear-gradient(135deg,#EEF2FF,#E0E7FF)', titleColor: '#2E5FBF', onClick: () => this.nav('careerDetail', topCareer.id) }
        : { icon: '💡', title: 'Jelajahi Direktori Karir', desc: 'Lihat profesi dan jurusan yang ada di Indonesia.', bg: 'linear-gradient(135deg,#EEF2FF,#E0E7FF)', titleColor: '#2E5FBF', onClick: () => this.nav('careerDirectory') },
      fieldMentor ? { icon: '👨‍🏫', title: 'Sesi dengan Mentor', desc: `${fieldMentor.name}, ${fieldMentor.role} di ${fieldMentor.co}.`, bg: 'linear-gradient(135deg,#FFF8E1,#FEF3C7)', titleColor: '#92400E', onClick: () => this.nav('mentorProfile', fieldMentor.id) } : null,
    ].filter(Boolean).map((r) => ({ ...r, descColor: '#6B7280' }));
    const dotByKind = { assess: '#16A34A', chat: '#6B4FCF', roadmap: '#2E5FBF', mentor: '#F5A623', join: '#9CA3AF' };
    const activities = act.activities.map((a) => ({ text: a.text, time: timeAgo(a.at), dotColor: dotByKind[a.kind] || '#9CA3AF' }));

    /* sidebar */
    const sbSiswa = [['Dashboard', '◉', 'dashboard'], ['AI Companion', '◈', 'chat'], ['Asesmen', '◇', 'assessment'], ['Roadmap', '▷', 'roadmap'], ['Mentoring', '◎', 'mentorSearch'], ['Direktori Karir', '◆', 'careerDirectory'], ['Pengaturan', '○', 'settings']];
    const sbBK = [['Dashboard', '◉', 'bkDashboard'], ['Laporan Kelas', '◇', 'bkReport'], ['Pengaturan', '○', 'settings']];
    const activePages = { dashboard: ['dashboard'], chat: ['chat', 'chatHistory'], assessment: ['assessment', 'assessmentTest', 'assessmentResult'], roadmap: ['roadmap', 'roadmapDetail'],
      mentorSearch: ['mentorSearch', 'mentorProfile', 'mentorBooking', 'mentorSession', 'mentorPostSession'], careerDirectory: ['careerDirectory', 'careerDetail'], settings: ['settings'],
      bkDashboard: ['bkDashboard', 'bkStudentProfile'], bkReport: ['bkReport'] };
    const sbItems = (isBK ? sbBK : sbSiswa).map(([label, icon, page]) => {
      const active = (activePages[page] || [page]).includes(pg);
      return { label, icon, page, onClick: () => this.nav(page), bg: active ? 'rgba(107,79,207,0.1)' : 'transparent', fw: active ? '700' : '500', color: active ? '#6B4FCF' : '#4A5568' };
    });

    /* BK & laporan */
    const bk = s.bk || { stats: { total: 0 }, school: { name: '-' } };
    const bkAlerts = [
      ...s.students.filter((st) => st.tags.includes('Perlu perhatian')).slice(0, 2).map((st, i) => ({
        text: `${st.name} (${st.class_name}) skor ${st.score}${st.tags.includes('Tidak aktif 7 hari') ? ' dan tidak aktif lebih dari 7 hari' : ''}${st.assess_done === 0 ? ', belum mulai asesmen' : ''}`,
        action: () => this.nav('bkStudentProfile', st.id), bg: i === 0 ? '#FEF2F2' : '#FFF8E1', borderColor: i === 0 ? '#DC2626' : '#F59E0B', textColor: i === 0 ? '#991B1B' : '#92400E', icon: i === 0 ? '🚨' : '⚠️' })),
      { text: `${bk.stats.no_assessment || 0} siswa belum memulai asesmen${bk.stats.pending_consent ? ` · ${bk.stats.pending_consent} menunggu persetujuan orang tua` : ''}`, action: () => this.setState({ bkQ: '' }), bg: '#EEF2FF', borderColor: '#2E5FBF', textColor: '#1E3A5F', icon: '📋' },
    ];
    const rp = s.report;
    const dist = rp && rp.score_dist ? rp.score_dist : [0, 0, 0, 0, 0];
    const maxD = Math.max(1, ...dist);
    const rep = { subtitle: rp ? (rp.hidden ? `Data disembunyikan: kurang dari ${rp.min_group} siswa` : `${rp.school.name} · ${rp.n} siswa aktif · ${rp.pct_2plus}% selesai ≥2 asesmen · laporan tanpa nama`) : 'Memuat…',
      interests: (rp && rp.interests ? rp.interests : []).map((x, i) => ({ ...x, color: ['#6B4FCF', '#2E5FBF', '#F5A623', '#16A34A', '#9CA3AF'][i] })) };
    dist.forEach((n, i) => { rep['h' + i] = Math.max(4, Math.round(n / maxD * 100)); rep['n' + i] = n; });

    const prof = s.profileLine;
    const circ = 2 * Math.PI * 54;
    const interestOpts = ['Teknologi', 'Seni & Desain', 'Kesehatan', 'Bisnis', 'Hukum', 'Pendidikan', 'Teknik', 'Sosial', 'Media', 'Olahraga', 'Lingkungan', 'Kuliner'];
    const concernOpts = ['Tidak tahu mau jadi apa', 'Takut salah pilih jurusan', 'Tidak tahu cara memulai', 'Khawatir soal biaya kuliah', 'Merasa kurang skill'];
    const selM = allMentors.find((m) => m.id === s.selMentor) || allMentors[0] || { name: '-', initial: '-', role: '', co: '', price: '0', rating: '-', field: '' };

    return {
      pg, isPublic, isOb, isApp, isBK, isSiswa,
      showLanding: pg === 'landing', showRegister: pg === 'register', showLogin: pg === 'login',
      showOb: isOb, showObForm: isOb && !s.obDone,
      showDash: pg === 'dashboard', showChat: pg === 'chat', showChatHist: pg === 'chatHistory', showAssess: pg === 'assessment',
      showAssessTest: pg === 'assessmentTest', showAssessResult: pg === 'assessmentResult',
      showRoadmap: pg === 'roadmap', showRoadDetail: pg === 'roadmapDetail',
      showMentorSearch: pg === 'mentorSearch', showMentorProfile: pg === 'mentorProfile', showMentorBook: pg === 'mentorBooking',
      showMentorSession: pg === 'mentorSession', showMentorPost: pg === 'mentorPostSession', showBKDash: pg === 'bkDashboard',
      showBKStudent: pg === 'bkStudentProfile', showBKReport: pg === 'bkReport', showDirectory: pg === 'careerDirectory',
      showCareerDetail: pg === 'careerDetail', showSettings: pg === 'settings',
      userName: u.nickname && isSiswa ? u.nickname : (s.userName || ''), userInitial: (s.userName || 'A')[0], userEmail: s.userEmail,
      sidebarOpen: s.sidebarOpen,
      regName: s.regName, regEmail: s.regEmail, regPassword: s.regPassword, regConfirm: s.regConfirm, regRole: s.regRole,
      loginEmail: s.loginEmail, loginPass: s.loginPass,
      obStep: s.obStep, obDone: s.obDone, nickname: s.nickname, birthDate: s.birthDate, gender: s.gender, city: s.city, school: s.school, grade: s.grade, major: s.major,
      chatInput: s.chatInput, typing: s.typing, currentQ: s.currentQ,
      bookDate: s.bookDate, bookTime: s.bookTime, searchQ: s.searchQ, mentorQ: s.mentorQ, bkQ: s.bkQ, histQ: s.histQ,
      nChat: s.nChat, nMentor: s.nMentor, nAssess: s.nAssess,
      selRND, sbItems, mentors, students, careers: pg === 'assessmentResult' ? res.careersTop : careers, roadmapNodes, milestones, notifs, aiRecs, activities, bkAlerts,
      suggestedPrompts: ['Jurusan apa yang cocok untuk saya?', 'Bedanya Informatika dan Sistem Informasi?', 'Skill apa yang harus saya pelajari?', 'Info beasiswa kuliah']
        .map((text) => ({ text, onClick: () => this.sendMsg(text) })),
      assessDone, assessTotal: 4, assessPct: assessDone * 25, assessRemaining: 4 - assessDone,
      interestChips: interestOpts.map((i) => { const on = s.interests.includes(i); return { label: i, active: on, onClick: () => this.toggleInterest(i), bg: on ? '#6B4FCF' : '#fff', color: on ? '#fff' : '#4A5568', borderColor: on ? '#6B4FCF' : '#E8E5F0' }; }),
      concernChips: concernOpts.map((c) => { const on = s.concern === c; return { label: c, active: on, onClick: () => this.setF('concern', c), bg: on ? '#F3F0FF' : '#fff', color: on ? '#6B4FCF' : '#4A5568', borderColor: on ? '#6B4FCF' : '#E8E5F0' }; }),
      scaleOpts, testTypes, msgList, chatSessions,
      selMentor: selM, selStudent, selCareer, riasecBars: res.bars, res, campuses: res.campuses,
      pageTitle: PAGE_TITLES[pg] || '',
      currentQText: item ? item.text : 'Memuat pertanyaan…', currentQDisplay: s.currentQ + 1,
      testProgress, totalQ, testProgressPct: totalQ ? (testProgress / totalQ) * 100 : 0,
      score, circ, scoreOff: circ * (1 - score / 100),
      scoreColor: score >= 70 ? '#16A34A' : score >= 40 ? '#F59E0B' : '#DC2626',
      obPct: (s.obStep / 3) * 100, obStep1: s.obStep === 1, obStep2: s.obStep === 2, obStep3: s.obStep === 3,
      showPrevOb: s.obStep > 1, obNextLabel: s.obStep < 3 ? 'Lanjut' : 'Selesai',
      nextOrFinishLabel: isLastQ ? 'Selesai' : 'Berikutnya →',
      handleNextOrFinish: isLastQ ? () => this.finishTest() : () => this.nextQ(),
      nChatBg: s.nChat ? '#6B4FCF' : '#D1D5DB', nChatTransform: s.nChat ? 'translateX(20px)' : 'translateX(0)',
      nMentorBg: s.nMentor ? '#6B4FCF' : '#D1D5DB', nMentorTransform: s.nMentor ? 'translateX(20px)' : 'translateX(0)',
      nAssessBg: s.nAssess ? '#6B4FCF' : '#D1D5DB', nAssessTransform: s.nAssess ? 'translateX(20px)' : 'translateX(0)',
      /* nilai tambahan (bagian template yang dulunya statis) */
      lastChat: dash.last_chat ? dash.last_chat.text.slice(0, 80) + (dash.last_chat.text.length > 80 ? '…' : '') : 'Belum ada obrolan — tanyakan apa saja soal jurusan!',
      msLabel: `${milestones.filter((m) => m.done).length}/${milestones.length || 5} selesai`,
      dailyTip: TIPS[new Date().getDate() % TIPS.length],
      histSessions: s.sessions.length, histQuestions: s.sessions.reduce((a, x) => a + Math.ceil(x.n / 2), 0),
      histRecs: s.messages.filter((m) => m.sources && m.sources.length).length,
      rmSubtitle: rmTop ? `Jalur karir kamu menuju ${rmTop.name}` : (s.roadmapMsg || 'Selesaikan minimal 2 asesmen untuk membuat roadmap personal'),
      rmDone, rmTotal: steps.length, rmLeft: steps.length - rmDone, rmPct: rd ? rd.progress : 0,
      rmTarget: rmTop ? rmTop.name : (careers[0] ? careers[0].name : 'Belum ditentukan'),
      rmTargetMatch: rmTop ? `Kecocokan ${rmTop.match}% berdasarkan asesmen` : 'Kerjakan asesmen untuk melihat kecocokan',
      aiProfileLine: `Minat: ${(u.interests || []).join(' & ') || '-'} · Kelas: ${u.class_name || '-'} · Skor: ${score}/100 · Target: ${topCareer ? topCareer.name : '-'}`,
      sessionNote: s.sessionNote, reviewText: s.reviewText,
      bkSchoolLine: `${bk.school.name} · ${bk.stats.total} siswa aktif`, bkActive: bk.stats.total,
      bkLow: s.students.filter((x) => x.score < 40).length, bkNoAssess: bk.stats.no_assessment || 0, bkMentoring: s.bkMentoring,
      bkSum: s.bkSum, notes: s.notes.map((n) => ({ date: fmtDate(n.created_at), text: n.text })), noteDraft: s.noteDraft, rep, prof,
      /* aksi */
      goLanding: () => this.nav('landing'), goRegister: () => this.nav('register'), goLogin: () => this.nav('login'),
      goDash: () => this.nav('dashboard'), goChat: () => this.nav('chat'), goChatHist: () => this.nav('chatHistory'),
      goAssess: () => this.nav('assessment'), goRoadmap: () => this.nav('roadmap'), goMentorSearch: () => this.nav('mentorSearch'),
      goDirectory: () => this.nav('careerDirectory'), goSettings: () => this.nav('settings'), goBKDash: () => this.nav('bkDashboard'),
      goBKReport: () => this.nav('bkReport'), goMentorBook: () => this.nav('mentorBooking', s.selMentor), goMentorProfile: () => this.nav('mentorProfile', s.selMentor),
      goMentorSession: () => this.nav('mentorSession'), goMentorPost: () => this.nav('mentorPostSession'),
      toggleSidebar: () => this.setState((st) => ({ sidebarOpen: !st.sidebarOpen })),
      register: () => this.register(), login: () => this.login(),
      nextOb: () => this.nextOb(), prevOb: () => this.prevOb(), finishOb: () => this.finishOb(),
      sendMsg: () => this.sendMsg(), nextQ: () => this.nextQ(), prevQ: () => this.prevQ(), finishTest: () => this.finishTest(),
      logout: () => this.logout(), switchBK: () => this.switchRole('guru_bk'), switchSiswa: () => this.switchRole('siswa'),
      confirmBook: () => this.confirmBook(), endSession: () => this.endSession(),
      regenRoadmap: () => this.regenRoadmap(), saveNote: () => this.saveNote(), printReport: () => window.print(),
      chatKeydown: (e) => { if (e.key === 'Enter') { e.preventDefault(); this.sendMsg(e.target.value); } },
      onRegName: (e) => this.setF('regName', e.target.value), onRegEmail: (e) => this.setF('regEmail', e.target.value),
      onRegPass: (e) => this.setF('regPassword', e.target.value), onRegConfirm: (e) => this.setF('regConfirm', e.target.value),
      onRegRole: (e) => this.setF('regRole', e.target.value),
      onLoginEmail: (e) => this.setF('loginEmail', e.target.value), onLoginPass: (e) => this.setF('loginPass', e.target.value),
      onNickname: (e) => this.setF('nickname', e.target.value), onBirthDate: (e) => this.setF('birthDate', e.target.value),
      onGender: (e) => this.setF('gender', e.target.value), onCity: (e) => this.setF('city', e.target.value),
      onSchool: (e) => this.setF('school', e.target.value), onGrade: (e) => this.setF('grade', e.target.value), onMajor: (e) => this.setF('major', e.target.value),
      onChatInput: (e) => this.setF('chatInput', e.target.value), onSearchQ: (e) => this.setF('searchQ', e.target.value),
      onBookDate: (e) => this.setF('bookDate', e.target.value), onBookTime: (e) => this.setF('bookTime', e.target.value),
      onMentorQ: (e) => this.setF('mentorQ', e.target.value), onBkQ: (e) => this.setF('bkQ', e.target.value), onHistQ: (e) => this.setF('histQ', e.target.value),
      onSessionNote: (e) => this.setF('sessionNote', e.target.value), onReviewText: (e) => this.setF('reviewText', e.target.value),
      onNoteDraft: (e) => this.setF('noteDraft', e.target.value),
      toggleNChat: () => this.setState((st) => ({ nChat: !st.nChat })), toggleNMentor: () => this.setState((st) => ({ nMentor: !st.nMentor })),
      toggleNAssess: () => this.setState((st) => ({ nAssess: !st.nAssess })),
    };
  }

  /* hasil asesmen sesuai jenis tes */
  resultVals() {
    const s = this.state, r = s.result && s.result.latest && s.result.latest.result, key = s.currentTest;
    const careersTop = s.resultCareers.slice(0, 4).map((c) => ({ id: c.id, name: c.name, field: c.field, salary: c.salary.replace('/bln', ''), match: c.match ?? '—', desc: c.description, skills: c.skills, onSelect: () => this.nav('careerDetail', c.id) }));
    const campusMap = new Map();
    s.resultMajors.slice(0, 4).forEach((m) => (m.campuses || []).forEach((c) => { if (!campusMap.has(c)) campusMap.set(c, []); campusMap.get(c).push(m.name); }));
    const campuses = [...campusMap.entries()].slice(0, 4).map(([c, ms]) => { const k = CAMPUS[c] || [c.slice(0, 3).toUpperCase(), '#F3F0FF', '#6B4FCF']; return { abbr: k[0], bg: k[1], color: k[2], name: k[3] || c, majors: ms.slice(0, 2).join(', ') }; });
    const empty = { careersTop, title: 'Hasil Asesmen', headline: 'Memuat…', desc: '', v1: '', l1: '', v2: '', l2: '', v3: '', l3: '', barsTitle: '', bars: [], c1t: '', c1d: '', c2t: '', c2d: '', c3t: '', c3d: '', campuses };
    if (!r) return empty;
    const bestMatch = careersTop[0] ? careersTop[0].match + '%' : '—';
    const sorted = (scores, names) => Object.entries(scores).sort((a, b) => b[1] - a[1]).map(([k, v], i) => ({ label: names[k], pct: v, barColor: BAR_COLORS[i % BAR_COLORS.length] }));
    if (key === 'minat') {
      const [a, b] = r.top;
      return { ...empty, title: 'Hasil Asesmen Minat', headline: `${RIASEC[a]}–${RIASEC[b]}`,
        desc: `Kamu paling menikmati ${RIASEC_INFO[a][3]} serta ${RIASEC_INFO[b][3]}. Hasil ini indikasi, bukan penentu jurusan.`,
        v1: r.scores[a] + '%', l1: RIASEC[a], v2: r.scores[b] + '%', l2: RIASEC[b], v3: bestMatch, l3: 'Kecocokan',
        barsTitle: 'Profil Minat RIASEC', bars: sorted(r.scores, RIASEC),
        c1t: 'Gaya Belajar', c1d: RIASEC_INFO[a][0], c2t: 'Lingkungan Kerja Ideal', c2d: RIASEC_INFO[a][1], c3t: 'Kekuatan Utama', c3d: RIASEC_INFO[a][2] + ' ' + RIASEC_INFO[b][2] };
    }
    if (key === 'bakat') {
      const [a, b] = r.top;
      return { ...empty, title: 'Hasil Asesmen Bakat', headline: `${TALENTS[a]} & ${TALENTS[b]}`, desc: r.summary + ' Hasil ini indikasi, bukan diagnosis.',
        v1: r.scores[a] + '%', l1: TALENTS[a], v2: r.scores[b] + '%', l2: TALENTS[b], v3: bestMatch, l3: 'Kecocokan',
        barsTitle: 'Profil Kecerdasan Majemuk', bars: sorted(r.scores, TALENTS),
        c1t: 'Kekuatan Utama', c1d: r.top.map((k) => TALENTS[k]).join(', '), c2t: 'Cara Mengembangkan', c2d: 'Pilih kegiatan yang memakai kekuatan ini — ekskul, lomba, atau proyek kecil — agar makin terasah.', c3t: 'Catatan', c3d: 'Kecerdasan bisa berkembang. Gunakan hasil ini untuk eksplorasi, bukan untuk membatasi diri.' };
    }
    if (key === 'nilai') {
      const [a, b] = r.top;
      return { ...empty, title: 'Hasil Asesmen Nilai Karir', headline: `${VALUES[a]} & ${VALUES[b]}`, desc: r.summary,
        v1: r.scores[a] + '%', l1: VALUES[a], v2: r.scores[b] + '%', l2: VALUES[b], v3: bestMatch, l3: 'Kecocokan',
        barsTitle: 'Profil Nilai Kerja', bars: sorted(r.scores, VALUES),
        c1t: 'Yang Paling Penting', c1d: r.top.map((k) => VALUES[k]).join(', '), c2t: 'Lingkungan Kerja Ideal', c2d: `Tempat kerja yang menghargai ${VALUES[a].toLowerCase()}.`, c3t: 'Tips', c3d: 'Saat membandingkan jurusan atau profesi, cek apakah sejalan dengan nilai-nilai ini.' };
    }
    const d0 = r.dims;
    return { ...empty, title: 'Hasil Asesmen Kepribadian', headline: `Pola ${r.type}`, desc: r.summary + ' Ini kecenderungan, bukan label tetap.',
      v1: d0[0].left_pct >= 50 ? d0[0].left_pct + '%' : (100 - d0[0].left_pct) + '%', l1: d0[0].left_pct >= 50 ? 'Ekstrover' : 'Introver',
      v2: d0[2].left_pct >= 50 ? d0[2].left_pct + '%' : (100 - d0[2].left_pct) + '%', l2: d0[2].left_pct >= 50 ? 'Logika' : 'Perasaan',
      v3: bestMatch, l3: 'Kecocokan', barsTitle: 'Dimensi Kepribadian',
      bars: d0.map((x, i) => { const left = x.left_pct >= 50; return { label: left ? x.left : x.right, pct: left ? x.left_pct : 100 - x.left_pct, barColor: BAR_COLORS[i] }; }),
      c1t: 'Cara Berinteraksi', c1d: d0[0].left_pct >= 50 ? 'Kamu mendapat energi dari bertemu banyak orang.' : 'Kamu mengisi energi lewat waktu tenang dan refleksi.',
      c2t: 'Cara Mengambil Keputusan', c2d: d0[2].left_pct >= 50 ? 'Kamu cenderung memakai logika dan data.' : 'Kamu cenderung mempertimbangkan perasaan dan nilai.',
      c3t: 'Cara Bekerja', c3d: d0[3].left_pct >= 50 ? 'Kamu nyaman dengan jadwal dan rencana yang jelas.' : 'Kamu nyaman dengan keleluasaan dan spontanitas.' };
  }
}

window.addEventListener('DOMContentLoaded', async () => {
  const tpl = await (await fetch('/template.html')).text();
  const el = document.getElementById('dc-root');
  el.innerHTML = '';
  const app = new Component();
  window.__arka = app;
  DC.mount(tpl, app, el);
});
