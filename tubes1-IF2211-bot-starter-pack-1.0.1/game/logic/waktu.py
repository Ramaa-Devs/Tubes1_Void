from typing import Optional
from game.logic.base import BaseLogic
from game.models import Board, GameObject, Position
from game.util import get_direction


class GreedyDiamondLogic(BaseLogic):
    shared_targets : list[Position] = []
    shared_portal_target : GameObject = None
    shared_intermediate_target : Position = None
    shared_return_via_portal : bool = False

    def __init__(self) -> None:
        self.movement_vectors = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        self.target_location: Optional[Position] = None
        self.current_heading = 0
        self.calculated_distance = 0

    def next_move(self, player_bot: GameObject, game_board: Board):
        bot_stats = player_bot.properties
        self.game_board = game_board
        self.player_bot = player_bot
        self.available_diamonds = game_board.diamonds
        self.all_bots = game_board.bots
        self.portal_objects = [obj for obj in self.game_board.game_objects if obj.type == "TeleportGameObject"]
        self.special_buttons = [obj for obj in self.game_board.game_objects if obj.type == "DiamondButtonGameObject"]
        self.opponent_bots = [bot for bot in self.all_bots if bot.id != self.player_bot.id]
        self.opponent_diamonds = [bot.properties.diamonds for bot in self.opponent_bots]

        # HAPUS SEMUA DATA STATIS KETIKA DI BASE
        if (self.player_bot.position == self.player_bot.properties.base):
            self.shared_targets = []
            self.shared_portal_target = None
            self.shared_intermediate_target = None
            self.shared_return_via_portal = False

        # HAPUS TARGET STATIS DI TELEPORT
        if (self.shared_portal_target and self.player_bot.position == self.locate_paired_portal(self.shared_portal_target)):
            self.shared_targets.remove(self.shared_portal_target.position)
            self.shared_portal_target = None
        if (not self.shared_portal_target and self.player_bot.position in self.shared_targets):
            self.shared_targets.remove(self.player_bot.position)
        
        # Hapus target sementara jika sudah tercapai
        if (self.player_bot.position == self.shared_intermediate_target):
            self.shared_intermediate_target = None

        # TIME-WEIGHTED DECISION MAKING
        time_left_ratio = bot_stats.milliseconds_left / 30000.0  # Normalize to 0-1
        urgency_threshold = self.calculate_urgency_threshold(time_left_ratio, bot_stats.diamonds)

        # Analisis kondisi baru dengan time-weighted priority
        if (bot_stats.diamonds == 5 or 
            (bot_stats.milliseconds_left < urgency_threshold and bot_stats.diamonds > 0) or
            self.should_return_early(bot_stats, time_left_ratio)):
            # Bergerak ke base dengan pertimbangan waktu
            self.target_location = self.determine_optimal_base_route()
            if not self.shared_return_via_portal:
                self.shared_targets = []
                self.shared_portal_target = None
        else:
            if (len(self.shared_targets) == 0):
                self.locate_closest_diamond_time_weighted()
            self.target_location = self.shared_targets[0]

        # Evaluasi kedekatan base dengan time factor
        if (self.evaluate_base_proximity_time_weighted(time_left_ratio) and bot_stats.diamonds > 1):
            self.target_location = self.determine_optimal_base_route()
            if not self.shared_return_via_portal:
                self.shared_targets = []
                self.shared_portal_target = None

        if self.shared_intermediate_target: # Jika ada target sementara, gunakan itu
            self.target_location = self.shared_intermediate_target

        # Hitung langkah selanjutnya
        bot_position = player_bot.position
        if self.target_location:
            # Periksa apakah ada teleporter di jalur
            if (not self.shared_intermediate_target):
                self.check_path_obstacles(
                    'teleporter',
                    bot_position.x,
                    bot_position.y,
                    self.target_location.x,
                    self.target_location.y,
                )

            # Periksa apakah ada diamond merah di jalur
            if (bot_stats.diamonds == 4):
                self.check_path_obstacles(
                    'redDiamond',
                    bot_position.x,
                    bot_position.y,
                    self.target_location.x,
                    self.target_location.y,
                )
            
            # Kita menuju posisi spesifik, hitung delta
            move_x, move_y = get_direction(
                bot_position.x,
                bot_position.y,
                self.target_location.x,
                self.target_location.y,
            )
        else:
            # Berkeliaran
            movement = self.movement_vectors[self.current_heading]
            move_x = movement[0]
            move_y = movement[1]
            self.current_heading = (self.current_heading + 1) % len(
                self.movement_vectors
            )

        if (move_x == 0 and move_y == 0):
            # Reset target
            self.shared_targets = []
            self.shared_return_via_portal = False
            self.shared_portal_target = None
            self.shared_intermediate_target = None
            self.target_location = None
            recursive_move = self.next_move(player_bot, game_board)
            move_x, move_y = recursive_move[0], recursive_move[1]

        return move_x, move_y

    def calculate_urgency_threshold(self, time_ratio, diamonds_count):
        """Hitung threshold waktu untuk kembali ke base berdasarkan jumlah diamond"""
        base_threshold = 8000  # 8 detik base threshold
        
        # Semakin banyak diamond, semakin early return
        diamond_multiplier = 1.0 + (diamonds_count * 0.3)
        
        # Semakin sedikit waktu, threshold semakin tinggi (lebih konservatif)
        time_multiplier = 1.0 + (1.0 - time_ratio) * 0.5
        
        return base_threshold * diamond_multiplier * time_multiplier

    def should_return_early(self, bot_stats, time_ratio):
        """Tentukan apakah harus kembali lebih awal berdasarkan waktu dan posisi"""
        if bot_stats.diamonds == 0:
            return False
            
        # Hitung waktu minimum yang dibutuhkan untuk kembali ke base
        min_return_time = self.calculate_minimum_return_time()
        time_left_ms = bot_stats.milliseconds_left
        
        # Faktor safety berdasarkan jumlah diamond (semakin banyak semakin konservatif)
        safety_factor = 1.2 + (bot_stats.diamonds * 0.1)
        
        # Return early jika waktu tersisa kurang dari waktu kembali + safety margin
        return time_left_ms < (min_return_time * 1000 * safety_factor)

    def calculate_minimum_return_time(self):
        """Hitung waktu minimum untuk kembali ke base (dalam detik)"""
        bot_position = self.player_bot.position
        home_base = self.player_bot.properties.base
        
        # Jarak langsung ke base
        direct_distance = abs(home_base.x - bot_position.x) + abs(home_base.y - bot_position.y)
        
        # Jarak via portal jika ada
        portal_distance = self.calculate_base_distance_via_portal()
        
        # Pilih rute tercepat
        min_distance = min(direct_distance, portal_distance)
        
        # Asumsi 1 langkah = 1 detik (adjust sesuai game speed)
        return min_distance

    def evaluate_base_proximity_time_weighted(self, time_ratio):
        """Evaluasi kedekatan base dengan mempertimbangkan waktu tersisa"""
        bot_position = self.player_bot.position
        home_base = self.player_bot.properties.base

        # Hitung jarak ke base
        direct_distance = abs(home_base.x - bot_position.x) + abs(home_base.y - bot_position.y)
        portal_distance = self.calculate_base_distance_via_portal()
        optimal_distance = min(direct_distance, portal_distance)

        if optimal_distance == 0:
            return False
        
        # Time-weighted proximity calculation
        # Semakin sedikit waktu, threshold kedekatan semakin besar
        time_urgency = 1.0 - time_ratio  # 0 = banyak waktu, 1 = sedikit waktu
        proximity_threshold = 3 + (time_urgency * 7)  # Range 3-10 langkah
        
        # Juga pertimbangkan jarak ke diamond terdekat
        closest_diamond_distance = self.calculated_distance if self.calculated_distance > 0 else float('inf')
        
        return (optimal_distance <= proximity_threshold or 
                (closest_diamond_distance != float('inf') and optimal_distance < closest_diamond_distance))

    def locate_closest_diamond_time_weighted(self) -> Optional[Position]:
        """Cari diamond dengan Time-Weighted Priority"""
        bot_stats = self.player_bot.properties
        time_left_ratio = bot_stats.milliseconds_left / 30000.0
        
        direct_option = self.find_closest_diamond_direct_time_weighted(time_left_ratio)
        portal_option = self.find_closest_diamond_via_portal_time_weighted(time_left_ratio)
        button_option = self.find_closest_special_button_time_weighted(time_left_ratio)
        
        # Pilih opsi dengan score tertinggi
        if (direct_option[0] >= portal_option[0] and direct_option[0] >= button_option[0]):
            self.shared_targets = [direct_option[1]]
            self.calculated_distance = abs(self.player_bot.position.x - direct_option[1].x) + abs(self.player_bot.position.y - direct_option[1].y)
        elif (portal_option[0] >= direct_option[0] and portal_option[0] >= button_option[0]):
            self.shared_targets = portal_option[1]
            self.shared_portal_target = portal_option[2]
            self.calculated_distance = abs(self.player_bot.position.x - portal_option[1][0].x) + abs(self.player_bot.position.y - portal_option[1][0].y)
        else:
            self.shared_targets = [button_option[1]]
            self.calculated_distance = abs(self.player_bot.position.x - button_option[1].x) + abs(self.player_bot.position.y - button_option[1].y)

    def calculate_time_weighted_score(self, points, distance, time_ratio):
        """Hitung score berdasarkan Time-Weighted Priority"""
        if distance == 0:
            return 0
            
        # Base score: points per distance
        base_score = points / distance
        
        # Time factor: semakin sedikit waktu, semakin prioritas yang dekat
        # time_ratio: 1.0 = awal game, 0.0 = akhir game
        time_urgency = 1.0 - time_ratio
        
        # Pada awal game (time_ratio tinggi): prioritas value/distance
        # Pada akhir game (time_ratio rendah): prioritas distance (yang dekat)
        if time_ratio > 0.7:  # Awal game (70%+ waktu tersisa)
            time_weight = 1.0 + (points * 0.1)  # Bonus untuk diamond bernilai tinggi
        elif time_ratio > 0.3:  # Mid game (30-70% waktu tersisa)
            time_weight = 1.0 + (time_urgency * 0.5)  # Moderate urgency
        else:  # End game (<30% waktu tersisa)
            distance_penalty = distance * time_urgency * 0.3
            time_weight = max(0.1, 1.0 - distance_penalty)  # Heavy penalty untuk jarak jauh
        
        return base_score * time_weight

    def find_closest_diamond_direct_time_weighted(self, time_ratio):
        """Cari diamond terdekat dengan rute langsung menggunakan time-weighted scoring"""
        bot_position = self.player_bot.position
        best_score = 0
        best_diamond = None
        
        for gem in self.available_diamonds:
            if not self.is_diamond_collectible(gem):
                continue
                
            distance = abs(gem.position.x - bot_position.x) + abs(gem.position.y - bot_position.y)
            score = self.calculate_time_weighted_score(gem.properties.points, distance, time_ratio)
            
            if score > best_score:
                best_score = score
                best_diamond = gem.position
                
        return best_score, best_diamond

    def find_closest_diamond_via_portal_time_weighted(self, time_ratio):
        """Cari diamond terdekat via portal dengan time-weighted scoring"""
        bot_position = self.player_bot.position
        closest_portal_pos, distant_portal_pos, closest_portal = self.locate_nearest_portal()

        if not all([closest_portal_pos, distant_portal_pos, closest_portal]):
            return 0, None, None
    
        best_score = 0
        best_diamond_path = None

        for gem in self.available_diamonds:
            if not self.is_diamond_collectible(gem):
                continue
                
            # Total distance via portal
            portal_to_diamond = abs(gem.position.x - distant_portal_pos.x) + abs(gem.position.y - distant_portal_pos.y)
            bot_to_portal = abs(closest_portal_pos.x - bot_position.x) + abs(closest_portal_pos.y - bot_position.y)
            total_distance = portal_to_diamond + bot_to_portal
            
            score = self.calculate_time_weighted_score(gem.properties.points, total_distance, time_ratio)
            
            if score > best_score:
                best_score = score
                best_diamond_path = [closest_portal_pos, gem.position]
                
        return best_score, best_diamond_path, closest_portal

    def find_closest_special_button_time_weighted(self, time_ratio):
        """Cari tombol merah dengan time-weighted scoring"""
        if not self.special_buttons:
            return 0, None
            
        bot_position = self.player_bot.position
        button = self.special_buttons[0]  # Asumsi hanya ada 1 button
        distance = abs(button.position.x - bot_position.x) + abs(button.position.y - bot_position.y)
        
        # Button memberikan banyak diamond, tapi pertimbangkan waktu juga
        button_value = 3  # Estimasi value dari button
        score = self.calculate_time_weighted_score(button_value, distance, time_ratio)
        
        return score, button.position

    def is_diamond_collectible(self, gem):
        """Cek apakah diamond bisa diambil berdasarkan kondisi saat ini"""
        # Hindari red diamond (2 points) jika sudah punya 4 diamond
        if gem.properties.points == 2 and self.player_bot.properties.diamonds == 4:
            return False
        return True

    # ====== METHODS DARI KODE ORIGINAL (TIDAK DIUBAH) ======
    
    def determine_optimal_base_route(self):
        bot_position = self.player_bot.position
        home_base = self.player_bot.properties.base
        base_coords = Position(home_base.y, home_base.x)

        # Hitung jarak ke base dengan rute langsung dan teleporter
        direct_base_distance = abs(home_base.x - bot_position.x) + abs(home_base.y - bot_position.y)
        closest_portal_pos, distant_portal_pos, closest_portal_obj = self.locate_nearest_portal()

        if (closest_portal_pos == None and distant_portal_pos == None):
            return base_coords

        # Cari cara terbaik ke base
        portal_base_distance = abs(home_base.x - distant_portal_pos.x) + abs(home_base.y - distant_portal_pos.y) + abs(closest_portal_pos.x - bot_position.x) + abs(closest_portal_pos.y - bot_position.y)
        if (direct_base_distance < portal_base_distance):
            return base_coords
        else:
            self.shared_return_via_portal = True
            self.shared_portal_target = closest_portal_obj
            self.shared_targets = [closest_portal_pos, home_base]
            return closest_portal_pos

    def calculate_base_distance_via_portal(self):
        bot_position = self.player_bot.position
        closest_portal_pos, distant_portal_pos, closest_portal = self.locate_nearest_portal()

        if (closest_portal_pos == None and distant_portal_pos == None and closest_portal == None):
            return float("inf")

        home_base = self.player_bot.properties.base
        portal_route_distance = abs(home_base.x - distant_portal_pos.x) + abs(home_base.y - distant_portal_pos.y) + abs(closest_portal_pos.x - bot_position.x) + abs(closest_portal_pos.y - bot_position.y)
        return portal_route_distance    

    def locate_nearest_portal(self):
        closest_portal_pos, distant_portal_pos, closest_portal_obj = None, None, None
        minimum_distance = float("inf")
        for portal in self.portal_objects:
            distance = abs(portal.position.x - self.player_bot.position.x) + abs(portal.position.y - self.player_bot.position.y)
            if distance == 0:
                return None, None, None
            if distance < minimum_distance:
                minimum_distance = distance
                closest_portal_pos, distant_portal_pos = portal.position, self.locate_paired_portal(portal)
                closest_portal_obj = portal
        return closest_portal_pos, distant_portal_pos, closest_portal_obj
    
    def locate_paired_portal(self, portal: GameObject):
        for tp in self.portal_objects:
            if tp.id != portal.id:
                return tp.position
            
    def check_path_obstacles(self, obstacle_type, start_x, start_y, target_x, target_y):
        if obstacle_type == 'teleporter':
            obstacles = self.portal_objects
        elif obstacle_type == 'redDiamond':
            obstacles = [gem for gem in self.available_diamonds if gem.properties.points == 2]
        elif obstacle_type == 'redButton':
            obstacles = self.special_buttons
        
        for obstacle in obstacles:
            if start_x == obstacle.position.x and start_y == obstacle.position.y:
                continue
            # Kondisi saat obstacle sejajar dengan destinasi dalam sumbu y dan berada pada jalur start->target
            if obstacle.position.x == target_x and (target_y < obstacle.position.y <= start_y or start_y <= obstacle.position.y < target_y):

                # Kondisi saat start tidak sejajar dengan destinasi pada sumbu y
                if (target_x != start_x):
                    self.target_location = Position(target_y, target_x-1) if target_x > start_x else Position(target_y, target_x+1)

                # Kondisi saat start sejajar dengan destinasi pada sumbu y
                else:
                    # Handle jika di pinggir kiri/kanan
                    if (target_x <= 1):
                        self.target_location = Position(target_y, target_x+1)
                    else:
                        self.target_location = Position(target_y, target_x-1)
                self.shared_intermediate_target = self.target_location

            # Kondisi saat obstacle sejajar dengan destinasi dalam sumbu x dan berada pada jalur start->target
            elif obstacle.position.y == target_y and (target_x < obstacle.position.x <= start_x or start_x <= obstacle.position.x < target_x):

                # Kondisi saat start tidak sejajar dengan destinasi pada sumbu x
                if (target_y != start_y):
                    self.target_location = Position(target_y-1, target_x) if target_y > start_y else Position(target_y+1, target_x)

                # Kondisi saat start sejajar dengan destinasi pada sumbu x
                else:
                    # Handle jika di pinggir atas/bawah
                    if (target_y <= 1):
                        self.target_location = Position(target_y+1, target_x)
                    else:
                        self.target_location = Position(target_y-1, target_x)

                self.shared_intermediate_target = self.target_location
                        
            # Kondisi saat obstacle sejajar dengan start dalam sumbu x dan berada pada jalur start->target
            elif obstacle.position.y == start_y and (target_x < obstacle.position.x <= start_x or start_x <= obstacle.position.x < target_x): 

                # Kondisi saat start tidak sejajar dengan destinasi pada sumbu x
                if (target_y != start_y):
                    self.target_location = Position(target_y, start_x)

                # Kondisi saat start sejajar dengan destinasi pada sumbu y
                else:
                    # Handle jika di pinggir kiri/kanan
                    if (start_y <= 1):
                        self.target_location = Position(start_y+1, start_x)
                    else:
                        self.target_location = Position(start_y-1, start_x)
                        
                self.shared_intermediate_target = self.target_location