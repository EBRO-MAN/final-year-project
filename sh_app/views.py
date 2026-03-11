import csv
import io
import json
import logging
import datetime
from datetime import date, datetime, timedelta

from urllib import request

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    View, TemplateView, ListView, DetailView, CreateView, UpdateView
)

from .decorators import allowed_users
from .form import (
    CullingForm, MortalityForm, DistributionForm, SheepForm,
    CSVImportForm, AddRecordForm
)
from .models import (
    Sheep, BreedingCycle, AuditLog, User,
    CullingRecord, MortalityRecord, DistributionRecord
)
from .services1 import (
    get_available_rams, get_available_lambs, get_available_ewes,
    get_available_gimmers, get_available_young_rams, get_compatible_ewes,
    get_ram_capacity_info, get_family_relationship,
    distribute_ewes_by_priority, check_breed_compatibility,
    check_for_inbreeding, predict_lamb_breed,
    get_breed_compatibility_info
)

logger = logging.getLogger(__name__)

@login_required
@allowed_users(allowed_roles=['Breeder',])
def breeding_selection(request):
    """
    View to display eligible rams and ewes for manual selection.
    This view is the one mapped to the '/selection/' URL.
    """
    # Filter for sheep that are ready for selection (ACTIVE or FLASHING)
    eligible_rams = Sheep.objects.filter(
        sex='MALE', 
        type__in=['RAM', 'YOUNG_RAM'], 
        state__in=['ACTIVE', 'FLASHING', 'IDLE'] # Allow IDLE for display/flashing prep
    ).order_by('ear_tag_number')

    eligible_ewes = Sheep.objects.filter(
        sex='FEMALE', 
        type__in=['EWE', 'GIMMER'], 
        state__in=['ACTIVE', 'FLASHING', 'IDLE']
    ).order_by('ear_tag_number')
    
    # Note: all_rams/all_ewes are used for the bulk action modals (FLASHING)
    # They should include all relevant sheep regardless of current state
    all_rams = Sheep.objects.filter(sex='MALE', type__in=['RAM', 'YOUNG_RAM']).order_by('ear_tag_number')
    all_ewes = Sheep.objects.filter(sex='FEMALE', type__in=['EWE', 'GIMMER']).order_by('ear_tag_number')

    context = {
        'eligible_rams': eligible_rams,
        'eligible_ewes': eligible_ewes,
        'all_rams': all_rams,
        'all_ewes': all_ewes,
    }
    return render(request, 'breeding.html', context)


@login_required
@allowed_users(allowed_roles=['Breeder',])
@require_POST
def process_assignment(request):
    """
    Handles the submission from the final 'Process Final Assignment' button 
    on the breeding_selection page.

    This function saves the user's manual card selections (ram_selection, ewe_selection) 
    to the session and redirects to the detailed compatibility/assignment view.
    """
    # 1. Get selections from the POST data (from hidden checkboxes in breeding.html)
    selected_ram_tags = request.POST.getlist('ram_selection')
    selected_ewe_tags = request.POST.getlist('ewe_selection')

    if not selected_ram_tags:
        messages.error(request, "Please select at least one Ram to proceed.")
        return redirect('breeding_selection')

    if not selected_ewe_tags:
        messages.error(request, "Please select at least one Ewe to proceed.")
        return redirect('breeding_selection')

    # 2. Store the selected Ear Tag Numbers in the session 
    # This data will be used by the subsequent BreedingTaskView to run compatibility checks.
    request.session['selected_rams'] = selected_ram_tags
    request.session['selected_ewes'] = selected_ewe_tags 
    request.session.modified = True

    messages.info(request, f"Selection confirmed: {len(selected_ram_tags)} Rams and {len(selected_ewe_tags)} Ewes selected for assignment.")
    
    # 3. Redirect to the detailed assignment/task view
    return redirect('breeding_task')






