import csv
from io import StringIO
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import ExtractHour, TruncDate
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import UserProfile
from accounts.permissions import is_receptionist, is_resident, roles_required
from .forms import GateVisitorRequestForm, MainGateResidentMovementForm, SystemSettingsForm, UnitResidentMovementForm
from .models import SystemSettings
from residents.models import CommunityUnit, Resident
from traffic_logs.models import TrafficLog
from vehicles.models import Vehicle
from visitors.models import MainGate, Notification, Visitor, VisitorEvent


def _choice_label(choices, value):
    return dict(choices).get(value, value or '-')


def _simple_pdf_response(filename, title, lines):
    def esc(value):
        return str(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    text_ops = ['BT', '/F1 18 Tf', '72 760 Td', f'({esc(title)}) Tj', '/F1 11 Tf']
    for line in lines[:34]:
        text_ops.append('0 -18 Td')
        text_ops.append(f'({esc(line)}) Tj')
    text_ops.append('ET')
    stream = '\n'.join(text_ops)
    objects = [
        '1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj',
        '2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj',
        '3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj',
        '4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj',
        f'5 0 obj << /Length {len(stream.encode("utf-8"))} >> stream\n{stream}\nendstream endobj',
    ]
    pdf = ['%PDF-1.4']
    offsets = [0]
    for obj in objects:
        offsets.append(sum(len(part.encode('utf-8')) + 1 for part in pdf))
        pdf.append(obj)
    xref_start = sum(len(part.encode('utf-8')) + 1 for part in pdf)
    pdf.extend(['xref', f'0 {len(objects) + 1}', '0000000000 65535 f '])
    pdf.extend(f'{offset:010d} 00000 n ' for offset in offsets[1:])
    pdf.extend([f'trailer << /Size {len(objects) + 1} /Root 1 0 R >>', 'startxref', str(xref_start), '%%EOF'])
    response = HttpResponse('\n'.join(pdf).encode('utf-8'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _gate_counts():
    return [
        {
            'value': value,
            'label': label,
            'entries': TrafficLog.objects.filter(gate=value, direction=TrafficLog.Direction.ENTRY).count(),
            'exits': TrafficLog.objects.filter(gate=value, direction=TrafficLog.Direction.EXIT).count(),
            'waiting': Visitor.objects.filter(main_gate=value, status__in=[Visitor.Status.APPROVED, Visitor.Status.UNIT_EXIT_CONFIRMED]).count(),
        }
        for value, label in MainGate.choices
    ]


def _receptionist_unit(user):
    if not is_receptionist(user):
        return None
    person = Resident.objects.select_related('community_unit').filter(user=user).first()
    return person.community_unit if person else None


@login_required
def home(request):
    try:
        if not request.user.is_superuser and request.user.userprofile.role == UserProfile.Role.UNIT_GUARD:
            return redirect('dashboard:tasks')
        if not request.user.is_superuser and request.user.userprofile.role == UserProfile.Role.MAIN_GATE_GUARD:
            return redirect('dashboard:gate_tasks')
    except UserProfile.DoesNotExist:
        pass

    visitor_queryset = Visitor.objects.select_related('host', 'destination')
    recent_logs = TrafficLog.objects.select_related('resident', 'visitor', 'visitor__destination', 'vehicle', 'community_unit', 'recorded_by')
    if is_resident(request.user):
        visitor_queryset = visitor_queryset.filter(host__user=request.user)
        recent_logs = recent_logs.filter(visitor__host__user=request.user)

    today = timezone.localdate()
    inside_statuses = [
        Visitor.Status.ARRIVED_MAIN_GATE,
        Visitor.Status.REDIRECTED,
        Visitor.Status.UNIT_CONFIRMED,
        Visitor.Status.CHECKED_IN,
        Visitor.Status.CHECKOUT_REQUESTED,
        Visitor.Status.UNIT_EXIT_CONFIRMED,
    ]
    overdue_visitors = visitor_queryset.filter(
        expected_departure__lt=timezone.now(),
        status__in=inside_statuses,
    )
    status_counts = [
        {
            'label': _choice_label(Visitor.Status.choices, row['status']),
            'status': row['status'],
            'total': row['total'],
        }
        for row in visitor_queryset.values('status').annotate(total=Count('id')).order_by('status')
    ]
    max_status_count = max([row['total'] for row in status_counts] or [1])
    for row in status_counts:
        row['percent'] = int((row['total'] / max_status_count) * 100)

    gate_rows = [
        {
            'label': _choice_label(MainGate.choices, row['main_gate']),
            'total': row['total'],
        }
        for row in visitor_queryset.exclude(main_gate='').values('main_gate').annotate(total=Count('id')).order_by('main_gate')
    ]
    max_gate_count = max([row['total'] for row in gate_rows] or [1])
    for row in gate_rows:
        row['percent'] = int((row['total'] / max_gate_count) * 100)

    entry_total = recent_logs.filter(direction=TrafficLog.Direction.ENTRY).count()
    exit_total = recent_logs.filter(direction=TrafficLog.Direction.EXIT).count()
    max_direction_count = max(entry_total, exit_total, 1)

    context = {
        'resident_count': Resident.objects.filter(is_active=True).count(),
        'visitor_count': visitor_queryset.count(),
        'pending_visitors': visitor_queryset.filter(status=Visitor.Status.PENDING).count(),
        'vehicle_count': Vehicle.objects.filter(is_active=True).count(),
        'entry_count': recent_logs.filter(direction=TrafficLog.Direction.ENTRY).count(),
        'exit_count': recent_logs.filter(direction=TrafficLog.Direction.EXIT).count(),
        'today_arrivals': visitor_queryset.filter(expected_arrival__date=today).count(),
        'inside_count': visitor_queryset.filter(status__in=inside_statuses).count(),
        'overdue_count': overdue_visitors.count(),
        'incident_count': visitor_queryset.filter(incident_flagged=True).count(),
        'recurring_count': visitor_queryset.exclude(recurrence=Visitor.Recurrence.NONE).count(),
        'entry_exit_chart': [
            {'label': 'Entries', 'total': entry_total, 'percent': int((entry_total / max_direction_count) * 100), 'class': 'chart-entry'},
            {'label': 'Exits', 'total': exit_total, 'percent': int((exit_total / max_direction_count) * 100), 'class': 'chart-exit'},
        ],
        'status_counts': status_counts,
        'gate_rows': gate_rows,
        'recent_logs': recent_logs[:8],
        'pending_approvals': visitor_queryset.filter(status=Visitor.Status.PENDING)[:8],
        'recent_bookings': visitor_queryset[:8],
    }
    return render(request, 'dashboard/home.html', context)


@login_required
@roles_required(UserProfile.Role.ADMIN)
def system_settings(request):
    settings = SystemSettings.current()
    form = SystemSettingsForm(request.POST or None, instance=settings)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'System settings updated.')
        return redirect('dashboard:settings')
    return render(request, 'dashboard/settings.html', {'form': form, 'settings_obj': settings})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.UNIT_GUARD)
def tasks(request):
    arrivals = Visitor.objects.select_related('host', 'destination').filter(
        status__in=[Visitor.Status.ARRIVED_MAIN_GATE, Visitor.Status.REDIRECTED],
    )
    exits = Visitor.objects.select_related('host', 'destination').filter(
        status=Visitor.Status.CHECKOUT_REQUESTED,
    )
    return render(request, 'dashboard/tasks.html', {
        'arrivals': arrivals,
        'exits': exits,
        'destinations': CommunityUnit.objects.filter(is_active=True),
        'movement_form': UnitResidentMovementForm(),
        'registered_vehicles': UnitResidentMovementForm().fields['vehicle'].queryset,
        'arrival_count': arrivals.count(),
        'exit_count': exits.count(),
    })


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.UNIT_GUARD)
def record_unit_movement(request):
    if request.method != 'POST':
        return redirect('dashboard:tasks')

    form = UnitResidentMovementForm(request.POST)
    if form.is_valid():
        vehicle = form.cleaned_data['vehicle']
        direction = form.cleaned_data['direction']
        owner = vehicle.resident_owner
        notes = (
            'Unit guard confirmed resident/employee entry after main gate record.'
            if direction == TrafficLog.Direction.ENTRY
            else 'Unit guard recorded resident/employee exit for main gate confirmation.'
        )
        TrafficLog.objects.create(
            checkpoint_type=TrafficLog.CheckpointType.COMMUNITY_UNIT,
            subject_type=TrafficLog.SubjectType.VEHICLE,
            direction=direction,
            resident=owner,
            vehicle=vehicle,
            community_unit=owner.community_unit if owner else None,
            recorded_by=request.user,
            notes=notes,
        )
        messages.success(request, 'Unit movement recorded.')
    else:
        error_text = '; '.join(error for errors in form.errors.values() for error in errors)
        messages.error(request, f'Please correct the unit movement form: {error_text}')
    return redirect('dashboard:tasks')


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD)
def gate_tasks(request):
    approved_visitors = Visitor.objects.select_related('host', 'destination').filter(
        status=Visitor.Status.APPROVED,
    )
    released_visitors = Visitor.objects.select_related('host', 'destination').filter(
        status=Visitor.Status.UNIT_EXIT_CONFIRMED,
    )
    return render(request, 'dashboard/gate_tasks.html', {
        'movement_form': MainGateResidentMovementForm(),
        'visitor_request_form': GateVisitorRequestForm(),
        'registered_vehicles': MainGateResidentMovementForm().fields['vehicle'].queryset,
        'approved_visitors': approved_visitors,
        'released_visitors': released_visitors,
        'approved_count': approved_visitors.count(),
        'released_count': released_visitors.count(),
    })


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD)
def record_gate_movement(request):
    if request.method != 'POST':
        return redirect('dashboard:gate_tasks')

    form = MainGateResidentMovementForm(request.POST)
    if form.is_valid():
        vehicle = form.cleaned_data['vehicle']
        direction = form.cleaned_data['direction']
        gate = form.cleaned_data['gate']
        owner = vehicle.resident_owner
        notes = (
            'Main gate guard recorded resident/employee entry into community.'
            if direction == TrafficLog.Direction.ENTRY
            else 'Main gate guard recorded resident/employee final exit from community.'
        )
        TrafficLog.objects.create(
            checkpoint_type=TrafficLog.CheckpointType.MAIN_GATE,
            subject_type=TrafficLog.SubjectType.VEHICLE,
            direction=direction,
            resident=owner,
            vehicle=vehicle,
            gate=gate,
            community_unit=owner.community_unit if owner else None,
            recorded_by=request.user,
            notes=notes,
        )
        messages.success(request, 'Main gate movement recorded.')
    else:
        error_text = '; '.join(error for errors in form.errors.values() for error in errors)
        messages.error(request, f'Please correct the gate movement form: {error_text}')
    return redirect('dashboard:gate_tasks')


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD)
def create_gate_visitor_request(request):
    if request.method != 'POST':
        return redirect('dashboard:gate_tasks')

    form = GateVisitorRequestForm(request.POST)
    if form.is_valid():
        visitor = form.save(commit=False)
        visitor.status = Visitor.Status.PENDING
        visitor.alert_sent = True
        if visitor.host and not visitor.destination_id:
            visitor.destination = visitor.host.community_unit
        visitor.save()
        VisitorEvent.objects.create(
            visitor=visitor,
            actor=request.user,
            title='Main gate request created',
            note='Guard submitted visitor request for host approval',
            status=visitor.status,
        )
        if visitor.host and visitor.host.user:
            Notification.objects.create(
                user=visitor.host.user,
                visitor=visitor,
                title='Visitor approval needed',
                message=f'{visitor.full_name} is waiting at the main gate for approval.',
            )
        messages.success(request, 'Visitor request sent for approval.')
    else:
        error_text = '; '.join(error for errors in form.errors.values() for error in errors)
        messages.error(request, f'Please correct the visitor request form: {error_text}')
    return redirect('dashboard:gate_tasks')


