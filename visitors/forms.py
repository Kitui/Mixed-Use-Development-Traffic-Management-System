from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
import re

from .models import ParkingSlot, Visitor, VisitorAttachment, WatchlistEntry


PHONE_RE = re.compile(r'^\+?\d[\d\s-]{6,18}$')
PLATE_RE = re.compile(r'^[A-Z0-9][A-Z0-9\s-]{2,14}$')
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\s.'-]{1,118}$")


class VisitorForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'full_name': 'e.g. Jane Wanjiku',
            'id_number': 'National ID or passport number',
            'phone': 'e.g. 0712 345 678',
            'purpose': 'e.g. Family visit, delivery, maintenance',
            'company_name': 'Company or service provider name',
            'vehicle_plate': 'e.g. KDA 123A',
            'vehicle_make_model': 'e.g. Toyota Axio',
            'vehicle_color': 'e.g. White',
            'incident_reason': 'Reason for incident flag',
        }
        labels = {
            'guest_type': 'Guest type',
            'id_number': 'ID/passport number',
            'vehicle_class': 'Vehicle class',
            'vehicle_plate': 'Vehicle plate number',
            'vehicle_make_model': 'Vehicle make/model',
            'vehicle_color': 'Vehicle color',
            'main_gate': 'Expected main gate',
            'expected_departure': 'Expected departure',
            'incident_flagged': 'Incident flag',
            'incident_reason': 'Incident reason',
            'recurrence': 'Repeat visit',
            'recurrence_until': 'Repeat until',
        }
        for name, field in self.fields.items():
            if name in labels:
                field.label = labels[name]
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            else:
                existing = widget.attrs.get('class', '')
                widget.attrs['class'] = f'{existing} form-control'.strip()
            if name in placeholders:
                widget.attrs.setdefault('placeholder', placeholders[name])
        for name in ('guest_type', 'host', 'destination', 'main_gate', 'redirected_from', 'recurrence', 'vehicle_class'):
            if name in self.fields:
                self.fields[name].widget.attrs['class'] = 'form-select'

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
            'redirected_from',
            'alert_sent',
            'expected_arrival',
            'expected_departure',
            'approval_notes',
            'incident_flagged',
            'incident_reason',
            'recurrence',
            'recurrence_until',
        )
        widgets = {
            'expected_arrival': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'expected_departure': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'recurrence_until': forms.DateInput(attrs={'type': 'date'}),
            'approval_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_full_name(self):
        value = (self.cleaned_data.get('full_name') or '').strip()
        if not NAME_RE.match(value):
            raise ValidationError('Enter a valid visitor name.')
        return value

    def clean_id_number(self):
        value = (self.cleaned_data.get('id_number') or '').strip().upper()
        if value and not re.match(r'^[A-Z0-9][A-Z0-9/-]{2,28}$', value):
            raise ValidationError('Enter a valid ID or passport number.')
        return value

    def clean_phone(self):
        value = (self.cleaned_data.get('phone') or '').strip()
        if not PHONE_RE.match(value):
            raise ValidationError('Enter a valid phone number.')
        digits = re.sub(r'\D', '', value)
        if len(digits) < 7 or len(digits) > 15:
            raise ValidationError('Phone number must contain 7 to 15 digits.')
        return value

    def clean_purpose(self):
        value = (self.cleaned_data.get('purpose') or '').strip()
        if len(value) < 3:
            raise ValidationError('Purpose must be at least 3 characters.')
        return value

    def clean_vehicle_plate(self):
        value = (self.cleaned_data.get('vehicle_plate') or '').strip().upper()
        value = re.sub(r'\s+', ' ', value)
        if value and not PLATE_RE.match(value):
            raise ValidationError('Enter a valid plate number, for example KDA 123A.')
        return value

    def clean_vehicle_make_model(self):
        value = (self.cleaned_data.get('vehicle_make_model') or '').strip()
        if value and len(value) < 2:
            raise ValidationError('Vehicle make/model is too short.')
        return value

    def clean_vehicle_color(self):
        value = (self.cleaned_data.get('vehicle_color') or '').strip()
        if value and not re.match(r'^[A-Za-z][A-Za-z\s/-]{1,38}$', value):
            raise ValidationError('Enter a valid vehicle color.')
        return value

    def clean(self):
        cleaned = super().clean()
        try:
            from dashboard.models import SystemSettings
            settings = SystemSettings.current()
        except Exception:
            settings = None

        if not settings:
            return cleaned

        if settings.require_visitor_id and not cleaned.get('id_number'):
            self.add_error('id_number', 'Visitor ID/passport is required by system settings.')

        vehicle_values = {
            'vehicle_class': cleaned.get('vehicle_class'),
            'vehicle_plate': cleaned.get('vehicle_plate'),
            'vehicle_make_model': cleaned.get('vehicle_make_model'),
            'vehicle_color': cleaned.get('vehicle_color'),
        }
        if any(vehicle_values.values()) and not vehicle_values['vehicle_class']:
            self.add_error('vehicle_class', 'Select Car or Motorcycle when vehicle details are provided.')
        if settings.require_vehicle_details and any(vehicle_values.values()) and not all(vehicle_values.values()):
            message = 'Complete class, plate, make/model, and color when vehicle details are provided.'
            for field_name, field_value in vehicle_values.items():
                if not field_value:
                    self.add_error(field_name, message)

        arrival = cleaned.get('expected_arrival')
        departure = cleaned.get('expected_departure')
        recurrence = cleaned.get('recurrence')
        recurrence_until = cleaned.get('recurrence_until')
        if arrival and arrival < timezone.now() - timezone.timedelta(minutes=5):
            self.add_error('expected_arrival', 'Expected arrival cannot be in the past.')
        if arrival and departure:
            if departure <= arrival:
                self.add_error('expected_departure', 'Expected departure must be after expected arrival.')
            elif departure - arrival > timezone.timedelta(hours=settings.max_visit_hours):
                self.add_error('expected_departure', f'Maximum configured visit duration is {settings.max_visit_hours} hours.')
        if recurrence and recurrence != Visitor.Recurrence.NONE and not recurrence_until:
            self.add_error('recurrence_until', 'Choose an end date for recurring bookings.')
        if recurrence_until and arrival and recurrence_until < arrival.date():
            self.add_error('recurrence_until', 'Repeat-until date cannot be before expected arrival.')

        return cleaned


class VisitorAttachmentForm(forms.ModelForm):
    class Meta:
        model = VisitorAttachment
        fields = ('title', 'document')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'class': 'form-control', 'placeholder': 'e.g. ID copy, delivery note, work permit'})
        self.fields['document'].widget.attrs.update({'class': 'form-control'})

    def clean_title(self):
        value = (self.cleaned_data.get('title') or '').strip()
        if len(value) < 3:
            raise ValidationError('Attachment title must be at least 3 characters.')
        return value

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if document and document.size > 5 * 1024 * 1024:
            raise ValidationError('Attachment must be 5MB or smaller.')
        return document


