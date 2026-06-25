from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import UserProfile
from accounts.permissions import is_main_gate_guard, is_resident, is_unit_guard, roles_required
from residents.models import CommunityUnit, Resident
from traffic_logs.models import TrafficLog
from .forms import ParkingSlotForm, VisitorAttachmentForm, VisitorForm, WatchlistEntryForm
from .models import MainGate, Notification, ParkingSlot, Visitor, VisitorAttachment, VisitorEvent, WatchlistEntry


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


ANY_VISITOR_ROLE = (
    UserProfile.Role.ADMIN,
    UserProfile.Role.SECURITY,
    UserProfile.Role.RESIDENT,
    UserProfile.Role.RECEPTIONIST,
)

VISITOR_VIEW_ROLE = (
    UserProfile.Role.ADMIN,
    UserProfile.Role.SECURITY,
    UserProfile.Role.RESIDENT,
    UserProfile.Role.RECEPTIONIST,
    UserProfile.Role.MAIN_GATE_GUARD,
    UserProfile.Role.UNIT_GUARD,
)

HOST_APPROVAL_ROLE = (
    UserProfile.Role.ADMIN,
    UserProfile.Role.RESIDENT,
    UserProfile.Role.RECEPTIONIST,
)

MAIN_GATE_ROLE = (
    UserProfile.Role.ADMIN,
    UserProfile.Role.SECURITY,
    UserProfile.Role.MAIN_GATE_GUARD,
)

UNIT_GATE_ROLE = (
    UserProfile.Role.ADMIN,
    UserProfile.Role.SECURITY,
    UserProfile.Role.UNIT_GUARD,
    UserProfile.Role.RESIDENT,
    UserProfile.Role.RECEPTIONIST,
)


def _users_with_roles(*roles):
    User = get_user_model()
    return User.objects.filter(userprofile__role__in=roles, is_active=True)


