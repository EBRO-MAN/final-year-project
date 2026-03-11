from django.core.exceptions import ValidationError
from datetime import datetime
from django.db.models import Q
from .models import Sheep, BreedingCycle


from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def get_available_ewes():
    """Get all healthy ewes available for breeding"""
    return Sheep.objects.filter(
        sex='FEMALE',
        is_healthy=True,
        type__in=['EWE'],
        # state='FLASHING'
    ).select_related('parent_ewe', 'parent_ram')


from django.db.models import Q
from django.core.exceptions import ValidationError
from datetime import date

def get_available_rams():
    """Get all healthy rams available for breeding, sorted by breed priority"""
    rams = Sheep.objects.filter(
        sex='MALE',
        type__in=['RAM'],
        is_healthy=True
    ).select_related('parent_ewe', 'parent_ram')
    
    # Sort by breed priority: PD > PA > LOCAL > AC > DC
    breed_priority = {'PD': 0, 'PA': 1, 'LOCAL': 2, 'AC': 3, 'DC': 4}
    return sorted(rams, key=lambda ram: breed_priority.get(ram.breed, 5))



def get_compatible_ewes(ram):
    """Get all ewes compatible with a specific ram considering inbreeding and capacity"""
    # ... existing query ...
    ewes = Sheep.objects.filter(
        sex='female',
        type__in=['ewe'],
        is_healthy=True,
        state='FLASHING' 
    )

    compatible_ewes = []
    for ewe in ewes:
        try:
            # 1. Check breed compatibility
            if not check_breed_compatibility(ram, ewe):
                continue
            
            # 2. FIX: Explicitly check if inbreeding returns False
            if not check_for_inbreeding(ewe, ram):
                continue
            
            # 3. Check ram capacity
            if check_ram_capacity(ram):
                compatible_ewes.append(ewe)
                
        except ValidationError:
            continue
    
    return compatible_ewes

def distribute_ewes_by_priority(rams, all_compatible_ewes):
    """
    Distribute ewes among rams with breed priority (PD > PA > LOCAL)
    and ensure no duplicate assignments
    """
    if not rams or not all_compatible_ewes:
        return {}
    
    # Sort rams by breed priority
    breed_priority = {'PD': 0, 'PA': 1, 'LOCAL': 2, 'AC': 3, 'DC': 4}
    sorted_rams = sorted(rams, key=lambda ram: breed_priority.get(ram.breed, 5))
    
    assignments = {}
    assigned_ewes = set()  # Track already assigned ewes to prevent duplicates
    
    # Initialize assignments
    for ram in sorted_rams:
        assignments[ram.ear_tag_number] = []
    
    # First pass: Assign ewes to PD rams
    for ram in sorted_rams:
        if ram.breed != 'PD':
            continue
            
        ram_capacity = get_ram_capacity_info(ram)['remaining']
        compatible_ewes = get_compatible_ewes(ram)
        
        for ewe in compatible_ewes:
            if ewe.ear_tag_number not in assigned_ewes and len(assignments[ram.ear_tag_number]) < ram_capacity:
                assignments[ram.ear_tag_number].append(ewe)
                assigned_ewes.add(ewe.ear_tag_number)
    
    # Second pass: Assign ewes to PA rams
    for ram in sorted_rams:
        if ram.breed != 'PA':
            continue
            
        ram_capacity = get_ram_capacity_info(ram)['remaining']
        compatible_ewes = get_compatible_ewes(ram)
        
        for ewe in compatible_ewes:
            if ewe.ear_tag_number not in assigned_ewes and len(assignments[ram.ear_tag_number]) < ram_capacity:
                assignments[ram.ear_tag_number].append(ewe)
                assigned_ewes.add(ewe.ear_tag_number)
    
    # Third pass: Assign ewes to LOCAL rams
    for ram in sorted_rams:
        if ram.breed != 'LOCAL':
            continue
            
        ram_capacity = get_ram_capacity_info(ram)['remaining']
        compatible_ewes = get_compatible_ewes(ram)
        
        for ewe in compatible_ewes:
            if ewe.ear_tag_number not in assigned_ewes and len(assignments[ram.ear_tag_number]) < ram_capacity:
                assignments[ram.ear_tag_number].append(ewe)
                assigned_ewes.add(ewe.ear_tag_number)
    
    return assignments



