from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('BREEDER', 'Breeder'),
    ]
    
    user_id = models.CharField(max_length=50, unique=True, primary_key=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    
    # Add these to resolve the clash
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name="sh_app_user_set",  # Changed related_name
        related_query_name="sh_app_user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="sh_app_user_set",  # Changed related_name
        related_query_name="sh_app_user",
    )
    
    def save(self, *args, **kwargs):
        if not self.user_id:
            self.user_id = f"USER_{self.username.upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.username} ({self.role})"

class Sheep(models.Model):
    SEX_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
    ]
    
    TYPE_CHOICES = [
        ('LAMB', 'Lamb'),
        ('YOUNG_RAM', 'Young Ram'),
        ('GIMMER', 'Gimmer'),
        ('RAM', 'Ram'),
        ('EWE', 'Ewe'),
    ]

    STATE_CHOICES = [
        ('IN_ACTIVE', 'In_active'),
        ('ACTIVE', 'Active'),
        ('FLASHING', 'Flashing'),
        ('BREEDING', 'Breeding'),
       ('PREGNANT', 'Pregnant'),
       ('BIRTHING', 'Birthing'),
    ]
    
    BREED_CHOICES = [
        ('LOCAL', 'Local'),
        ('PA', 'PA'),
        ('PD', 'PD'),
        ('AC', 'AC'),
        ('DC', 'DC'),
    ]
    
    ear_tag_number = models.CharField(max_length=50, unique=True, primary_key=True)
    breed = models.CharField(max_length=10, choices=BREED_CHOICES)
    blood_level = models.FloatField()
    sex = models.CharField(max_length=10, choices=SEX_CHOICES)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    birth_weight = models.FloatField(null=True, blank=True)
    weaning_date = models.DateField(null=True, blank=True)
    weaning_weight = models.FloatField(null=True, blank=True)
    parent_ewe = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='ewe_offspring',
        limit_choices_to={'sex': 'FEMALE'}
    )
    parent_ram = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='ram_offspring',
        limit_choices_to={'sex': 'MALE'}
    )
    is_healthy = models.BooleanField(default=True)
    health_notes = models.TextField(blank=True)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default='ACTIVE')
    flagged_for_culling = models.BooleanField(default=False)
    culling_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def clean(self):
        # Validate parent relationships
        if self.parent_ewe and self.parent_ewe.sex != 'FEMALE':
            raise ValidationError("Parent ewe must be female")
        if self.parent_ram and self.parent_ram.sex != 'MALE':
            raise ValidationError("Parent ram must be male")
        
        # Auto-culling rule
        if self.weaning_weight and self.weaning_weight < 11:
            self.flagged_for_culling = True
            if not self.culling_reason:
                self.culling_reason = "Low Weaning Weight"
    
    def __str__(self):
        return f"{self.ear_tag_number} - {self.breed} - {self.type}"
    


