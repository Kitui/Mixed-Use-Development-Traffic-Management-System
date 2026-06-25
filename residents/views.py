from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import UserProfile
from accounts.permissions import is_receptionist, roles_required
from .forms import CommunityUnitForm, ResidentForm
from .models import CommunityUnit, Resident


def _receptionist_unit(user):
    if not is_receptionist(user):
        return None
    person = Resident.objects.select_related('community_unit').filter(user=user).first()
    return person.community_unit if person else None


@login_required
@roles_required(UserProfile.Role.ADMIN)
def development_list(request):
    developments = CommunityUnit.objects.all()
    query = request.GET.get('q', '').strip()
    unit_type = request.GET.get('type', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        developments = developments.filter(
            Q(name__icontains=query)
            | Q(contact_phone__icontains=query)
        )
    if unit_type:
        developments = developments.filter(unit_type=unit_type)
    if status == 'active':
        developments = developments.filter(is_active=True)
    elif status == 'inactive':
        developments = developments.filter(is_active=False)

    return render(request, 'residents/development_list.html', {
        'developments': developments,
        'query': query,
        'unit_type': unit_type,
        'status': status,
        'unit_types': CommunityUnit.UnitType.choices,
    })


@login_required
@roles_required(UserProfile.Role.ADMIN)
def development_create(request):
    form = CommunityUnitForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('residents:developments')
    return render(request, 'residents/development_form.html', {'form': form, 'title': 'Add Development'})


@login_required
@roles_required(UserProfile.Role.ADMIN)
def development_update(request, pk):
    development = get_object_or_404(CommunityUnit, pk=pk)
    form = CommunityUnitForm(request.POST or None, instance=development)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('residents:developments')
    return render(request, 'residents/development_form.html', {'form': form, 'title': 'Edit Development'})


@login_required
@roles_required(UserProfile.Role.ADMIN)
def development_delete(request, pk):
    if request.method != 'POST':
        raise PermissionDenied
    development = get_object_or_404(CommunityUnit, pk=pk)
    development.is_active = False
    development.save(update_fields=['is_active'])
    return redirect('residents:developments')


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.SECURITY, UserProfile.Role.RECEPTIONIST)
def resident_list(request):
    residents = Resident.objects.all()
    company_unit = _receptionist_unit(request.user)
    if company_unit:
        residents = residents.filter(community_unit=company_unit, person_type=Resident.PersonType.EMPLOYEE)
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        residents = residents.filter(
            Q(full_name__icontains=query)
            | Q(house_number__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
    if status == 'active':
        residents = residents.filter(is_active=True)
    elif status == 'inactive':
        residents = residents.filter(is_active=False)

    return render(request, 'residents/resident_list.html', {
        'residents': residents,
        'query': query,
        'status': status,
        'company_unit': company_unit,
    })


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.RECEPTIONIST)
def resident_create(request):
    form = ResidentForm(request.POST or None)
    company_unit = _receptionist_unit(request.user)
    if company_unit:
        form.fields.pop('community_unit', None)
        form.fields.pop('person_type', None)
    if request.method == 'POST' and form.is_valid():
        resident = form.save(commit=False)
        if company_unit:
            resident.community_unit = company_unit
            resident.person_type = Resident.PersonType.EMPLOYEE
        resident.save()
        return redirect('residents:list')
    return render(request, 'residents/resident_form.html', {'form': form, 'title': 'Add Employee' if company_unit else 'Add Resident', 'company_unit': company_unit})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.RECEPTIONIST)
def resident_update(request, pk):
    resident = get_object_or_404(Resident, pk=pk)
    company_unit = _receptionist_unit(request.user)
    if company_unit and (resident.community_unit_id != company_unit.id or resident.person_type != Resident.PersonType.EMPLOYEE):
        raise PermissionDenied
    form = ResidentForm(request.POST or None, instance=resident)
    if company_unit:
        form.fields.pop('community_unit', None)
        form.fields.pop('person_type', None)
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        if company_unit:
            updated.community_unit = company_unit
            updated.person_type = Resident.PersonType.EMPLOYEE
        updated.save()
        return redirect('residents:list')
    return render(request, 'residents/resident_form.html', {'form': form, 'title': 'Edit Employee' if company_unit else 'Edit Resident', 'company_unit': company_unit})


@login_required
@roles_required(UserProfile.Role.ADMIN, UserProfile.Role.RECEPTIONIST)
def resident_delete(request, pk):
    if request.method != 'POST':
        raise PermissionDenied
    resident = get_object_or_404(Resident, pk=pk)
    company_unit = _receptionist_unit(request.user)
    if company_unit and (resident.community_unit_id != company_unit.id or resident.person_type != Resident.PersonType.EMPLOYEE):
        raise PermissionDenied
    resident.is_active = False
    resident.save(update_fields=['is_active'])
    return redirect('residents:list')