def get_available_lambs():
    """Get all healthy lambs available for breeding"""
    return Sheep.objects.filter(
        
        type__in=["LAMB"]
    ).select_related('parent_ewe', 'parent_ram')

def get_available_gimmers():
    """Get all healthy gimmers available for breeding"""
    return Sheep.objects.filter(
        
        type__in=["GIMMER"]
    ).select_related('parent_ewe', 'parent_ram')

def get_available_young_rams():
    """Get all healthy young rams available for breeding"""
    return Sheep.objects.filter(
        
        type__in=["YOUNG_RAM"]
    ).select_related('parent_ewe', 'parent_ram')

def check_breed_compatibility(ram, ewe):
    """
    Check if ram and ewe breeds are compatible based on registration rules
    Returns True if compatible, False if not
    """

    # Define allowed pairings: (RAM_BREED, EWE_BREED)
    ALLOWED_PAIRINGS = {
        ('PD', 'PD'), ('PD', 'DC'), ('PD', 'LOCAL'), 
        ('PA', 'PA'), ('PA', 'AC'),('PA', 'LOCAL'), 
        ('LOCAL', 'LOCAL'), 
        # --- NEW: Add AC Ram pairings to LOCAL, PA, and AC Ewes ---
        ('AC', 'LOCAL'), 
        ('AC', 'PA'),
        ('AC', 'AC'),
        # --- (Add other specific pairings you need here) ---
        ('DC', 'LOCAL'), 
        ('DC', 'PD'),
        ('DC', 'DC'),
        # Example for DC:
        # ('DC', 'AC'), ('DC', 'PD'), ...
    }

    ram_breed = ram.breed.upper()
    ewe_breed = ewe.breed.upper()
    
    if (ram_breed, ewe_breed) in ALLOWED_PAIRINGS:
        return True
    
    # logger.warning(f"Compatibility failed: Ram {ram.ear_tag_number} ({ram_breed}) x Ewe {ewe.ear_tag_number} ({ewe_breed}) is not in ALLOWED_PAIRINGS.")
    # return False
    
    # Optionally, raise an error or return a message for incompatibility
    # raise ValidationError(f"Incompatible breeds: {ram_breed} x {ewe_breed}")
    # return False

    # Breed compatibility rules from SSD section 3.1
    # RAM restrictions (what ewes they can mate with)
    ram_restrictions = {
        'PA': ['LOCAL', 'PA', 'AC'],    # PA rams can mate with LOCAL, PA, AC ewes
        'PD': ['LOCAL', 'PD', 'DC'],    # PD rams can mate with LOCAL, PD, DC ewes  
        'LOCAL': ['LOCAL'],             # LOCAL rams can only mate with LOCAL ewes
        'AC': ['PA'],                   # AC rams follow PA rules
        'DC': ['PD']                    # DC rams follow PD rules
    }
    
    # EWE restrictions (what rams they can mate with)
    ewe_restrictions = {
        'AC': ['PA'],                   # AC ewes can only mate with PA rams
        'DC': ['PD'],                   # DC ewes can only mate with PD rams
        # LOCAL, PA, PD ewes have no restrictions on which rams they can mate with
        # Their compatibility is determined by the ram's restrictions
    }
    
    # Check ram restrictions
    if ram_breed in ram_restrictions:
        allowed_ewe_breeds = ram_restrictions[ram_breed]
        if ewe_breed not in allowed_ewe_breeds:
            return False
    
    # Check ewe restrictions (only for breeds that have specific requirements)
    if ewe_breed in ewe_restrictions:
        allowed_ram_breeds = ewe_restrictions[ewe_breed]
        if ram_breed not in allowed_ram_breeds:
            return False
    
    return True

