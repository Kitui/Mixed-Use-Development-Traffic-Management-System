from .permissions import get_role, is_admin, is_main_gate_guard, is_receptionist, is_resident, is_security, is_unit_guard


def _safe_counts(user):
    if not user.is_authenticated:
        return {}
    from visitors.models import Notification, Visitor

    visitor_scope = Visitor.objects.all()
    if is_resident(user):
        visitor_scope = visitor_scope.filter(host__user=user)

    return {
        'notification_count': Notification.objects.filter(user=user, is_read=False).count(),
        'sidebar_pending_count': visitor_scope.filter(status=Visitor.Status.PENDING).count(),
        'sidebar_arrival_count': Visitor.objects.filter(status__in=[Visitor.Status.ARRIVED_MAIN_GATE, Visitor.Status.REDIRECTED]).count()
        if is_unit_guard(user) or is_admin(user)
        else 0,
        'sidebar_gate_arrival_count': Visitor.objects.filter(status=Visitor.Status.APPROVED).count()
        if is_main_gate_guard(user) or is_admin(user)
        else 0,
        'sidebar_exit_count': Visitor.objects.filter(status__in=[Visitor.Status.CHECKOUT_REQUESTED, Visitor.Status.UNIT_EXIT_CONFIRMED]).count()
        if is_security(user) or is_admin(user)
        else visitor_scope.filter(status=Visitor.Status.CHECKED_IN).count(),
    }


def role_flags(request):
    user = request.user
    context = {
        'current_role': get_role(user),
        'is_admin_user': is_admin(user),
        'is_security_user': is_security(user),
        'is_main_gate_guard_user': is_main_gate_guard(user),
        'is_unit_guard_user': is_unit_guard(user),
        'is_resident_user': is_resident(user),
        'is_receptionist_user': is_receptionist(user),
    }
    context.update(_safe_counts(user))
    try:
        from dashboard.models import SystemSettings
        context['system_settings'] = SystemSettings.current()
    except Exception:
        context['system_settings'] = None
    return context
