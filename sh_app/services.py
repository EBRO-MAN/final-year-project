from django.core.exceptions import ValidationError
# from .models import Sheep, BreedingCycle, SheepPedigree
from .models import Sheep, BreedingCycle
import logging

logger = logging.getLogger(__name__)

def check_breed_compatibility(ram, ewe):
    """
    Checks if a ram and ewe are compatible based on breed.
    """
    # Define allowed pairings: (RAM_BREED, EWE_BREED)
    ALLOWED_PAIRINGS = {
        # Existing pairings
        ('PD', 'PD'), ('PD', 'PA'), ('PD', 'LOCAL'), 
        ('PA', 'PA'), ('PA', 'LOCAL'), 
        ('LOCAL', 'LOCAL'),
        
        # --- FIX 1: Explicitly Allow AC Ram Pairings ---
        ('AC', 'AC'), 
        ('AC', 'PA'), 
        ('AC', 'LOCAL'),
        ('AC', 'PD'), # Add if AC-PD is allowed
        # -----------------------------------------------
    }
    
    ram_breed = ram.breed.upper()
    ewe_breed = ewe.breed.upper()
    
    if (ram_breed, ewe_breed) in ALLOWED_PAIRINGS:
        return True
    
    return False

def check_for_inbreeding(ewe, ram):
    """
    Checks if the ewe and ram are closely related.
    Returns True if safe, False if inbreeding detected.
    """
    try:
        # Get or Create Pedigrees (Safety check)
        ewe_pedigree = getattr(ewe, 'pedigree', None)
        ram_pedigree = getattr(ram, 'pedigree', None)

        if not ewe_pedigree or not ram_pedigree:
            # If pedigree data is missing, we assume safe but log warning
            return True

        # Check Parents (1st Generation)
        if ewe_pedigree.sire == ram or ewe_pedigree.dam == ram:
            return False
        if ram_pedigree.sire == ewe or ram_pedigree.dam == ewe:
            return False
            
        # Check Siblings (Share same parents)
        if (ewe_pedigree.sire and ewe_pedigree.sire == ram_pedigree.sire) or \
           (ewe_pedigree.dam and ewe_pedigree.dam == ram_pedigree.dam):
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Inbreeding check error: {e}")
        return True # Fail open (allow) or closed (deny) depending on preference

def check_ram_capacity(ram):
    """
    Checks if the ram has reached its maximum breeding capacity.
    """
    # Define capacities
    if ram.breed.upper() == 'PD':
        capacity = 55
    else:
        # Default for PA, LOCAL, AC, etc.
        capacity = 40 

    # Count active assignments
    active_assignments_count = BreedingCycle.objects.filter(
        ram=ram,
        status__in=['PLANNED', 'IN_PROGRESS']
    ).count()

    return active_assignments_count < capacity

def get_compatible_ewes(ram):
    """Get all ewes compatible with a specific ram"""
    
    # --- FIX 3: Ensure Ewes are in 'FLASHING' state ---
    ewes = Sheep.objects.filter(
        sex='FEMALE',
        type__in=['EWE', 'GIMMER'], # Adjust types as needed
        is_healthy=True,
        state='FLASHING' # <--- CRITICAL for breeding logic
    )
    # --------------------------------------------------

    compatible_ewes = []
    for ewe in ewes:
        try:
            # 1. Breed Check
            if not check_breed_compatibility(ram, ewe):
                continue
            
            # 2. Inbreeding Check
            # --- FIX 2: Actually utilize the return value ---
            if not check_for_inbreeding(ewe, ram):
                continue
            # ------------------------------------------------
            
            # 3. Capacity Check (Optional here, usually checked before loop)
            if check_ram_capacity(ram):
                compatible_ewes.append(ewe)
                
        except ValidationError:
            continue
    
    return compatible_ewes

def get_ram_capacity_info(ram):
    """
    Helper to return capacity details for the frontend
    """
    if ram.breed.upper() == 'PD':
        max_cap = 55
    else:
        max_cap = 40
        
    current = BreedingCycle.objects.filter(
        ram=ram,
        status__in=['PLANNED', 'IN_PROGRESS']
    ).count()
    
    return {
        'max': max_cap,
        'current': current,
        'remaining': max_cap - current
    }

def distribute_ewes_by_priority(rams, compatible_ewes_list):
    """
    Distributes a list of unique ewes to rams based on priority/capacity.
    """
    assignments = {ram.ear_tag_number: [] for ram in rams}
    
    # Sort rams by priority if needed (e.g. PD first)
    # rams.sort(key=lambda r: r.breed == 'PD', reverse=True)

    for ewe in compatible_ewes_list:
        assigned = False
        for ram in rams:
            # Double check compatibility for this specific pair
            if check_breed_compatibility(ram, ewe) and \
               check_for_inbreeding(ewe, ram) and \
               check_ram_capacity(ram):
                
                # Check if Ram has room in this specific distribution batch
                current_batch_count = len(assignments[ram.ear_tag_number])
                info = get_ram_capacity_info(ram)
                
                if (info['current'] + current_batch_count) < info['max']:
                    assignments[ram.ear_tag_number].append(ewe)
                    assigned = True
                    break
        
        if not assigned:
            # Ewe remains unassigned
            pass

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