@require_POST
def bulk_flash_rams(request):
    """
    Updates the state of selected Rams to 'FLASHING'.
    """
    # 1. Get list of selected IDs from the form
    selected_ids = request.POST.getlist('selected_rams')
    
    if not selected_ids:
        messages.warning(request, "No rams selected for flashing.")
        return redirect('breeding_selection') # Adjust redirect as needed

    try:
        # 2. Filter and Update
        # We ensure we only update Rams to be safe
        updated_count = Sheep.objects.filter(
            ear_tag_number__in=selected_ids, 
            sex='MALE'
        ).update(state='FLASHING')
        
        messages.success(request, f"Successfully set {updated_count} Rams to FLASHING state.")
        
    except Exception as e:
        messages.error(request, f"Error updating rams: {e}")

    return redirect('breeding_selection')


@require_POST
def bulk_flash_ewes(request):
    """
    Updates the state of selected Ewes to 'FLASHING'.
    """
    # 1. Get list of selected IDs from the form
    selected_ids = request.POST.getlist('selected_ewes')
    
    if not selected_ids:
        messages.warning(request, "No ewes selected for flashing.")
        return redirect('breeding_selection')

    try:
        # 2. Filter and Update
        updated_count = Sheep.objects.filter(
            ear_tag_number__in=selected_ids, 
            sex='FEMALE'
        ).update(state='FLASHING')
        
        messages.success(request, f"Successfully set {updated_count} Ewes to FLASHING state.")
        
    except Exception as e:
        messages.error(request, f"Error updating ewes: {e}")

    return redirect('breeding_selection')


    
def records_history(request):
    """
    Display historical records for Culling, Mortality, and Distribution.
    """
    # Fetch records ordered by newest first
    # select_related is used to fetch the linked Sheep data efficiently
    culling_records = CullingRecord.objects.select_related('sheep').order_by('-date_culled')
    mortality_records = MortalityRecord.objects.select_related('sheep').order_by('-date_of_death')
    distribution_records = DistributionRecord.objects.select_related('sheep').order_by('-distribution_date')

    context = {
        'culling_records': culling_records,
        'mortality_records': mortality_records,
        'distribution_records': distribution_records,
    }
    return render(request, 'records_history.html', context)

@login_required
@allowed_users(allowed_roles=['Admin', 'Breeder'])
def dashboard(request):
    """
    The main landing page with the action buttons.
    """
    # Initialize forms
    culling_form = CullingForm()
    mortality_form = MortalityForm()
    distribution_form = DistributionForm()

    context = {
        'culling_form': culling_form,
        'mortality_form': mortality_form,
        'distribution_form': distribution_form,
    }
    return render(request, 'dashboard.html', context)

@login_required
@allowed_users(allowed_roles=['Breeder',])
def add_record(request):
    """
    Page to add a single sheep manually or upload CSV.
    """
    if request.method == 'POST':
        form = SheepForm(request.POST)
        if form.is_valid():
            sheep = form.save(commit=False)
            # Set default state if needed
            if not sheep.state:
                sheep.state = 'AVAILABLE' 
            sheep.save()
            messages.success(request, f"Sheep {sheep.ear_tag_number} added successfully.")
            return redirect('add_record')
    else:
        form = SheepForm()

    return render(request, 'add_record.html', {'form': form})

# --- ACTION HANDLERS ---
@login_required
@allowed_users(allowed_roles=['Breeder',])
def register_culling(request):
    if request.method == 'POST':
        form = CullingForm(request.POST)
        if form.is_valid():
            ear_tag = form.cleaned_data['ear_tag']
            reason = form.cleaned_data['reason']
            
            try:
                sheep = Sheep.objects.get(ear_tag_number=ear_tag)
                
                # Update State
                sheep.state = 'In_Active'
                sheep.save()
                
                # Create Record
                CullingRecord.objects.create(sheep=sheep, reason=reason)
                
                messages.success(request, f"Culling registered for {ear_tag}.")
            except Sheep.DoesNotExist:
                messages.error(request, f"Sheep with tag {ear_tag} not found.")
                
    return redirect('dashboard')