def predict_lamb_breed(ewe, ram):
    """
    Predict lamb breed and breed level based on parent combinations
    Returns: (breed, blood_level) or (None, None) for manual input
    """
    ewe_breed = ewe.breed
    ram_breed = ram.breed
    ewe_level = ewe.blood_level
    ram_level = ram.blood_level
    
    # Breed prediction rules from SSD section 3.1
    breed_prediction_rules = {
        ('LOCAL', 'LOCAL'): ('LOCAL', 100.0),
        ('PA', 'LOCAL'): ('AC', 50.0),
        ('PD', 'LOCAL'): ('DC', 50.0),
        ('AC', 'PA'): ('AC', (ewe_level + ram_level) / 2),
        ('DC', 'PD'): ('DC', (ewe_level + ram_level) / 2),
        ('PA', 'PA'): ('PA', 100.0),
        ('PD', 'PD'): ('PD', 100.0),
    }
    
    # Try both orderings since rules might be directional
    if (ewe_breed, ram_breed) in breed_prediction_rules:
        return breed_prediction_rules[(ewe_breed, ram_breed)]
    elif (ram_breed, ewe_breed) in breed_prediction_rules:
        return breed_prediction_rules[(ram_breed, ewe_breed)]
    
    return None, None  # Manual input required



def get_breed_restrictions(ram):
    """
    Get the breed restrictions for a specific ram
    Returns a list of allowed ewe breeds
    """
    breed_restrictions = {
        'PA': ['LOCAL', 'PA', 'AC'],
        'PD': ['LOCAL', 'PD', 'DC'], 
        'LOCAL': ['LOCAL'],
        'AC': ['PA'],  # AC rams follow PA rules
        'DC': ['PD']   # DC rams follow PD rules
    }
    
    return breed_restrictions.get(ram.breed, [])

def get_breed_compatibility_info(ram):
    """
    Get detailed breed compatibility information for display
    """
    restrictions = get_breed_restrictions(ram)
    
    compatibility_info = {
        'ram_breed': ram.breed,
        'allowed_ewe_breeds': restrictions,
        'restriction_description': get_restriction_description(ram.breed),
        'example_pairings': get_example_pairings(ram.breed)
    }
    
    return compatibility_info

def get_restriction_description(ram_breed):
    """
    Get a human-readable description of breed restrictions
    """
    descriptions = {
        'PA': "PA rams can breed with Local, PA, and AC ewes to produce AC lambs (50%) or PA lambs (100%)",
        'PD': "PD rams can breed with Local, PD, and DC ewes to produce DC lambs (50%) or PD lambs (100%)",
        'LOCAL': "Local rams can only breed with Local ewes to produce Local lambs (100%)",
        'AC': "AC rams follow the same rules as PA rams",
        'DC': "DC rams follow the same rules as PD rams"
    }
    
    return descriptions.get(ram_breed, "No specific breed restrictions")

def get_example_pairings(ram_breed):
    """
    Get example breed pairings and their outcomes
    """
    examples = {
        'PA': [
            {'ewe': 'LOCAL', 'lamb': 'AC', 'level': '50%'},
            {'ewe': 'PA', 'lamb': 'PA', 'level': '100%'},
            {'ewe': 'AC', 'lamb': 'AC', 'level': 'Average of parents'}
        ],
        'PD': [
            {'ewe': 'LOCAL', 'lamb': 'DC', 'level': '50%'},
            {'ewe': 'PD', 'lamb': 'PD', 'level': '100%'},
            {'ewe': 'DC', 'lamb': 'DC', 'level': 'Average of parents'}
        ],
        'LOCAL': [
            {'ewe': 'LOCAL', 'lamb': 'LOCAL', 'level': '100%'}
        ],
       
    }
    
    return examples.get(ram_breed, [])

