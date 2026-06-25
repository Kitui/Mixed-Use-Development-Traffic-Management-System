from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserProfile
from accounts.permissions import is_receptionist, roles_required
from residents.models import Resident
from .forms import VehicleForm
from .models import Vehicle


def _receptionist_unit(user):
    if not is_receptionist(user):
        return None
    person = Resident.objects.select_related('community_unit').filter(user=user).first()
    return person.community_unit if person else None


def _scope_vehicle_form(form, company_unit):
    if not company_unit:
        return
    form.fields['resident_owner'].queryset = Resident.objects.filter(
        community_unit=company_unit,
        person_type=Resident.PersonType.EMPLOYEE,
        is_active=True,
    )
    form.fields.pop('visitor_owner', None)
    form.fields.pop('vehicle_type', None)


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.RECEPTIONIST)
def vehicle_list(request):
    vehicles = Vehicle.objects.select_related('resident_owner', 'visitor_owner')
    company_unit = _receptionist_unit(request.user)
    if company_unit:
        vehicles = vehicles.filter(resident_owner__community_unit=company_unit)
    query = request.GET.get('q', '').strip()
    vehicle_type = request.GET.get('type', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        vehicles = vehicles.filter(
            Q(plate_number__icontains=query)
            | Q(make_model__icontains=query)
            | Q(color__icontains=query)
            | Q(resident_owner__full_name__icontains=query)
            | Q(visitor_owner__full_name__icontains=query)
        )
    if vehicle_type:
        vehicles = vehicles.filter(vehicle_type=vehicle_type)
    if status == 'active':
        vehicles = vehicles.filter(is_active=True)
    elif status == 'inactive':
        vehicles = vehicles.filter(is_active=False)

    return render(request, 'vehicles/vehicle_list.html', {
        'vehicles': vehicles,
        'query': query,
        'vehicle_type': vehicle_type,
        'status': status,
        'vehicle_types': Vehicle.VehicleType.choices,
        'company_unit': company_unit,
    })


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.RECEPTIONIST)
def vehicle_create(request):
    form = VehicleForm(request.POST or None)
    company_unit = _receptionist_unit(request.user)
    _scope_vehicle_form(form, company_unit)
    if request.method == 'POST' and form.is_valid():
        vehicle = form.save(commit=False)
        if company_unit:
            vehicle.vehicle_type = Vehicle.VehicleType.RESIDENT
            vehicle.visitor_owner = None
            if vehicle.resident_owner and vehicle.resident_owner.community_unit_id != company_unit.id:
                raise PermissionDenied
        vehicle.save()
        return redirect('vehicles:list')
    return render(request, 'vehicles/vehicle_form.html', {'form': form, 'title': 'Add Company Vehicle' if company_unit else 'Add Vehicle', 'company_unit': company_unit})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.RECEPTIONIST)
def vehicle_update(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    company_unit = _receptionist_unit(request.user)
    if company_unit and (not vehicle.resident_owner or vehicle.resident_owner.community_unit_id != company_unit.id):
        raise PermissionDenied
    form = VehicleForm(request.POST or None, instance=vehicle)
    _scope_vehicle_form(form, company_unit)
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        if company_unit:
            updated.vehicle_type = Vehicle.VehicleType.RESIDENT
            updated.visitor_owner = None
            if updated.resident_owner and updated.resident_owner.community_unit_id != company_unit.id:
                raise PermissionDenied
        updated.save()
        return redirect('vehicles:list')
    return render(request, 'vehicles/vehicle_form.html', {'form': form, 'title': 'Edit Company Vehicle' if company_unit else 'Edit Vehicle', 'company_unit': company_unit})


@login_required
@roles_required(UserProfile.Role.ADMIN)
def vehicle_delete(request, pk):
    if request.method != 'POST':
        raise PermissionDenied
    vehicle = get_object_or_404(Vehicle, pk=pk)
    vehicle.delete()
    return redirect('vehicles:list')
