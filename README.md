# BikinLaper.com — Arsip Website Asli

Rekonstruksi statis website **BikinLaper.com** berdasarkan snapshot publik yang
tersedia sebelum 11 Oktober 2025. Tampilan, navigasi, halaman artikel, kategori,
gambar, stylesheet, JavaScript, dan struktur URL asli dipertahankan.

## Konten yang dipulihkan

- **228 artikel** yang tercantum pada `post-sitemap.xml`.
- **661 halaman HTML**, termasuk halaman utama, artikel, kategori, tag, arsip,
  halaman penulis, dan attachment.
- Lebih dari **900 file gambar** beserta variasi thumbnail WordPress.
- Seluruh gambar utama artikel dan kartu artikel sudah diperbaiki.
- Sitemap, feed, `robots.txt`, aset tema, serta data REST WordPress yang
  tersedia di arsip.

File `_recovery/manifest.csv` mencatat sumber historis setiap snapshot. Skrip
`_recovery/recover_archived_images.py` dapat mencari gambar asli tambahan di
Wayback Machine; `_recovery/repair_site.py` memperbaiki referensi gambar
berdasarkan metadata artikel, attachment, dan thumbnail yang tersedia.

## GitHub Pages

1. Buka **Settings → Pages** pada repositori ini.
2. Pilih **Deploy from a branch**.
3. Pilih branch **main** dan folder **/ (root)**, kemudian klik **Save**.
4. Website dapat diakses melalui:

   `https://adnanyogi88-dev.github.io/bikinlaper.com/`

Struktur tautan internal menggunakan path relatif agar kompatibel dengan GitHub
Pages, Vercel, dan hosting statis lain. Karena ini merupakan arsip statis,
database WordPress, login admin, komentar, dan pencarian dinamis tidak aktif.