def _date_range(request):
    today = timezone.localdate()
    start = request.GET.get('start') or today.replace(day=1).isoformat()
    end = request.GET.get('end') or today.isoformat()
    return start, end


def _filtered_logs(start, end):
    return TrafficLog.objects.select_related(
        'resident',
        'visitor',
        'vehicle',
        'community_unit',
        'recorded_by',
    ).filter(recorded_at__date__gte=start, recorded_at__date__lte=end)


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.UNIT_GUARD)
def reports(request):
    start, end = _date_range(request)
    logs = _filtered_logs(start, end)

    daily_logs_raw = (
        logs.annotate(day=TruncDate('recorded_at'))
        .values('day', 'direction')
        .annotate(total=Count('id'))
        .order_by('day', 'direction')
    )
    daily_logs = [
        {
            'day': row['day'],
            'direction': _choice_label(TrafficLog.Direction.choices, row['direction']),
            'total': row['total'],
        }
        for row in daily_logs_raw
    ]
    visitor_statuses = [
        {
            'status': _choice_label(Visitor.Status.choices, row['status']),
            'total': row['total'],
        }
        for row in Visitor.objects.values('status').annotate(total=Count('id')).order_by('status')
    ]
    guest_types = [
        {
            'guest_type': _choice_label(Visitor.GuestType.choices, row['guest_type']),
            'total': row['total'],
        }
        for row in Visitor.objects.values('guest_type').annotate(total=Count('id')).order_by('guest_type')
    ]
    destination_activity = Visitor.objects.values('destination__name').annotate(total=Count('id')).order_by('destination__name')
    vehicle_types = [
        {
            'vehicle_type': _choice_label(Vehicle.VehicleType.choices, row['vehicle_type']),
            'total': row['total'],
        }
        for row in Vehicle.objects.values('vehicle_type').annotate(total=Count('id')).order_by('vehicle_type')
    ]
    gate_activity = [
        {
            'checkpoint_type': _choice_label(TrafficLog.CheckpointType.choices, row['checkpoint_type']),
            'gate': _choice_label(TrafficLog._meta.get_field('gate').choices, row['gate']) if row['gate'] else '-',
            'community_unit__name': row['community_unit__name'] or '-',
            'direction': _choice_label(TrafficLog.Direction.choices, row['direction']),
            'total': row['total'],
        }
        for row in logs.values('checkpoint_type', 'gate', 'community_unit__name', 'direction').annotate(total=Count('id')).order_by('checkpoint_type', 'gate', 'direction')
    ]
    gate_summary_map = {}
    for row in logs.values('checkpoint_type', 'gate', 'community_unit__name', 'direction').annotate(total=Count('id')).order_by('checkpoint_type', 'gate', 'community_unit__name'):
        key = (
            _choice_label(TrafficLog.CheckpointType.choices, row['checkpoint_type']),
            _choice_label(TrafficLog._meta.get_field('gate').choices, row['gate']) if row['gate'] else '-',
            row['community_unit__name'] or '-',
        )
        if key not in gate_summary_map:
            gate_label = key[2] if row['checkpoint_type'] == TrafficLog.CheckpointType.COMMUNITY_UNIT and key[1] == '-' else key[1]
            gate_summary_map[key] = {
                'checkpoint_type': key[0],
                'gate': gate_label,
                'destination': key[2],
                'entries': 0,
                'exits': 0,
            }
        if row['direction'] == TrafficLog.Direction.ENTRY:
            gate_summary_map[key]['entries'] = row['total']
        elif row['direction'] == TrafficLog.Direction.EXIT:
            gate_summary_map[key]['exits'] = row['total']
    gate_activity_summary = []
    for row in gate_summary_map.values():
        row['total'] = row['entries'] + row['exits']
        gate_activity_summary.append(row)
    stacked_gate_rows = list(
        logs.values('gate', 'community_unit__unit_type')
        .annotate(total=Count('id'))
        .order_by('gate', 'community_unit__unit_type')
    )
    stacked_gate_labels = []
    stacked_gate_map = {}
    for row in stacked_gate_rows:
        gate_label = _choice_label(TrafficLog._meta.get_field('gate').choices, row['gate']) if row['gate'] else 'Estate/Company'
        if gate_label not in stacked_gate_labels:
            stacked_gate_labels.append(gate_label)
        unit_type = row['community_unit__unit_type'] or 'UNASSIGNED'
        stacked_gate_map[(gate_label, unit_type)] = row['total']
    hourly_rows = list(
        logs.annotate(hour=ExtractHour('recorded_at'))
        .values('hour')
        .annotate(total=Count('id'))
        .order_by('hour')
    )
    hourly_map = {row['hour']: row['total'] for row in hourly_rows}
    hourly_activity = [
        {'hour': f'{hour:02d}:00', 'total': hourly_map.get(hour, 0)}
        for hour in range(24)
    ]
    vehicle_classes = [
        {
            'vehicle_class': _choice_label(Vehicle.VehicleClass.choices, row['vehicle_class']),
            'total': row['total'],
        }
        for row in Vehicle.objects.values('vehicle_class').annotate(total=Count('id')).order_by('vehicle_class')
    ]
    gate_workload_rows = list(
        logs.values('gate', 'direction')
        .annotate(total=Count('id'))
        .order_by('gate', 'direction')
    )
    gate_workload_labels = []
    gate_workload_map = {}
    for row in gate_workload_rows:
        gate_label = _choice_label(TrafficLog._meta.get_field('gate').choices, row['gate']) if row['gate'] else 'Estate/Company'
        if gate_label not in gate_workload_labels:
            gate_workload_labels.append(gate_label)
        gate_workload_map[(gate_label, row['direction'])] = row['total']
    destination_chart_rows = [
        {
            'destination': row['destination__name'] or 'Unassigned',
            'total': row['total'],
        }
        for row in destination_activity[:8]
    ]

    context = {
        'start': start,
        'end': end,
        'log_count': logs.count(),
        'entry_count': logs.filter(direction=TrafficLog.Direction.ENTRY).count(),
        'exit_count': logs.filter(direction=TrafficLog.Direction.EXIT).count(),
        'visitor_count': Visitor.objects.count(),
        'vehicle_count': Vehicle.objects.count(),
        'resident_count': Resident.objects.filter(is_active=True).count(),
        'daily_logs': daily_logs,
        'visitor_statuses': visitor_statuses,
        'guest_types': guest_types,
        'destination_activity': destination_activity,
        'vehicle_types': vehicle_types,
        'gate_activity': gate_activity,
        'gate_activity_summary': gate_activity_summary,
        'daily_chart_json': {
            'labels': [str(row['day']) for row in daily_logs],
            'values': [row['total'] for row in daily_logs],
            'directions': [row['direction'] for row in daily_logs],
        },
        'visitor_status_chart_json': {
            'labels': [row['status'] for row in visitor_statuses],
            'values': [row['total'] for row in visitor_statuses],
        },
        'gate_activity_chart_json': {
            'labels': stacked_gate_labels,
            'residential': [stacked_gate_map.get((label, CommunityUnit.UnitType.RESIDENTIAL), 0) for label in stacked_gate_labels],
            'commercial': [stacked_gate_map.get((label, CommunityUnit.UnitType.COMMERCIAL), 0) for label in stacked_gate_labels],
            'unassigned': [stacked_gate_map.get((label, 'UNASSIGNED'), 0) for label in stacked_gate_labels],
        },
        'hourly_activity_chart_json': {
            'labels': [row['hour'] for row in hourly_activity],
            'values': [row['total'] for row in hourly_activity],
        },
        'guest_type_chart_json': {
            'labels': [row['guest_type'] for row in guest_types],
            'values': [row['total'] for row in guest_types],
        },
        'vehicle_class_chart_json': {
            'labels': [row['vehicle_class'] for row in vehicle_classes],
            'values': [row['total'] for row in vehicle_classes],
        },
        'destination_load_chart_json': {
            'labels': [row['destination'] for row in destination_chart_rows],
            'values': [row['total'] for row in destination_chart_rows],
        },
        'gate_workload_chart_json': {
            'labels': gate_workload_labels,
            'entries': [gate_workload_map.get((label, TrafficLog.Direction.ENTRY), 0) for label in gate_workload_labels],
            'exits': [gate_workload_map.get((label, TrafficLog.Direction.EXIT), 0) for label in gate_workload_labels],
        },
    }
    return render(request, 'dashboard/reports.html', context)