class ParkingSlotForm(forms.ModelForm):
    class Meta:
        model = ParkingSlot
        fields = ('name', 'community_unit', 'assigned_visitor', 'is_active', 'notes')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_active':
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

    def clean_name(self):
        value = (self.cleaned_data.get('name') or '').strip().upper()
        if not re.match(r'^[A-Z0-9][A-Z0-9\s-]{1,38}$', value):
            raise ValidationError('Use a valid parking slot name, for example BAY 12.')
        return value

    def clean(self):
        cleaned = super().clean()
        assigned_visitor = cleaned.get('assigned_visitor')
        is_active = cleaned.get('is_active')
        if assigned_visitor and not is_active:
            self.add_error('is_active', 'A slot assigned to a visitor must remain active.')
        return cleaned


class WatchlistEntryForm(forms.ModelForm):
    class Meta:
        model = WatchlistEntry
        fields = ('entry_type', 'value', 'reason', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['entry_type'].widget.attrs.update({'class': 'form-select'})
        self.fields['value'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Name, ID, phone, or plate'})
        self.fields['reason'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Reason for watchlist'})
        self.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})

    def clean_value(self):
        entry_type = self.cleaned_data.get('entry_type')
        value = (self.cleaned_data.get('value') or '').strip().upper()
        if entry_type == WatchlistEntry.EntryType.PLATE and not PLATE_RE.match(value):
            raise ValidationError('Enter a valid vehicle plate for plate watchlist entries.')
        if entry_type == WatchlistEntry.EntryType.PERSON and len(value) < 3:
            raise ValidationError('Person watchlist entries must be at least 3 characters.')
        return value

    def clean_reason(self):
        value = (self.cleaned_data.get('reason') or '').strip()
        if len(value) < 5:
            raise ValidationError('Provide a clear reason for the watchlist entry.')
        return value
