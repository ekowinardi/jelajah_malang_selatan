USE jelajah_malang_selatan;

CREATE TABLE IF NOT EXISTS pengaturan_banner (
    id_banner VARCHAR(36) PRIMARY KEY,
    slug VARCHAR(80) NOT NULL UNIQUE,
    label VARCHAR(180) NULL,
    judul VARCHAR(255) NOT NULL,
    deskripsi TEXT NULL,
    foto_urls JSON NULL,
    aktif BOOLEAN NOT NULL DEFAULT TRUE,
    diperbarui_pada DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS pengaturan_website (
    id_pengaturan VARCHAR(36) PRIMARY KEY,
    kunci VARCHAR(100) NOT NULL UNIQUE,
    nilai JSON NULL,
    diperbarui_pada DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS hasil_scraping_maps (
    id_hasil VARCHAR(36) PRIMARY KEY,
    nama_tempat VARCHAR(255) NOT NULL,
    rating DECIMAL(3,2) NULL,
    alamat TEXT NULL,
    telepon VARCHAR(100) NULL,
    jam_operasional TEXT NULL,
    foto_url VARCHAR(1000) NULL,
    sumber_url VARCHAR(1000) NULL,
    status_review ENUM('menunggu_review','disetujui','ditolak') NOT NULL DEFAULT 'menunggu_review',
    id_resort VARCHAR(36) NULL,
    dibuat_pada DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    diperbarui_pada DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_scrape_resort FOREIGN KEY (id_resort)
      REFERENCES resort_penginapan(id_resort) ON UPDATE CASCADE ON DELETE SET NULL,
    KEY idx_scrape_status (status_review),
    KEY idx_scrape_nama (nama_tempat)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