@login_required
def notifications(request):
    notes = Notification.objects.select_related('visitor').filter(user=request.user)
    return render(request, 'dashboard/notifications.html', {'notifications': notes})


@login_required
def mark_notification_read(request, pk):
    if request.method != 'POST':
        raise PermissionDenied
    note = Notification.objects.get(pk=pk, user=request.user)
    note.is_read = True
    note.save(update_fields=['is_read'])
    if note.visitor_id:
        return redirect('visitors:detail', pk=note.visitor_id)
    return redirect('dashboard:notifications')


@login_required
def global_search(request):
    query = request.GET.get('q', '').strip()
    visitors = Visitor.objects.select_related('host', 'destination').none()
    residents = Resident.objects.select_related('community_unit').none()
    vehicles = Vehicle.objects.select_related('resident_owner', 'visitor_owner').none()
    logs = TrafficLog.objects.select_related('resident', 'visitor', 'vehicle', 'community_unit').none()

    if query:
        visitor_results = Visitor.objects.select_related('host', 'destination').filter(
            Q(full_name__icontains=query)
            | Q(id_number__icontains=query)
            | Q(phone__icontains=query)
            | Q(host__full_name__icontains=query)
            | Q(host__house_number__icontains=query)
            | Q(destination__name__icontains=query)
            | Q(vehicle_plate__icontains=query)
            | Q(purpose__icontains=query)
        )
        if is_resident(request.user):
            visitor_results = visitor_results.filter(host__user=request.user)
        visitors = visitor_results[:8]
        if request.user.is_superuser:
            residents = Resident.objects.select_related('community_unit').filter(
                Q(full_name__icontains=query) | Q(house_number__icontains=query) | Q(phone__icontains=query) | Q(email__icontains=query)
            )[:8]
            vehicles = Vehicle.objects.select_related('resident_owner', 'visitor_owner').filter(
                Q(plate_number__icontains=query)
                | Q(make_model__icontains=query)
                | Q(color__icontains=query)
                | Q(resident_owner__full_name__icontains=query)
                | Q(visitor_owner__full_name__icontains=query)
            )[:8]
        if not is_resident(request.user):
            logs = TrafficLog.objects.select_related('resident', 'visitor', 'vehicle', 'community_unit').filter(
                Q(resident__full_name__icontains=query)
                | Q(visitor__full_name__icontains=query)
                | Q(vehicle__plate_number__icontains=query)
                | Q(notes__icontains=query)
                | Q(community_unit__name__icontains=query)
            )[:8]

    return render(request, 'dashboard/search.html', {
        'query': query,
        'visitors': visitors,
        'residents': residents,
        'vehicles': vehicles,
        'logs': logs,
    })


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.UNIT_GUARD)
def handoff(request):
    query = request.GET.get('q', '').strip()
    visitor = None
    if query:
        visitor = Visitor.objects.select_related('host', 'destination').filter(
            Q(full_name__icontains=query) | Q(phone__icontains=query) | Q(id_number__icontains=query) | Q(vehicle_plate__icontains=query)
        ).first()
    return render(request, 'dashboard/handoff.html', {'query': query, 'visitor': visitor})


