
from datetime import date, timedelta
from functools import wraps
import os
import sqlite3

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import koneksi, buat_database


app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "kunci-lokal-peminjaman-laboratorium"
)

# Pastikan database dan tabel sudah tersedia.
buat_database()


# ==================================================
# FUNGSI BANTU
# ==================================================

def wajib_login(peran):
    def decorator(fungsi):
        @wraps(fungsi)
        def pembungkus(*args, **kwargs):
            if "user_id" not in session:
                flash("Silakan login terlebih dahulu.", "warning")
                return redirect(url_for("index"))

            if session.get("peran") != peran:
                flash("Kamu tidak memiliki akses ke halaman ini.", "danger")
                if session.get("peran") == "admin":
                    return redirect(url_for("dashboard_admin"))
                return redirect(url_for("dashboard_mahasiswa"))

            return fungsi(*args, **kwargs)

        return pembungkus
    return decorator


def ambil_barang():
    conn = koneksi()
    try:
        return conn.execute(
            """
            SELECT id, nama_barang, nama_barang AS nama,
                   kategori, stok, gambar
            FROM barang
            ORDER BY nama_barang
            """
        ).fetchall()
    finally:
        conn.close()


def ambil_detail_peminjaman(peminjaman_id):
    conn = koneksi()
    try:
        return conn.execute(
            """
            SELECT dp.id, dp.peminjaman_id, dp.barang_id, dp.jumlah,
                   b.nama_barang, b.nama_barang AS nama,
                   b.kategori, b.gambar
            FROM detail_peminjaman dp
            JOIN barang b ON b.id = dp.barang_id
            WHERE dp.peminjaman_id = ?
            """,
            (peminjaman_id,)
        ).fetchall()
    finally:
        conn.close()


# ==================================================
# HALAMAN UTAMA
# ==================================================

@app.route("/")
def index():
    if session.get("peran") == "admin":
        return redirect(url_for("dashboard_admin"))

    if session.get("peran") == "mahasiswa":
        return redirect(url_for("dashboard_mahasiswa"))

    return render_template("index.html")


# ==================================================
# LOGIN MAHASISWA
# ==================================================

@app.route("/login_mahasiswa", methods=["GET", "POST"])
def login_mahasiswa():
    if request.method == "POST":
        nim = request.form.get("nim", "").strip()
        password = request.form.get("password", "")

        conn = koneksi()
        try:
            mahasiswa = conn.execute(
                """
                SELECT id, nama, nim, password
                FROM mahasiswa
                WHERE nim = ?
                """,
                (nim,)
            ).fetchone()
        finally:
            conn.close()

        if mahasiswa:
            password_db = mahasiswa["password"]

            try:
                password_valid = check_password_hash(
                    password_db, password
                )
            except (ValueError, TypeError):
                password_valid = False

            # Mendukung akun lama yang menyimpan password biasa.
            if not password_valid:
                password_valid = password_db == password

            if password_valid:
                session.clear()
                session["user_id"] = mahasiswa["id"]
                session["nama"] = mahasiswa["nama"]
                session["nim"] = mahasiswa["nim"]
                session["peran"] = "mahasiswa"

                flash("Login berhasil. Selamat datang!", "success")
                return redirect(url_for("dashboard_mahasiswa"))

        flash("NIM atau password salah.", "danger")

    return render_template("login_mahasiswa.html")


# ==================================================
# REGISTRASI MAHASISWA
# ==================================================


@app.route("/register_mahasiswa", methods=["GET", "POST"])
def register_mahasiswa():
    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        nim = request.form.get("nim", "").strip()
        no_whatsapp = request.form.get("no_whatsapp", "").strip()
        password = request.form.get("password", "")

        if not nama or not nim or not no_whatsapp or not password:
            flash("Semua kolom wajib diisi.", "warning")
            return render_template("register_mahasiswa.html")

        if len(password) < 8:
            flash("Password minimal 8 karakter.", "warning")
            return render_template("register_mahasiswa.html")

        if not no_whatsapp.replace("+", "").replace(" ", "").isdigit():
            flash("Nomor WhatsApp hanya boleh berisi angka dan tanda +.", "warning")
            return render_template("register_mahasiswa.html")

        conn = koneksi()
        try:
            conn.execute(
                """
                INSERT INTO mahasiswa (nama, nim, password, no_whatsapp)
                VALUES (?, ?, ?, ?)
                """,
                (
                    nama,
                    nim,
                    generate_password_hash(password),
                    no_whatsapp
                )
            )
            conn.commit()

            flash("Registrasi berhasil. Silakan login.", "success")
            return redirect(url_for("login_mahasiswa"))

        except sqlite3.IntegrityError:
            conn.rollback()
            flash("NIM sudah terdaftar.", "warning")

        except Exception as e:
            conn.rollback()
            print("ERROR REGISTRASI:", e)
            flash("Registrasi gagal.", "danger")

        finally:
            conn.close()

    return render_template("register_mahasiswa.html")


