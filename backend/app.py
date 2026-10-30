import json
import os
import uuid
from functools import wraps

import pymysql
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session
from flask_cors import CORS

load_dotenv()
app = Flask(__name__)
secret_key = os.getenv("SECRET_KEY", "")
if len(secret_key) < 32:
    raise RuntimeError("SECRET_KEY wajib diisi dengan minimal 32 karakter acak.")
app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=__import__("datetime").timedelta(hours=8),
)
allowed = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost").split(",") if x.strip()]
CORS(app, origins=allowed)


def db():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "jelajah_app"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "jelajah_malang_selatan"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def api_key_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        expected = os.getenv("API_KEY", "")
        provided = request.headers.get("X-API-Key", "")
        if len(expected) < 32 or not provided or not __import__("hmac").compare_digest(provided, expected):
            return jsonify({"error": "API key tidak valid atau belum dikonfigurasi"}), 401
        return fn(*args, **kwargs)
    return wrapped


def err(message, code=400):
    return jsonify({"error": message}), code


def new_id():
    return str(uuid.uuid4())




def public_user(row):
    return {"id": row["id"], "username": row["username"], "name": row["name"],
            "role": row["role"], "area": row.get("area")}


def auth_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return err("Silakan login terlebih dahulu.", 401)
        return fn(*args, **kwargs)
    return wrapped


@app.post("/api/auth/login")
def auth_login():
    from werkzeug.security import check_password_hash
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not username or not password:
        return err("Username dan password wajib diisi.", 400)
    con = db()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT id,username,name,password_hash,role,area,is_active FROM users WHERE username=%s LIMIT 1", (username,))
            user = cur.fetchone()
    finally:
        con.close()
    if not user or not user["is_active"] or not check_password_hash(user["password_hash"], password):
        return err("Username/password salah atau akun dinonaktifkan.", 401)
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session["area"] = user.get("area")
    return jsonify({"message": "Login berhasil", "user": public_user(user)})


@app.get("/api/auth/me")
@auth_required
def auth_me():
    con = db()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT id,username,name,role,area,is_active FROM users WHERE id=%s LIMIT 1", (session["user_id"],))
            user = cur.fetchone()
    finally:
        con.close()
    if not user or not user["is_active"]:
        session.clear()
        return err("Sesi tidak berlaku.", 401)
    return jsonify({"user": public_user(user)})


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return jsonify({"message": "Logout berhasil"})


@app.get("/api/health")
def health():
    try:
        con = db()
        with con.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        con.close()
        return jsonify({"status": "ok", "database": "connected"})
    except Exception:
        app.logger.exception("Database health check failed")
        return err("Backend berjalan, tetapi koneksi database gagal. Periksa konfigurasi server.", 503)


@app.get("/api/resorts")
def list_resorts():
    status = request.args.get("status", "terbit")
    desa_id = request.args.get("id_desa")
    sql = """SELECT r.id_resort, r.nama_resort, r.jenis, r.harga_per_malam,
                    r.kontak_reservasi, r.alamat, r.id_desa, d.nama_desa,
                    r.latitude, r.longitude, r.foto_url, r.link_google_maps,
                    r.status_publikasi, r.id_mata_uang
             FROM resort_penginapan r LEFT JOIN desa d ON d.id_desa=r.id_desa
             WHERE (%s IS NULL OR r.status_publikasi=%s)
               AND (%s IS NULL OR r.id_desa=%s)
             ORDER BY r.nama_resort"""
    try:
        con = db()
        with con.cursor() as cur:
            cur.execute(sql, (status or None, status, desa_id, desa_id))
            rows = cur.fetchall()
        con.close()
        return jsonify(rows)
    except Exception:
        app.logger.exception("List resorts failed")
        return err("Gagal membaca data resort.", 500)