@login_required
def expected_calendar(request):
    visitors = Visitor.objects.select_related('host', 'destination').exclude(status=Visitor.Status.CHECKED_OUT)
    if is_resident(request.user):
        visitors = visitors.filter(host__user=request.user)
    visitors = visitors.order_by('expected_arrival', 'created_at')[:100]
    return render(request, 'dashboard/calendar.html', {'visitors': visitors})


@login_required
def workflow_board(request):
    visitors = Visitor.objects.select_related('host', 'destination')
    if is_resident(request.user):
        visitors = visitors.filter(host__user=request.user)
    columns = [
        (Visitor.Status.PENDING, 'Pending Approval'),
        (Visitor.Status.APPROVED, 'Approved'),
        (Visitor.Status.ARRIVED_MAIN_GATE, 'Main Gate'),
        (Visitor.Status.UNIT_CONFIRMED, 'Unit Gate'),
        (Visitor.Status.CHECKED_IN, 'Checked In'),
        (Visitor.Status.CHECKOUT_REQUESTED, 'Checkout'),
        (Visitor.Status.UNIT_EXIT_CONFIRMED, 'Released'),
        (Visitor.Status.CHECKED_OUT, 'Checked Out'),
    ]
    board = [{'status': status, 'label': label, 'visitors': visitors.filter(status=status)[:20]} for status, label in columns]
    return render(request, 'dashboard/board.html', {'board': board})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.UNIT_GUARD)