@login_required
@allowed_users(allowed_roles=['Breeder',])
def register_mortality(request):
    if request.method == 'POST':
        form = MortalityForm(request.POST)
        if form.is_valid():
            ear_tag = form.cleaned_data['ear_tag']
            reason = form.cleaned_data['reason']
            
            try:
                sheep = Sheep.objects.get(ear_tag_number=ear_tag)
                
                # Update State
                sheep.state = 'In_Active'
                sheep.save()
                
                # Create Record
                MortalityRecord.objects.create(sheep=sheep, reason=reason)
                
                messages.warning(request, f"Mortality registered for {ear_tag}.")
            except Sheep.DoesNotExist:
                messages.error(request, f"Sheep with tag {ear_tag} not found.")
                
    return redirect('dashboard')

@login_required
@allowed_users(allowed_roles=['Breeder',])
def register_distribution(request):
    if request.method == 'POST':
        form = DistributionForm(request.POST)
        if form.is_valid():
            selected_rams = form.cleaned_data['selected_rams']
            count = 0
            
            for sheep in selected_rams:
                # Update State
                sheep.state = 'In_Active'
                sheep.save()
                
                # Create Record
                DistributionRecord.objects.create(sheep=sheep)
                count += 1
            
            messages.success(request, f"Successfully distributed {count} Young Rams.")
        else:
            messages.error(request, "Invalid selection.")
            
    return redirect('dashboard')


@login_required
@allowed_users(allowed_roles=['Breeder',])
def import_sheep_csv(request):
    """View for importing sheep data from CSV with robust handling"""
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            update_existing = form.cleaned_data['update_existing']
            
            try:
                # 1. Read and Normalize Line Endings (\r -> \n)
                # This fixes the "271120152.csv" crash
                data_set = csv_file.read().decode('UTF-8').replace('\r\n', '\n').replace('\r', '\n')
                io_string = io.StringIO(data_set)
                
                # 2. Use DictReader to map columns by name (Robust to order changes)
                reader = csv.DictReader(io_string)
                
                # Normalize headers: remove spaces, lower case, fix typos
                # e.g. "ear_tag number" -> "ear_tag_number", "Birth_weght" -> "birth_weight"
                field_map = {}
                for field in reader.fieldnames:
                    clean_field = field.strip().lower().replace(' ', '_').replace('__', '_')
                    # Fix specific typos found in your file
                    if 'weght' in clean_field: clean_field = 'birth_weight'
                    if 'note' in clean_field: clean_field = 'health_notes'
                    field_map[clean_field] = field

                success_count = 0
                error_count = 0
                errors = []
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Helper to safely get data using normalized names
                        def get_val(key):
                            col_name = field_map.get(key)
                            if col_name and row.get(col_name):
                                return row[col_name].strip()
                            return None

                        # 3. Extract Data
                        ear_tag = get_val('ear_tag_number') or get_val('ear_tag')
                        if not ear_tag:
                            raise ValueError("Missing Ear Tag")

                        breed = (get_val('breed') or '').upper()
                        
                        # Handle float parsing safely
                        try:
                            blood_lvl_str = get_val('blood_level')
                            blood_level = float(blood_lvl_str) if blood_lvl_str else 0.0
                        except ValueError:
                            blood_level = 0.0

                        sex = (get_val('sex') or '').upper()
                        sheep_type = (get_val('type') or '').upper()
                        
                        # Handle Dates (Multiple formats)
                        dob_str = get_val('date_of_birth')
                        date_of_birth = None
                        if dob_str:
                            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
                                try:
                                    date_of_birth = datetime.strptime(dob_str, fmt).date()
                                    break
                                except ValueError:
                                    continue

                        # Handle Weights
                        try:
                            bw_str = get_val('birth_weight')
                            birth_weight = float(bw_str) if bw_str else None
                        except ValueError:
                            birth_weight = None

                        try:
                            ww_str = get_val('weaning_weight')
                            weaning_weight = float(ww_str) if ww_str else None
                        except ValueError:
                            weaning_weight = None

                        # Handle Parents
                        parent_ram_tag = get_val('parent_ram')
                        parent_ewe_tag = get_val('parent_ewe')
                        
                        parent_ram = Sheep.objects.filter(ear_tag_number=parent_ram_tag).first() if parent_ram_tag else None
                        parent_ewe = Sheep.objects.filter(ear_tag_number=parent_ewe_tag).first() if parent_ewe_tag else None

                        # Handle Boolean
                        healthy_str = get_val('is_healthy')
                        is_healthy = str(healthy_str).lower() in ['true', 'yes', '1', 'y'] if healthy_str else True

                        # 4. Save to Database
                        defaults = {
                            'breed': breed,
                            'blood_level': blood_level,
                            'sex': sex,
                            'type': sheep_type,
                            'date_of_birth': date_of_birth,
                            'birth_weight': birth_weight,
                            'weaning_weight': weaning_weight,
                            'parent_ram': parent_ram,
                            'parent_ewe': parent_ewe,
                            'is_healthy': is_healthy
                        }

                        obj, created = Sheep.objects.update_or_create(
                            ear_tag_number=ear_tag,
                            defaults=defaults
                        )
                        
                        if created or update_existing:
                            success_count += 1

                    except Exception as e:
                        error_count += 1
                        errors.append(f"Row {row_num} ({ear_tag if 'ear_tag' in locals() else 'Unknown'}): {str(e)}")

                if success_count > 0:
                    messages.success(request, f'Successfully processed {success_count} records.')
                if error_count > 0:
                    messages.warning(request, f'Failed on {error_count} records.')
                    for err in errors[:5]:
                        messages.error(request, err)
                
                return redirect('home')

            except Exception as e:
                messages.error(request, f'Critical Error: {str(e)}')
    else:
        form = CSVImportForm()
    
    return render(request, 'import_sheep_csv.html', {'form': form})








