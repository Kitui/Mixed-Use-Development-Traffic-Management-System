from django import forms
from django.core.exceptions import ValidationError
import re

from .models import CommunityUnit, Resident


PHONE_RE = re.compile(r'^\+?\d[\d\s-]{6,18}$')
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\s.'&/-]{1,118}$")


def _clean_phone(value, field_label='Phone', required=False):
    value = (value or '').strip()
    if not value:
        if required:
            raise ValidationError(f'{field_label} is required.')
        return value
    if not PHONE_RE.match(value):
        raise ValidationError(f'{field_label} must be a valid phone number.')
    digits = re.sub(r'\D', '', value)
    if len(digits) < 7 or len(digits) > 15:
        raise ValidationError(f'{field_label} must contain 7 to 15 digits.')
    return value


class CommunityUnitForm(forms.ModelForm):
    class Meta:
        model = CommunityUnit
        fields = (
            'name',
            'unit_type',
            'contact_phone',
            'is_active',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'name': 'e.g. Maisha Makao or Coast Cables',
            'contact_phone': 'e.g. 0712 000 000',
        }
        labels = {
            'name': 'Development name',
            'unit_type': 'Development type',
            'contact_phone': 'Contact phone',
            'is_active': 'Active development',
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

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not NAME_RE.match(name):
            raise ValidationError('Use a clear development name with letters, numbers, spaces, hyphens, slashes, or dots.')
        return name

    def clean_contact_phone(self):
        return _clean_phone(self.cleaned_data.get('contact_phone'), 'Contact phone')


class ResidentForm(forms.ModelForm):
    class Meta:
        model = Resident
        fields = (
            'community_unit',
            'person_type',
            'full_name',
            'house_number',
            'phone',
            'email',
            'emergency_contact',
            'is_active',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'full_name': 'e.g. Hilda Atsenga',
            'house_number': 'e.g. D 3.1 or Reception',
            'phone': 'e.g. 0712 000 000',
            'email': 'name@example.com',
            'emergency_contact': 'Emergency phone number',
        }
        labels = {
            'community_unit': 'Community unit',
            'person_type': 'Person type',
            'full_name': 'Full name',
            'house_number': 'House / office number',
            'emergency_contact': 'Emergency contact',
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

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not NAME_RE.match(full_name):
            raise ValidationError('Enter a valid full name.')
        return full_name

    def clean_house_number(self):
        house_number = self.cleaned_data.get('house_number', '').strip().upper()
        if not re.match(r"^[A-Z0-9][A-Z0-9\s./-]{0,28}$", house_number):
            raise ValidationError('Use a valid house, unit, or office number.')
        return house_number

    def clean_phone(self):
        return _clean_phone(self.cleaned_data.get('phone'), 'Phone', required=True)

    def clean_emergency_contact(self):
        return _clean_phone(self.cleaned_data.get('emergency_contact'), 'Emergency contact')

    def clean(self):
        cleaned = super().clean()
        person_type = cleaned.get('person_type')
        community_unit = cleaned.get('community_unit')
        if person_type and not community_unit:
            self.add_error('community_unit', 'Select the residential estate or company for this person.')
        return cleaned
