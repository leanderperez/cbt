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
from django.db.models import F
from .models import (
    Obra, Fase, Tarea, RequerimientoMaterial,
    MedicionMaterial, Material, Personal
)
from .forms import (
    ObraForm,
    FaseForm,
    TareaForm,
    TareaUpdateProgressForm,
    RequerimientoMaterialFormSet,
    MaterialForm,
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

class ObraMedicionesView(DetailView):
    model = Obra
    template_name = 'project_app/obra_mediciones.html'
    context_object_name = 'obra'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obra = self.get_object()

        # Obtener todos los requerimientos de la obra
        requerimientos = RequerimientoMaterial.objects.filter(tarea__fase__obra=obra).select_related('tarea', 'material', 'tarea__fase').order_by('tarea__fase', 'tarea')

        tabla_mediciones = []
        fechas_medicion_set = set()

        # Cargar las mediciones existentes en un diccionario para acceso rápido
        mediciones_data = MedicionMaterial.objects.filter(tarea__fase__obra=obra).values('tarea', 'material', 'cantidad', 'fecha_medicion')
        mediciones_dict = {}
        for med in mediciones_data:
            key = (med['tarea'], med['material'])
            if key not in mediciones_dict:
                mediciones_dict[key] = {}
            fecha_str = med['fecha_medicion'].strftime('%Y-%m-%d')
            mediciones_dict[key][fecha_str] = med['cantidad']
            fechas_medicion_set.add(fecha_str)

        # Crear la estructura de la tabla
        for req in requerimientos:
            tarea_pk = req.tarea.pk
            material_pk = req.material.pk
            
            mediciones_historicas = mediciones_dict.get((tarea_pk, material_pk), {})
            
            row = {
                'fase_nombre': req.tarea.fase.nombre,
                'tarea_nombre': req.tarea.nombre,
                'tarea_pk': tarea_pk,
                'material_nombre': req.material.nombre,
                'material_unidad': req.material.unidad,
                'material_pk': material_pk,
                'cantidad_requerida': req.cantidad_requerida,
                'mediciones': mediciones_historicas
            }
            tabla_mediciones.append(row)

        fechas_medicion_list = sorted(list(fechas_medicion_set))

        context['tabla_mediciones'] = tabla_mediciones
        context['fechas_medicion'] = fechas_medicion_list
        return context

    def post(self, request, *args, **kwargs):
        print("Datos recibidos en el POST:", request.POST) # <-- LÍNEA PARA DEPURAR

        obra = self.get_object()
        fecha_medicion = request.POST.get('fecha_medicion')
        if not fecha_medicion:
            return redirect('obra-mediciones', pk=obra.pk)
        
        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith('medicion-'):
                    try:
                        _, tarea_id, material_id = key.split('-')
                        cantidad_str = value.replace(',', '.')  # Manejar comas si es necesario
                        cantidad = Decimal(cantidad_str)

                        if cantidad > 0:
                            MedicionMaterial.objects.create(
                                tarea_id=int(tarea_id),
                                material_id=int(material_id),
                                cantidad=cantidad,
                                fecha_medicion=fecha_medicion
                            )
                            print(f"Medición guardada: Tarea={tarea_id}, Material={material_id}, Cantidad={cantidad}")
                    except (ValueError, IndexError) as e:
                        print(f"Error al procesar la clave '{key}': {e}")
                        continue

        return redirect('obra-mediciones', pk=obra.pk)
        obra = self.get_object()
        fecha_medicion = request.POST.get('fecha_medicion')
        if not fecha_medicion:
            return redirect('obra-mediciones', pk=obra.pk)
        
        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith('medicion-'):
                    try:
                        # Extrae los IDs de la clave 'medicion-tarea_id-material_id'
                        # El split devuelve una lista: ['medicion', 'tarea_id', 'material_id']
                        # Usamos la desestructuración para asignar los valores directamente
                        _, tarea_id, material_id = key.split('-')
                        cantidad = Decimal(value)

                        if cantidad > 0:
                            MedicionMaterial.objects.create(
                                tarea_id=int(tarea_id),
                                material_id=int(material_id),
                                cantidad=cantidad,
                                fecha_medicion=fecha_medicion
                            )
                    except (ValueError, IndexError):
                        # Ignora las claves que no tengan el formato correcto
                        continue

        return redirect('obra-mediciones', pk=obra.pk)

class MaterialListView(ListView):
    model = Material
    template_name = 'project_app/material_list.html'
    context_object_name = 'materiales'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['material_form'] = MaterialForm()
        return context

    def post(self, request):
        if 'update_costs' in request.POST:
            with transaction.atomic():
                for key, value in request.POST.items():
                    if key.startswith('cost-'):
                        try:
                            material_pk = int(key.split('-')[-1])
                            costo = float(value) if value else 0.0
                            if costo > 0:
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


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Tarea, Obra

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from .models import Tarea, Obra, Fase
from datetime import datetime
from decimal import Decimal

def gantt_data_view(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    
    # Obtener todas las tareas de la obra
    tareas = Tarea.objects.filter(fase__obra=obra).order_by('fecha_inicio')
    
    # Obtener las fases únicas de la obra
    fases_obra = Fase.objects.filter(obra=obra).order_by('id')
    
    gantt_data = []

    # 1. Crear los objetos de las Fases (actúan como los "agrupadores")
    for fase in fases_obra:
        # Encontrar la fecha de inicio más temprana y la fecha de fin más tardía de las tareas en esta fase
        tareas_en_fase = tareas.filter(fase=fase)
        
        if not tareas_en_fase:
            # Si la fase no tiene tareas, la saltamos o la definimos como un hito
            continue

        fecha_inicio_fase = min(t.fecha_inicio for t in tareas_en_fase)
        fecha_fin_fase = max(t.fecha_fin_estimada for t in tareas_en_fase)

        # Calcular el progreso promedio de la fase
        total_avance = sum(t.porcentaje_avance for t in tareas_en_fase)
        promedio_avance = total_avance / len(tareas_en_fase) if tareas_en_fase else Decimal('0.00')

        gantt_data.append({
            'id': f'fase-{fase.id}',
            'name': fase.nombre,
            'start': fecha_inicio_fase.strftime('%Y-%m-%d'),
            'end': fecha_fin_fase.strftime('%Y-%m-%d'),
            'progress': float(promedio_avance),
            'dependencies': '',  # Las fases no tienen dependencias
            'custom_class': 'gantt-phase' # Clase CSS para estilizar si es necesario
        })

    # 2. Crear los objetos de las Tareas (actúan como los "elementos hijos")
    for tarea in tareas:
        start = tarea.fecha_inicio.strftime('%Y-%m-%d')
        end = tarea.fecha_fin_estimada.strftime('%Y-%m-%d')
        
        gantt_data.append({
            'id': f'tarea-{tarea.id}',
            'name': tarea.nombre,
            'start': start,
            'end': end,
            'progress': float(tarea.porcentaje_avance),
            'dependencies': f'fase-{tarea.fase.id}', #La tarea depende de la fase
        })
        
    return JsonResponse(gantt_data, safe=False)

def gantt_chart_view(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    return render(request, 'project_app/gantt_chart.html', {
        'obra_pk': pk,
        'obra_nombre': obra.nombre,})


    model = Tarea
    template_name = 'project_app/tarea_material_update.html'
    form_class = TareaForm # Usamos TareaForm solo para mostrar los detalles de la tarea

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tarea = self.object
        context['tarea'] = tarea
        context['materiales'] = Material.objects.all().order_by('nombre')
        
        # Cargar las cantidades requeridas existentes en un diccionario
        requerimientos = {req.material.pk: req.cantidad_requerida for req in tarea.requerimientomaterial_set.all()}
        context['requerimientos'] = requerimientos
        
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        with transaction.atomic():
            # Eliminar todos los requerimientos existentes para la tarea
            RequerimientoMaterial.objects.filter(tarea=self.object).delete()
            
            # Crear los nuevos requerimientos a partir del formulario
            for key, value in request.POST.items():
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
    
def calculadora_view(request):
    # No se necesita lógica de servidor, solo renderizar el template.
    return render(request, 'project_app/calculadora.html', {})