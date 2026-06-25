from django import forms
from django.core.exceptions import ValidationError
import re

from .models import Vehicle


PLATE_RE = re.compile(r'^[A-Z0-9][A-Z0-9\s-]{2,14}$')


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = (
            'plate_number',
            'vehicle_type',
            'vehicle_class',
            'resident_owner',
            'visitor_owner',
            'make_model',
            'color',
            'is_active',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'plate_number': 'e.g. KBE 309V',
            'make_model': 'e.g. Toyota Prado',
            'color': 'e.g. White',
        }
        labels = {
            'plate_number': 'Plate number',
            'vehicle_type': 'Vehicle owner type',
            'vehicle_class': 'Vehicle class',
            'resident_owner': 'Resident / employee owner',
            'visitor_owner': 'Visitor owner',
            'make_model': 'Make / model',
            'is_active': 'Active record',
        }

        for name, field in self.fields.items():
            if name in labels:
                field.label = labels[name]
            if name == 'is_active':
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({
                    'class': 'form-control',
                    'placeholder': placeholders.get(name, ''),
                })

    def clean_plate_number(self):
        plate = (self.cleaned_data.get('plate_number') or '').strip().upper()
        plate = re.sub(r'\s+', ' ', plate)
        if not PLATE_RE.match(plate):
            raise ValidationError('Enter a valid plate number, for example KBE 309V.')
        return plate

    def clean_make_model(self):
        value = (self.cleaned_data.get('make_model') or '').strip()
        if value and len(value) < 2:
            raise ValidationError('Make/model is too short.')
        return value

    def clean_color(self):
        value = (self.cleaned_data.get('color') or '').strip()
        if value and not re.match(r'^[A-Za-z][A-Za-z\s/-]{1,38}$', value):
            raise ValidationError('Enter a valid vehicle color.')
        return value

    def clean(self):
        cleaned = super().clean()
        vehicle_type = cleaned.get('vehicle_type')
        resident_owner = cleaned.get('resident_owner')
        visitor_owner = cleaned.get('visitor_owner')

        if resident_owner and visitor_owner:
            raise ValidationError('Select either a resident/employee owner or a visitor owner, not both.')
        if vehicle_type == Vehicle.VehicleType.RESIDENT and not resident_owner:
            self.add_error('resident_owner', 'Resident/employee vehicles must have an owner.')
        if vehicle_type == Vehicle.VehicleType.VISITOR and not visitor_owner:
            self.add_error('visitor_owner', 'Visitor vehicles must have a visitor owner.')
        if vehicle_type == Vehicle.VehicleType.SERVICE and (resident_owner or visitor_owner):
            raise ValidationError('Service vehicles should not be assigned to a resident or visitor owner.')
        return cleaned