def home(request):
    sheeps = Sheep.objects.all()

    # Check to see if logging in
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        # Authenticate
        user = authenticate(request, username = username, password = password)
        if user is not None:
            login(request, user)
            messages.success(request, "You Have Been Logged in!")
            return redirect('breeding_selection')
        else:
                messages.success(request,"There was an Error Logging In, Please Try Again...")
                return redirect('home')
    else:
            return render(request, 'home.html', {'sheeps':sheeps})
    

def logout_user(request):
    logout(request)
    messages.success(request, "You Have Been Logged Out...")
    return redirect('home')


def sheep_record(request, pk):
     if request.user.is_authenticated:
        #   Can look records
        sheep_record = Sheep.objects.get(ear_tag_number=pk)
        return render(request, 'record.html', {'sheep_record':sheep_record})
     
     else:
          messages.success(request, "You must be logged in to view records...")
          return redirect('home')
     

def delete_record(request, pk):
     if request.user.is_authenticated:
        delete_it = Sheep.objects.get(ear_tag_number=pk)
        delete_it.delete()

        messages.success(request, "Record deleted does successfully")
        return redirect('breeding_selection')
     else:
        messages.success(request, "You must to loggedin to perform this")
        return redirect('home')

# def add_record(request):
#      form = AddRecordForm(request.POST or None)
#      if request.user.is_authenticated:
#           if request.method =="POST":
#                if form.is_valid():
#                     add_record = form.save()
#                     messages.success(request, "Record Added...")
#                     return redirect('home')
#           return render(request, 'add_record.html', {'form':form})
#      else:
#           messages.success(request, "You must be logged in...")
#           return redirect('home')
     
def update_record(request, pk):
     if request.user.is_authenticated:
          current_record = Sheep.objects.get(ear_tag_number=pk)
          form = AddRecordForm(request.POST or None, instance=current_record)
          if form.is_valid():
               form.save()
               messages.success(request, "Record has been updated!")
               return redirect('breeding_selection')
          return render(request, 'update_record.html', {'form':form})
     else:
          messages.success(request, "You must be logged in...")
          return redirect('home')


