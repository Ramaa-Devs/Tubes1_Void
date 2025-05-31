from typing import Optional
from game.logic.base import BaseLogic
from game.models import Board, GameObject, Position
from game.util import get_direction
import math


class GreedyDiamondLogic(BaseLogic):
    target_bersama : list[Position] = []
    target_portal_bersama : GameObject = None
    target_perantara_bersama : Position = None
    kembali_via_portal_bersama : bool = False

    def __init__(self) -> None:
        self.vektor_gerakan = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        self.lokasi_target: Optional[Position] = None
        self.arah_sekarang = 0

    def next_move(self, player_bot: GameObject, game_board: Board):
        stats_bot = player_bot.properties
        self.papan_game = game_board
        self.bot_pemain = player_bot
        self.diamond_tersedia = game_board.diamonds
        self.semua_bot = game_board.bots
        self.objek_portal = [obj for obj in self.papan_game.game_objects if obj.type == "TeleportGameObject"]
        self.tombol_khusus = [obj for obj in self.papan_game.game_objects if obj.type == "DiamondButtonGameObject"]
        self.bot_lawan = [bot for bot in self.semua_bot if bot.id != self.bot_pemain.id]

        # Reset data statis ketika di base
        if (self.bot_pemain.position == self.bot_pemain.properties.base):
            self.target_bersama = []
            self.target_portal_bersama = None
            self.target_perantara_bersama = None
            self.kembali_via_portal_bersama = False

        # Reset target statis di teleport
        if (self.target_portal_bersama and self.bot_pemain.position == self.cari_portal_pasangan(self.target_portal_bersama)):
            self.target_bersama.remove(self.target_portal_bersama.position)
            self.target_portal_bersama = None
        if (not self.target_portal_bersama and self.bot_pemain.position in self.target_bersama):
            self.target_bersama.remove(self.bot_pemain.position)
        
        if (self.bot_pemain.position == self.target_perantara_bersama):
            self.target_perantara_bersama = None

        # Penilaian risiko yang disederhanakan
        tingkat_risiko = self.nilai_tingkat_risiko()
        
        # Pengambilan keputusan berdasarkan risiko
        if (stats_bot.diamonds == 5 or self.harus_kembali_ke_base(stats_bot, tingkat_risiko)):
            self.lokasi_target = self.dapatkan_rute_base()
            if not self.kembali_via_portal_bersama:
                self.target_bersama = []
                self.target_portal_bersama = None
        else:
            if (len(self.target_bersama) == 0):
                self.cari_diamond_terbaik()
            self.lokasi_target = self.target_bersama[0]

        # Kembali darurat jika terlalu berisiko
        if (tingkat_risiko > 0.7 and stats_bot.diamonds > 0):
            self.lokasi_target = self.dapatkan_rute_base()
            if not self.kembali_via_portal_bersama:
                self.target_bersama = []
                self.target_portal_bersama = None

        if self.target_perantara_bersama:
            self.lokasi_target = self.target_perantara_bersama

        # Hitung langkah selanjutnya
        posisi_bot = player_bot.position
        if self.lokasi_target:
            if (not self.target_perantara_bersama):
                self.periksa_hambatan_jalur('teleporter', posisi_bot.x, posisi_bot.y, 
                                        self.lokasi_target.x, self.lokasi_target.y)

            if (stats_bot.diamonds == 4):
                self.periksa_hambatan_jalur('redDiamond', posisi_bot.x, posisi_bot.y, 
                                        self.lokasi_target.x, self.lokasi_target.y)
            
            gerak_x, gerak_y = get_direction(posisi_bot.x, posisi_bot.y, 
                                         self.lokasi_target.x, self.lokasi_target.y)
        else:
            gerakan = self.dapatkan_gerakan_acak_aman()
            gerak_x, gerak_y = gerakan[0], gerakan[1]

        if (gerak_x == 0 and gerak_y == 0):
            # Reset dan coba lagi
            self.target_bersama = []
            self.kembali_via_portal_bersama = False
            self.target_portal_bersama = None
            self.target_perantara_bersama = None
            self.lokasi_target = None
            gerakan_rekursif = self.next_move(player_bot, game_board)
            gerak_x, gerak_y = gerakan_rekursif[0], gerakan_rekursif[1]

        return gerak_x, gerak_y

    def nilai_tingkat_risiko(self):
        """Penilaian risiko yang disederhanakan"""
        faktor_risiko = []
        
        # Risiko inventory diamond
        risiko_inventory = self.bot_pemain.properties.diamonds / 5.0
        faktor_risiko.append(risiko_inventory * 0.4)
        
        # Risiko tekanan waktu
        risiko_waktu = 1.0 - (self.bot_pemain.properties.milliseconds_left / 30000.0)
        faktor_risiko.append(risiko_waktu * 0.3)
        
        # Risiko kedekatan lawan
        posisi_bot = self.bot_pemain.position
        jarak_minimum = float('inf')
        for lawan in self.bot_lawan:
            jarak = abs(lawan.position.x - posisi_bot.x) + abs(lawan.position.y - posisi_bot.y)
            jarak_minimum = min(jarak_minimum, jarak)
        
        if jarak_minimum != float('inf') and jarak_minimum <= 5:
            risiko_kedekatan = 1.0 - (jarak_minimum / 5.0)
            faktor_risiko.append(risiko_kedekatan * 0.3)
        
        return min(1.0, sum(faktor_risiko))

    def harus_kembali_ke_base(self, stats_bot, level_risiko):
        """Tentukan apakah harus kembali berdasarkan kriteria sederhana"""
        if stats_bot.diamonds == 0:
            return False
        
        # Ambang batas sederhana berdasarkan diamond yang dibawa
        ambang_batas = {1: 0.8, 2: 0.7, 3: 0.6, 4: 0.5}
        batas = ambang_batas.get(stats_bot.diamonds, 0.4)
        
        return level_risiko > batas

    def dapatkan_rute_base(self):
        """Dapatkan rute ke base (langsung atau via portal)"""
        posisi_bot = self.bot_pemain.position
        base_rumah = self.bot_pemain.properties.base
        
        # Jarak langsung
        jarak_langsung = abs(base_rumah.x - posisi_bot.x) + abs(base_rumah.y - posisi_bot.y)
        
        # Jarak portal
        pos_portal_terdekat, pos_portal_jauh, obj_portal_terdekat = self.cari_portal_terdekat()
        
        if pos_portal_terdekat:
            jarak_portal = (abs(pos_portal_terdekat.x - posisi_bot.x) + 
                           abs(pos_portal_terdekat.y - posisi_bot.y) +
                           abs(base_rumah.x - pos_portal_jauh.x) + 
                           abs(base_rumah.y - pos_portal_jauh.y))
            
            # Gunakan portal jika jauh lebih pendek
            if jarak_portal < jarak_langsung * 0.8:
                self.kembali_via_portal_bersama = True
                self.target_portal_bersama = obj_portal_terdekat
                self.target_bersama = [pos_portal_terdekat, base_rumah]
                return pos_portal_terdekat
        
        return Position(base_rumah.y, base_rumah.x)

    def cari_diamond_terbaik(self):
        """Cari diamond terbaik dengan mempertimbangkan risiko dan reward"""
        opsi_langsung = self.cari_diamond_terbaik_langsung()
        opsi_portal = self.cari_diamond_terbaik_via_portal()
        opsi_tombol = self.cari_tombol_khusus_terbaik()
        
        # Pilih opsi terbaik
        skor_terbaik = max(opsi_langsung[0], opsi_portal[0], opsi_tombol[0])
        
        if opsi_langsung[0] == skor_terbaik and opsi_langsung[1]:
            self.target_bersama = [opsi_langsung[1]]
        elif opsi_portal[0] == skor_terbaik and opsi_portal[1]:
            self.target_bersama = opsi_portal[1]
            self.target_portal_bersama = opsi_portal[2]
        elif opsi_tombol[1]:
            self.target_bersama = [opsi_tombol[1]]

    def hitung_skor_diamond(self, poin, jarak, posisi_target):
        """Hitung skor diamond yang disesuaikan dengan risiko"""
        if jarak == 0:
            return 0
        
        skor_dasar = poin / jarak
        
        # Penyesuaian risiko sederhana berdasarkan kedekatan lawan
        penalti_risiko = 0
        for lawan in self.bot_lawan:
            jarak_lawan = abs(lawan.position.x - posisi_target.x) + abs(lawan.position.y - posisi_target.y)
            if jarak_lawan <= 3:
                penalti_risiko += (3 - jarak_lawan) * 0.2
        
        return max(0.1, skor_dasar - penalti_risiko)

    def cari_diamond_terbaik_langsung(self):
        """Cari diamond terbaik via rute langsung"""
        posisi_bot = self.bot_pemain.position
        skor_terbaik = 0
        diamond_terbaik = None
        
        for permata in self.diamond_tersedia:
            # Lewati red diamond jika membawa 4 diamond
            if permata.properties.points == 2 and self.bot_pemain.properties.diamonds == 4:
                continue
                
            jarak = abs(permata.position.x - posisi_bot.x) + abs(permata.position.y - posisi_bot.y)
            skor = self.hitung_skor_diamond(permata.properties.points, jarak, permata.position)
            
            if skor > skor_terbaik:
                skor_terbaik = skor
                diamond_terbaik = permata.position
                
        return skor_terbaik, diamond_terbaik

    def cari_diamond_terbaik_via_portal(self):
        """Cari diamond terbaik via rute portal"""
        posisi_bot = self.bot_pemain.position
        pos_portal_terdekat, pos_portal_jauh, portal_terdekat = self.cari_portal_terdekat()

        if not all([pos_portal_terdekat, pos_portal_jauh, portal_terdekat]):
            return 0, None, None
    
        skor_terbaik = 0
        jalur_diamond_terbaik = None

        for permata in self.diamond_tersedia:
            if permata.properties.points == 2 and self.bot_pemain.properties.diamonds == 4:
                continue
                
            portal_ke_diamond = abs(permata.position.x - pos_portal_jauh.x) + abs(permata.position.y - pos_portal_jauh.y)
            bot_ke_portal = abs(pos_portal_terdekat.x - posisi_bot.x) + abs(pos_portal_terdekat.y - posisi_bot.y)
            total_jarak = portal_ke_diamond + bot_ke_portal
            
            skor = self.hitung_skor_diamond(permata.properties.points, total_jarak, permata.position)
            
            if skor > skor_terbaik:
                skor_terbaik = skor
                jalur_diamond_terbaik = [pos_portal_terdekat, permata.position]
                
        return skor_terbaik, jalur_diamond_terbaik, portal_terdekat

    def cari_tombol_khusus_terbaik(self):
        """Cari tombol khusus terbaik"""
        if not self.tombol_khusus:
            return 0, None
            
        posisi_bot = self.bot_pemain.position
        tombol = self.tombol_khusus[0]
        jarak = abs(tombol.position.x - posisi_bot.x) + abs(tombol.position.y - posisi_bot.y)
        
        skor = self.hitung_skor_diamond(3, jarak, tombol.position)  # Asumsikan tombol bernilai 3 poin
        return skor, tombol.position

    def dapatkan_gerakan_acak_aman(self):
        """Dapatkan gerakan acak yang lebih aman"""
        posisi_bot = self.bot_pemain.position
        gerakan_teraman = self.vektor_gerakan[self.arah_sekarang]
        
        # Coba hindari lawan
        for gerakan in self.vektor_gerakan:
            posisi_selanjutnya = Position(posisi_bot.y + gerakan[1], posisi_bot.x + gerakan[0])
            aman = True
            
            for lawan in self.bot_lawan:
                if abs(lawan.position.x - posisi_selanjutnya.x) + abs(lawan.position.y - posisi_selanjutnya.y) <= 2:
                    aman = False
                    break
            
            if aman:
                gerakan_teraman = gerakan
                break
        
        self.arah_sekarang = (self.arah_sekarang + 1) % len(self.vektor_gerakan)
        return gerakan_teraman

    def cari_portal_terdekat(self):
        """Cari portal terdekat"""
        pos_portal_terdekat, pos_portal_jauh, obj_portal_terdekat = None, None, None
        jarak_minimum = float("inf")
        
        for portal in self.objek_portal:
            jarak = abs(portal.position.x - self.bot_pemain.position.x) + abs(portal.position.y - self.bot_pemain.position.y)
            if jarak == 0:
                return None, None, None
            if jarak < jarak_minimum:
                jarak_minimum = jarak
                pos_portal_terdekat, pos_portal_jauh = portal.position, self.cari_portal_pasangan(portal)
                obj_portal_terdekat = portal
                
        return pos_portal_terdekat, pos_portal_jauh, obj_portal_terdekat
    
    def cari_portal_pasangan(self, portal: GameObject):
        """Cari portal pasangan"""
        for tp in self.objek_portal:
            if tp.id != portal.id:
                return tp.position
            
    def periksa_hambatan_jalur(self, tipe_hambatan, start_x, start_y, target_x, target_y):
        """Periksa dan tangani hambatan jalur"""
        if tipe_hambatan == 'teleporter':
            hambatan_list = self.objek_portal
        elif tipe_hambatan == 'redDiamond':
            hambatan_list = [permata for permata in self.diamond_tersedia if permata.properties.points == 2]
        else:
            return
        
        for hambatan in hambatan_list:
            if start_x == hambatan.position.x and start_y == hambatan.position.y:
                continue
                
            # Periksa apakah hambatan menghalangi jalur vertikal
            if (hambatan.position.x == target_x and 
                ((target_y < hambatan.position.y <= start_y) or (start_y <= hambatan.position.y < target_y))):
                
                if target_x != start_x:
                    offset_x = target_x - 1 if target_x > start_x else target_x + 1
                    self.lokasi_target = Position(target_y, offset_x)
                else:
                    offset_x = target_x + 1 if target_x <= 1 else target_x - 1
                    self.lokasi_target = Position(target_y, offset_x)
                self.target_perantara_bersama = self.lokasi_target
                
            # Periksa apakah hambatan menghalangi jalur horizontal  
            elif (hambatan.position.y == target_y and 
                  ((target_x < hambatan.position.x <= start_x) or (start_x <= hambatan.position.x < target_x))):
                
                if target_y != start_y:
                    offset_y = target_y - 1 if target_y > start_y else target_y + 1
                    self.lokasi_target = Position(offset_y, target_x)
                else:
                    offset_y = target_y + 1 if target_y <= 1 else target_y - 1
                    self.lokasi_target = Position(offset_y, target_x)
                self.target_perantara_bersama = self.lokasi_target