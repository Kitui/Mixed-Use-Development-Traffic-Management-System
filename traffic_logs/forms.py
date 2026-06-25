from django import forms
from django.core.exceptions import ValidationError

from visitors.models import Visitor
from .models import TrafficLog


class TrafficLogForm(forms.ModelForm):
    class Meta:
        model = TrafficLog
        fields = (
            'checkpoint_type',
            'subject_type',
            'direction',
            'resident',
            'visitor',
            'vehicle',
            'gate',
            'community_unit',
            'notes',
        )
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'notes': 'Optional guard notes or context',
        }
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.update({'class': 'form-select'})
            else:
                widget.attrs.update({
                    'class': 'form-control',
                    'placeholder': placeholders.get(name, ''),
                })

    def clean(self):
        cleaned_data = super().clean()
        checkpoint_type = cleaned_data.get('checkpoint_type')
        subject_type = cleaned_data.get('subject_type')
        direction = cleaned_data.get('direction')
        resident = cleaned_data.get('resident')
        visitor = cleaned_data.get('visitor')
        vehicle = cleaned_data.get('vehicle')
        gate = cleaned_data.get('gate')
        community_unit = cleaned_data.get('community_unit')

        required = {
            TrafficLog.SubjectType.RESIDENT: resident,
            TrafficLog.SubjectType.VISITOR: visitor,
            TrafficLog.SubjectType.VEHICLE: vehicle,
        }
        if subject_type and not required.get(subject_type):
            raise ValidationError(f'Select a {subject_type.lower()} for this log.')

        if checkpoint_type == TrafficLog.CheckpointType.MAIN_GATE and not gate:
            self.add_error('gate', 'Select the main gate for main gate logs.')
        if checkpoint_type == TrafficLog.CheckpointType.COMMUNITY_UNIT and not community_unit:
            self.add_error('community_unit', 'Select the estate/company for internal logs.')
        if subject_type == TrafficLog.SubjectType.RESIDENT and (visitor or vehicle):
            raise ValidationError('Resident logs should not also select visitor or vehicle subjects.')
        if subject_type == TrafficLog.SubjectType.VISITOR and (resident or vehicle):
            raise ValidationError('Visitor logs should not also select resident or vehicle subjects.')
        if subject_type == TrafficLog.SubjectType.VEHICLE and (resident or visitor):
            raise ValidationError('Vehicle logs should not also select resident or visitor subjects.')
        if vehicle and not vehicle.is_active:
            self.add_error('vehicle', 'Select an active vehicle.')
        if resident and not resident.is_active:
            self.add_error('resident', 'Select an active resident/employee.')

        if subject_type == TrafficLog.SubjectType.VISITOR and visitor:
            if direction == TrafficLog.Direction.ENTRY:
                if checkpoint_type == TrafficLog.CheckpointType.MAIN_GATE and visitor.status != Visitor.Status.APPROVED:
                    raise ValidationError('Main gate entry is allowed only after resident/company approval.')
                if checkpoint_type == TrafficLog.CheckpointType.COMMUNITY_UNIT and visitor.status not in {
                    Visitor.Status.ARRIVED_MAIN_GATE,
                    Visitor.Status.REDIRECTED,
                }:
                    raise ValidationError('Estate/company entry requires approval, main gate arrival, or redirection.')
                if checkpoint_type == TrafficLog.CheckpointType.COMMUNITY_UNIT and not community_unit:
                    raise ValidationError('Select the destination estate/company for internal check-in.')
            if direction == TrafficLog.Direction.EXIT:
                if checkpoint_type == TrafficLog.CheckpointType.COMMUNITY_UNIT and visitor.status != Visitor.Status.CHECKED_IN:
                    raise ValidationError('Checkout can be requested only after resident/company confirmed check-in.')
                if checkpoint_type == TrafficLog.CheckpointType.MAIN_GATE and visitor.status != Visitor.Status.UNIT_EXIT_CONFIRMED:
                    raise ValidationError('Main gate checkout is allowed only after unit guard releases the visitor.')

        return cleaned_data
