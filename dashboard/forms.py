from django import forms
from django.core.exceptions import ValidationError
import re

from residents.models import Resident
from traffic_logs.models import TrafficLog
from vehicles.models import Vehicle
from visitors.models import Visitor
from visitors.models import MainGate
from .models import SystemSettings


PHONE_RE = re.compile(r'^\+?\d[\d\s-]{6,18}$')
PLATE_RE = re.compile(r'^[A-Z0-9][A-Z0-9\s-]{2,14}$')
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\s.'-]{1,118}$")


class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = (
            'estate_name',
            'logo_url',
            'contact_phone',
            'contact_email',
            'timezone_name',
            'default_theme',
            'compact_mode',
            'sms_simulation_enabled',
            'email_simulation_enabled',
            'require_visitor_id',
            'require_vehicle_details',
            'max_visit_hours',
            'session_timeout_minutes',
            'failed_login_warning',
            'default_report_days',
        )
        widgets = {
            'logo_url': forms.TextInput(attrs={'placeholder': 'Optional image URL for a hosted logo'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

    def clean_contact_phone(self):
        value = (self.cleaned_data.get('contact_phone') or '').strip()
        if not PHONE_RE.match(value):
            raise ValidationError('Enter a valid contact phone number.')
        return value

    def clean_timezone_name(self):
        value = (self.cleaned_data.get('timezone_name') or '').strip()
        if not re.match(r'^[A-Za-z_]+/[A-Za-z_]+$', value):
            raise ValidationError('Use a valid timezone format, for example Africa/Nairobi.')
        return value

    def clean_max_visit_hours(self):
        value = self.cleaned_data.get('max_visit_hours')
        if value < 1 or value > 168:
            raise ValidationError('Max visit hours must be between 1 and 168.')
        return value

    def clean_session_timeout_minutes(self):
        value = self.cleaned_data.get('session_timeout_minutes')
        if value < 5 or value > 720:
            raise ValidationError('Session timeout must be between 5 and 720 minutes.')
        return value

    def clean_default_report_days(self):
        value = self.cleaned_data.get('default_report_days')
        if value < 1 or value > 366:
            raise ValidationError('Default report days must be between 1 and 366.')
        return value


class UnitResidentMovementForm(forms.Form):
    vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.none(),
        label='Registered car or motorcycle',
        empty_label='Select from master vehicle list',
    )
    direction = forms.ChoiceField(
        choices=TrafficLog.Direction.choices,
        label='Movement',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = (
            Vehicle.objects.select_related('resident_owner', 'resident_owner__community_unit')
            .filter(is_active=True, resident_owner__isnull=False)
            .order_by('plate_number')
        )
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select'

    def clean_vehicle(self):
        vehicle = self.cleaned_data.get('vehicle')
        if vehicle and not vehicle.is_active:
            raise ValidationError('Select an active registered vehicle.')
        if vehicle and not vehicle.resident_owner_id:
            raise ValidationError('Selected vehicle must belong to a resident or employee.')
        return vehicle


class MainGateResidentMovementForm(UnitResidentMovementForm):
    gate = forms.ChoiceField(choices=MainGate.choices, label='Main gate')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gate'].widget.attrs['class'] = 'form-select'


class GateVisitorRequestForm(forms.ModelForm):
    class Meta:
        model = Visitor
        fields = (
            'guest_type',
            'full_name',
            'id_number',
            'phone',
            'host',
            'destination',
            'purpose',
            'company_name',
            'vehicle_class',
            'vehicle_plate',
            'vehicle_make_model',
            'vehicle_color',
            'main_gate',
        )
        widgets = {
            'purpose': forms.TextInput(attrs={'placeholder': 'Reason for visit or delivery'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['host'].queryset = Resident.objects.select_related('community_unit').filter(is_active=True)
        self.fields['host'].label = 'Resident / company contact'
        self.fields['destination'].label = 'Estate / company destination'
        self.fields['main_gate'].label = 'Gate where visitor arrived'
        self.fields['vehicle_class'].label = 'Vehicle class'
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_full_name(self):
        value = (self.cleaned_data.get('full_name') or '').strip()
        if not NAME_RE.match(value):
            raise ValidationError('Enter a valid visitor name.')
        return value

    def clean_id_number(self):
        value = (self.cleaned_data.get('id_number') or '').strip().upper()
        if not re.match(r'^[A-Z0-9][A-Z0-9/-]{2,28}$', value):
            raise ValidationError('Enter a valid ID or passport number.')
        return value

    def clean_phone(self):
        value = (self.cleaned_data.get('phone') or '').strip()
        if not PHONE_RE.match(value):
            raise ValidationError('Enter a valid phone number.')
        return value

    def clean_vehicle_plate(self):
        value = (self.cleaned_data.get('vehicle_plate') or '').strip().upper()
        value = re.sub(r'\s+', ' ', value)
        if value and not PLATE_RE.match(value):
            raise ValidationError('Enter a valid plate number, for example KDA 123A.')
        return value

    def clean_vehicle_color(self):
        value = (self.cleaned_data.get('vehicle_color') or '').strip()
        if value and not re.match(r'^[A-Za-z][A-Za-z\s/-]{1,38}$', value):
            raise ValidationError('Enter a valid vehicle color.')
        return value

    def clean_purpose(self):
        value = (self.cleaned_data.get('purpose') or '').strip()
        if len(value) < 3:
            raise ValidationError('Purpose must be at least 3 characters.')
        return value

    def clean(self):
        cleaned = super().clean()
        vehicle_values = {
            'vehicle_class': cleaned.get('vehicle_class'),
            'vehicle_plate': cleaned.get('vehicle_plate'),
            'vehicle_make_model': cleaned.get('vehicle_make_model'),
            'vehicle_color': cleaned.get('vehicle_color'),
        }
        if any(vehicle_values.values()) and not vehicle_values['vehicle_class']:
            self.add_error('vehicle_class', 'Select Car or Motorcycle when vehicle details are provided.')
        if cleaned.get('host') and not cleaned.get('destination'):
            cleaned['destination'] = cleaned['host'].community_unit
        return cleaned