@login_required
@allowed_users(allowed_roles=['Breeder',])
def breeding_selection(request):
    """Main breeding selection view"""
    rams = get_available_rams()
    ewes = get_available_ewes()
    lambs = get_available_lambs()
    young_rams = get_available_young_rams()
    gimmers = get_available_gimmers()
    
    selected_ram_id = request.GET.get('ram_id')
    selected_ram = None
    compatible_ewes = []
    
    if selected_ram_id:
        try:
            selected_ram = Sheep.objects.get(ear_tag_number=selected_ram_id)
            compatible_ewes = get_compatible_ewes(selected_ram)
        except Sheep.DoesNotExist:
            pass
    
    context = {
        'rams': rams,
        'ewes': ewes,
        'young_rams': young_rams,
        'gimmers': gimmers,
        'lambs': lambs,
        'selected_ram': selected_ram,
        'compatible_ewes': compatible_ewes,
    }
    
    return render(request, 'breeding.html', context)   
     
@login_required
@allowed_users(allowed_roles=['Breeder',])
def flash_rams_state(request):
    if request.method == "POST":
        selected = request.POST.getlist("rams")

        updated = Sheep.objects.filter(
            ear_tag_number__in=selected,
            state="ACTIVE",
            type="RAM"
        ).update(state="FLASHING")

        messages.success(request, f"{updated} ram(s) set to FLASHING")
    return redirect('breeding_selection')

@login_required
@allowed_users(allowed_roles=['Breeder',])
def flash_ewes_state(request):
    if request.method == "POST":
        selected = request.POST.getlist("ewes")

        updated = Sheep.objects.filter(
            ear_tag_number__in=selected,
            state="ACTIVE",
            type="EWE"
        ).update(state="FLASHING")

        messages.success(request, f"{updated} ewe(s) set to FLASHING")
    return redirect('breeding_selection')


@login_required
@allowed_users(allowed_roles=['Breeder',])
def breed_rams_state(request):
    if request.method == "POST":
        selected_rams = request.POST.getlist("rams")

        if not selected_rams:
            messages.warning(request, "No rams were selected.")
            return redirect('breeding_selection')

        # Update selected rams only if their current state is FLASHING
        updated = Sheep.objects.filter(
            ear_tag_number__in=selected_rams,
            state="FLASHING"
        ).update(state="BREEDING")

        if updated > 0:
            messages.success(request, f"{updated} ram(s) successfully set to BREEDING state.")
        else:
            messages.info(request, "No rams were updated. They may not be in FLASHING state.")

        return redirect('breeding_selection')

    return redirect('breeding_selection')


@login_required
@allowed_users(allowed_roles=['Breeder',])
def breed_sheep_state(request):
    if request.method == "POST":
        selected_sheep = request.POST.getlist("sheeps")

        if not selected_sheep:
            messages.warning(request, "No sheep were selected.")
            return redirect('breeding_selection')

        # Update selected rams only if their current state is FLASHING
        updated = Sheep.objects.filter(
            ear_tag_number__in=selected_sheep,
            state="FLASHING"
        ).update(state="BREEDING")

        if updated > 0:
            messages.success(request, f"{updated} sheep(s) successfully set to BREEDING state.")
        else:
            messages.info(request, "No sheep were updated. They may not be in FLASHING state.")

        return redirect('breeding_selection')

    return redirect('breeding_selection')




@login_required
@require_POST
def process_ram_selection(request):
    """
    Receives the list of selected rams from breeding.html,
    stores them in the session, and redirects to the task page.
    """
    selected_ram_ids = request.POST.getlist('rams')
    
    if not selected_ram_ids:
        messages.warning(request, "Please select at least one ram to proceed.")
        return redirect('breeding_selection')

    # Validate that these rams actually exist and are in the correct state
    valid_rams = Sheep.objects.filter(
        ear_tag_number__in=selected_ram_ids,
        type='RAM'  # Optional: Add state='FLASHING' check if strict
    ).values_list('ear_tag_number', flat=True)

    if not valid_rams:
        messages.error(request, "Invalid rams selected.")
        return redirect('breeding_selection')

    # Store in session
    request.session['selected_rams'] = list(valid_rams)
    request.session.modified = True

    return redirect('breeding_task')