# ==================================================
# LOGIN ADMIN
# ==================================================

@app.route("/login_admin", methods=["GET", "POST"])
def login_admin():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = koneksi()
        try:
            admin = conn.execute(
                """
                SELECT id, username, password
                FROM admin
                WHERE username = ?
                """,
                (username,)
            ).fetchone()
        finally:
            conn.close()

        if admin:
            password_db = admin["password"]

            try:
                password_valid = check_password_hash(
                    password_db, password
                )
            except (ValueError, TypeError):
                password_valid = False

            # Mendukung password admin awal yang masih berupa teks biasa.
            if not password_valid:
                password_valid = password_db == password

            if password_valid:
                session.clear()
                session["user_id"] = admin["id"]
                session["username"] = admin["username"]
                session["peran"] = "admin"

                flash("Login admin berhasil.", "success")
                return redirect(url_for("dashboard_admin"))

        flash("Username atau password admin salah.", "danger")

    return render_template("login_admin.html")


# ==================================================
# DASHBOARD MAHASISWA
# ==================================================

@app.route("/mahasiswa")
@wajib_login("mahasiswa")
def dashboard_mahasiswa():
    conn = koneksi()
    try:
        barang = conn.execute(
            "SELECT id, nama_barang, kategori, stok, gambar FROM barang"
        ).fetchall()

        riwayat = conn.execute(
            """
            SELECT
                p.id,
                p.tanggal_pinjam,
                p.tenggat_kembali,
                p.status,
                GROUP_CONCAT(b.nama_barang, ', ') AS nama_barang,
                COALESCE(SUM(dp.jumlah), 0) AS jumlah
            FROM peminjaman p
            LEFT JOIN detail_peminjaman dp
                ON dp.peminjaman_id = p.id
            LEFT JOIN barang b
                ON b.id = dp.barang_id
            WHERE p.mahasiswa_id = ?
            GROUP BY p.id
            ORDER BY p.id DESC
            """,
            (session["user_id"],)
        ).fetchall()

    finally:
        conn.close()

    return render_template(
        "dashboard_mahasiswa.html",
        barang=barang,
        riwayat=riwayat,
        hari_ini=date.today().isoformat()
    )


# ==================================================
# DASHBOARD ADMIN
# ==================================================

@app.route("/admin")
@wajib_login("admin")
def dashboard_admin():
    conn = koneksi()
    try:
        jumlah_barang = conn.execute(
            "SELECT COUNT(*) FROM barang"
        ).fetchone()[0]

        jumlah_mahasiswa = conn.execute(
            "SELECT COUNT(*) FROM mahasiswa"
        ).fetchone()[0]

        jumlah_peminjaman = conn.execute(
            "SELECT COUNT(*) FROM peminjaman"
        ).fetchone()[0]

        menunggu = conn.execute(
            """
            SELECT COUNT(*) FROM peminjaman
            WHERE status = 'Menunggu'
            """
        ).fetchone()[0]
    finally:
        conn.close()

    return render_template(
        "dashboard_admin.html",
        jumlah_barang=jumlah_barang,
        jumlah_mahasiswa=jumlah_mahasiswa,
        jumlah_peminjaman=jumlah_peminjaman,
        menunggu=menunggu
    )


# ==================================================
# DATA MAHASISWA - KHUSUS ADMIN
# ==================================================

@app.route("/admin/mahasiswa")
@wajib_login("admin")
def data_mahasiswa_admin():
    conn = koneksi()
    try:
        mahasiswa = conn.execute("""
            SELECT id, nama, nim, no_whatsapp
            FROM mahasiswa
            ORDER BY nama ASC
        """).fetchall()
    finally:
        conn.close()

    return render_template(
        "data_mahasiswa_admin.html",
        mahasiswa=mahasiswa
    )

# ==================================================
# DATA BARANG ADMIN
# ==================================================

@app.route("/data_barang_admin")
@wajib_login("admin")
def daftar_barang_admin():
    barang = ambil_barang()
    return render_template("data_barang_admin.html", barang=barang)