# ... (keep all the existing family relationship functions the same)
def get_all_siblings(sheep, include_half_siblings=True):
    """Get all siblings (full and half) of a sheep"""
    if not sheep:
        return Sheep.objects.none()
    
    siblings = Sheep.objects.none()
    
    # Full siblings (same both parents)
    if sheep.parent_ewe and sheep.parent_ram:
        siblings = Sheep.objects.filter(
            parent_ewe=sheep.parent_ewe,
            parent_ram=sheep.parent_ram
        ).exclude(ear_tag_number=sheep.ear_tag_number)
    
    if include_half_siblings:
        # Half-siblings (same mother, different father)
        if sheep.parent_ewe:
            half_sibs_mother = Sheep.objects.filter(
                parent_ewe=sheep.parent_ewe
            ).exclude(
                Q(parent_ram=sheep.parent_ram) | Q(ear_tag_number=sheep.ear_tag_number)
            )
            siblings = siblings.union(half_sibs_mother)
        
        # Half-siblings (same father, different mother)
        if sheep.parent_ram:
            half_sibs_father = Sheep.objects.filter(
                parent_ram=sheep.parent_ram
            ).exclude(
                Q(parent_ewe=sheep.parent_ewe) | Q(ear_tag_number=sheep.ear_tag_number)
            )
            siblings = siblings.union(half_sibs_father)
    
    return siblings

def get_nieces_and_nephews(sheep):
    """Get all nieces and nephews of a sheep (children of siblings)"""
    nieces_nephews = Sheep.objects.none()
    siblings = get_all_siblings(sheep, include_half_siblings=True)
    
    for sibling in siblings:
        # Get all children of each sibling
        children = Sheep.objects.filter(
            Q(parent_ewe=sibling) | Q(parent_ram=sibling)
        )
        nieces_nephews = nieces_nephews.union(children)
    
    return nieces_nephews

def get_uncles_and_aunts(sheep):
    """Get all uncles and aunts of a sheep (siblings of parents)"""
    uncles_aunts = Sheep.objects.none()
    
    # Mother's siblings
    if sheep.parent_ewe:
        mother_siblings = get_all_siblings(sheep.parent_ewe, include_half_siblings=True)
        uncles_aunts = uncles_aunts.union(mother_siblings)
    
    # Father's siblings
    if sheep.parent_ram:
        father_siblings = get_all_siblings(sheep.parent_ram, include_half_siblings=True)
        uncles_aunts = uncles_aunts.union(father_siblings)
    
    return uncles_aunts

def check_for_inbreeding(ewe, ram):
    """
    Comprehensive inbreeding prevention check
    Returns True if breeding is allowed, False if prohibited
    """
    # Direct parent-child relationships
    if ram == ewe.parent_ram:
        return False  # Father-daughter
    if ewe == ram.parent_ewe:
        return False  # Mother-son
    
    # Full siblings (same both parents)
    if (ewe.parent_ewe and ram.parent_ewe and 
        ewe.parent_ewe == ram.parent_ewe and 
        ewe.parent_ram == ram.parent_ram):
        return False
    
    # Half-siblings (same father, different mother)
    if (ewe.parent_ram and ram.parent_ram and 
        ewe.parent_ram == ram.parent_ram and 
        ewe.parent_ewe != ram.parent_ewe):
        return False
    
    # Half-siblings (same mother, different father)
    if (ewe.parent_ewe and ram.parent_ewe and 
        ewe.parent_ewe == ram.parent_ewe and 
        ewe.parent_ram != ram.parent_ram):
        return False
    
    # Uncle/niece relationships
    ewe_uncles_aunts = get_uncles_and_aunts(ewe)
    if ram in ewe_uncles_aunts:
        return False
    
    # Aunt/nephew relationships
    ram_uncles_aunts = get_uncles_and_aunts(ram)
    if ewe in ram_uncles_aunts:
        return False
    
    # Grandparent relationships
    grandparents = set()
    if ewe.parent_ewe:
        grandparents.add(ewe.parent_ewe.parent_ewe)
        grandparents.add(ewe.parent_ewe.parent_ram)
    if ewe.parent_ram:
        grandparents.add(ewe.parent_ram.parent_ewe)
        grandparents.add(ewe.parent_ram.parent_ram)
    grandparents = {gp for gp in grandparents if gp}
    if ram in grandparents:
        return False
    
    # Ram's grandparents
    ram_grandparents = set()
    if ram.parent_ewe:
        ram_grandparents.add(ram.parent_ewe.parent_ewe)
        ram_grandparents.add(ram.parent_ewe.parent_ram)
    if ram.parent_ram:
        ram_grandparents.add(ram.parent_ram.parent_ewe)
        ram_grandparents.add(ram.parent_ram.parent_ram)
    ram_grandparents = {gp for gp in ram_grandparents if gp}
    if ewe in ram_grandparents:
        return False
    
    # First cousins
    if are_first_cousins(ewe, ram):
        return False
    
    # Niece/nephew relationships
    ram_nieces_nephews = get_nieces_and_nephews(ram)
    if ewe in ram_nieces_nephews:
        return False
    
    ewe_nieces_nephews = get_nieces_and_nephews(ewe)
    if ram in ewe_nieces_nephews:
        return False
    
    return True  # No inbreeding detected

