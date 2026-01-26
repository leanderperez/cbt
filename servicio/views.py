from datetime import datetime

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .models import Reporte

from .forms import (ReporteForm, ReporteAdminForm)



class CustomLoginView(LoginView):
  template_name = 'app/login.html'
  next_page = reverse_lazy('crear_reporte')
  form_class = forms.CustomAuthenticationForm

  def dispatch(self, request, *args, **kwargs):
    if self.request.user.is_authenticated:
      return redirect('crear_reporte')
    return super().dispatch(request, *args, **kwargs)

def is_coordinador(user):
    return user.groups.filter(name='Coordinadores').exists()

def acceso_denegado(request):
    return render(request, 'app/acceso_denegado.html')

@login_required
def crear_reporte(request):
    if is_coordinador(request.user):
        FormClass = ReporteAdminForm
        template = 'app/formulario_admin.html'
    else:
        FormClass = ReporteForm
        template = 'app/formulario.html'

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES)
        if form.is_valid():
            reporte = form.save(commit=False)
            if request.user.groups.filter(name='Supervisores').exists():
                reporte.referencia = "Nuevo ⚠"
            form.save()
            return redirect('datatable')
    else:
        form = FormClass()
    return render(request, template, {'form': form})

@login_required
@user_passes_test(is_coordinador, login_url='/acceso-denegado/')
def modificar_reporte(request, pk):
    reporte = Reporte.objects.get(pk=pk)
    if request.method == 'POST':
        form = ReporteAdminForm(request.POST, request.FILES, instance=reporte)
        if form.is_valid():
            # Obtener el personal del formulario
            personal = form.cleaned_data.get('personal')
            if personal in ['Técnico de Cuadrilla', 'Técnico de Infraestructura']:
                # Construir el código de referencia
                year = datetime.now().year % 100 
                referencia = f"GEEI{year:02d}-{reporte.id:04d}"
                # Asignar el código de referencia 
                form.instance.referencia = referencia
            form.save()
            return redirect('datatable')
    else:
        form = ReporteAdminForm(instance=reporte)
    return render(request, 'app/formulario_admin.html', {'form': form, 'objeto': form})