@app.route("/tambah_barang", methods=["GET", "POST"])
@wajib_login("admin")
def tambah_barang():
    if request.method == "POST":
        nama_barang = (
            request.form.get("nama_barang")
            or request.form.get("nama")
            or ""
        ).strip()

        kategori = request.form.get("kategori", "").strip()

        try:
            stok = int(request.form.get("stok", "0"))
            if stok < 0:
                raise ValueError
        except (ValueError, TypeError):
            flash("Stok harus berupa angka nol atau lebih.", "warning")
            return redirect(url_for("tambah_barang"))

        gambar = request.form.get("gambar", "").strip()

        if not nama_barang:
            flash("Nama barang wajib diisi.", "warning")
            return redirect(url_for("tambah_barang"))

        conn = koneksi()
        try:
            conn.execute(
                """
                INSERT INTO barang (nama_barang, kategori, stok, gambar)
                VALUES (?, ?, ?, ?)
                """,
                (nama_barang, kategori, stok, gambar)
            )
            conn.commit()
            flash("Barang berhasil ditambahkan.", "success")

        except Exception as e:
            conn.rollback()
            print("ERROR TAMBAH BARANG:", e)
            flash("Barang gagal ditambahkan.", "danger")

        finally:
            conn.close()

        return redirect(url_for("data_barang_admin"))

    return render_template("tambah_barang.html")


@app.route("/edit_barang/<int:barang_id>", methods=["GET", "POST"])
@wajib_login("admin")
def edit_barang(barang_id):
    conn = koneksi()
    try:
        barang = conn.execute(
            "SELECT * FROM barang WHERE id = ?",
            (barang_id,)
        ).fetchone()

        if not barang:
            flash("Barang tidak ditemukan.", "warning")
            return redirect(url_for("data_barang_admin"))

        if request.method == "POST":
            nama_barang = (
                request.form.get("nama_barang")
                or request.form.get("nama")
                or ""
            ).strip()

            kategori = request.form.get("kategori", "").strip()
            gambar = request.form.get("gambar", "").strip()

            try:
                stok = int(request.form.get("stok", "0"))
                if stok < 0:
                    raise ValueError
            except (ValueError, TypeError):
                flash("Stok harus berupa angka nol atau lebih.", "warning")
                return redirect(
                    url_for("edit_barang", barang_id=barang_id)
                )

            if not nama_barang:
                flash("Nama barang wajib diisi.", "warning")
                return redirect(
                    url_for("edit_barang", barang_id=barang_id)
                )

            conn.execute(
                """
                UPDATE barang
                SET nama_barang = ?, kategori = ?, stok = ?, gambar = ?
                WHERE id = ?
                """,
                (nama_barang, kategori, stok, gambar, barang_id)
            )
            conn.commit()
            flash("Barang berhasil diperbarui.", "success")
            return redirect(url_for("data_barang_admin"))

    except Exception as e:
        conn.rollback()
        print("ERROR EDIT BARANG:", e)
        flash("Gagal memperbarui barang.", "danger")
        return redirect(url_for("data_barang_admin"))

    finally:
        conn.close()

    return render_template("edit_barang.html", barang=barang)


@app.route("/hapus_barang/<int:barang_id>", methods=["POST", "GET"])
@wajib_login("admin")
def hapus_barang(barang_id):
    conn = koneksi()
    try:
        dipakai = conn.execute(
            """
            SELECT COUNT(*)
            FROM detail_peminjaman
            WHERE barang_id = ?
            """,
            (barang_id,)
        ).fetchone()[0]

        if dipakai:
            flash(
                "Barang memiliki riwayat peminjaman sehingga tidak dapat dihapus.",
                "warning"
            )
        else:
            conn.execute(
                "DELETE FROM barang WHERE id = ?",
                (barang_id,)
            )
            conn.commit()
            flash("Barang berhasil dihapus.", "success")

    except Exception as e:
        conn.rollback()
        print("ERROR HAPUS BARANG:", e)
        flash("Barang gagal dihapus.", "danger")

    finally:
        conn.close()

    return redirect(url_for("data_barang_admin"))


# ==================================================
# PENGAJUAN PEMINJAMAN MAHASISWA
# ==================================================