def are_first_cousins(ewe, ram):
    """Check if two sheep are first cousins"""
    ewe_grandparents = set()
    ram_grandparents = set()
    
    # Ewe's grandparents
    if ewe.parent_ewe:
        ewe_grandparents.add(ewe.parent_ewe.parent_ewe)
        ewe_grandparents.add(ewe.parent_ewe.parent_ram)
    if ewe.parent_ram:
        ewe_grandparents.add(ewe.parent_ram.parent_ewe)
        ewe_grandparents.add(ewe.parent_ram.parent_ram)
    
    # Ram's grandparents
    if ram.parent_ewe:
        ram_grandparents.add(ram.parent_ewe.parent_ewe)
        ram_grandparents.add(ram.parent_ewe.parent_ram)
    if ram.parent_ram:
        ram_grandparents.add(ram.parent_ram.parent_ewe)
        ram_grandparents.add(ram.parent_ram.parent_ram)
    
    # Remove None values
    ewe_grandparents = {gp for gp in ewe_grandparents if gp}
    ram_grandparents = {gp for gp in ram_grandparents if gp}
    
    # If they share any grandparents, they are cousins
    return bool(ewe_grandparents.intersection(ram_grandparents))

def get_family_relationship(ewe, ram):
    """Helper function to determine the specific family relationship"""
    relationships = []
    
    # Direct parent-child
    if ram == ewe.parent_ram:
        relationships.append("Father-Daughter")
    if ewe == ram.parent_ewe:
        relationships.append("Mother-Son")
    
    # Siblings
    if (ewe.parent_ewe and ram.parent_ewe and 
        ewe.parent_ewe == ram.parent_ewe and 
        ewe.parent_ram == ram.parent_ram):
        relationships.append("Full Siblings")
    
    # Half-siblings
    if (ewe.parent_ram and ram.parent_ram and 
        ewe.parent_ram == ram.parent_ram and 
        ewe.parent_ewe != ram.parent_ewe):
        relationships.append("Half-Siblings (Same Father)")
    
    if (ewe.parent_ewe and ram.parent_ewe and 
        ewe.parent_ewe == ram.parent_ewe and 
        ewe.parent_ram != ram.parent_ram):
        relationships.append("Half-Siblings (Same Mother)")
    
    # Uncle/niece
    ewe_uncles_aunts = get_uncles_and_aunts(ewe)
    if ram in ewe_uncles_aunts:
        relationships.append("Uncle-Niece")
    
    # Aunt/nephew
    ram_uncles_aunts = get_uncles_and_aunts(ram)
    if ewe in ram_uncles_aunts:
        relationships.append("Aunt-Nephew")
    
    # Grandparent
    grandparents = set()
    if ewe.parent_ewe:
        grandparents.add(ewe.parent_ewe.parent_ewe)
        grandparents.add(ewe.parent_ewe.parent_ram)
    if ewe.parent_ram:
        grandparents.add(ewe.parent_ram.parent_ewe)
        grandparents.add(ewe.parent_ram.parent_ram)
    grandparents = {gp for gp in grandparents if gp}
    if ram in grandparents:
        relationships.append("Grandparent-Grandchild")
    
    # Niece/nephew
    ram_nieces_nephews = get_nieces_and_nephews(ram)
    if ewe in ram_nieces_nephews:
        relationships.append("Niece")
    
    ewe_nieces_nephews = get_nieces_and_nephews(ewe)
    if ram in ewe_nieces_nephews:
        relationships.append("Nephew")
    
    # First cousins
    if are_first_cousins(ewe, ram):
        relationships.append("First Cousins")
    
    return relationships if relationships else ["No close relationship detected"]