# 2. UPDATED VIEW: The main Breeding Task logic

class BreedingTaskView(View):
    template_name = 'breeding_task.html'
    
    def get(self, request):
        # 1. Retrieve selected rams from session
        selected_ram_ids = request.session.get('selected_rams', [])
        
        if not selected_ram_ids:
            messages.warning(request, "Session expired or no rams selected. Please select rams again.")
            return redirect('breeding_selection')
        
        try:
            # 2. Fetch Ram Objects
            rams = Sheep.objects.filter(ear_tag_number__in=selected_ram_ids)
            
            # 3. Get Capacity Info & Compatible Ewes
            all_compatible_ewes = set()
            ram_compatible_ewes_by_ewe = {}  # Map: ewe_id -> [ram_id1, ram_id2]
            
            for ram in rams:
                ram.capacity_info = get_ram_capacity_info(ram) # Ensure this service function exists
                
                # Get compatible ewes for this specific ram
                comp_ewes = get_compatible_ewes(ram) # Ensure this service function exists
                
                for ewe in comp_ewes:
                    all_compatible_ewes.add(ewe)
                    
                    if ewe.ear_tag_number not in ram_compatible_ewes_by_ewe:
                        ram_compatible_ewes_by_ewe[ewe.ear_tag_number] = []
                    ram_compatible_ewes_by_ewe[ewe.ear_tag_number].append(ram.ear_tag_number)

            # 4. Distribute Ewes (Initial Assignment)
            # Convert set to list for distribution function
            distributed_assignments = distribute_ewes_by_priority(rams, list(all_compatible_ewes))
            
            # 5. Identify Unassigned Ewes
            # Get IDs of currently assigned ewes
            assigned_ewe_ids = set()
            for ewe_list in distributed_assignments.values():
                for ewe in ewe_list:
                    assigned_ewe_ids.add(ewe.ear_tag_number)
            
            # Filter unassigned from the compatible list AND get completely unassigned ones from DB
            # (depending on if you want to show ALL ewes or just compatible ones)
            # Here we show all available ewes that aren't assigned yet
            unassigned_ewes = Sheep.objects.filter(
                sex='FEMALE',
                type__in=['EWE'],
                is_healthy=True
            ).exclude(ear_tag_number__in=assigned_ewe_ids)

            # 6. Prepare JSON Data for JavaScript
            rams_json = [
                {
                    'ear_tag': ram.ear_tag_number,
                    'breed': ram.breed,
                    'remaining': ram.capacity_info.get('remaining', 0),
                    'capacity': ram.capacity_info.get('max', 0)
                } for ram in rams
            ]
            
            ewes_json = {}
            # Combine compatible and unassigned for the JS lookup
            all_relevant_ewes = list(all_compatible_ewes) + list(unassigned_ewes)
            for ewe in all_relevant_ewes:
                ewes_json[ewe.ear_tag_number] = {
                    'ear_tag': ewe.ear_tag_number,
                    'breed': ewe.breed,
                    'type': ewe.type,
                    'compatible_with': ram_compatible_ewes_by_ewe.get(ewe.ear_tag_number, [])
                }

            initial_assignments_simple = {
                ram_id: [ewe.ear_tag_number for ewe in ewes]
                for ram_id, ewes in distributed_assignments.items()
            }

            context = {
                'rams': rams,
                'distributed_assignments': distributed_assignments,
                'unassigned_ewes': unassigned_ewes,
                'ram_compatible_ewes_by_ewe': ram_compatible_ewes_by_ewe,
                'rams_json': json.dumps(rams_json),
                'ewes_json': json.dumps(ewes_json),
                'initial_assignments_json': json.dumps(initial_assignments_simple),
            }
            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Error in BreedingTaskView: {e}")
            messages.error(request, f"System Error: {e}")
            return redirect('breeding_selection')

    def post(self, request):
        """
        Handles the Save button from the Task page.
        Redirects to the Info/Confirmation page.
        """
        try:
            assignments_json = request.POST.get('breedingAssignments')
            if not assignments_json:
                raise ValueError("No assignment data received.")
            
            assignments = json.loads(assignments_json)
            
            # Store finalized assignments in session
            request.session['breeding_assignments'] = assignments
            request.session.modified = True
            
            return redirect('breeding_info')
            
        except Exception as e:
            messages.error(request, f"Error saving assignments: {e}")
            return redirect('breeding_task')






