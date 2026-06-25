from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserProfile
from accounts.permissions import roles_required
from residents.models import CommunityUnit
from visitors.models import MainGate, Visitor
from .forms import TrafficLogForm
from .models import TrafficLog


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.UNIT_GUARD)
def log_list(request):
    logs = TrafficLog.objects.select_related('resident', 'visitor', 'vehicle', 'community_unit', 'recorded_by')
    query = request.GET.get('q', '').strip()
    subject_type = request.GET.get('subject_type', '').strip()
    direction = request.GET.get('direction', '').strip()
    checkpoint_type = request.GET.get('checkpoint_type', '').strip()
    destination = request.GET.get('destination', '').strip()
    main_gate = request.GET.get('main_gate', '').strip()

    if query:
        logs = logs.filter(
            Q(resident__full_name__icontains=query)
            | Q(visitor__full_name__icontains=query)
            | Q(visitor__vehicle_plate__icontains=query)
            | Q(vehicle__plate_number__icontains=query)
            | Q(gate__icontains=query)
            | Q(community_unit__name__icontains=query)
            | Q(recorded_by__username__icontains=query)
        )
    if subject_type:
        logs = logs.filter(subject_type=subject_type)
    if direction:
        logs = logs.filter(direction=direction)
    if checkpoint_type:
        logs = logs.filter(checkpoint_type=checkpoint_type)
    if destination:
        logs = logs.filter(community_unit_id=destination)
    if main_gate:
        logs = logs.filter(gate=main_gate)

    return render(request, 'traffic_logs/log_list.html', {
        'logs': logs,
        'query': query,
        'subject_type': subject_type,
        'direction': direction,
        'checkpoint_type': checkpoint_type,
        'destination': destination,
        'main_gate': main_gate,
        'subject_types': TrafficLog.SubjectType.choices,
        'directions': TrafficLog.Direction.choices,
        'checkpoint_types': TrafficLog.CheckpointType.choices,
        'destinations': CommunityUnit.objects.filter(is_active=True),
        'main_gates': MainGate.choices,
    })


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD)
def log_create(request):
    form = TrafficLogForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        log = form.save(commit=False)
        log.recorded_by = request.user
        log.save()
        if log.subject_type == TrafficLog.SubjectType.VISITOR and log.visitor:
            if log.direction == TrafficLog.Direction.ENTRY:
                if log.checkpoint_type == TrafficLog.CheckpointType.MAIN_GATE:
                    log.visitor.status = Visitor.Status.ARRIVED_MAIN_GATE
                else:
                    log.visitor.status = Visitor.Status.UNIT_CONFIRMED
            else:
                if log.checkpoint_type == TrafficLog.CheckpointType.MAIN_GATE:
                    log.visitor.status = Visitor.Status.CHECKED_OUT
                else:
                    log.visitor.status = Visitor.Status.UNIT_EXIT_CONFIRMED
            if log.community_unit and not log.visitor.destination_id:
                log.visitor.destination = log.community_unit
            log.visitor.save(update_fields=['status', 'destination'])
        return redirect('traffic_logs:list')
    return render(request, 'traffic_logs/log_form.html', {'form': form, 'title': 'Record Entry/Exit'})


@login_required
@roles_required(UserProfile.Role.ADMIN)
def log_delete(request, pk):
    if request.method != 'POST':
        raise PermissionDenied
    log = get_object_or_404(TrafficLog, pk=pk)
    log.delete()
    return redirect('traffic_logs:list')
