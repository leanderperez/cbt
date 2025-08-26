from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView,
    View
)
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.http import HttpResponseRedirect
from django.db.models import F
from .models import (
    Obra, Fase, Tarea, RequerimientoMaterial, AsignacionMaterial,
    MedicionMaterial, Material, Personal
)
from .forms import (
    ObraForm,
    FaseForm,
    TareaForm,
    TareaUpdateProgressForm,
    RequerimientoMaterialFormSet,
    AsignacionMaterialFormSet,
    MaterialForm, # Nuevo formulario
    PersonalForm
)
import datetime
import json
from decimal import Decimal



class ObraListView(ListView):
    model = Obra
    template_name = 'project_app/obra_list.html'
    context_object_name = 'obras'

class ObraCreateView(CreateView):
    model = Obra
    form_class = ObraForm
    template_name = 'project_app/obra_form.html'
    success_url = reverse_lazy('obra-list')

class ObraUpdateView(UpdateView):
    model = Obra
    form_class = ObraForm
    template_name = 'project_app/obra_form.html'
    success_url = reverse_lazy('obra-list')

class ObraDetailView(DetailView):
    model = Obra
    template_name = 'project_app/obra_detail.html'
    context_object_name = 'obra'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

class FaseCreateView(CreateView):
    model = Fase
    form_class = FaseForm
    template_name = 'project_app/fase_form.html'
    
    def form_valid(self, form):
        obra = get_object_or_404(Obra, pk=self.kwargs['pk'])
        form.instance.obra = obra
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('obra-detail', kwargs={'pk': self.object.obra.pk})

class TareaCreateView(CreateView):
    model = Tarea
    form_class = TareaForm
    template_name = 'project_app/tarea_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fase = get_object_or_404(Fase, pk=self.kwargs['pk'])
        context['fase'] = fase
        # Obtener todos los materiales disponibles para la tabla
        context['materiales'] = Material.objects.all().order_by('nombre')
        return context

    def form_valid(self, form):
        with transaction.atomic():
            fase = get_object_or_404(Fase, pk=self.kwargs['pk'])
            form.instance.fase = fase
            self.object = form.save()

            # Procesar los datos de la tabla de materiales
            for key, value in self.request.POST.items():
                if key.startswith('material-quantity-'):
                    try:
                        material_pk = int(key.split('-')[-1])
                        cantidad = float(value) if value else 0
                        
                        if cantidad > 0:
                            material = get_object_or_404(Material, pk=material_pk)
                            RequerimientoMaterial.objects.create(
                                tarea=self.object,
                                material=material,
                                cantidad_requerida=cantidad
                            )
                    except (ValueError, IndexError, Material.DoesNotExist):
                        continue
            
            return redirect('obra-detail', pk=self.object.fase.obra.pk)

class TareaUpdateView(UpdateView):
    model = Tarea
    form_class = TareaUpdateProgressForm
    template_name = 'project_app/tarea_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tarea'] = self.object
        if self.request.POST:
            context['requerimientos_formset'] = RequerimientoMaterialFormSet(self.request.POST, instance=self.object, prefix='req')
            context['asignaciones_formset'] = AsignacionMaterialFormSet(self.request.POST, instance=self.object, prefix='asig')
        else:
            context['requerimientos_formset'] = RequerimientoMaterialFormSet(instance=self.object, prefix='req')
            context['asignaciones_formset'] = AsignacionMaterialFormSet(instance=self.object, prefix='asig')
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        requerimientos_formset = context['requerimientos_formset']
        asignaciones_formset = context['asignaciones_formset']

        with transaction.atomic():
            self.object = form.save()
            if requerimientos_formset.is_valid() and asignaciones_formset.is_valid():
                requerimientos_formset.instance = self.object
                requerimientos_formset.save()
                asignaciones_formset.instance = self.object
                asignaciones_formset.save()
                return redirect('obra-detail', pk=self.object.fase.obra.pk)
            else:
                return self.render_to_response(self.get_context_data(form=form))
        
    def get_success_url(self):
        return reverse_lazy('obra-detail', kwargs={'pk': self.object.fase.obra.pk})