class BreedingInfoView(View):
    template_name = 'breeding_info.html'
    # ... GET method remains the same ...
    def get(self, request):
        """
        Display the breeding plan stored in the session for review.
        """
        # 1. Retrieve draft assignments from session
        breeding_assignments = request.session.get('breeding_assignments', {})
        
        # 2. Redirect if empty (e.g. direct access without selection)
        if not breeding_assignments:
            messages.warning(request, "No breeding plan found. Please select rams and assign ewes first.")
            return redirect('breeding_task')
        
        # 3. Prepare display data (Ram objects, Ewe objects, Dates)
        breeding_info = []
        today = date.today()
        end_date = today + timedelta(days=51)  # Example breeding period
        expected_birth = today + timedelta(days=155) # Standard gestation
        expected_birth_end_date = end_date + timedelta(days=155) # Standard gestation

        for ram_tag, ewe_tags in breeding_assignments.items():
            try:
                ram = Sheep.objects.get(ear_tag_number=ram_tag)
                # Get all assigned ewes for this ram
                ewes = Sheep.objects.filter(ear_tag_number__in=ewe_tags)
                
                # Get capacity for progress bars
                capacity = get_ram_capacity_info(ram) 
                # Note: This capacity calculation might need to account for 
                # the *proposed* ewes if you want to show "Projected Capacity".
                # For now, we show current DB capacity + session additions if needed, 
                # or just current status.
                
                for ewe in ewes:
                    breeding_info.append({
                        'ram': ram,
                        'ewe': ewe,
                        'start_date': today,
                        'end_date': end_date,
                        'expected_birth_date': expected_birth,
                        'expected_birth_end_date': expected_birth_end_date,
                        'capacity_info': capacity
                    })
            except Sheep.DoesNotExist:
                continue
            # --- NEW: Sort by Ram Breed to enable grouping in template ---
        breeding_info.sort(key=lambda x: x['ram'].breed)
        
        context = {
            'breeding_info': breeding_info
        }
        return render(request, self.template_name, context)
    def post(self, request):
        """
        Commit the breeding plan from session to the database and update Ewe states.
        """
        breeding_assignments = request.session.get('breeding_assignments', {})
        
        if not breeding_assignments:
            messages.error(request, "Session expired or empty. Please try again.")
            return redirect('breeding_task')
        
        created_count = 0
        ewe_tags_to_update = set()
        
        try:
            with transaction.atomic():
                for ram_tag, ewe_tags in breeding_assignments.items():
                    ram = Sheep.objects.get(ear_tag_number=ram_tag)
                    
                    for ewe_tag in ewe_tags:
                        ewe = Sheep.objects.get(ear_tag_number=ewe_tag)
                        
                        # Store the Ewe tag for state update later
                        ewe_tags_to_update.add(ewe_tag)

                        # Generate ID
                        # Using the shorter ID format from previous step to avoid max_length error
                        import uuid
                        short_hash = str(uuid.uuid4())[:8]
                        cycle_id = f"BC-{short_hash}"
                        
                        # Avoid duplicates
                        if BreedingCycle.objects.filter(cycle_id=cycle_id).exists():
                            continue

                        # Create the cycle
                        BreedingCycle.objects.create(
                            cycle_id=cycle_id,
                            ewe=ewe,
                            ram=ram,
                            start_date=date.today(),
                            status='PLANNED', 
                            created_by=request.user if request.user.is_authenticated else None
                        )
                        created_count += 1

                # --- FIX: Update all assigned Ewes' states outside the inner loop ---
                # Retrieve all unique Ewe objects assigned
                Ewes = Sheep.objects.filter(ear_tag_number__in=list(ewe_tags_to_update))
                Rams = Sheep.objects.filter(ear_tag_number__in=list(breeding_assignments.keys()))
                
                # Bulk update the state to 'BREEDING'
                Ewes.update(state='BREEDING') 
                # ----------------------------------------------------------------------
            
            # Success! Clear the session
            if 'breeding_assignments' in request.session:
                del request.session['breeding_assignments']
            if 'selected_rams' in request.session:
                del request.session['selected_rams']
                
            messages.success(request, f"Successfully created {created_count} breeding cycles and updated {len(ewe_tags_to_update)} ewes to 'BREEDING' state!")
            return redirect('home')
            
        except Sheep.DoesNotExist:
            messages.error(request, "One or more sheep could not be found. Please retry selection.")
            return redirect('breeding_info')
            
        except Exception as e:
            logger.error(f"Error saving breeding plan: {e}")
            messages.error(request, f"An error occurred while saving: {e}")
            return redirect('breeding_info')
        




