from functools import wraps

from django.core.exceptions import PermissionDenied

from .models import UserProfile


def get_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return UserProfile.Role.ADMIN
    try:
        return user.userprofile.role
    except UserProfile.DoesNotExist:
        return None


def is_admin(user):
    return get_role(user) == UserProfile.Role.ADMIN


def is_security(user):
    return get_role(user) in {
        UserProfile.Role.SECURITY,
        UserProfile.Role.MAIN_GATE_GUARD,
        UserProfile.Role.UNIT_GUARD,
    }


def is_main_gate_guard(user):
    return get_role(user) in {UserProfile.Role.SECURITY, UserProfile.Role.MAIN_GATE_GUARD}


def is_unit_guard(user):
    return get_role(user) in {UserProfile.Role.SECURITY, UserProfile.Role.UNIT_GUARD}


def is_resident(user):
    return get_role(user) in {UserProfile.Role.RESIDENT, UserProfile.Role.RECEPTIONIST}


def is_receptionist(user):
    return get_role(user) == UserProfile.Role.RECEPTIONIST


def has_any_role(user, *roles):
    return get_role(user) in roles


def roles_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if has_any_role(request.user, *roles):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied

        return wrapped

    return decorator