def _notify(users, title, message, visitor=None):
    notifications = [
        Notification(user=user, visitor=visitor, title=title, message=message)
        for user in users
        if user and user.is_active
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


def _event(visitor, request, title, note='', status=None):
    VisitorEvent.objects.create(
        visitor=visitor,
        actor=request.user if request.user.is_authenticated else None,
        title=title,
        note=note,
        status=status or visitor.status,
    )


def _notify_host(visitor, title, message):
    if visitor.host and visitor.host.user:
        _notify([visitor.host.user], title, message, visitor)


def _notify_main_gate(visitor, title, message):
    _notify(_users_with_roles(UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.SECURITY), title, message, visitor)


def _notify_unit_guard(visitor, title, message):
    _notify(_users_with_roles(UserProfile.Role.UNIT_GUARD, UserProfile.Role.SECURITY), title, message, visitor)


def _workflow_redirect(user):
    if is_main_gate_guard(user):
        return redirect('dashboard:gate_tasks')
    if is_unit_guard(user):
        return redirect('dashboard:tasks')
    return redirect('visitors:list')


def _matching_watchlist(visitor):
    terms = [visitor.full_name, visitor.id_number, visitor.phone, visitor.vehicle_plate]
    return WatchlistEntry.objects.filter(is_active=True).filter(
        Q(entry_type=WatchlistEntry.EntryType.PERSON, value__in=[term for term in terms[:3] if term])
        | Q(entry_type=WatchlistEntry.EntryType.PLATE, value=visitor.vehicle_plate)
    )


def _create_recurring_visits(visitor, request):
    if visitor.recurrence == Visitor.Recurrence.NONE or not visitor.expected_arrival or not visitor.recurrence_until:
        return 0
    delta = {
        Visitor.Recurrence.DAILY: timedelta(days=1),
        Visitor.Recurrence.WEEKLY: timedelta(days=7),
        Visitor.Recurrence.MONTHLY: timedelta(days=30),
    }.get(visitor.recurrence)
    if not delta:
        return 0
    count = 0
    next_arrival = visitor.expected_arrival + delta
    while next_arrival.date() <= visitor.recurrence_until and count < 24:
        Visitor.objects.create(
            guest_type=visitor.guest_type,
            full_name=visitor.full_name,
            id_number=visitor.id_number,
            phone=visitor.phone,
            host=visitor.host,
            destination=visitor.destination,
            purpose=visitor.purpose,
            company_name=visitor.company_name,
            vehicle_class=visitor.vehicle_class,
            vehicle_plate=visitor.vehicle_plate,
            vehicle_make_model=visitor.vehicle_make_model,
            vehicle_color=visitor.vehicle_color,
            main_gate=visitor.main_gate,
            expected_arrival=next_arrival,
            expected_departure=visitor.expected_departure + (next_arrival - visitor.expected_arrival) if visitor.expected_departure else None,
            status=visitor.status,
            recurrence=Visitor.Recurrence.NONE,
        )
        count += 1
        next_arrival += delta
    if count:
        _event(visitor, request, 'Recurring visits created', f'{count} follow-up bookings generated')
    return count


@login_required
@roles_required(*ANY_VISITOR_ROLE)
def visitor_list(request):
    visitors = Visitor.objects.select_related('host', 'destination')
    if is_resident(request.user):
        visitors = visitors.filter(host__user=request.user)

    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    guest_type = request.GET.get('guest_type', '').strip()
    destination = request.GET.get('destination', '').strip()
    main_gate = request.GET.get('main_gate', '').strip()
    if query:
        visitors = visitors.filter(
            Q(full_name__icontains=query)
            | Q(id_number__icontains=query)
            | Q(phone__icontains=query)
            | Q(host__full_name__icontains=query)
            | Q(host__house_number__icontains=query)
            | Q(destination__name__icontains=query)
            | Q(vehicle_plate__icontains=query)
            | Q(purpose__icontains=query)
        )
    if status:
        visitors = visitors.filter(status=status)
    if guest_type:
        visitors = visitors.filter(guest_type=guest_type)
    if destination:
        visitors = visitors.filter(destination_id=destination)
    if main_gate:
        visitors = visitors.filter(main_gate=main_gate)

    return render(request, 'visitors/visitor_list.html', {
        'visitors': visitors,
        'query': query,
        'status': status,
        'guest_type': guest_type,
        'destination': destination,
        'main_gate': main_gate,
        'statuses': Visitor.Status.choices,
        'guest_types': Visitor.GuestType.choices,
        'destinations': CommunityUnit.objects.filter(is_active=True),
        'main_gates': Visitor._meta.get_field('main_gate').choices,
    })


@login_required
@roles_required(*ANY_VISITOR_ROLE)
def visitor_create(request):
    form = VisitorForm(request.POST or None)
    if is_resident(request.user):
        resident = get_object_or_404(Resident, user=request.user)
        for field in ('host', 'destination', 'redirected_from', 'alert_sent', 'approval_notes', 'incident_flagged', 'incident_reason'):
            form.fields.pop(field, None)

    if request.method == 'POST' and form.is_valid():
        visitor = form.save(commit=False)
        if is_resident(request.user):
            visitor.host = resident
            visitor.destination = resident.community_unit
            visitor.status = Visitor.Status.APPROVED
        else:
            visitor.status = Visitor.Status.PENDING
        visitor.save()
        _event(visitor, request, 'Visitor request created', 'Created by resident/company contact' if is_resident(request.user) else 'Created by security/admin')
        recurring_count = _create_recurring_visits(visitor, request)
        watchlist_hits = _matching_watchlist(visitor)
        if watchlist_hits.exists():
            visitor.incident_flagged = True
            visitor.incident_reason = f'Watchlist match: {watchlist_hits.first().reason}'
            visitor.incident_reported_at = timezone.now()
            visitor.save(update_fields=['incident_flagged', 'incident_reason', 'incident_reported_at'])
            _event(visitor, request, 'Watchlist match', visitor.incident_reason)
        if is_resident(request.user):
            _notify_main_gate(visitor, 'Approved visitor ready', f'{visitor.full_name} is pre-approved for main gate entry.')
        else:
            _notify_host(visitor, 'Visitor approval needed', f'{visitor.full_name} is waiting for your approval.')
        messages.success(request, f'Visitor saved successfully. {recurring_count} recurring booking(s) created.')
        return redirect('visitors:list')
    return render(request, 'visitors/visitor_form.html', {'form': form, 'title': 'Add Visitor'})


@login_required
@roles_required(*ANY_VISITOR_ROLE)
def visitor_update(request, pk):
    visitor = get_object_or_404(Visitor, pk=pk)
    if is_resident(request.user):
        if visitor.host.user_id != request.user.id or visitor.status not in {Visitor.Status.PENDING, Visitor.Status.APPROVED}:
            raise PermissionDenied

    form = VisitorForm(request.POST or None, instance=visitor)
    if is_resident(request.user):
        for field in ('host', 'destination', 'redirected_from', 'alert_sent', 'approval_notes', 'incident_flagged', 'incident_reason'):
            form.fields.pop(field, None)

    if request.method == 'POST' and form.is_valid():
        updated_visitor = form.save(commit=False)
        if is_resident(request.user):
            updated_visitor.host = visitor.host
            updated_visitor.destination = visitor.destination
            updated_visitor.status = Visitor.Status.APPROVED
        updated_visitor.save()
        messages.success(request, 'Visitor updated successfully.')
        return redirect('visitors:list')
    return render(request, 'visitors/visitor_form.html', {'form': form, 'title': 'Edit Visitor'})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.RESIDENT, UserProfile.Role.RECEPTIONIST)