class BreedingHistoryView(View):
    template_name = 'breeding_history.html'
    
    def get(self, request):
        """
        Display historical breeding records grouped by date with pagination.
        """
        # 1. Fetch all cycles, ordered by newest date first
        all_cycles_list = BreedingCycle.objects.select_related('ram', 'ewe').order_by('-start_date')
        
        # 2. Set up Pagination (10 entries per page)
        paginator = Paginator(all_cycles_list, 10) 
        
        page_number = request.GET.get('page')
        try:
            cycles = paginator.page(page_number)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            cycles = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999), deliver last page of results.
            cycles = paginator.page(paginator.num_pages)
        
        context = {
            'cycles': cycles # This is now a Page object, not the full list
        }
        return render(request, self.template_name, context)
    
@login_required
def debug_breeding_flow(request):
    """Debug view to test the entire breeding flow"""
    if request.method == 'POST':
        # Simulate selecting some rams
        test_rams = Sheep.objects.filter(sex='male', type__in=['ram'], is_healthy=True)[:2]
        if test_rams:
            request.session['selected_rams'] = [ram.ear_tag_number for ram in test_rams]
            request.session.modified = True
            messages.success(request, f"Auto-selected {len(test_rams)} rams for testing")
            return redirect('breeding_task')
        else:
            messages.error(request, "No rams available for testing")
    
    return render(request, 'debug_breeding.html')

@login_required
@allowed_users(allowed_roles=['Breeder',])
def create_breeding_cycle(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            breeding_cycles = data.get('breeding_cycles', [])
            created_cycles = []

            for cycle_data in breeding_cycles:
                ewe_id = cycle_data.get('ewe_id')
                ram_id = cycle_data.get('ram_id')
                start_date_str = cycle_data.get('start_date')

                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                ewe = Sheep.objects.get(ear_tag_number=ewe_id)
                ram = Sheep.objects.get(ear_tag_number=ram_id)

                breeding_cycle = BreedingCycle(
                    ewe=ewe,
                    ram=ram,
                    start_date=start_date,
                    created_by=request.user
                )
                breeding_cycle.save()
                created_cycles.append(breeding_cycle.cycle_id)

            return JsonResponse({
                'success': True,
                'message': f'Successfully created {len(created_cycles)} breeding cycles',
                'cycle_ids': created_cycles
            })

        except Exception as e:
            logger.error(f"Error creating breeding cycle: {str(e)}")
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})

    