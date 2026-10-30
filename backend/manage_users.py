import argparse
import getpass
import uuid
from werkzeug.security import generate_password_hash
from app import db


def main():
    parser = argparse.ArgumentParser(description="Kelola akun login Jelajah Malang Selatan")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Buat akun baru")
    create.add_argument("--username", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--role", required=True, choices=["super", "desa", "damri"])
    create.add_argument("--area", default=None)
    create.add_argument("--password", help="Jika tidak diberikan, password diminta secara interaktif")
    sub.add_parser("list", help="Lihat daftar akun")
    status = sub.add_parser("status", help="Aktifkan/nonaktifkan akun")
    status.add_argument("--username", required=True)
    status.add_argument("--active", choices=["yes", "no"], required=True)
    delete = sub.add_parser("delete", help="Hapus akun")
    delete.add_argument("--username", required=True)
    args = parser.parse_args()
    con = db()
    try:
        with con.cursor() as cur:
            if args.command == "create":
                password = args.password or getpass.getpass("Password baru: ")
                if len(password) < 12:
                    raise SystemExit("Gunakan password minimal 12 karakter.")
                if args.role == "desa" and not args.area:
                    raise SystemExit("Akun role desa wajib memakai --area.")
                if args.role == "damri":
                    args.area = "DAMRI"
                cur.execute("INSERT INTO users (id,username,name,password_hash,role,area) VALUES (%s,%s,%s,%s,%s,%s)",
                            (str(uuid.uuid4()), args.username, args.name, generate_password_hash(password), args.role, args.area))
                con.commit()
                print(f"Akun {args.username} berhasil dibuat ({args.role}).")
            elif args.command == "list":
                cur.execute("SELECT username,name,role,area,is_active,created_at FROM users ORDER BY role,username")
                for row in cur.fetchall():
                    print(f"{row['username']} | {row['name']} | {row['role']} | {row['area'] or '-'} | {'aktif' if row['is_active'] else 'nonaktif'}")
            elif args.command == "status":
                cur.execute("UPDATE users SET is_active=%s WHERE username=%s", (1 if args.active == "yes" else 0, args.username))
                con.commit()
                print("Status akun diperbarui." if cur.rowcount else "Username tidak ditemukan.")
            elif args.command == "delete":
                cur.execute("DELETE FROM users WHERE username=%s", (args.username,))
                con.commit()
                print("Akun dihapus." if cur.rowcount else "Username tidak ditemukan.")
    finally:
        con.close()

if __name__ == "__main__":
    main()