def visitor_delete(request, pk):
    if request.method != 'POST':
        raise PermissionDenied
    visitor = get_object_or_404(Visitor, pk=pk)
    if is_resident(request.user):
        if visitor.host.user_id != request.user.id or visitor.status not in {Visitor.Status.PENDING, Visitor.Status.APPROVED}:
            raise PermissionDenied
    visitor.delete()
    messages.success(request, 'Visitor deleted.')
    return _workflow_redirect(request.user)


@login_required
@roles_required(*HOST_APPROVAL_ROLE)
def visitor_approve(request, pk):
    visitor = get_object_or_404(Visitor, pk=pk)
    if request.method != 'POST':
        raise PermissionDenied
    if is_resident(request.user) and visitor.host.user_id != request.user.id:
        raise PermissionDenied
    visitor.status = Visitor.Status.APPROVED
    visitor.save(update_fields=['status'])
    _event(visitor, request, 'Visit approved', 'Resident/company contact approved the request')
    _notify_main_gate(visitor, 'Visitor approved', f'{visitor.full_name} can be admitted at the main gate.')
    messages.success(request, 'Visitor approved.')
    return _workflow_redirect(request.user)


@login_required
@roles_required(*HOST_APPROVAL_ROLE)
def visitor_deny(request, pk):
    visitor = get_object_or_404(Visitor, pk=pk)
    if request.method != 'POST':
        raise PermissionDenied
    if is_resident(request.user) and visitor.host.user_id != request.user.id:
        raise PermissionDenied
    visitor.status = Visitor.Status.DENIED
    visitor.save(update_fields=['status'])
    _event(visitor, request, 'Visit denied', 'Request denied by host/admin')
    _notify_main_gate(visitor, 'Visitor denied', f'{visitor.full_name} was denied by the host.')
    messages.success(request, 'Visitor denied.')
    return _workflow_redirect(request.user)


def _ensure_post(request):
    if request.method != 'POST':
        raise PermissionDenied


def _ensure_host_owner(user, visitor):
    if is_resident(user) and visitor.host.user_id != user.id:
        raise PermissionDenied


def _log_visitor_movement(visitor, request, checkpoint_type, direction, gate=None, community_unit=None, notes=''):
    TrafficLog.objects.create(
        checkpoint_type=checkpoint_type,
        subject_type=TrafficLog.SubjectType.VISITOR,
        direction=direction,
        visitor=visitor,
        gate=gate or visitor.main_gate or MainGate.CHUNGA_MALI,
        community_unit=community_unit or visitor.destination,
        recorded_by=request.user,
        notes=notes,
    )