def gate_summary(request):
    return render(request, 'dashboard/gate_summary.html', {'gates': _gate_counts()})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.RECEPTIONIST)
def bulk_import(request):
    result = None
    company_unit = _receptionist_unit(request.user)
    if request.method == 'POST' and request.FILES.get('csv_file'):
        target = request.POST.get('target')
        content = request.FILES['csv_file'].read().decode('utf-8-sig')
        reader = csv.DictReader(StringIO(content))
        created = 0
        for row in reader:
            if target == 'residents':
                house_number = row.get('house_number') or row.get('house') or row.get('office')
                if not house_number:
                    continue
                if company_unit:
                    unit = company_unit
                    person_type = Resident.PersonType.EMPLOYEE
                else:
                    unit, _ = CommunityUnit.objects.get_or_create(
                        name=row.get('community_unit') or 'Unassigned',
                        defaults={'unit_type': CommunityUnit.UnitType.RESIDENTIAL},
                    )
                    person_type = row.get('person_type') or Resident.PersonType.RESIDENT
                Resident.objects.update_or_create(
                    house_number=house_number,
                    defaults={
                        'community_unit': unit,
                        'full_name': row.get('full_name') or row.get('name') or 'Unnamed',
                        'phone': row.get('phone') or '',
                        'email': row.get('email') or '',
                        'person_type': person_type,
                        'is_active': True,
                    },
                )
                created += 1
            elif target == 'vehicles':
                plate_number = row.get('plate_number') or row.get('plate')
                if not plate_number:
                    continue
                owner = Resident.objects.filter(house_number=row.get('house_number') or row.get('owner_house')).first()
                if company_unit:
                    owner = Resident.objects.filter(
                        house_number=row.get('house_number') or row.get('owner_house'),
                        community_unit=company_unit,
                        person_type=Resident.PersonType.EMPLOYEE,
                    ).first()
                Vehicle.objects.update_or_create(
                    plate_number=plate_number,
                    defaults={
                        'resident_owner': owner,
                        'vehicle_type': Vehicle.VehicleType.RESIDENT if company_unit else row.get('vehicle_type') or Vehicle.VehicleType.RESIDENT,
                        'vehicle_class': row.get('vehicle_class') or Vehicle.VehicleClass.CAR,
                        'make_model': row.get('make_model') or '',
                        'color': row.get('color') or '',
                        'is_active': True,
                    },
                )
                created += 1
        result = f'Imported/updated {created} {target} rows.'
    return render(request, 'dashboard/bulk_import.html', {'result': result, 'company_unit': company_unit})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.UNIT_GUARD)