@app.post("/api/resorts")
@api_key_required
def create_resort():
    data = request.get_json(silent=True) or {}
    name = (data.get("nama_resort") or "").strip()
    if not name:
        return err("nama_resort wajib diisi")
    resort_id = data.get("id_resort") or new_id()
    try:
        con = db()
        with con.cursor() as cur:
            if data.get("id_desa"):
                cur.execute("SELECT id_desa FROM desa WHERE id_desa=%s", (data["id_desa"],))
                if not cur.fetchone():
                    con.rollback()
                    return err("id_desa tidak ditemukan")
            cur.execute("""INSERT INTO resort_penginapan
                (id_resort,id_mata_uang,nama_resort,jenis,harga_per_malam,kontak_reservasi,
                 alamat,id_desa,latitude,longitude,foto_url,link_google_maps,status_publikasi)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (resort_id, data.get("id_mata_uang") or "IDR", name, data.get("jenis"),
                 data.get("harga_per_malam"), data.get("kontak_reservasi"), data.get("alamat"),
                 data.get("id_desa"), data.get("latitude"), data.get("longitude"),
                 data.get("foto_url"), data.get("link_google_maps"),
                 data.get("status_publikasi") or "draft"))
        con.commit()
        con.close()
        return jsonify({"message": "Resort berhasil dibuat", "id_resort": resort_id}), 201
    except Exception:
        app.logger.exception("Create resort failed")
        return err("Gagal menyimpan resort. Pastikan id_mata_uang dan id_desa valid.", 500)


@app.put("/api/resorts/<resort_id>")
@api_key_required
def update_resort(resort_id):
    data = request.get_json(silent=True) or {}
    allowed_fields = ["nama_resort","jenis","harga_per_malam","kontak_reservasi","alamat",
                      "id_desa","latitude","longitude","foto_url","link_google_maps",
                      "status_publikasi","id_mata_uang"]
    fields = [f for f in allowed_fields if f in data]
    if not fields:
        return err("Tidak ada kolom yang diperbarui")
    if "nama_resort" in data and not str(data["nama_resort"]).strip():
        return err("nama_resort tidak boleh kosong")
    try:
        con = db()
        with con.cursor() as cur:
            if "id_desa" in data and data["id_desa"]:
                cur.execute("SELECT id_desa FROM desa WHERE id_desa=%s", (data["id_desa"],))
                if not cur.fetchone():
                    con.rollback()
                    return err("id_desa tidak ditemukan")
            assignments = ", ".join(f"`{f}`=%s" for f in fields)
            cur.execute(f"UPDATE resort_penginapan SET {assignments} WHERE id_resort=%s",
                        [data[f] for f in fields] + [resort_id])
            if cur.rowcount == 0:
                con.rollback()
                return err("Resort tidak ditemukan atau tidak ada perubahan", 404)
        con.commit()
        con.close()
        return jsonify({"message": "Resort berhasil diperbarui"})
    except Exception:
        app.logger.exception("Update resort failed")
        return err("Gagal memperbarui resort.", 500)


@app.delete("/api/resorts/<resort_id>")
@api_key_required
def delete_resort(resort_id):
    try:
        con = db()
        with con.cursor() as cur:
            cur.execute("DELETE FROM resort_penginapan WHERE id_resort=%s", (resort_id,))
            if cur.rowcount == 0:
                con.rollback()
                return err("Resort tidak ditemukan", 404)
        con.commit()
        con.close()
        return jsonify({"message": "Resort berhasil dihapus"})
    except Exception:
        app.logger.exception("Delete resort failed")
        return err("Gagal menghapus resort.", 500)


@app.get("/api/banners")
def get_banners():
    try:
        con = db()
        with con.cursor() as cur:
            cur.execute("SELECT slug,label,judul,deskripsi,foto_urls,aktif,diperbarui_pada FROM pengaturan_banner WHERE aktif=1 ORDER BY slug")
            rows = cur.fetchall()
        con.close()
        for row in rows:
            if isinstance(row.get("foto_urls"), (str, bytes)):
                try:
                    row["foto_urls"] = json.loads(row["foto_urls"])
                except Exception:
                    row["foto_urls"] = []
            if row.get("diperbarui_pada"):
                row["diperbarui_pada"] = row["diperbarui_pada"].isoformat()
        return jsonify(rows)
    except Exception:
        app.logger.exception("Get banners failed")
        return err("Gagal membaca banner.", 500)


@app.put("/api/banners/<slug>")
@api_key_required
def save_banner(slug):
    data = request.get_json(silent=True) or {}
    if not data.get("judul"):
        return err("judul wajib diisi")
    photos = data.get("foto_urls", [])
    if not isinstance(photos, list) or not all(isinstance(x, str) for x in photos):
        return err("foto_urls harus berupa array URL teks")
    try:
        con = db()
        with con.cursor() as cur:
            cur.execute("""INSERT INTO pengaturan_banner
                (id_banner,slug,label,judul,deskripsi,foto_urls,aktif)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE label=VALUES(label),judul=VALUES(judul),
                deskripsi=VALUES(deskripsi),foto_urls=VALUES(foto_urls),aktif=VALUES(aktif)""",
                (new_id(), slug, data.get("label"), data["judul"], data.get("deskripsi"),
                 json.dumps(photos, ensure_ascii=False), bool(data.get("aktif", True))))
        con.commit()
        con.close()
        return jsonify({"message": "Banner berhasil disimpan"})
    except Exception:
        app.logger.exception("Save banner failed")
        return err("Gagal menyimpan banner.", 500)


@app.post("/api/scraper/import")
@api_key_required
def import_scraper_results():
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return err("Body harus berupa array hasil scraper")
    saved = 0
    con = db()
    try:
        with con.cursor() as cur:
            for item in data[:500]:
                name = (item.get("nama_tempat") or "").strip()
                if not name:
                    continue
                cur.execute("""SELECT id_hasil FROM hasil_scraping_maps
                               WHERE nama_tempat=%s AND COALESCE(alamat,'')=COALESCE(%s,'')
                                 AND status_review='menunggu_review' LIMIT 1""",
                            (name, item.get("alamat")))
                if cur.fetchone():
                    continue
                cur.execute("""INSERT INTO hasil_scraping_maps
                    (id_hasil,nama_tempat,rating,alamat,telepon,jam_operasional,foto_url,sumber_url)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (new_id(), name, item.get("rating"), item.get("alamat"), item.get("telepon"),
                     item.get("jam_operasional"), item.get("foto_url"), item.get("sumber_url")))
                saved += 1
        con.commit()
        return jsonify({"message": "Impor selesai", "tersimpan": saved}), 201
    except Exception:
        con.rollback()
        app.logger.exception("Scraper import failed")
        return err("Gagal mengimpor hasil scraper.", 500)
    finally:
        con.close()