@app.route("/ajukan_peminjaman", methods=["GET", "POST"])
@wajib_login("mahasiswa")
def ajukan_peminjaman():
    if request.method == "POST":
        try:
            barang_id = int(request.form.get("barang_id", ""))
            jumlah = int(request.form.get("jumlah", ""))

            tanggal_pinjam = request.form.get(
                "tanggal_pinjam", ""
            ).strip()

            tenggat_kembali = request.form.get(
                "tenggat_kembali", ""
            ).strip()

            if jumlah <= 0:
                raise ValueError("Jumlah harus lebih dari nol.")

            tanggal_mulai = date.fromisoformat(tanggal_pinjam)
            tanggal_akhir = date.fromisoformat(tenggat_kembali)

            if tanggal_akhir < tanggal_mulai:
                flash(
                    "Tanggal kembali tidak boleh sebelum tanggal pinjam.",
                    "warning"
                )
                return redirect(url_for("ajukan_peminjaman"))

        except (ValueError, TypeError):
            flash(
                "Jumlah dan tanggal peminjaman harus valid.",
                "warning"
            )
            return redirect(url_for("ajukan_peminjaman"))

        conn = koneksi()
        try:
            barang = conn.execute(
                "SELECT id, nama_barang, stok FROM barang WHERE id = ?",
                (barang_id,)
            ).fetchone()

            if not barang:
                flash("Barang tidak ditemukan.", "warning")
                return redirect(url_for("ajukan_peminjaman"))

            if jumlah > barang["stok"]:
                flash(
                    "Jumlah yang diminta melebihi stok barang.",
                    "warning"
                )
                return redirect(url_for("ajukan_peminjaman"))

            cursor = conn.execute(
                """
                INSERT INTO peminjaman
                    (mahasiswa_id, tanggal_pinjam, tenggat_kembali, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    tanggal_pinjam,
                    tenggat_kembali,
                    "Menunggu"
                )
            )

            peminjaman_id = cursor.lastrowid

            conn.execute(
                """
                INSERT INTO detail_peminjaman
                    (peminjaman_id, barang_id, jumlah)
                VALUES (?, ?, ?)
                """,
                (peminjaman_id, barang_id, jumlah)
            )

            conn.commit()
            flash(
                "Pengajuan peminjaman berhasil dikirim.",
                "success"
            )
            return redirect(url_for("riwayat_peminjaman"))

        except Exception as e:
            conn.rollback()
            print("ERROR PEMINJAMAN:", e)
            flash(
                "Peminjaman gagal. Periksa terminal untuk detail error.",
                "danger"
            )

        finally:
            conn.close()

        return redirect(url_for("ajukan_peminjaman"))

    barang = ambil_barang()
    return render_template("form_peminjaman.html", barang=barang)

# ==================================================
# RIWAYAT PEMINJAMAN MAHASISWA
# ==================================================


@app.route("/riwayat_peminjaman")
@wajib_login("mahasiswa")
def riwayat_peminjaman():
    conn = koneksi()
    try:
        riwayat = conn.execute(
            """
            SELECT
                p.id,
                p.tanggal_pinjam,
                p.tenggat_kembali,
                p.status,
                GROUP_CONCAT(b.nama_barang, ', ') AS nama_barang,
                COALESCE(SUM(dp.jumlah), 0) AS jumlah
            FROM peminjaman p
            LEFT JOIN detail_peminjaman dp
                ON dp.peminjaman_id = p.id
            LEFT JOIN barang b
                ON b.id = dp.barang_id
            WHERE p.mahasiswa_id = ?
            GROUP BY p.id
            ORDER BY p.id DESC
            """,
            (session["user_id"],)
        ).fetchall()
    finally:
        conn.close()

    return render_template(
        "riwayat-peminjaman.html",
        riwayat=riwayat
    )


# ==================================================
# DATA PEMINJAMAN ADMIN
# ==================================================

@app.route("/data_peminjaman_admin")
@wajib_login("admin")
def data_peminjaman_admin():
    conn = koneksi()
    try:
        peminjaman = conn.execute(
            """
            SELECT p.id, p.mahasiswa_id, m.nama, m.nim,
                   p.tanggal_pinjam, p.tenggat_kembali, p.status,
                   GROUP_CONCAT(b.nama_barang, ', ') AS nama_barang,
                   GROUP_CONCAT(b.nama_barang, ', ') AS barang,
                   SUM(dp.jumlah) AS jumlah
            FROM peminjaman p
            JOIN mahasiswa m ON m.id = p.mahasiswa_id
            LEFT JOIN detail_peminjaman dp
                ON dp.peminjaman_id = p.id
            LEFT JOIN barang b ON b.id = dp.barang_id
            GROUP BY p.id
            ORDER BY p.id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    return render_template(
        "data_peminjaman_admin.html",
        peminjaman=peminjaman
    )


# ==================================================
# PROSES PERSETUJUAN PEMINJAMAN
# ==================================================

@app.route("/setujui_peminjaman/<int:peminjaman_id>", methods=["POST", "GET"])
@wajib_login("admin")
def setujui_peminjaman(peminjaman_id):
    conn = koneksi()
    try:
        pinjam = conn.execute(
            "SELECT * FROM peminjaman WHERE id = ?",
            (peminjaman_id,)
        ).fetchone()

        if not pinjam:
            flash("Data peminjaman tidak ditemukan.", "warning")
            return redirect(url_for("data_peminjaman_admin"))

        if pinjam["status"] != "Menunggu":
            flash("Peminjaman ini sudah diproses.", "warning")
            return redirect(url_for("data_peminjaman_admin"))

        detail = conn.execute(
            """
            SELECT barang_id, jumlah
            FROM detail_peminjaman
            WHERE peminjaman_id = ?
            """,
            (peminjaman_id,)
        ).fetchall()

        for item in detail:
            barang = conn.execute(
                "SELECT stok FROM barang WHERE id = ?",
                (item["barang_id"],)
            ).fetchone()

            if not barang or barang["stok"] < item["jumlah"]:
                flash(
                    "Stok barang tidak mencukupi untuk menyetujui peminjaman.",
                    "warning"
                )
                return redirect(url_for("data_peminjaman_admin"))

        for item in detail:
            conn.execute(
                """
                UPDATE barang
                SET stok = stok - ?
                WHERE id = ?
                """,
                (item["jumlah"], item["barang_id"])
            )

        conn.execute(
            "UPDATE peminjaman SET status = ? WHERE id = ?",
            ("Disetujui", peminjaman_id)
        )

        conn.commit()
        flash("Peminjaman berhasil disetujui.", "success")

    except Exception as e:
        conn.rollback()
        print("ERROR PERSETUJUAN:", e)
        flash("Gagal menyetujui peminjaman.", "danger")

    finally:
        conn.close()

    return redirect(url_for("data_peminjaman_admin"))


# ==================================================
# TOLAK PEMINJAMAN
# ==================================================

@app.route("/tolak_peminjaman/<int:peminjaman_id>", methods=["POST", "GET"])
@wajib_login("admin")
def tolak_peminjaman(peminjaman_id):
    conn = koneksi()
    try:
        pinjam = conn.execute(
            "SELECT * FROM peminjaman WHERE id = ?",
            (peminjaman_id,)
        ).fetchone()

        if not pinjam:
            flash("Data peminjaman tidak ditemukan.", "warning")
        elif pinjam["status"] != "Menunggu":
            flash("Peminjaman ini sudah diproses.", "warning")
        else:
            conn.execute(
                "UPDATE peminjaman SET status = ? WHERE id = ?",
                ("Ditolak", peminjaman_id)
            )
            conn.commit()
            flash("Pengajuan peminjaman ditolak.", "success")

    except Exception as e:
        conn.rollback()
        print("ERROR TOLAK PEMINJAMAN:", e)
        flash("Gagal menolak peminjaman.", "danger")

    finally:
        conn.close()

    return redirect(url_for("data_peminjaman_admin"))


# ==================================================
# PROSES PENGEMBALIAN BARANG
# ==================================================

@app.route("/kembalikan_peminjaman/<int:peminjaman_id>", methods=["POST", "GET"])
@wajib_login("admin")
def kembalikan_peminjaman(peminjaman_id):
    conn = koneksi()
    try:
        pinjam = conn.execute(
            "SELECT * FROM peminjaman WHERE id = ?",
            (peminjaman_id,)
        ).fetchone()

        if not pinjam:
            flash("Data peminjaman tidak ditemukan.", "warning")
        elif pinjam["status"] != "Disetujui":
            flash(
                "Hanya peminjaman yang disetujui yang dapat dikembalikan.",
                "warning"
            )
        else:
            detail = conn.execute(
                """
                SELECT barang_id, jumlah
                FROM detail_peminjaman
                WHERE peminjaman_id = ?
                """,
                (peminjaman_id,)
            ).fetchall()

            for item in detail:
                conn.execute(
                    """
                    UPDATE barang
                    SET stok = stok + ?
                    WHERE id = ?
                    """,
                    (item["jumlah"], item["barang_id"])
                )

            conn.execute(
                "UPDATE peminjaman SET status = ? WHERE id = ?",
                ("Dikembalikan", peminjaman_id)
            )

            conn.commit()
            flash("Pengembalian barang berhasil dicatat.", "success")

    except Exception as e:
        conn.rollback()
        print("ERROR PENGEMBALIAN:", e)
        flash("Gagal memproses pengembalian barang.", "danger")

    finally:
        conn.close()

    return redirect(url_for("data_peminjaman_admin"))


# ==================================================
# LOGOUT
# ==================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("Kamu berhasil logout.", "success")
    return redirect(url_for("index"))


# ==================================================
# JALANKAN APLIKASI
# ==================================================

if __name__ == "__main__":
    app.run(debug=True)
