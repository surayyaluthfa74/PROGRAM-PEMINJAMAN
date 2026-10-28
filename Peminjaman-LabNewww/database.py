
import sqlite3

DATABASE = "laboratorium.db"


def koneksi():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def buat_database():
    conn = koneksi()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mahasiswa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            nim TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            no_whatsapp TEXT
        );

        CREATE TABLE IF NOT EXISTS barang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_barang TEXT NOT NULL,
            kategori TEXT,
            stok INTEGER NOT NULL DEFAULT 0 CHECK (stok >= 0),
            gambar TEXT
        );

        CREATE TABLE IF NOT EXISTS peminjaman (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mahasiswa_id INTEGER NOT NULL,
            tanggal_pinjam TEXT NOT NULL,
            tenggat_kembali TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Menunggu',
            FOREIGN KEY (mahasiswa_id) REFERENCES mahasiswa(id)
        );

        CREATE TABLE IF NOT EXISTS detail_peminjaman (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peminjaman_id INTEGER NOT NULL,
            barang_id INTEGER NOT NULL,
            jumlah INTEGER NOT NULL CHECK (jumlah > 0),
            FOREIGN KEY (peminjaman_id) REFERENCES peminjaman(id),
            FOREIGN KEY (barang_id) REFERENCES barang(id)
        );
    """)
     # Tambahkan kolom WhatsApp jika belum tersedia
    cursor.execute("PRAGMA table_info(mahasiswa)")
    kolom_mahasiswa = [
        kolom["name"] for kolom in cursor.fetchall()
    ]

    if "no_whatsapp" not in kolom_mahasiswa:
        cursor.execute("""
            ALTER TABLE mahasiswa
            ADD COLUMN no_whatsapp TEXT
        """)
        
    # Akun admin awal
    cursor.execute("""
        INSERT OR IGNORE INTO admin (username, password)
        VALUES (?, ?)
    """, ("admin", "admin123"))

    # Contoh barang awal
    cursor.execute("""
        SELECT COUNT(*) FROM barang
    """)
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO barang (nama_barang, kategori, stok, gambar)
            VALUES (?, ?, ?, ?)
        """, [
            ("LAN Tester", "Alat Jaringan", 10, "lan_tester.jpg"),
            ("Kabel LAN", "Kabel Jaringan", 20, "kabel_lan.jpg"),
            ("Router", "Perangkat Jaringan", 5, "router.jpg"),
            ("Tang Crimping", "Alat Jaringan", 8, "tang_crimping.jpg")
        ])

    conn.commit()
    conn.close()


if __name__ == "__main__":
    buat_database()
    print("Database berhasil dibuat!")
