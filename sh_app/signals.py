# signals.py - Automated integrations
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import BreedingCycle, Sheep
from django.utils import timezone

@receiver(post_save, sender=BreedingCycle)
def handle_breeding_cycle_completion(sender, instance, **kwargs):
    """
    Handle automatic actions when breeding cycle is completed
    """
    if instance.status == 'COMPLETED' and instance.actual_birth_date:
        # Check if we need to create distribution alerts for young rams
        from .services1 import check_young_ram_distribution
        check_young_ram_distribution(instance.actual_birth_date.year)

@receiver(post_save, sender=Sheep)
def handle_lamb_separation_weight(sender, instance, **kwargs):
    """
    Auto-flag for culling if lamb separation weight < 11kg
    """
    if (instance.type == 'LAMB' and 
        instance.separation_weight is not None and 
        instance.separation_weight < 11):
        
        # Auto-create culling record
        from .models import CullingRecord
        culling_record = CullingRecord.objects.create(
            sheep=instance,
            date=timezone.now().date(),
            reason="Low Separation Weight (Auto-flagged)"
        )
        
        # Log the auto-culling
        AuditLog.objects.create(
            user_id='SYSTEM',
            action='AUTO_CULL_FLAG',
            entity='Sheep',
            entity_id=instance.ear_tag_number,
            new_values={
                'separation_weight': instance.separation_weight,
                'culling_reason': 'Low Separation Weight'
            },
            notes=f"Auto-flagged for culling due to low separation weight: {instance.separation_weight} kg"
        )