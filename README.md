# Jelajah Malang Selatan — Docker (Ubuntu + Docker Desktop + Nginx)

Paket ini menggabungkan HTML yang dikirim, backend Flask yang ada di ZIP backend, Nginx, dan MariaDB. URL publik dan dashboard:

- `/` — website publik
- `/admin` — login khusus role `super` (Admin Utama)
- `/pengeloladesa` — login khusus role `desa`
- `/damri` — login khusus role `damri`
- `/api/health` — pemeriksaan backend/database

Semua URL dashboard menyajikan HTML yang sama. JavaScript memilih tampilan berdasarkan path, lalu memeriksa sesi melalui backend.

## 1. Persiapan di Ubuntu

Pastikan Docker Desktop sudah aktif dan integrasi/akses Docker Engine tersedia di terminal Ubuntu. Periksa:

```bash
docker version
docker compose version
```

Ekstrak ZIP, masuk ke folder `jelajah-malang-selatan-docker`, lalu:

```bash
cp .env.example .env
nano .env
```

Ganti `DB_PASSWORD`, `DB_ROOT_PASSWORD`, `SECRET_KEY`, dan `API_KEY` dengan nilai acak kuat. Contoh membuat secret:

```bash
openssl rand -hex 32
```

Jalankan perintah tersebut beberapa kali dan gunakan hasil berbeda untuk setiap secret. Jangan kirim file `.env` ke orang lain atau unggah ke GitHub.

## 2. Jalankan container

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f
```

Akses `http://IP-PUBLIK/`. Port 80 harus diizinkan pada firewall Ubuntu dan firewall/security group penyedia server. Backend port 5000 dan MariaDB 3306 tidak dipublikasikan ke internet.

Tes backend:

```bash
curl http://127.0.0.1/api/health
```

## 3. Buat akun login pertama

Buat Admin Utama (password diminta secara interaktif dan disimpan sebagai hash):

```bash
docker compose exec backend python manage_users.py create --username admin --name "Admin Utama" --role super
```

Buat akun pengelola desa. Contoh Bantur:

```bash
docker compose exec backend python manage_users.py create --username pengelola-bantur --name "Pengelola Bantur" --role desa --area "Bantur"
```

Buat akun DAMRI:

```bash
docker compose exec backend python manage_users.py create --username pengelola-damri --name "Pengelola DAMRI" --role damri
```

Daftar akun:

```bash
docker compose exec backend python manage_users.py list
```

Nonaktifkan akun:

```bash
docker compose exec backend python manage_users.py status --username pengelola-bantur --active no
```

## 4. Routing dan login

- Admin Utama hanya bisa login dari `/admin`.
- Pengelola Desa hanya bisa login dari `/pengeloladesa`.
- Pengelola DAMRI hanya bisa login dari `/damri`.
- Login diverifikasi oleh Flask terhadap tabel `users` MariaDB.
- Password menggunakan hash Werkzeug; tidak ada password akun contoh di HTML/LocalStorage.
- Cookie sesi memakai HttpOnly dan SameSite=Lax.

## 5. Catatan penting sebelum dipakai publik

1. **HTTPS wajib untuk penggunaan sungguhan.** Paket awal mendengarkan HTTP port 80. Pada tahap uji awal, `COOKIE_SECURE=false`; jangan gunakan login dengan password penting melalui HTTP publik. Pasang domain dan sertifikat TLS pada Nginx, lalu ubah `COOKIE_SECURE=true` dan konfigurasi listener 443 sebelum operasional. Jangan hanya membuka port 443 tanpa konfigurasi sertifikat.
2. HTML asli masih menyimpan banyak data konten dashboard di `localStorage`. Paket ini mengamankan autentikasi login, tetapi belum memindahkan seluruh CRUD wisata/UMKM/event/pengaturan ke database. Data lokal browser tidak otomatis tersinkron antar pengguna/perangkat.
3. Backend dari ZIP sebelumnya mengasumsikan tabel bisnis seperti `desa`, `resort_penginapan`, dan lainnya sudah ada. ZIP awal yang diberikan tidak memuat skema database inti tersebut. Paket ini membuat tabel `users` untuk login; impor skema database inti milik proyek sebelum mengaktifkan endpoint bisnis yang memerlukannya.
4. Fitur scraper pada HTML lama memanggil `/api/scrape-maps`, sedangkan `app.py` dari ZIP yang disertakan tidak menyediakan endpoint itu. Fitur tersebut perlu disambungkan ke `scraper.py`/endpoint antrean review pada tahap terpisah.
5. Panel pengelolaan akun yang sebelumnya berbasis LocalStorage dinonaktifkan. Kelola akun melalui `manage_users.py` sampai UI pengelolaan akun server-side dibuat.
6. Pastikan backup volume MariaDB dilakukan rutin. Jangan menjalankan `docker compose down -v` karena akan menghapus volume database.

## 6. Perintah operasional

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose restart
docker compose down
```

Untuk backup database:

```bash
docker compose exec mariadb sh -c 'mariadb-dump -u root -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' > backup-jelajah.sql
```

File `.env` harus tetap aman. Backup database tidak menggantikan backup file `.env` dan skema proyek.
