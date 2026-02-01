from datetime import datetime
from django.db import transaction

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .models import Reporte
from .forms import (ReporteAdminForm)


def is_coordinador(user):
    return user.groups.filter(name='Coordinadores').exists()

def acceso_denegado(request):
    return render(request, 'app/acceso_denegado.html')

@login_required
def crear_reporte(request):
    FormClass = ReporteAdminForm
    template = 'servicio/reporte_form.html'

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES)
        if form.is_valid():
            reporte = form.save(commit=False)
            # Usar una transacción para insertar y actualizar la referencia
            with transaction.atomic():
                reporte.save()
                # Construir el código de referencia una vez que existe el id
                year = datetime.now().year % 100
                referencia = f"GEEI{year:02d}-{reporte.id:04d}"
                # Actualizar la referencia con una query para evitar llamar save() de nuevo
                Reporte.objects.filter(pk=reporte.pk).update(referencia=referencia)
            return redirect('datatable')
    else:
        form = FormClass()
    return render(request, template, {'form': form})

@login_required
# @user_passes_test(is_coordinador, login_url='/acceso-denegado/')
def modificar_reporte(request, pk):
    reporte = Reporte.objects.get(pk=pk)
    if request.method == 'POST':
        form = ReporteAdminForm(request.POST, request.FILES, instance=reporte)
        if form.is_valid():
            # Construir el código de referencia
            year = datetime.now().year % 100 
            referencia = f"GEEI{year:02d}-{reporte.id:04d}"
            # Asignar el código de referencia 
            form.instance.referencia = referencia
        form.save()
        return redirect('datatable')
    else:
        form = ReporteAdminForm(instance=reporte)
    return render(request, 'servicio/reporte_form.html', {'form': form, 'objeto': form})

@login_required
def datatable(request):
    user = request.user
    if user.groups.filter(name='Supervisores').exists():
        sucursal = user.perfil.sucursal
        reportes = Reporte.objects.filter(sucursal=sucursal, estatus=False)
    else:
        reportes = Reporte.objects.all()
    contexto = {'reportes': reportes}
    return render(request, 'servicio/datatable.html', contexto)