def reports_pdf(request):
    start, end = _date_range(request)
    logs = _filtered_logs(start, end)
    lines = [
        f'Date range: {start} to {end}',
        f'Logs: {logs.count()}',
        f'Entries: {logs.filter(direction=TrafficLog.Direction.ENTRY).count()}',
        f'Exits: {logs.filter(direction=TrafficLog.Direction.EXIT).count()}',
        f'Visitors: {Visitor.objects.count()}',
        f'Vehicles: {Vehicle.objects.count()}',
        f'Residents: {Resident.objects.filter(is_active=True).count()}',
        '',
        'Gate Summary:',
    ]
    for gate in _gate_counts():
        lines.append(f"{gate['label']}: entries {gate['entries']}, exits {gate['exits']}, waiting {gate['waiting']}")
    return _simple_pdf_response(f'tilisi_report_{start}_to_{end}.pdf', 'Tilisi Traffic Report', lines)


def _csv_response(filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.UNIT_GUARD)
def export_logs_csv(request):
    start, end = _date_range(request)
    response = _csv_response(f'traffic_logs_{start}_to_{end}.csv')
    writer = csv.writer(response)
    writer.writerow(['Time', 'Checkpoint', 'Subject Type', 'Direction', 'Resident', 'Visitor', 'Vehicle', 'Gate', 'Destination', 'Guard', 'Notes'])

    for log in _filtered_logs(start, end):
        writer.writerow([
            timezone.localtime(log.recorded_at).strftime('%Y-%m-%d %H:%M:%S'),
            log.get_checkpoint_type_display(),
            log.get_subject_type_display(),
            log.get_direction_display(),
            log.resident or '',
            log.visitor or '',
            log.vehicle or '',
            log.get_gate_display() if log.gate else '',
            log.community_unit or '',
            log.recorded_by or '',
            log.notes,
        ])
    return response


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.UNIT_GUARD)
def export_visitors_csv(request):
    response = _csv_response('visitors.csv')
    writer = csv.writer(response)
    writer.writerow(['Name', 'Guest Type', 'ID Number', 'Phone', 'Host', 'Destination', 'Purpose', 'Company', 'Vehicle Class', 'Vehicle Plate', 'Main Gate', 'Alert Sent', 'Expected Arrival', 'Status', 'Created At'])

    visitors = Visitor.objects.select_related('host', 'destination')
    for visitor in visitors:
        writer.writerow([
            visitor.full_name,
            visitor.get_guest_type_display(),
            visitor.id_number,
            visitor.phone,
            visitor.host,
            visitor.destination or '',
            visitor.purpose,
            visitor.company_name,
            visitor.get_vehicle_class_display() if visitor.vehicle_class else '',
            visitor.vehicle_plate,
            visitor.get_main_gate_display() if visitor.main_gate else '',
            'Yes' if visitor.alert_sent else 'No',
            visitor.expected_arrival or '',
            visitor.get_status_display(),
            timezone.localtime(visitor.created_at).strftime('%Y-%m-%d %H:%M:%S'),
        ])
    return response


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.UNIT_GUARD)
def export_vehicles_csv(request):
    response = _csv_response('vehicles.csv')
    writer = csv.writer(response)
    writer.writerow(['Plate Number', 'Type', 'Class', 'Resident Owner', 'Visitor Owner', 'Make/Model', 'Color', 'Active'])

    vehicles = Vehicle.objects.select_related('resident_owner', 'visitor_owner')
    for vehicle in vehicles:
        writer.writerow([
            vehicle.plate_number,
            vehicle.get_vehicle_type_display(),
            vehicle.get_vehicle_class_display(),
            vehicle.resident_owner or '',
            vehicle.visitor_owner or '',
            vehicle.make_model,
            vehicle.color,
            'Yes' if vehicle.is_active else 'No',
        ])
    return response
