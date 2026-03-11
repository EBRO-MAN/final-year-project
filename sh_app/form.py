from django import forms
from .models import Sheep

# Create Add Sheep Record
class AddRecordForm(forms.ModelForm):
    ear_tag_number = forms.CharField(required=True, widget=forms.widgets.TextInput(attrs={"placeholder": "Ear tag", "class": "form-control"}), label="Ear Tag Number")
    # breed = forms.ChoiceField(required=True, widget=forms.widgets.Select(attrs={"placeholder": "Breed", "class": "form-control"}), label="")
    breed = forms.ChoiceField(choices=Sheep.BREED_CHOICES, widget=forms.Select(attrs={"class": "form-control"}), label="Breed")
    blood_level =forms.FloatField(required=True, widget=forms.widgets.TextInput(attrs={"placeholder": "Blood level", "class": "form-control"}), label="Blood Level (%)")
    sex = forms.ChoiceField(choices=Sheep.SEX_CHOICES, widget=forms.Select(attrs={"class": "form-control"}), label="Sex")
    type = forms.ChoiceField(choices=Sheep.TYPE_CHOICES, widget=forms.Select(attrs={"class": "form-control"}), label="Sheep Type")
    # date_of_birth = forms.DateField(required=True, widget=forms.widgets.TextInput(attrs={"placeholder": "Date of birth", "class": "form-control"}), label="")
    # date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}), label="Date of Birth")
    date_of_birth = forms.DateField(
    label="Date of Birth",
    required=False,
    widget=forms.DateInput(attrs={
        "type": "date",
        "class": "form-control",
        "placeholder": "mm/dd/yyyy"
    })
)

    birth_weight =forms.FloatField(required=True, widget=forms.widgets.TextInput(attrs={"placeholder": "Birth weight", "class": "form-control"}), label="Birth Weight (kg)")
        
    weaning_date = forms.DateField(
    label="Weaning Date",
    required=False,
    widget=forms.DateInput(attrs={
        "type": "date",
        "class": "form-control",
        "placeholder": "mm/dd/yyyy"
    })
)

    
    weaning_weight = forms.FloatField(
    label="Weaning Weight (kg)",
    required=False,
    widget=forms.NumberInput(attrs={"placeholder": "Weaning weight", "class": "form-control"})
)

       
    parent_ewe = forms.ModelChoiceField(
    queryset=Sheep.objects.filter(type='EWE'),
    required=False,
    widget=forms.Select(attrs={"class": "form-control"}),
    label="Parent Ewe (Mother)"
)

       
    parent_ram = forms.ModelChoiceField(
    queryset=Sheep.objects.filter(type='RAM'),
    required=False,
    widget=forms.Select(attrs={"class": "form-control"}),
    label="Parent Ram (Father)"
)

    
    is_healthy = forms.BooleanField(
    label="Is the Sheep Healthy?",
    required=False,
    widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
)


    health_notes = forms.CharField(required=False, widget=forms.widgets.TextInput(attrs={"placeholder": "Health note", "class": "form-control"}), label="Health Notes")
    state = forms.ChoiceField(choices=Sheep.STATE_CHOICES, widget=forms.Select(attrs={"class": "form-control"}), label="Sheep State")
    # flagged_for_culling = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}), label="Flagged for Culling")
    flagged_for_culling = forms.BooleanField(
    label="Flag for Culling?",
    required=False,
    widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
)


    culling_reason = forms.CharField(required=False, widget=forms.widgets.TextInput(attrs={"placeholder": "Culling reason", "class": "form-control"}), label="Culling Reason")

    class Meta:
        model = Sheep
        exclude = ("user",)



from .models import BreedingCycle

class RamSelectionForm(forms.Form):
    rams = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        label="Select Rams for Breeding"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .services1 import get_available_rams
        self.fields['rams'].queryset = get_available_rams()

class BreedingAssignmentForm(forms.Form):
    """Form for final breeding assignments"""
    def __init__(self, *args, **kwargs):
        ram_ewe_assignments = kwargs.pop('ram_ewe_assignments', {})
        super().__init__(*args, **kwargs)
        
        for ram_id, ewe_list in ram_ewe_assignments.items():
            for ewe in ewe_list:
                field_name = f"assign_{ram_id}_{ewe.ear_tag_number}"
                self.fields[field_name] = forms.BooleanField(
                    initial=True,
                    required=False,
                    label=f"{ewe.ear_tag_number} - {ewe.breed}"
                )




class CSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label="Select CSV File",
        help_text="Upload a CSV file containing sheep records."
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        label="Update Existing Records",
        help_text="If checked, records with matching Ear Tags will be updated. Otherwise, they will be skipped."
    )



from django import forms
from .models import Sheep, CullingRecord, MortalityRecord

# Form for Adding a Single Sheep manually
class SheepForm(forms.ModelForm):
    class Meta:
        model = Sheep
        fields = '__all__'
        exclude = ['state', 'parent_ram', 'parent_ewe'] # Exclude fields you don't want manual entry for
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'separation_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

class CullingForm(forms.Form):
    ear_tag = forms.CharField(
        label="Ear Tag Number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Ear Tag'})
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label="Reason for Culling"
    )

class MortalityForm(forms.Form):
    ear_tag = forms.CharField(
        label="Ear Tag Number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Ear Tag'})
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label="Cause of Death"
    )

class DistributionForm(forms.Form):
    # This field will be populated with checkboxes of Young Rams
    selected_rams = forms.ModelMultipleChoiceField(
        queryset=Sheep.objects.none(), # Populated in __init__
        widget=forms.CheckboxSelectMultiple,
        label="Select Young Rams to Distribute"
    )

    def __init__(self, *args, **kwargs):
        super(DistributionForm, self).__init__(*args, **kwargs)
        # Filter for active YOUNG_RAMs
        self.fields['selected_rams'].queryset = Sheep.objects.filter(
            type='YOUNG_RAM'
        ).exclude(state='IN_ACTIVE')

        