@login_required
@roles_required(*MAIN_GATE_ROLE)
def visitor_alert_host(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    visitor.alert_sent = True
    visitor.status = Visitor.Status.PENDING
    visitor.save(update_fields=['alert_sent', 'status'])
    _event(visitor, request, 'Host alerted', 'Main gate requested resident/company approval')
    _notify_host(visitor, 'Visitor at main gate', f'{visitor.full_name} is awaiting your approval.')
    return _workflow_redirect(request.user)


@login_required
@roles_required(*MAIN_GATE_ROLE)
def visitor_main_gate_checkin(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    if visitor.status not in {Visitor.Status.APPROVED, Visitor.Status.REDIRECTED}:
        raise PermissionDenied
    visitor.status = Visitor.Status.ARRIVED_MAIN_GATE
    if not visitor.main_gate:
        visitor.main_gate = MainGate.CHUNGA_MALI
    visitor.save(update_fields=['status', 'main_gate'])
    _log_visitor_movement(
        visitor,
        request,
        TrafficLog.CheckpointType.MAIN_GATE,
        TrafficLog.Direction.ENTRY,
        notes='Main gate check-in',
    )
    _event(visitor, request, 'Main gate entry confirmed', f'Visitor entered through {visitor.get_main_gate_display() or "main gate"}')
    _notify_unit_guard(visitor, 'Visitor en route to unit', f'{visitor.full_name} has entered the community.')
    _notify_host(visitor, 'Visitor entered Tilisi', f'{visitor.full_name} has entered at the main gate.')
    return _workflow_redirect(request.user)


@login_required
@roles_required(*UNIT_GATE_ROLE)
def visitor_unit_checkin(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    if is_resident(request.user):
        _ensure_host_owner(request.user, visitor)
    if visitor.status not in {Visitor.Status.APPROVED, Visitor.Status.ARRIVED_MAIN_GATE, Visitor.Status.REDIRECTED}:
        raise PermissionDenied
    visitor.status = Visitor.Status.UNIT_CONFIRMED
    visitor.save(update_fields=['status'])
    _log_visitor_movement(
        visitor,
        request,
        TrafficLog.CheckpointType.COMMUNITY_UNIT,
        TrafficLog.Direction.ENTRY,
        community_unit=visitor.destination,
        notes='Estate/company check-in',
    )
    _event(visitor, request, 'Unit arrival confirmed', 'Estate/company guard confirmed arrival')
    _notify_host(visitor, 'Confirm visitor check-in', f'{visitor.full_name} has arrived at your destination.')
    return _workflow_redirect(request.user)


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.RESIDENT, UserProfile.Role.RECEPTIONIST)
def visitor_confirm_checkin(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    _ensure_host_owner(request.user, visitor)
    if visitor.status != Visitor.Status.UNIT_CONFIRMED:
        raise PermissionDenied
    visitor.status = Visitor.Status.CHECKED_IN
    visitor.save(update_fields=['status'])
    _event(visitor, request, 'Host confirmed check-in', 'Resident/company confirmed visitor has checked in')
    return _workflow_redirect(request.user)


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.RESIDENT, UserProfile.Role.RECEPTIONIST)
def visitor_request_checkout(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    _ensure_host_owner(request.user, visitor)
    if visitor.status != Visitor.Status.CHECKED_IN:
        raise PermissionDenied
    visitor.status = Visitor.Status.CHECKOUT_REQUESTED
    visitor.save(update_fields=['status'])
    _log_visitor_movement(
        visitor,
        request,
        TrafficLog.CheckpointType.COMMUNITY_UNIT,
        TrafficLog.Direction.EXIT,
        community_unit=visitor.destination,
        notes='Checkout requested by host',
    )
    _event(visitor, request, 'Checkout requested', 'Host initiated visitor checkout')
    _notify_unit_guard(visitor, 'Checkout requested', f'{visitor.full_name} is ready for unit exit release.')
    return _workflow_redirect(request.user)


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.UNIT_GUARD)
def visitor_unit_release_exit(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    if visitor.status != Visitor.Status.CHECKOUT_REQUESTED:
        raise PermissionDenied
    visitor.status = Visitor.Status.UNIT_EXIT_CONFIRMED
    visitor.save(update_fields=['status'])
    _log_visitor_movement(
        visitor,
        request,
        TrafficLog.CheckpointType.COMMUNITY_UNIT,
        TrafficLog.Direction.EXIT,
        community_unit=visitor.destination,
        notes='Unit guard released visitor to main gate',
    )
    _event(visitor, request, 'Released to main gate', 'Unit guard released visitor for final exit')
    _notify_main_gate(visitor, 'Visitor ready for final exit', f'{visitor.full_name} has been released by the unit guard.')
    return redirect('dashboard:tasks')


@login_required
@roles_required(*MAIN_GATE_ROLE)
def visitor_main_gate_checkout(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    if visitor.status != Visitor.Status.UNIT_EXIT_CONFIRMED:
        raise PermissionDenied
    visitor.status = Visitor.Status.CHECKED_OUT
    visitor.save(update_fields=['status'])
    _log_visitor_movement(
        visitor,
        request,
        TrafficLog.CheckpointType.MAIN_GATE,
        TrafficLog.Direction.EXIT,
        notes='Main gate checkout',
    )
    _event(visitor, request, 'Main gate exit confirmed', 'Visitor left the community')
    _notify_host(visitor, 'Visitor checked out', f'{visitor.full_name} has left Tilisi.')
    return redirect('dashboard:gate_tasks')


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.UNIT_GUARD)
def visitor_redirect(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    destination_id = request.POST.get('destination')
    new_destination = get_object_or_404(CommunityUnit, pk=destination_id, is_active=True)
    visitor.redirected_from = visitor.destination
    visitor.destination = new_destination
    visitor.status = Visitor.Status.REDIRECTED
    visitor.save(update_fields=['redirected_from', 'destination', 'status'])
    _event(visitor, request, 'Visitor redirected', f'Redirected to {new_destination.name}')
    _notify_unit_guard(visitor, 'Visitor redirected', f'{visitor.full_name} was redirected to {new_destination.name}.')
    return _workflow_redirect(request.user)


@login_required
@roles_required(*VISITOR_VIEW_ROLE)
def visitor_detail(request, pk):
    visitor = get_object_or_404(
        Visitor.objects.select_related('host', 'destination', 'redirected_from').prefetch_related('events__actor'),
        pk=pk,
    )
    if is_resident(request.user) and visitor.host.user_id != request.user.id:
        raise PermissionDenied
    access_url = request.build_absolute_uri(visitor.get_absolute_url() if hasattr(visitor, 'get_absolute_url') else f'/visitors/{visitor.pk}/')
    workflow = [
        (Visitor.Status.PENDING, 'Request'),
        (Visitor.Status.APPROVED, 'Host Approved'),
        (Visitor.Status.ARRIVED_MAIN_GATE, 'Main Gate'),
        (Visitor.Status.UNIT_CONFIRMED, 'Unit Gate'),
        (Visitor.Status.CHECKED_IN, 'Checked In'),
        (Visitor.Status.CHECKOUT_REQUESTED, 'Checkout'),
        (Visitor.Status.UNIT_EXIT_CONFIRMED, 'Released'),
        (Visitor.Status.CHECKED_OUT, 'Final Exit'),
    ]
    status_order = [status for status, _ in workflow]
    current_index = status_order.index(visitor.status) if visitor.status in status_order else 0
    workflow_steps = [
        {
            'label': label,
            'state': 'is-current' if index == current_index else 'is-complete' if index < current_index else '',
            'number': index + 1,
        }
        for index, (_, label) in enumerate(workflow)
    ]
    return render(request, 'visitors/visitor_detail.html', {
        'visitor': visitor,
        'events': visitor.events.select_related('actor'),
        'attachment_form': VisitorAttachmentForm(),
        'workflow_steps': workflow_steps,
        'qr_payload': f'TILISI:{visitor.qr_token}:{access_url}',
    })


@login_required
@roles_required(*VISITOR_VIEW_ROLE)
def visitor_upload_attachment(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    if is_resident(request.user) and visitor.host.user_id != request.user.id:
        raise PermissionDenied
    form = VisitorAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.visitor = visitor
        attachment.uploaded_by = request.user
        attachment.save()
        _event(visitor, request, 'Attachment uploaded', attachment.title)
        messages.success(request, 'Attachment uploaded.')
    return redirect('visitors:detail', pk=visitor.pk)


@login_required
@roles_required(*VISITOR_VIEW_ROLE)
def visitor_qr_svg(request, pk):
    visitor = get_object_or_404(Visitor, pk=pk)
    if is_resident(request.user) and visitor.host.user_id != request.user.id:
        raise PermissionDenied
    token = str(visitor.qr_token).replace('-', '')
    cells = 17
    size = 238
    cell = size // cells
    rects = []
    for index, char in enumerate((token * 10)[: cells * cells]):
        row = index // cells
        col = index % cells
        if int(char, 16) % 3 != 0 or row in {0, cells - 1} or col in {0, cells - 1}:
            rects.append(f'<rect x="{col * cell}" y="{row * cell}" width="{cell}" height="{cell}"/>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" role="img" aria-label="Visitor access code">
<rect width="{size}" height="{size}" fill="#fff"/>
<g fill="#113f2a">{''.join(rects)}</g>
</svg>'''
    return HttpResponse(svg, content_type='image/svg+xml')


@login_required
@roles_required(*VISITOR_VIEW_ROLE)
def visitor_pass(request, pk):
    visitor = get_object_or_404(Visitor.objects.select_related('host', 'destination'), pk=pk)
    if is_resident(request.user) and visitor.host.user_id != request.user.id:
        raise PermissionDenied
    return render(request, 'visitors/visitor_pass.html', {'visitor': visitor})


@login_required
@roles_required(*VISITOR_VIEW_ROLE)
def visitor_pass_pdf(request, pk):
    visitor = get_object_or_404(Visitor.objects.select_related('host', 'destination'), pk=pk)
    if is_resident(request.user) and visitor.host.user_id != request.user.id:
        raise PermissionDenied
    lines = [
        f'Visitor: {visitor.full_name}',
        f'Guest type: {visitor.get_guest_type_display()}',
        f'Phone: {visitor.phone}',
        f'ID: {visitor.id_number}',
        f'Host: {visitor.host}',
        f'Destination: {visitor.destination or "-"}',
        f'Purpose: {visitor.purpose}',
        f'Vehicle: {visitor.get_vehicle_class_display() if visitor.vehicle_class else "-"} {visitor.vehicle_plate or "-"} {visitor.vehicle_color} {visitor.vehicle_make_model}',
        f'Main gate: {visitor.get_main_gate_display() if visitor.main_gate else "-"}',
        f'Status: {visitor.get_status_display()}',
        f'Access code: {visitor.qr_token}',
    ]
    return _simple_pdf_response(f'visitor_pass_{visitor.pk}.pdf', 'Tilisi Visitor Pass', lines)


@login_required
@roles_required(*VISITOR_VIEW_ROLE)
def visitor_send_sms(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    if is_resident(request.user) and visitor.host.user_id != request.user.id:
        raise PermissionDenied
    _event(visitor, request, 'SMS simulated', f'SMS sent to {visitor.phone}: visit status is {visitor.get_status_display()}')
    if visitor.host and visitor.host.user:
        Notification.objects.create(
            user=visitor.host.user,
            visitor=visitor,
            title='SMS simulated',
            message=f'A prototype SMS was sent to {visitor.full_name}.',
        )
    return redirect('visitors:detail', pk=visitor.pk)


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD, UserProfile.Role.UNIT_GUARD)
def visitor_flag_incident(request, pk):
    _ensure_post(request)
    visitor = get_object_or_404(Visitor, pk=pk)
    visitor.incident_flagged = True
    visitor.incident_reason = request.POST.get('incident_reason', '').strip() or 'Flagged by guard'
    visitor.incident_reported_at = timezone.now()
    visitor.save(update_fields=['incident_flagged', 'incident_reason', 'incident_reported_at'])
    _event(visitor, request, 'Incident flagged', visitor.incident_reason)
    _notify_host(visitor, 'Visitor incident flagged', f'{visitor.full_name}: {visitor.incident_reason}')
    messages.success(request, 'Incident flagged.')
    return redirect('visitors:detail', pk=visitor.pk)


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY)
def parking_list(request):
    slots = ParkingSlot.objects.select_related('community_unit', 'assigned_visitor')
    return render(request, 'visitors/parking_list.html', {'slots': slots})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY)
def parking_create(request):
    form = ParkingSlotForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Parking slot saved.')
        return redirect('visitors:parking')
    return render(request, 'visitors/parking_form.html', {'form': form, 'title': 'Add Parking Slot'})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY)
def parking_update(request, pk):
    slot = get_object_or_404(ParkingSlot, pk=pk)
    form = ParkingSlotForm(request.POST or None, instance=slot)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Parking slot updated.')
        return redirect('visitors:parking')
    return render(request, 'visitors/parking_form.html', {'form': form, 'title': 'Edit Parking Slot'})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY)
def watchlist_list(request):
    entries = WatchlistEntry.objects.all()
    return render(request, 'visitors/watchlist_list.html', {'entries': entries})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY)
def watchlist_create(request):
    form = WatchlistEntryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        entry = form.save(commit=False)
        entry.created_by = request.user
        entry.save()
        messages.success(request, 'Watchlist entry saved.')
        return redirect('visitors:watchlist')
    return render(request, 'visitors/watchlist_form.html', {'form': form, 'title': 'Add Watchlist Entry'})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY)
def watchlist_update(request, pk):
    entry = get_object_or_404(WatchlistEntry, pk=pk)
    form = WatchlistEntryForm(request.POST or None, instance=entry)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Watchlist entry updated.')
        return redirect('visitors:watchlist')
    return render(request, 'visitors/watchlist_form.html', {'form': form, 'title': 'Edit Watchlist Entry'})