def check_ram_capacity(ram):
    """
    Checks if the ram has reached its maximum breeding capacity.
    Capacity is based on breed (e.g., PD=55, others=40).
    """
    
    # Define capacities based on breed (Add AC if it's special, otherwise use default)
    if ram.breed.upper() == 'PD':
        capacity = 55
    # Assuming AC is treated like other standard breeds (not PD)
    # If AC has a different capacity, you must define it here.
    elif ram.breed.upper() in ['PA', 'LOCAL', 'AC', 'DC']: # Explicitly including AC
        capacity = 40
    else:
        # Default for any other breed
        capacity = 40 

    # Count the number of active assignments for this ram
    # Note: This counts assignments saved to the database (status='PLANNED' or 'IN_PROGRESS')
    # If the assignment is only in the session, this count might be too low.
    active_assignments_count = BreedingCycle.objects.filter(
        ram=ram,
        status__in=['PLANNED', 'IN_PROGRESS']
    ).count()

    # The ram is AVAILABLE if the current count is less than the capacity
    if active_assignments_count < capacity:
        return True
    else:
        # Optionally log that the ram is at capacity
        logger.info(f"Ram {ram.ear_tag_number} ({ram.breed}) is at capacity ({active_assignments_count}/{capacity}).")
        return False

def get_ram_capacity_info(ram, breeding_season=None):
    """Get current capacity usage for a ram"""
    from .models import BreedingCycle
    
    # Use current year if no breeding_season provided
    if breeding_season is None:
        breeding_season = date.today()
    
    CAPACITY_RULES = {
        'PD': 55,
        'PA': 40,
        'LOCAL': 40,
        'AC': 40,
        'DC': 40,
    }
    
    current_cycles = BreedingCycle.objects.filter(
        ram=ram,
        start_date__year=breeding_season.year,
        status__in=['planned', 'in_progress']
    ).count()
    
    capacity = CAPACITY_RULES.get(ram.breed, 0)
    return {
        'current': current_cycles,
        'max': capacity,
        'remaining': capacity - current_cycles
    }


def create_lambs_from_cycle(breeding_cycle, lamb_count=1, lamb_sexes=None):
    """
    Automatically create lamb records from a breeding cycle
    lamb_sexes: List of sexes for each lamb (e.g., ['MALE', 'FEMALE'])
    """
    from .models import Sheep, AuditLog
    
    if not breeding_cycle.actual_birth_date:
        raise ValueError("Cannot create lambs without actual birth date")
    
    if lamb_sexes is None:
        lamb_sexes = ['UNKNOWN'] * lamb_count
    
    lambs = []
    with transaction.atomic():
        for i, sex in enumerate(lamb_sexes):
            lamb_breed, lamb_level = predict_lamb_breed(breeding_cycle.ewe, breeding_cycle.ram)
            
            lamb = Sheep.objects.create(
                ear_tag_number=f"LAMB_{breeding_cycle.cycle_id}_{i+1}",
                breed=lamb_breed,
                blood_level=lamb_level,
                sex=sex,
                type='LAMB',
                date_of_birth=breeding_cycle.actual_birth_date,
                parent_ewe=breeding_cycle.ewe,
                parent_ram=breeding_cycle.ram,
                is_healthy=True
            )
            lambs.append(lamb)
            
            # Log creation
            AuditLog.objects.create(
                user_id='SYSTEM',
                action='AUTO_CREATE_LAMB',
                entity='Sheep',
                entity_id=lamb.ear_tag_number,
                new_values={
                    'ear_tag_number': lamb.ear_tag_number,
                    'breed': lamb.breed,
                    'blood_level': lamb.blood_level,
                    'parent_ewe': breeding_cycle.ewe.ear_tag_number,
                    'parent_ram': breeding_cycle.ram.ear_tag_number
                },
                notes=f"Automatically created from breeding cycle {breeding_cycle.cycle_id}"
            )
    
    return lambs

