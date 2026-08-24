# Panduan Memasang Backup di GitHub Pages

## Satu domain = satu repositori

Contoh untuk `bikinlaper.com`:

1. Buka GitHub dan pilih **New repository**.
2. Beri nama, misalnya `backup-bikinlaper`, lalu buat repositori kosong.
3. Ekstrak ZIP domain. Pastikan `index.html`, `.nojekyll`, `README.md`, dan folder aset berada di root hasil ekstrak.
4. Karena setiap backup berisi ratusan/ribuan file, gunakan **GitHub Desktop** atau Git CLI; unggahan browser dibatasi 100 file sekaligus.
5. Dengan Git CLI, jalankan dari dalam folder hasil ekstrak:

   ```bash
   git init
   git add .
   git commit -m "Pulihkan website lama"
   git branch -M main
   git remote add origin https://github.com/USERNAME/NAMA-REPO.git
   git push -u origin main
   ```

6. Di GitHub, buka **Settings → Pages**.
7. Pada **Build and deployment**, pilih **Deploy from a branch**.
8. Pilih branch `main` dan folder `/ (root)`, kemudian **Save**.
9. Tunggu deployment. Alamat domain bawaan GitHub akan berbentuk:
   `https://USERNAME.github.io/backup-bikinlaper/`

Tidak perlu membeli domain untuk memakai alamat `github.io` tersebut.

Dokumentasi resmi:

- https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository

## Batasan

- Ini merupakan website statis; database WordPress tidak tersedia.
- Formulir, login, komentar, pencarian dinamis, checkout, dan dashboard admin tidak aktif.
- File yang tidak pernah dicrawl tidak dapat dipulihkan dari Wayback Machine.
- Daftar lengkap file dan sumber snapshot terdapat di `_recovery/manifest.csv`.