# models.py - BreedingCycle Model Enhancements
class BreedingCycle(models.Model):
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    cycle_id = models.CharField(max_length=100, unique=True, primary_key=True)
    ewe = models.ForeignKey(Sheep, on_delete=models.CASCADE, related_name='breeding_cycles_as_ewe')
    ram = models.ForeignKey(Sheep, on_delete=models.CASCADE, related_name='breeding_cycles_as_ram')
    start_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANNED')
    actual_birth_date = models.DateField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
   
    # Add the missing created_by field
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='breeding_cycles_created'
    )

    @property
    def end_date(self):
        """Breeding End Date = Start Date + 51 days"""
        return self.start_date + timedelta(days=51)
    
    @property
    def expected_birth_date(self):
        """Expected Birth Date = Start Date + 155 days"""
        return self.start_date + timedelta(days=155)
    
    @property
    def days_until_birth(self):
        if self.status != 'COMPLETED':
            today = date.today()
            return (self.expected_birth_date - today).days
        return None
    
    @property
    def gestation_progress(self):
        if self.status in ['IN_PROGRESS', 'COMPLETED']:
            total_days = 155
            days_passed = (date.today() - self.start_date).days
            return min(100, max(0, int((days_passed / total_days) * 100)))
        return 0
    
    def save(self, *args, **kwargs):
        # Auto-update status based on dates
        today = date.today()
        if self.status == 'PLANNED' and self.start_date <= today:
            self.status = 'IN_PROGRESS'
        
        # Auto-create lambs when actual_birth_date is set
        if self.actual_birth_date and not self._state.adding:
            original = BreedingCycle.objects.get(pk=self.cycle_id)
            if not original.actual_birth_date:
                self.create_lambs_from_cycle()
        
        super().save(*args, **kwargs)
    
    def create_lambs_from_cycle(self):
        """Automatically create lamb records when birth date is recorded"""
        from .services1 import predict_lamb_breed
        
        # This would typically be called with the number of lambs born
        # For now, we'll create one lamb as placeholder
        lamb_breed, lamb_level = predict_lamb_breed(self.ewe, self.ram)
        
        lamb = Sheep.objects.create(
            ear_tag_number=f"LAMB_{self.cycle_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            breed=lamb_breed,
            blood_level=lamb_level,
            sex='UNKNOWN',  # Requires manual assignment
            type='LAMB',
            date_of_birth=self.actual_birth_date,
            parent_ewe=self.ewe,
            parent_ram=self.ram,
            is_healthy=True
        )
        
        # Log the automatic lamb creation
        AuditLog.objects.create(
            user_id='SYSTEM',
            action='AUTO_CREATE_LAMB',
            entity='Sheep',
            entity_id=lamb.ear_tag_number,
            new_values={
                'ear_tag_number': lamb.ear_tag_number,
                'breed': lamb.breed,
                'blood_level': lamb.blood_level,
                'parent_ewe': self.ewe.ear_tag_number,
                'parent_ram': self.ram.ear_tag_number
            },
            notes=f"Automatically created from breeding cycle {self.cycle_id}"
        )
    
    def __str__(self):
        return f"Cycle {self.cycle_id}: {self.ewe.ear_tag_number} × {self.ram.ear_tag_number}"
    
def clean(self):
    from .services1 import check_for_inbreeding, check_ram_capacity
    
    # Ensure start_date is a date object for validation
    if not isinstance(self.start_date, date):
        try:
            from datetime import datetime
            self.start_date = datetime.strptime(str(self.start_date), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            raise ValidationError("Invalid start date format")
    
    # Inbreeding prevention
    if not check_for_inbreeding(self.ewe, self.ram):
        raise ValidationError("Breeding cycle violates inbreeding prevention rules")
    
    # Ram capacity check
    if not check_ram_capacity(self.ram, self.start_date):
        raise ValidationError("Ram has exceeded breeding capacity for this season")

def save(self, *args, **kwargs):
    if not self.cycle_id:
        self.cycle_id = f"BC_{self.ewe.ear_tag_number}_{self.ram.ear_tag_number}_{self.start_date}"
    
    # Ensure we clean before saving
    self.full_clean()
    super().save(*args, **kwargs)

# class CullingRecord(models.Model):
#     record_id = models.CharField(max_length=50, unique=True, primary_key=True)
#     sheep = models.ForeignKey(Sheep, on_delete=models.CASCADE)
#     date = models.DateField()
#     reason = models.TextField(blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)

class CullingRecord(models.Model):
    sheep = models.ForeignKey(Sheep, on_delete=models.CASCADE, related_name='culling_records')
    reason = models.TextField()
    date_culled = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.sheep.ear_tag_number} - {self.reason}"

class MortalityRecord(models.Model):
    sheep = models.ForeignKey(Sheep, on_delete=models.CASCADE, related_name='mortality_records')
    reason = models.TextField()
    date_of_death = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.sheep.ear_tag_number} - {self.reason}"

class DistributionRecord(models.Model):
    sheep = models.ForeignKey(Sheep, on_delete=models.CASCADE, related_name='distribution_records')
    distribution_date = models.DateField(auto_now_add=True)
    # You can add 'destination' or 'price' fields here if needed later

    def __str__(self):
        return f"{self.sheep.ear_tag_number} - Distributed"



class AuditLog(models.Model):
    log_id = models.CharField(max_length=50, unique=True, primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=50)
    entity = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=50)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)


class Report(models.Model):
    report_id = models.CharField(max_length=50, unique=True, primary_key=True)
    breeding_season = models.CharField(max_length=50)
    report_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)