# BotVoid

Bot Etimo Diamonds yang Menggunakan Algoritma Greedy buatan kelompok VOID

## Tentang Proyek Ini

Algoritma greedy yang diimplementasikan dalam bot ini menggunakan pendekatan value-to-cost ratio, di mana setiap diamond dievaluasi berdasarkan efisiensi nilainya terhadap jarak tempuh. Bot akan selalu memilih target dengan rasio jarak terhadap poin terkecil, sehingga memprioritaskan diamond yang bernilai tinggi namun tetap efisien untuk dicapai. Strategi ini memungkinkan bot mengambil keputusan cepat untuk memaksimalkan skor sambil tetap mempertimbangkan kebutuhan untuk kembali ke base sebelum waktu habis.

Algoritma utama yang digunakan bernama `mysmartbot`.

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
    python main.py --logic mysmartbot --email=your_email@example.com --name=your_name --password=your_password --team etimo
  - Untuk beberapa bot ubah script yang ada pada run-bots.bat atau run-bots.sh dari segi logic yang digunakan, email, nama, dan password
    1. Untuk Windows
       ```bash
        ./run-bots.bat
    2. Untuk Linux / macOS
      ```bash
      ./run-bots.sh
