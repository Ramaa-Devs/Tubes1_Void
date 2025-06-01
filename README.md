# BotVoid

Bot Etimo Diamonds yang Menggunakan Algoritma Greedy buatan kelompok VOID

## Tentang Proyek Ini

Bot ini menggunakan algoritma greedy berbasis time-weighted. Setiap diamond dievaluasi berdasarkan kombinasi nilai, jarak, dan waktu tersisa. Bot akan memilih target dengan skor terbaik secara efisien dan lebih fokus ke diamond bernilai tinggi di awal game, dan makin memprioritaskan jarak dekat di akhir game. Selain itu, bot juga bisa menggunakan portal jika jalurnya lebih cepat, serta mempertimbangkan waktu optimal untuk kembali ke base agar diamond tidak hangus.

Algoritma utama yang digunakan bernama `tw`.

## Persiapan awal

### Cara menjalankan game engine
- Requirement yang harus diinstal
  - [Node.js](https://nodejs.org/)
  - [Docker Dekstop](https://www.docker.com/products/docker-desktop/)
  - Yarn
    ```bash
    npm install --global yarn
- Instalasi dan konfigurasi awal
  - [Download source code (.zip)](https://github.com/haziqam/tubes1-IF2211-game-engine/releases/tag/v1.1.0)
  -  Extract zip tersebut, lalu masuk ke folder hasil extractnya
  -  Buka terminal dan masuk ke root directory project
      ```bash
      cd tubes1-IF2110-game-engine-1.1.0
  - Install dependencies menggunakan Yarn
      ```bash
      yarn
  - Setup default environment variable dengan menjalankan script berikut 
    1. Untuk Windows
       ```bash
       ./scripts/copy-env.bat
    2. Untuk Linux/ macOS
       ```bash
       chmod +x ./scripts/copy-env.sh 
       ./scripts/copy-env.sh
  - Setup local database (buka aplikasi docker desktop terlebih dahulu, lalu jalankan command berikut di terminal) 
      ```bash
      docker compose up -d database
  - Lalu jalankan script berikut.
    1. Untuk Windows
       ```bash
        ./scripts/setup-db-prisma.bat
    2. Untuk Linux / masOS
        ```bash
        chmod +x ./scripts/setup-db-prisma.sh 
        ./scripts/setup-db-prisma.sh
- Build
    ```bash
    npm run build
- Run
    ```bash
     npm run start

### Cara menjalankan bot
- Requirement yang harus di-install
  - [Python](https://www.python.org/downloads/)
- Instalasi dan konfigurasi awal]
  - [Download source code (.zip)](https://github.com/haziqam/tubes1-IF2211-bot-starter-pack/releases/tag/v1.0.1)
  - Extract zip tersebut, lalu masuk ke folder hasil extractnya
  - Buka terminal dan masuk ke root directory project
      ```bash
       cd tubes1-IF2110-bot-starter-pack-1.0.1
  - Install dependencies menggunakan pip
      ```bash
      pip install -r requirements.txt
- Jalankan Bot
  - Untuk 1 bot menggunakan logic utama yang digunakan
    ```bash
    python main.py --logic tw --email=tw@example.com --name=tw --password=your_password --team etimo
  - Untuk beberapa bot ubah script yang ada pada run-bots.bat atau run-bots.sh dari segi logic yang digunakan, email, nama, dan password
    1. Untuk Windows
       ```bash
        ./run-bots.bat
    2. Untuk Linux / macOS
      ```bash
      ./run-bots.sh

## Author
- Ketua     : Diwan Ramadhani Dwi Putra  123140116
- Anggota 1 : M. Gymnastiar Syahputra    123140135
- Anggota 2 : Jordy Anugrah Akbar        123140141
