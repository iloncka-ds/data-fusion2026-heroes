import polars as pl
import numpy as np

# Global parameters, as in our Heroes legend
VISIT_COST = 100
HERO_COST = 2500

class HeroesInstance:
    def __init__(self, data_path = 'data/'):
        """
        Init Heroes-themed VRPTW-like instance, load data from expected (data) path
        """

        self.heroes = None
        self.objects = None
        self.dist_matrix = None
        self.dist_start = None
        
        # Utility lookups
        self.hero_mp_map = {}
        self.obj_info_map = {}
        self.dist_start_map = {}
        
        # Main init
        self.load_data(data_path)

    def load_data(self, data_path):
        """
        Load data, prepare lookup dicts
        """

        # 0. Precautionary sanity considerations
        # We don't add explicit with_columns cast(pl.Int32), however it could be of use
        # Also OG time/distance matrix is 700x700, could require extra validation

        try:
            # 1. Load Heroes and Waterwheel (gold) Objects info
            self.heroes = pl.read_csv(f'{data_path}data_heroes.csv')
            self.objects = pl.read_csv(f'{data_path}data_objects.csv')
            
            # 2.1. Load Castle/Depot distance info
            self.dist_start = pl.read_csv(f'{data_path}dist_start.csv')
            
            # 2.2. Load Time/Distance matrix
            # NB it is expected to have a header ('object_i', ...) hence don't touch (default) option has_header=True
            dist_objects = pl.read_csv(f'{data_path}dist_objects.csv')
                        
            # Ensure int matrix and convert it to NumPy
            dist_objects = dist_objects.select(pl.all().cast(pl.Int32))
            self.dist_matrix = dist_objects.to_numpy()

            # 3. Prepare lookups
            self.hero_mp_map = {row['hero_id']: row['move_points'] for row in self.heroes.iter_rows(named = True)}
            self.obj_info_map = {row['object_id']: row for row in self.objects.iter_rows(named = True)}
            self.dist_start_map = {row['object_id']: row['dist_start'] for row in self.dist_start.iter_rows(named = True)}
            
        except Exception as e:
            print(f"Error loading data: {e}")
    
    def get_distance(self, from_id: int, to_id: int) -> int:
        """
        Helper function to get distance between two objects (0 reserved for Castle/Depot)
        """

        if from_id == 0:
            return self.dist_start_map.get(to_id, 0)
        return self.dist_matrix[from_id - 1, to_id - 1]

    def simulate_hero_movement(self, hero_id: int, current_state: dict, target_object: int) -> dict:
        """
        Simulate complete logic of a hero's transition 
        Note that current_state is a dict with {'current_object', 'current_day', 'current_move_points'} for a given hero
        """
        
        # 1. Prepare all required info for simulation
        max_move_points = self.hero_mp_map.get(hero_id, 0)
        target_object_data = self.obj_info_map.get(target_object)
        
        # Sanity check in case some improper data comes along (shouldn't happen if data is clean) 
        if not target_object_data:
            return {} 
        
        target_day_open = target_object_data['day_open']
        target_reward = target_object_data['reward']
        
        previous_object = current_state['current_object']
        required_travel_dist = self.get_distance(previous_object, target_object)

        # 2. Examine starting state of a transition
        if previous_object == 0:
            # Note that it is true only for this Heroes-themed data as any object is reachable by any hero in less than 1 day
            current_day = target_day_open
            current_move_points = max_move_points
        else:
            # Get info from current state (where the hero left off)
            current_day = current_state['current_day']
            current_move_points = current_state['current_move_points']
            
        # 3. Based on move point diff find out arrival day and move points (on arrival)
        diff_move_points = current_move_points - required_travel_dist
        
        if diff_move_points >= 0:
            # Common case with current day arrival 
            day_arrive = current_day
            move_points_arrive = diff_move_points
        else:
            # Case for carry-over of move points to next day
            day_arrive = current_day + 1
            move_points_arrive = max_move_points + diff_move_points

        # Prepare default values for if-then ssituation handling
        day_leave = day_arrive
        move_points_leave = 0
        move_points_burned = 0
        is_earlier = False
        is_late = False
            
        # 4. Simulate logic of object visits w.r.t. days (TW) and visit (service) cost
        days_diff = day_arrive - target_day_open
        
        if days_diff < 0:
            # Case: early arrival
            is_earlier = True
            day_leave = target_day_open
            
            # Move point burning logic
            total_wasted_days = -days_diff - 1
            move_points_burned = move_points_arrive + (max_move_points * total_wasted_days)
            
            # Hero waited, had move points replenished, and then charged a visit cost
            move_points_leave = max_move_points - VISIT_COST
            
        elif days_diff == 0:
            # Case: on-time arrival
            if move_points_arrive >= VISIT_COST:
                # Had enough move points for visit, spent them and moved on
                move_points_leave = move_points_arrive - VISIT_COST
            else:
                # Case: Last-Move Rule (on-time), pay remainder of move points, ends with 0
                move_points_leave = 0

        else:
            # Case: late arrival
            is_late = True
            if move_points_arrive >= VISIT_COST:
                # Had enough move points, however missed the date (and gold)
                move_points_leave = move_points_arrive - VISIT_COST
            else:
                # Case: Last-Move Rule (late arrival)
                move_points_leave = 0
        
        # 5. Track expected reward for visit of target object
        received_reward = 0 if is_late else target_reward
        
        return {
            'hero_id': hero_id, 
            'object_id_from': previous_object,
            'object_id_to': target_object,
            'day_start': current_day,
            'day_arrive': day_arrive,
            'day_leave': day_leave,
            'move_points_start': current_move_points,
            'move_points_arrive': move_points_arrive,
            'move_points_burned': move_points_burned,
            'move_points_leave': move_points_leave,
            'is_earlier': is_earlier,
            'is_late': is_late,
            'reward': received_reward
        }

    def hero_journey(self, hero_id: int, object_ids: list) -> list:
        """
        Iteratively simulate full journey of a hero across each object transition
        Note that object_ids input is a list, almost CVRPlib-style notation
        """

        # Init state of play which will be iterated upon
        current_state = {'current_object': 0, 
                         'current_day': 1, 
                         'current_move_points': self.hero_mp_map.get(hero_id, 0)}
        
        journey_rows = []
        
        for target_object in object_ids:
            # Process current transition 
            current_transit = self.simulate_hero_movement(hero_id, current_state, target_object)
            
            if current_transit:
                journey_rows.append(current_transit)
                                
                # Update state for next hero iteration step
                current_state = {'current_object': current_transit['object_id_to'], 
                                 'current_day': current_transit['day_leave'], 
                                 'current_move_points': current_transit['move_points_leave']}
                
        return journey_rows

    def expand_solution(self, submit: pl.DataFrame, remove_out_of_time = False) -> pl.DataFrame:
        """
        Expand schedule solution iteratively over each hero route
        Main function for hero routing solution evaluation 
        """

        # Sanity check
        if len(submit) == 0:
            return pl.DataFrame()

        # Group by hero_id to get each heroe's routes in CVRPlib-style format with lists of object locations
        # Collapse hero's object_id rows into a list and sort by hero_id (for convenience as of our legend)
        hero_list_routes = submit.group_by('hero_id').agg(pl.col('object_id').alias('route')).sort('hero_id')
        
        expanded_routes = []
        
        # Iterate over each hero's route
        for row in hero_list_routes.iter_rows(named=True):
            # Get our hero and his object route (as list of object_id)
            current_hero = row['hero_id']
            current_route = row['route']
            
            # Play heroes, simulate this hero route with all our Heroes-themed VRPTW logic
            current_journey = self.hero_journey(current_hero, current_route)

            # Collect expanded route with all resulting info
            expanded_routes.extend(current_journey)
            
        # Collect expanded results and arrange them in a readable manner
        expanded_submit = pl.DataFrame(expanded_routes)
        
        if len(expanded_submit) > 0:
            cols = ['hero_id', 'object_id_from', 'object_id_to', 'day_start', 'day_arrive', 
                    'day_leave', 'move_points_start', 'move_points_arrive', 'move_points_burned', 
                    'move_points_leave', 'is_earlier', 'is_late', 'reward']
            expanded_submit = expanded_submit.select(cols)

        # Special option to remove objects outside our gameplay week
        if remove_out_of_time:
            expanded_submit = expanded_submit.filter(pl.col('day_arrive') <= 7)
            
        return expanded_submit

    def basic_check(self, submit: pl.DataFrame) -> pl.DataFrame:
        """
        Validate schedule (submit candidate) DataFrame with basic sanity checks 
        """

        # Basic sanity checks for erroneous or empty solutions
        if submit is None or len(submit) == 0:
            return pl.DataFrame()
        if 'hero_id' not in submit.columns or 'object_id' not in submit.columns:
            raise ValueError("Schedule solution must include both 'hero_id' and 'object_id' columns")

        # Polars has a mind of its own so we should explicitly conserve original row order
        submit = submit.with_row_index("og_order")
        
        # Explicit type checks and filtering 
        # No out-of-bounds ids are allowed and therefore must be cleaned off
        clean_submit = submit.select(['og_order', 'hero_id', 'object_id']).with_columns([
            pl.col('hero_id').cast(pl.Int32),
            pl.col('object_id').cast(pl.Int32)
        ]).filter(
            (pl.col('hero_id') >= 1) & (pl.col('hero_id') <= 100) &
            (pl.col('object_id') >= 1) & (pl.col('object_id') <= 700)
        )
        
        # As promised, sanity check to remove duplicates (keep only first entry in case one chooses to cheat)
        clean_submit = clean_submit.unique(subset=['object_id'], keep='first').sort('og_order')

        # After restoring original order, clean up after ourselves
        clean_submit = clean_submit.drop('og_order')
        
        return clean_submit

    def evaluate_solution(self, submit: pl.DataFrame) -> int:
        """
        Run the full evaluation pipeline to produce a Gold Score
        """

        # Check proposed solution, clean up bad entries
        checked_submit = self.basic_check(submit)
        if len(checked_submit) == 0:
            return 0
        
        # Create a thorough simulated schedule overview across days and move points
        detailed_submit = self.expand_solution(checked_submit)
        if len(detailed_submit) == 0:
            return 0
        
        # Calculate Gold Score: total reward - total hero costs
        total_reward = detailed_submit['reward'].sum()
        max_id = detailed_submit['hero_id'].max()
        
        return int(total_reward - (max_id * HERO_COST))