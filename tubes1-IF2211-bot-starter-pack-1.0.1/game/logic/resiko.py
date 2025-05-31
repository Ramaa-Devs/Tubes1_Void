from typing import Optional
from game.logic.base import BaseLogic
from game.models import Board, GameObject, Position
from game.util import get_direction
import math


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
        
        # Risk assessment parameters
        self.risk_tolerance = 1.0  # Base risk tolerance
        self.last_opponent_positions = {}  # Track opponent movements

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

        # Update opponent tracking
        self.update_opponent_tracking()

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

        # RISK ASSESSMENT DECISION MAKING
        current_risk_level = self.assess_current_risk_level()
        
        # Adjust risk tolerance based on game state
        self.adjust_risk_tolerance(bot_stats, current_risk_level)

        # Risk-based decision making
        if (bot_stats.diamonds == 5 or 
            self.should_return_due_to_risk(bot_stats, current_risk_level)):
            # Bergerak ke base karena risiko tinggi
            self.target_location = self.determine_safest_base_route()
            if not self.shared_return_via_portal:
                self.shared_targets = []
                self.shared_portal_target = None
        else:
            if (len(self.shared_targets) == 0):
                self.locate_safest_diamond()
            self.target_location = self.shared_targets[0]

        # Risk-aware base proximity evaluation
        if (self.evaluate_risky_situation() and bot_stats.diamonds > 0):
            self.target_location = self.determine_safest_base_route()
            if not self.shared_return_via_portal:
                self.shared_targets = []
                self.shared_portal_target = None

        if self.shared_intermediate_target: # Jika ada target sementara, gunakan itu
            self.target_location = self.shared_intermediate_target

        # Hitung langkah selanjutnya dengan risk consideration
        bot_position = player_bot.position
        if self.target_location:
            # Periksa risiko di jalur yang akan dilalui
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
            # Berkeliaran dengan risk-aware movement
            movement = self.get_safest_random_movement()
            move_x = movement[0]
            move_y = movement[1]

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

    def assess_current_risk_level(self):
        """Assess overall risk level (0.0 = very safe, 1.0 = very risky)"""
        risk_factors = []
        
        # 1. Diamond inventory risk (more diamonds = higher risk)
        inventory_risk = self.player_bot.properties.diamonds / 5.0
        risk_factors.append(inventory_risk * 0.3)
        
        # 2. Distance to base risk
        distance_risk = self.calculate_base_distance_risk()
        risk_factors.append(distance_risk * 0.2)
        
        # 3. Time pressure risk
        time_risk = self.calculate_time_pressure_risk()
        risk_factors.append(time_risk * 0.2)
        
        # 4. Opponent proximity risk
        opponent_risk = self.calculate_opponent_proximity_risk()
        risk_factors.append(opponent_risk * 0.2)
        
        # 5. Competitive pressure risk
        competitive_risk = self.calculate_competitive_pressure_risk()
        risk_factors.append(competitive_risk * 0.1)
        
        return min(1.0, sum(risk_factors))

    def calculate_base_distance_risk(self):
        """Calculate risk based on distance to base"""
        bot_position = self.player_bot.position
        home_base = self.player_bot.properties.base
        
        # Get minimum distance to base (direct or via portal)
        direct_distance = abs(home_base.x - bot_position.x) + abs(home_base.y - bot_position.y)
        portal_distance = self.calculate_base_distance_via_portal()
        min_distance = min(direct_distance, portal_distance)
        
        # Normalize distance risk (assume max map size is ~20x20)
        max_distance = 40  # Conservative estimate
        return min(1.0, min_distance / max_distance)

    def calculate_time_pressure_risk(self):
        """Calculate risk based on remaining time"""
        time_left_ratio = self.player_bot.properties.milliseconds_left / 30000.0
        # Inverse relationship: less time = higher risk
        return 1.0 - time_left_ratio

    def calculate_opponent_proximity_risk(self):
        """Calculate risk based on how close opponents are"""
        bot_position = self.player_bot.position
        min_opponent_distance = float('inf')
        
        for opponent in self.opponent_bots:
            distance = abs(opponent.position.x - bot_position.x) + abs(opponent.position.y - bot_position.y)
            min_opponent_distance = min(min_opponent_distance, distance)
        
        if min_opponent_distance == float('inf'):
            return 0.0
            
        # Higher risk when opponents are closer
        # Risk is high when opponent is within 5 steps
        proximity_threshold = 5
        return max(0.0, 1.0 - (min_opponent_distance / proximity_threshold))

    def calculate_competitive_pressure_risk(self):
        """Calculate risk based on competitive situation"""
        my_diamonds = self.player_bot.properties.diamonds
        opponent_diamonds = [bot.properties.diamonds for bot in self.opponent_bots]
        
        if not opponent_diamonds:
            return 0.0
        
        max_opponent_diamonds = max(opponent_diamonds)
        
        # Higher risk if opponents have more diamonds
        if max_opponent_diamonds > my_diamonds:
            return (max_opponent_diamonds - my_diamonds) / 5.0
        else:
            return 0.0

    def adjust_risk_tolerance(self, bot_stats, current_risk_level):
        """Adjust risk tolerance based on game state"""
        base_tolerance = 1.0
        
        # Lower tolerance when carrying many diamonds
        inventory_factor = 1.0 - (bot_stats.diamonds / 5.0) * 0.3
        
        # Lower tolerance when time is running out
        time_factor = bot_stats.milliseconds_left / 30000.0
        time_factor = max(0.5, time_factor)  # Don't go below 0.5
        
        # Lower tolerance when current risk is already high
        risk_factor = max(0.7, 1.0 - current_risk_level * 0.3)
        
        self.risk_tolerance = base_tolerance * inventory_factor * time_factor * risk_factor

    def should_return_due_to_risk(self, bot_stats, risk_level):
        """Determine if should return to base due to risk assessment"""
        if bot_stats.diamonds == 0:
            return False
        
        # Risk-based return thresholds
        risk_thresholds = {
            1: 0.7,  # With 1 diamond, return if risk > 70%
            2: 0.6,  # With 2 diamonds, return if risk > 60%
            3: 0.5,  # With 3 diamonds, return if risk > 50%
            4: 0.4,  # With 4 diamonds, return if risk > 40%
        }
        
        threshold = risk_thresholds.get(bot_stats.diamonds, 0.3)
        return risk_level > threshold

    def determine_safest_base_route(self):
        """Determine the safest route to base"""
        bot_position = self.player_bot.position
        home_base = self.player_bot.properties.base
        base_coords = Position(home_base.y, home_base.x)

        # Calculate risks for different routes
        direct_risk = self.calculate_route_risk(bot_position, home_base)
        
        closest_portal_pos, distant_portal_pos, closest_portal_obj = self.locate_nearest_portal()
        
        if not all([closest_portal_pos, distant_portal_pos, closest_portal_obj]):
            return base_coords
        
        # Calculate portal route risk
        portal_risk = (self.calculate_route_risk(bot_position, closest_portal_pos) + 
                      self.calculate_route_risk(distant_portal_pos, home_base)) / 2
        
        # Choose route with lower risk
        if direct_risk <= portal_risk:
            return base_coords
        else:
            self.shared_return_via_portal = True
            self.shared_portal_target = closest_portal_obj
            self.shared_targets = [closest_portal_pos, home_base]
            return closest_portal_pos

    def calculate_route_risk(self, start_pos, end_pos):
        """Calculate risk level for a specific route"""
        # Simple risk calculation based on opponent proximity along route
        risk_score = 0.0
        
        # Check opponent proximity to route
        for opponent in self.opponent_bots:
            # Calculate minimum distance from opponent to the route line
            route_risk = self.calculate_opponent_route_threat(start_pos, end_pos, opponent.position)
            risk_score += route_risk
        
        return min(1.0, risk_score)

    def calculate_opponent_route_threat(self, start, end, opponent_pos):
        """Calculate threat level from opponent to a route"""
        # Simplified threat calculation
        # Check how close opponent is to the route midpoint
        mid_x = (start.x + end.x) / 2
        mid_y = (start.y + end.y) / 2
        
        distance_to_route = abs(opponent_pos.x - mid_x) + abs(opponent_pos.y - mid_y)
        
        # Threat decreases with distance
        threat_radius = 3
        if distance_to_route <= threat_radius:
            return 1.0 - (distance_to_route / threat_radius)
        else:
            return 0.0

    def evaluate_risky_situation(self):
        """Evaluate if current situation is too risky to continue"""
        current_risk = self.assess_current_risk_level()
        return current_risk > self.risk_tolerance

    def locate_safest_diamond(self):
        """Find diamond with best risk-adjusted value"""
        direct_option = self.find_safest_diamond_direct()
        portal_option = self.find_safest_diamond_via_portal()
        button_option = self.find_safest_special_button()
        
        # Choose option with highest risk-adjusted score
        if (direct_option[0] >= portal_option[0] and direct_option[0] >= button_option[0]):
            if direct_option[1]:
                self.shared_targets = [direct_option[1]]
                self.calculated_distance = abs(self.player_bot.position.x - direct_option[1].x) + abs(self.player_bot.position.y - direct_option[1].y)
        elif (portal_option[0] >= direct_option[0] and portal_option[0] >= button_option[0]):
            if portal_option[1]:
                self.shared_targets = portal_option[1]
                self.shared_portal_target = portal_option[2]
                self.calculated_distance = abs(self.player_bot.position.x - portal_option[1][0].x) + abs(self.player_bot.position.y - portal_option[1][0].y)
        else:
            if button_option[1]:
                self.shared_targets = [button_option[1]]
                self.calculated_distance = abs(self.player_bot.position.x - button_option[1].x) + abs(self.player_bot.position.y - button_option[1].y)

    def calculate_risk_adjusted_score(self, points, distance, target_position):
        """Calculate score adjusted for risk"""
        if distance == 0:
            return 0
        
        # Base score
        base_score = points / distance
        
        # Calculate risk factors for this target
        target_risk = self.calculate_target_risk(target_position)
        
        # Apply risk adjustment
        risk_multiplier = max(0.1, 1.0 - target_risk)
        
        return base_score * risk_multiplier

    def calculate_target_risk(self, target_position):
        """Calculate risk of going to a specific target"""
        risk_factors = []
        
        # 1. Opponent proximity to target
        opponent_proximity_risk = 0.0
        for opponent in self.opponent_bots:
            distance = abs(opponent.position.x - target_position.x) + abs(opponent.position.y - target_position.y)
            if distance <= 3:  # Dangerous if opponent within 3 steps
                opponent_proximity_risk = max(opponent_proximity_risk, 1.0 - distance / 3.0)
        risk_factors.append(opponent_proximity_risk * 0.4)
        
        # 2. Distance from base (further = riskier)
        home_base = self.player_bot.properties.base
        base_distance = abs(home_base.x - target_position.x) + abs(home_base.y - target_position.y)
        distance_risk = min(1.0, base_distance / 20.0)  # Normalize assuming max 20 distance
        risk_factors.append(distance_risk * 0.3)
        
        # 3. Route risk (how risky is the path to target)
        route_risk = self.calculate_route_risk(self.player_bot.position, target_position)
        risk_factors.append(route_risk * 0.3)
        
        return min(1.0, sum(risk_factors))

    def find_safest_diamond_direct(self):
        """Find safest diamond via direct route"""
        bot_position = self.player_bot.position
        best_score = 0
        best_diamond = None
        
        for gem in self.available_diamonds:
            if not self.is_diamond_collectible(gem):
                continue
                
            distance = abs(gem.position.x - bot_position.x) + abs(gem.position.y - bot_position.y)
            score = self.calculate_risk_adjusted_score(gem.properties.points, distance, gem.position)
            
            if score > best_score:
                best_score = score
                best_diamond = gem.position
                
        return best_score, best_diamond

    def find_safest_diamond_via_portal(self):
        """Find safest diamond via portal route"""
        bot_position = self.player_bot.position
        closest_portal_pos, distant_portal_pos, closest_portal = self.locate_nearest_portal()

        if not all([closest_portal_pos, distant_portal_pos, closest_portal]):
            return 0, None, None
    
        best_score = 0
        best_diamond_path = None

        for gem in self.available_diamonds:
            if not self.is_diamond_collectible(gem):
                continue
                
            # Calculate total distance and risk via portal
            portal_to_diamond = abs(gem.position.x - distant_portal_pos.x) + abs(gem.position.y - distant_portal_pos.y)
            bot_to_portal = abs(closest_portal_pos.x - bot_position.x) + abs(closest_portal_pos.y - bot_position.y)
            total_distance = portal_to_diamond + bot_to_portal
            
            # Use distant portal position for risk calculation (where we'll end up)
            score = self.calculate_risk_adjusted_score(gem.properties.points, total_distance, gem.position)
            
            if score > best_score:
                best_score = score
                best_diamond_path = [closest_portal_pos, gem.position]
                
        return best_score, best_diamond_path, closest_portal

    def find_safest_special_button(self):
        """Find safest special button"""
        if not self.special_buttons:
            return 0, None
            
        bot_position = self.player_bot.position
        button = self.special_buttons[0]
        distance = abs(button.position.x - bot_position.x) + abs(button.position.y - bot_position.y)
        
        # Button has high value but also consider risk
        button_value = 3  # Estimated value
        score = self.calculate_risk_adjusted_score(button_value, distance, button.position)
        
        return score, button.position

    def get_safest_random_movement(self):
        """Get safest random movement when no specific target"""
        bot_position = self.player_bot.position
        safest_movement = self.movement_vectors[self.current_heading]
        lowest_risk = float('inf')
        
        for movement in self.movement_vectors:
            next_pos = Position(
                bot_position.y + movement[1], 
                bot_position.x + movement[0]
            )
            risk = self.calculate_target_risk(next_pos)
            
            if risk < lowest_risk:
                lowest_risk = risk
                safest_movement = movement
        
        self.current_heading = (self.current_heading + 1) % len(self.movement_vectors)
        return safest_movement

    def update_opponent_tracking(self):
        """Update tracking of opponent positions for movement prediction"""
        for opponent in self.opponent_bots:
            if opponent.id not in self.last_opponent_positions:
                self.last_opponent_positions[opponent.id] = []
            
            # Keep last 3 positions for movement pattern analysis
            self.last_opponent_positions[opponent.id].append(opponent.position)
            if len(self.last_opponent_positions[opponent.id]) > 3:
                self.last_opponent_positions[opponent.id].pop(0)

    def is_diamond_collectible(self, gem):
        """Check if diamond is safe to collect"""
        # Don't collect red diamond if we have 4 diamonds
        if gem.properties.points == 2 and self.player_bot.properties.diamonds == 4:
            return False
        return True

    # ====== METHODS DARI KODE ORIGINAL (TIDAK DIUBAH) ======
    
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