def update_cycle_statuses():
    """
    Batch update breeding cycle statuses based on current dates
    """
    today = date.today()
    updated_count = 0
    
    # Update PLANNED → IN_PROGRESS
    planned_to_update = BreedingCycle.objects.filter(
        status='PLANNED',
        start_date__lte=today
    )
    
    for cycle in planned_to_update:
        cycle.status = 'IN_PROGRESS'
        cycle.save()
        updated_count += 1
    
    return updated_count

def get_upcoming_births(days=30):
    """
    Get breeding cycles with expected births in the next specified days
    """
    today = date.today()
    end_date = today + timedelta(days=days)
    end_date1 = today + timedelta(days=51)  # Example breeding period
    
    return BreedingCycle.objects.filter(
        status='IN_PROGRESS',
        expected_birth_date__range=[today, end_date],
        expected_birth_end__range=[end_date1, timedelta(days=155)]
    ).select_related('ewe', 'ram').order_by('expected_birth_date')

def check_ram_utilization():
    """
    Check ram capacity utilization and return warnings for over-utilized rams
    """
    rams = Sheep.objects.filter(sex='MALE', type__in=['RAM', 'YOUNG_RAM'])
    warnings = []
    
    for ram in rams:
        active_cycles = BreedingCycle.objects.filter(
            ram=ram,
            status__in=['PLANNED', 'IN_PROGRESS']
        ).count()
        
        capacity = 55 if ram.breed == 'PD' else 40
        
        if active_cycles >= capacity:
            warnings.append({
                'ram': ram,
                'active_cycles': active_cycles,
                'capacity': capacity,
                'message': f"Ram {ram.ear_tag_number} at or over capacity ({active_cycles}/{capacity})"
            })
        elif active_cycles >= capacity * 0.8:  # 80% threshold warning
            warnings.append({
                'ram': ram,
                'active_cycles': active_cycles,
                'capacity': capacity,
                'message': f"Ram {ram.ear_tag_number} approaching capacity ({active_cycles}/{capacity})"
            })
    
    return warnings

def generate_breeding_season_report(season_year):
    """
    Generate comprehensive breeding season report
    """
    from django.db.models import Count, Avg, Q
    
    cycles = BreedingCycle.objects.filter(
        start_date__year=season_year
    ).select_related('ewe', 'ram')
    
    # Basic statistics
    total_cycles = cycles.count()
    completed_cycles = cycles.filter(status='COMPLETED').count()
    cancelled_cycles = cycles.filter(status='CANCELLED').count()
    
    # Success rate
    success_rate = (completed_cycles / total_cycles * 100) if total_cycles > 0 else 0
    
    # Average gestation period
    completed_with_births = cycles.filter(
        status='COMPLETED',
        actual_birth_date__isnull=False
    )
    
    gestation_periods = [
        (cycle.actual_birth_date - cycle.start_date).days
        for cycle in completed_with_births
    ]
    avg_gestation = sum(gestation_periods) / len(gestation_periods) if gestation_periods else 0
    
    # Ram performance
    ram_performance = cycles.filter(status='COMPLETED').values(
        'ram__ear_tag_number', 'ram__breed'
    ).annotate(
        total_cycles=Count('cycle_id'),
        success_rate=Count('cycle_id', filter=Q(status='COMPLETED')) * 100.0 / Count('cycle_id')
    )
    
    # Breed distribution
    breed_distribution = cycles.filter(status='COMPLETED').values(
        'ewe__breed', 'ram__breed'
    ).annotate(count=Count('cycle_id'))
    
    report_data = {
        'season_year': season_year,
        'total_cycles': total_cycles,
        'completed_cycles': completed_cycles,
        'cancelled_cycles': cancelled_cycles,
        'success_rate': round(success_rate, 2),
        'average_gestation': round(avg_gestation, 2),
        'ram_performance': list(ram_performance),
        'breed_distribution': list(breed_distribution),
        'generated_at': timezone.now().isoformat()
    }
    
    return report_data


def get_ram_ewe_compatibility(ram):
    """
    Get detailed compatibility information for a ram
    """
    compatible_ewes = get_compatible_ewes(ram)
    
    return {
        'ram': ram,
        'compatible_ewes': compatible_ewes,
        'total_compatible': len(compatible_ewes)
    }