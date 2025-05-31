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

        # Analisis kondisi baru
        if bot_stats.diamonds == 5 or (bot_stats.milliseconds_left < 5000 and bot_stats.diamonds > 1):
            # Bergerak ke base
            self.target_location = self.determine_optimal_base_route()
            if not self.shared_return_via_portal:
                self.shared_targets = []
                self.shared_portal_target = None
        else:
            if (len(self.shared_targets) == 0):
                self.locate_closest_diamond()
            self.target_location = self.shared_targets[0]
    

        if (self.evaluate_base_proximity() and bot_stats.diamonds > 2):
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
    
    # Hitung rute terbaik ke base
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
    
    def evaluate_base_proximity(self):
        bot_position = self.player_bot.position
        home_base = self.player_bot.properties.base

        # Hitung jarak ke base dengan rute langsung dan teleporter
        direct_distance = abs(home_base.x - bot_position.x) + abs(home_base.y - bot_position.y)
        portal_distance = self.calculate_base_distance_via_portal()
        optimal_distance = portal_distance if portal_distance < direct_distance else direct_distance

        if (optimal_distance == 0):
            return False
        
        # Base dianggap dekat jika jaraknya <= 5 langkah atau lebih dekat dari jarak ke diamond terdekat
        return optimal_distance <= 5 or (self.calculated_distance > 0 and optimal_distance < self.calculated_distance)

    def calculate_base_distance_via_portal(self):
        bot_position = self.player_bot.position

        # Hitung jarak ke base dengan teleporter
        closest_portal_pos, distant_portal_pos, closest_portal = self.locate_nearest_portal()

        if (closest_portal_pos == None and distant_portal_pos == None and closest_portal == None):
            return float("inf")

        home_base = self.player_bot.properties.base
        portal_route_distance = abs(home_base.x - distant_portal_pos.x) + abs(home_base.y - distant_portal_pos.y) + abs(closest_portal_pos.x - bot_position.x) + abs(closest_portal_pos.y - bot_position.y)
        return portal_route_distance    

    def locate_closest_diamond(self) -> Optional[Position]:
        direct_option = self.find_closest_diamond_direct() # distance, position
        portal_option = self.find_closest_diamond_via_portal() # distance, [teleportPosition, diamondPosition]
        button_option = self.find_closest_special_button() # distance, position
        if (direct_option[0] < portal_option[0] and direct_option[0] < button_option[0]):
            self.shared_targets = [direct_option[1]]
            self.calculated_distance = direct_option[0]
        elif (portal_option[0] < direct_option[0] and portal_option[0] < button_option[0]):
            self.shared_targets = portal_option[1]
            self.shared_portal_target = portal_option[2]
            self.calculated_distance = portal_option[0]
        else:
            self.shared_targets = [button_option[1]]
            self.calculated_distance = button_option[0]
    
    # Cari tombol merah terdekat
    def find_closest_special_button(self):
        bot_position = self.player_bot.position
        distance = abs(self.special_buttons[0].position.x - bot_position.x) + abs(self.special_buttons[0].position.y - bot_position.y)
        return distance, self.special_buttons[0].position

    # Cari teleport terdekat
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
    
    # Cari teleport pasangan
    def locate_paired_portal(self, portal: GameObject):
        for tp in self.portal_objects:
            if tp.id != portal.id:
                return tp.position
            
    # Cari diamond terdekat dengan teleport
    def find_closest_diamond_via_portal(self) -> Optional[Position]:
        bot_position = self.player_bot.position
        closest_portal_pos, distant_portal_pos, closest_portal = self.locate_nearest_portal()

        if (closest_portal_pos == None and distant_portal_pos == None and closest_portal == None):
            return float("inf")
    
        minimum_distance = float("inf")
        best_diamond = None

        # Hitung jarak ke diamond dengan teleport
        for gem in self.available_diamonds:
            distance = abs(gem.position.x - distant_portal_pos.x) + abs(gem.position.y - distant_portal_pos.y) + abs(closest_portal_pos.x - bot_position.x) + abs(closest_portal_pos.y - bot_position.y)
            distance /= gem.properties.points
            if distance < minimum_distance and ((gem.properties.points == 2 and self.player_bot.properties.diamonds != 4) or (gem.properties.points == 1)):
                minimum_distance = distance
                best_diamond = [closest_portal_pos, gem.position]
        return minimum_distance, best_diamond, closest_portal
    
    # Cari diamond terdekat dengan rute langsung
    def find_closest_diamond_direct(self) -> Optional[Position]:
        bot_position = self.player_bot.position
        minimum_distance = float("inf")
        best_diamond = None
        for gem in self.available_diamonds:
            distance = abs(gem.position.x - bot_position.x) + abs(gem.position.y - bot_position.y)
            distance /= gem.properties.points
            if distance < minimum_distance and ((gem.properties.points == 2 and self.player_bot.properties.diamonds != 4) or (gem.properties.points == 1)):
                minimum_distance = distance
                best_diamond = gem.position
        return minimum_distance, best_diamond
    
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