class ObraMedicionesView(View):
    template_name = 'project_app/obra_mediciones.html'

    def get(self, request, pk):
        obra = get_object_or_404(Obra, pk=pk)
        
        # Lógica para obtener las mediciones y requerimientos
        requerimientos = RequerimientoMaterial.objects.filter(tarea__fase__obra=obra).select_related('tarea', 'material', 'tarea__fase')
        mediciones_qs = MedicionMaterial.objects.filter(tarea__fase__obra=obra).values('tarea__pk', 'material__pk', 'fecha_medicion', 'cantidad')
        
        mediciones_dict = {}
        fechas_medicion = sorted(list(set(m['fecha_medicion'] for m in mediciones_qs)))

        for m in mediciones_qs:
            key = (m['tarea__pk'], m['material__pk'], m['fecha_medicion'])
            mediciones_dict[key] = m['cantidad']

        tabla_mediciones = []
        for req in requerimientos:
            row_data = {
                'fase_nombre': req.tarea.fase.nombre,
                'tarea_nombre': req.tarea.nombre,
                'tarea_pk': req.tarea.pk,
                'material_nombre': req.material.nombre,
                'material_unidad': req.material.unidad,
                'material_pk': req.material.pk,
                'cantidad_requerida': req.cantidad_requerida,
                'mediciones': {}
            }
            for fecha in fechas_medicion:
                medicion_val = mediciones_dict.get((req.tarea.pk, req.material.pk, fecha))
                if isinstance(medicion_val, Decimal):
                    medicion_val = float(medicion_val)
                
                row_data['mediciones'][str(fecha)] = medicion_val
            tabla_mediciones.append(row_data)

        # Conversión de los datos para la plantilla
        def decimal_to_float(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

        tabla_mediciones_json = json.dumps(tabla_mediciones, default=decimal_to_float)
        fechas_medicion_str = [f.strftime('%Y-%m-%d') for f in fechas_medicion]
        fechas_medicion_json = json.dumps(fechas_medicion_str)
        
        context = {
            'obra': obra,
            'tabla_mediciones_json': tabla_mediciones_json,
            'fechas_medicion': fechas_medicion,
            'fechas_medicion_json': fechas_medicion_json,
        }

        return render(request, self.template_name, context)

    def post(self, request, pk):
        obra = get_object_or_404(Obra, pk=pk)
        fecha_str = request.POST.get('fecha_medicion')
        if not fecha_str:
            return redirect('obra-mediciones', pk=pk)
        try:
            fecha_medicion = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            return redirect('obra-mediciones', pk=pk)

        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith('medicion-'):
                    try:
                        parts = key.split('-')
                        tarea_id = int(parts[1])
                        material_id = int(parts[2])
                        cantidad = float(value) if value else 0
                        
                        if cantidad > 0:
                            # Reemplaza .get() con update_or_create para evitar errores si el objeto no existe
                            MedicionMaterial.objects.update_or_create(
                                tarea_id=tarea_id,
                                material_id=material_id,
                                fecha_medicion=fecha_medicion,
                                defaults={'cantidad': Decimal(str(cantidad))} # Usa Decimal para evitar problemas de precisión
                            )
                    except (ValueError, IndexError):
                        continue
        return redirect('obra-mediciones', pk=pk)

class MaterialListView(ListView):
    model = Material
    template_name = 'project_app/material_list.html'
    context_object_name = 'materiales'

    def post(self, request):
        if 'update_costs' in request.POST:
            with transaction.atomic():
                for key, value in request.POST.items():
                    if key.startswith('cost-'):
                        try:
                            material_pk = int(key.split('-')[-1])
                            costo = float(value) if value else 0.0
                            if costo >= 0:
                                Material.objects.filter(pk=material_pk).update(costo_unitario=costo)
                        except (ValueError, IndexError):
                            continue
        return redirect('material-list')

class MaterialCreateView(CreateView):
    model = Material
    form_class = MaterialForm
    template_name = 'project_app/material_form.html'
    success_url = reverse_lazy('material-list')

class PersonalCreateView(CreateView):
    model = Personal
    form_class = PersonalForm
    template_name = 'project_app/personal_form.html'
    success_url = reverse_lazy('personal-list')

class PersonalListView(ListView):
    model = Personal
    template_name = 'project_app/personal_list.html'
    context_object_name = 'personal'


# Custom Login View
from django.contrib.auth.views import LoginView

class CustomLoginView(LoginView):
    template_name = 'project_app/login.html'