@app.get("/api/scraper/review")
@api_key_required
def review_queue():
    status = request.args.get("status", "menunggu_review")
    try:
        con = db()
        with con.cursor() as cur:
            cur.execute("""SELECT id_hasil,nama_tempat,rating,alamat,telepon,jam_operasional,
                                  foto_url,sumber_url,status_review,dibuat_pada
                           FROM hasil_scraping_maps WHERE status_review=%s ORDER BY dibuat_pada DESC""",
                        (status,))
            rows = cur.fetchall()
        con.close()
        for row in rows:
            row["dibuat_pada"] = row["dibuat_pada"].isoformat() if row["dibuat_pada"] else None
        return jsonify(rows)
    except Exception:
        app.logger.exception("Review queue failed")
        return err("Gagal membaca antrean scraper.", 500)


@app.post("/api/scraper/review/<result_id>/approve")
@api_key_required
def approve_scrape(result_id):
    data = request.get_json(silent=True) or {}
    desa_id = data.get("id_desa")
    if not desa_id:
        return err("id_desa wajib dipilih sebelum menyetujui hasil")
    try:
        con = db()
        with con.cursor() as cur:
            cur.execute("SELECT id_desa FROM desa WHERE id_desa=%s", (desa_id,))
            if not cur.fetchone():
                con.rollback()
                return err("id_desa tidak ditemukan")
            cur.execute("SELECT * FROM hasil_scraping_maps WHERE id_hasil=%s AND status_review='menunggu_review'", (result_id,))
            item = cur.fetchone()
            if not item:
                con.rollback()
                return err("Hasil tidak ditemukan atau sudah ditinjau", 404)
            resort_id = new_id()
            cur.execute("""INSERT INTO resort_penginapan
                (id_resort,id_mata_uang,nama_resort,jenis,kontak_reservasi,alamat,id_desa,
                 foto_url,status_publikasi)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'draft')""",
                (resort_id, data.get("id_mata_uang") or "IDR", item["nama_tempat"],
                 data.get("jenis") or "Penginapan", item["telepon"], item["alamat"],
                 desa_id, item["foto_url"]))
            cur.execute("UPDATE hasil_scraping_maps SET status_review='disetujui',id_resort=%s WHERE id_hasil=%s",
                        (resort_id, result_id))
        con.commit()
        con.close()
        return jsonify({"message": "Hasil disetujui sebagai resort draft", "id_resort": resort_id}), 201
    except Exception:
        app.logger.exception("Approve scraper result failed")
        return err("Gagal menyetujui hasil. Pastikan IDR tersedia di mata_uang.", 500)


@app.delete("/api/scraper/review/<result_id>")
@api_key_required
def reject_scrape(result_id):
    try:
        con = db()
        with con.cursor() as cur:
            cur.execute("UPDATE hasil_scraping_maps SET status_review='ditolak' WHERE id_hasil=%s AND status_review='menunggu_review'", (result_id,))
            if cur.rowcount == 0:
                con.rollback()
                return err("Hasil tidak ditemukan atau sudah ditinjau", 404)
        con.commit()
        con.close()
        return jsonify({"message": "Hasil ditandai ditolak"})
    except Exception:
        app.logger.exception("Reject scraper result failed")
        return err("Gagal memperbarui status hasil.", 500)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
