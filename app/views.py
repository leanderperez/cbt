import json
import re
import datetime
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from collections import defaultdict


# Django
from django.conf import settings
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.text import slugify

# Terceros
from formtools.wizard.views import SessionWizardView
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
   

from io import BytesIO

# Locales (tu app)
from .models import (
    Obra,
    Fase,
    Tarea,
    RequerimientoMaterial,
    MedicionMaterial,
    Material,
    Personal,
    Corrida, 
    Equipo,
    Cotizacion,
    ReglaEquipoMaterial,
    ReglaMaterialMaterial
)
from .forms import (
    ObraForm,
    ObraPage1Form,
    ObraPage2Form,
    FaseForm,
    TareaForm,
    MaterialForm,
    PersonalForm,
    Pagina1Form,
    Pagina2Form,
    Pagina3Form
)

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
        context['requerimientos'] = {} 
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
    # Cambiamos la clase del formulario para que incluya todos los campos de la Tarea
    form_class = TareaForm
    template_name = 'project_app/tarea_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tarea = self.object
        context['fase'] = tarea.fase
        context['materiales'] = Material.objects.all().order_by('nombre')
        
        # Cargar las cantidades requeridas existentes para rellenar la tabla
        requerimientos_actuales = {
            req.material.pk: req.cantidad_requerida 
            for req in tarea.requerimientomaterial_set.all()
        }
        context['requerimientos'] = requerimientos_actuales
        return context

    def form_valid(self, form):
        with transaction.atomic():
            # 1. Guardar la información principal de la Tarea
            self.object = form.save()

            # 2. Eliminar los requerimientos de material existentes
            # Esto simplifica el proceso de actualización (se borra todo y se vuelve a crear)
            RequerimientoMaterial.objects.filter(tarea=self.object).delete()
            
            # 3. Procesar los nuevos datos de la tabla de materiales (similar a TareaCreateView)
            for key, value in self.request.POST.items():
                if key.startswith('material-quantity-'):
                    try:
                        material_pk = int(key.split('-')[-1])
                        # Usar float() para validar la entrada y permitir decimales
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
    
    def get_queryset(self):
        queryset = super().get_queryset()
        sistema_filtro = self.kwargs.get('sistema') 
        if sistema_filtro:
            if sistema_filtro.upper() in ['VRF', 'CHW']:
                queryset = queryset.filter(sistema__iexact=sistema_filtro)
        return queryset.order_by('nombre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['material_form'] = MaterialForm()
        context['sistemas'] = Material.SISTEMA_CHOICES
        context['sistema_actual'] = self.kwargs.get('sistema', 'Todos')
        return context

    def post(self, request, *args, **kwargs):
        # Actualización de costos
        if 'update_costs' in request.POST:
            with transaction.atomic():
                for key, value in request.POST.items():
                    if key.startswith('cost-'):
                        try:
                            material_pk = int(key.split('-')[-1])
                            costo = float(value.replace(',', '.')) if value else 0.0
                            if costo >= 0:
                                Material.objects.filter(pk=material_pk).update(costo_unitario=costo)
                        except (ValueError, IndexError):
                            continue

        # Actualización de stock
        if 'update_stock' in request.POST:
            with transaction.atomic():
                for key, value in request.POST.items():
                    if key.startswith('stock-'):
                        try:
                            material_pk = int(key.split('-')[-1])
                            stock = float(value.replace(',', '.')) if value else 0.0
                            if stock >= 0:
                                Material.objects.filter(pk=material_pk).update(stock=stock)
                        except (ValueError, IndexError):
                            continue

        sistema_actual = self.kwargs.get('sistema')
        if sistema_actual:
            return redirect('material-list-filter', sistema=sistema_actual)
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

class CustomLoginView(LoginView):
    template_name = 'project_app/login.html'

def gantt_data_view(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    
    # 1. Obtener y ordenar las tareas por fecha de inicio
    # (ya lo tienes correctamente)
    tareas = Tarea.objects.filter(fase__obra=obra).order_by('fecha_inicio', 'fase__id',)
    
    # Obtener las fases de la obra, el orden inicial no es crítico aquí
    fases_obra = Fase.objects.filter(obra=obra).order_by('id')
    
    # Lista para almacenar los objetos del diagrama de Gantt
    gantt_data_fases = [] # Usaremos una lista temporal para fases
    gantt_data_tareas = [] # Usaremos una lista temporal para tareas

    tareas_por_fase = {}
    for tarea in tareas:
        fase_id = tarea.fase.id
        if fase_id not in tareas_por_fase:
            tareas_por_fase[fase_id] = []
        tareas_por_fase[fase_id].append(tarea)

    for fase in fases_obra:
        tareas_en_fase = tareas_por_fase.get(fase.id, [])
        
        if not tareas_en_fase:
            continue

        # Calcular la fecha de inicio y fin de la FASE
        fecha_inicio_fase = min(t.fecha_inicio for t in tareas_en_fase)
        fecha_fin_fase = max(t.fecha_fin_estimada for t in tareas_en_fase)

        total_avance = sum(t.porcentaje_avance for t in tareas_en_fase)
        promedio_avance = total_avance / len(tareas_en_fase) if tareas_en_fase else Decimal('0.00')

        # 1. Objeto de la FASE (el padre)
        gantt_data_fases.append({
            'id': f'fase-{fase.id}',
            'name': fase.nombre,
            'start': fecha_inicio_fase.strftime('%Y-%m-%d'),
            'end': fecha_fin_fase.strftime('%Y-%m-%d'), 
            'progress': float(promedio_avance),
            'dependencies': '',
            'custom_class': 'gantt-phase',
            'fecha_inicio_orden': fecha_inicio_fase # Clave temporal para ordenar
        })

        # 2. Objetos de las Tareas (los hijos)
        for tarea in tareas_en_fase:
            start = tarea.fecha_inicio.strftime('%Y-%m-%d')
            end = tarea.fecha_fin_estimada.strftime('%Y-%m-%d')
            
            gantt_data_tareas.append({
                'id': f'tarea-{tarea.id}',
                'name': tarea.nombre,
                'start': start,
                'end': end,
                'progress': float(tarea.porcentaje_avance),
                'dependencies': f'fase-{tarea.fase.id}',
            })

    # 3. ORDENAR CRONOLÓGICAMENTE las fases
    # Las fases se ordenan por la 'fecha_inicio_orden' temporal
    gantt_data_fases.sort(key=lambda x: x['fecha_inicio_orden'])
    
    # 4. Combinar las fases y las tareas.
    # El diagrama de Gantt (como el JSGanttImproved) generalmente espera 
    # que la tarea vaya inmediatamente después de su fase padre en la lista 
    # para asegurar la correcta anidación en la interfaz.
    gantt_data_final = []
    
    # Volvemos a iterar sobre las fases ya ORDENADAS
    for fase_data in gantt_data_fases:
        # Eliminar la clave temporal de ordenamiento antes de añadir al JSON
        fecha_inicio_orden = fase_data.pop('fecha_inicio_orden')
        gantt_data_final.append(fase_data)

        # Buscar y añadir las tareas que dependen de esta fase
        fase_id = fase_data['id']
        tareas_de_esta_fase = [t for t in gantt_data_tareas if t['dependencies'] == fase_id]
        
        # Las tareas ya estaban ordenadas cronológicamente en la consulta inicial
        gantt_data_final.extend(tareas_de_esta_fase)
            
    return JsonResponse(gantt_data_final, safe=False)

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
    
def calculadora_velumoide(request):
    # No se necesita lógica de servidor, solo renderizar el template.
    return render(request, 'project_app/calculadora_velumoide.html', {})

def calculadora_tornilleria(request):
    # No se necesita lógica de servidor, solo renderizar el template.
    return render(request, 'project_app/calculadora_tornilleria.html', {})

# --- Wizard para la creación de Obra y Fases ---
FASES_WIZARD_FORMS = [
    ("obra_data", ObraPage1Form),
    ("card_selection", ObraPage2Form)
]
TEMPLATES_WIZARD_OBRA = {
    "obra_data": "project_app/obra_form.html",
    "card_selection": "project_app/obra_form2.html",
}

class ObraWizard(SessionWizardView):
    
    def get_template_names(self):
        return [TEMPLATES_WIZARD_OBRA[self.steps.current]]
        
    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        return context

    def done(self, form_list, **kwargs):
        # 1. Unifica los datos
        form_data = [form.cleaned_data for form in form_list]
        data = {}
        for d in form_data:
            data.update(d)
        
        obra_data = data.copy()
        fase_names_raw = self.request.POST.getlist('fases_seleccionadas')
        
        # Si la lista está vacía, la inicializamos a una lista vacía
        fase_names_list = fase_names_raw if fase_names_raw else []
        
        ingeniero_encargado_obj = obra_data.get('ingeniero_encargado')
        
        try:
            with transaction.atomic():
                # Crear la instancia de Obra
                nueva_obra = Obra.objects.create(
                    nombre=obra_data.get('nombre'),
                    descripcion=obra_data.get('descripcion'),
                    direccion=obra_data.get('direccion'),
                    centro_servicio=obra_data.get('centro_servicio'),
                    ingeniero_encargado=ingeniero_encargado_obj, 
                    toneladas_frio=obra_data.get('toneladas_frio'),
                    fecha_inicio=obra_data.get('fecha_inicio'),
                    fecha_fin_estimada=obra_data.get('fecha_fin_estimada'),
                    presupuesto_inicial=obra_data.get('presupuesto_inicial'),
                )
                
                # 2. Crear las Fases
                presupuesto_por_defecto = Decimal('100.00') 

                for fase_name in fase_names_list:
                    Fase.objects.create(
                        obra=nueva_obra,
                        nombre=fase_name,
                        presupuesto_asignado=presupuesto_por_defecto,
                        costo_mano_de_obra=Decimal('0.00')
                    )
                
                # Retorno exitoso
                return redirect('obra-detail', pk=nueva_obra.pk)
        
        except Exception as e:
            print(f"Error al crear Obra/Fases: {e}")
            return redirect('obra-list')

# --- Wizard para el cálculo de Cotizaciones ---
FORMS = [("1", Pagina1Form), ("2", Pagina2Form), ("3", Pagina3Form)]
TEMPLATES = {
    "1": "project_app/corrida1.html",
    "2": "project_app/corrida2.html",
    "3": "project_app/corrida3.html",
}

class CorridaWizard(SessionWizardView):
    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def done(self, form_list, **kwargs):
        form_data = [form.cleaned_data for form in form_list]
        
        # Unifica los datos COMPLETOS, limpios y validados
        data = {}
        for d in form_data:
            data.update(d)

        # 1. Generación del nombre de la Corrida
        nombre = data.pop('nombre_proyecto', 'sin nombre') 
        
        # --- Estructura para el JSONField 'datos' ---
        datos_finales = {
            "cliente": data.pop('cliente', ''),
            "direccion_proyecto": data.pop('direccion_proyecto', ''),
            "descripcion": data.pop('descripcion', ''),
            "ingeniero_encargado": str(data.pop('ingeniero_encargado', None)),
            "equipos": {},
            "tuberias": {}
        }

        # 2. Obtener Códigos de Referencia
        codigos_equipos = list(Equipo.objects.values_list('modelo', flat=True))
        codigos_tuberias = list(Material.objects.values_list('codigo', flat=True))

        # 3. Iterar sobre los datos restantes para clasificar y convertir
        for key, value in data.items():
            try:
                num_value = int(value) 
            except (TypeError, ValueError):
                continue 

            if num_value > 0:
                if key in codigos_equipos:
                    datos_finales["equipos"][key] = num_value
                elif key in codigos_tuberias:
                    datos_finales["tuberias"][key] = num_value

        # 4. Finaliza el guardado con correlativo anual reiniciable
        with transaction.atomic():
            ahora = datetime.now()
            año_actual = ahora.strftime("%Y")
            
            # Calculamos el número correlativo contando registros de este año
            # Nota: Se asume que el modelo tiene un campo de fecha 'created_at' o similar.
            # Si no lo tiene, filtramos por el campo 'correlativo' que contenga el año.
            conteo_año = Corrida.objects.filter(correlativo__contains=f"-{año_actual}-").count()
            nuevo_numero = conteo_año + 1
            
            # Formateamos el nombre (snake_case)
            nombre_slug = slugify(nombre).replace('-', '_')
            
            # Construimos el string: CORR-2024-GS-I-001-nombre_proyecto
            correlativo_final = f"CORR-{año_actual}-GS-I-{nuevo_numero:03d}-{nombre_slug}"

            # Creamos el objeto con todos los datos
            Corrida.objects.create(
                nombre=nombre, 
                datos=datos_finales,
                correlativo=correlativo_final
            )

        return redirect('corrida-list')

class CorridaListView(ListView):
    model = Corrida
    template_name = 'project_app/corrida_list.html'
    context_object_name = 'corridas'

def aplicar_reglas_equipo_material(equipos_dict):
    """Aplica las reglas de equipo a material y retorna un diccionario de materiales."""
    materiales_requeridos = defaultdict(Decimal)

    codigos_equipo = equipos_dict.keys()
    reglas = ReglaEquipoMaterial.objects.filter(
        equipo_origen__modelo__in=codigos_equipo
    ).select_related('equipo_origen')

    for regla in reglas:
        cantidad_equipo = equipos_dict.get(regla.equipo_origen.modelo)
        if cantidad_equipo is not None:
            for item in regla.materiales_requeridos:
                codigo_material = item['codigo']
                cantidad_por_equipo = Decimal(str(item['cantidad']))
                cantidad_total = cantidad_por_equipo * Decimal(str(cantidad_equipo))
                materiales_requeridos[codigo_material] += cantidad_total

    return materiales_requeridos

def aplicar_reglas_material_material(materiales_base_dict):
    materiales_requeridos = defaultdict(Decimal, {k: Decimal(str(v)) for k, v in materiales_base_dict.items()})
    materiales_pendientes = set(materiales_requeridos.keys())

    while materiales_pendientes:
        material_origen_codigo = materiales_pendientes.pop()
        reglas = ReglaMaterialMaterial.objects.filter(
            material_origen__codigo=material_origen_codigo
        )

        for regla in reglas:
            cantidad_origen = materiales_requeridos[material_origen_codigo]
            for item in regla.materiales_requeridos:
                codigo_material_req = item['codigo']
                cantidad_a_agregar = Decimal(str(item['cantidad'])) * cantidad_origen
                if cantidad_a_agregar > 0:
                    if codigo_material_req not in materiales_requeridos:
                        materiales_pendientes.add(codigo_material_req)
                    materiales_requeridos[codigo_material_req] += cantidad_a_agregar

    return {k: float(v) for k, v in materiales_requeridos.items() if v > 0}

def obtener_costos_materiales(materiales_dict):
    """
    Obtiene los costos unitarios de los materiales requeridos.
    Retorna un diccionario mapeando código de material a su costo unitario.
    """
    codigos_materiales = materiales_dict.keys()
    
    # Realiza una sola consulta para obtener los costos de todos los materiales
    # Asume que 'Material' tiene un campo 'codigo' que coincide con las claves del JSON
    materiales_info = Material.objects.filter(
        codigo__in=codigos_materiales
    ).values('codigo', 'costo_unitario')
    
    costos_map = {
        item['codigo']: Decimal(str(item['costo_unitario'])) 
        for item in materiales_info
    }
    return costos_map

@require_http_methods(["GET"])
def CotizacionCreateView(request, corrida_id):
    """
    Toma una Corrida por su ID, aplica las reglas y genera una Cotizacion
    con un correlativo anual reiniciable.
    """
    try:
        corrida = get_object_or_404(Corrida, id=corrida_id)
    except Exception as e:
        return JsonResponse({"error": f"Corrida no encontrada o error: {e}"}, status=404)

    # 1. Obtener los datos de la Corrida
    datos_corrida = corrida.datos
    
    materiales_totales = defaultdict(Decimal, {
        k: Decimal(str(v)) for k, v in datos_corrida.get('tuberias', {}).items()
    })
    
    # 2. Aplicar Reglas Equipo a Material
    equipos_corrida = datos_corrida.get('equipos', {})
    if equipos_corrida:
        materiales_por_equipo = aplicar_reglas_equipo_material(equipos_corrida)
        for codigo, cantidad in materiales_por_equipo.items():
            materiales_totales[codigo] += cantidad

    # 3. Aplicar Reglas Material a Material
    materiales_requeridos_con_decimales = aplicar_reglas_material_material(materiales_totales)

    # 4. Obtener Costos Unitarios
    costos_unitarios = obtener_costos_materiales(materiales_requeridos_con_decimales)
    
    utilidad = 0.30  # 30% de utilidad
    materiales_finales = {}
    for codigo, cantidad_dec in materiales_requeridos_con_decimales.items():
        costo_unitario = costos_unitarios.get(codigo, Decimal('0.00'))
        materiales_finales[codigo] = {
            'cantidad': float(cantidad_dec),
            'costo_unitario': float(costo_unitario)*(1 + utilidad)
        }

    # 5. Preparar el JSON de salida
    datos_cotizacion = {
        'cliente': datos_corrida.get('cliente', ''),
        'direccion_proyecto': datos_corrida.get('direccion_proyecto', ''),
        'descripcion': datos_corrida.get('descripcion', ''),
        'ingeniero_encargado': datos_corrida.get('ingeniero_encargado', ''),
        'materiales': materiales_finales
    }

    try:
        with transaction.atomic():
            # 1. Intentamos obtener una cotización existente para esta corrida
            cotizacion_existente = Cotizacion.objects.filter(corrida=corrida).first()

            if cotizacion_existente:
                # Si ya existe, mantenemos su correlativo
                correlativo_final = cotizacion_existente.correlativo
            else:
                # 2. Si es nueva, generamos el correlativo siguiendo la lógica anual
                ahora = datetime.now()
                año_actual = ahora.strftime("%Y")
                
                ultimo_ref = Cotizacion.objects.filter(
                    correlativo__contains=f"-{año_actual}-"
                ).order_by('-correlativo').first()

                if ultimo_ref and ultimo_ref.correlativo:
                    try:
                        partes = ultimo_ref.correlativo.split('-')
                        nuevo_numero = int(partes[4]) + 1
                    except (IndexError, ValueError):
                        nuevo_numero = Cotizacion.objects.filter(correlativo__contains=f"-{año_actual}-").count() + 1
                else:
                    nuevo_numero = 1
                
                nombre_slug = slugify(corrida.nombre).replace('-', '_')
                correlativo_final = f"COT-{año_actual}-GS-I-{nuevo_numero:03d}-{nombre_slug}"

            # 3. Guardamos
            cotizacion, created = Cotizacion.objects.update_or_create(
                corrida=corrida,
                defaults={
                    'nombre': corrida.nombre,
                    'correlativo': correlativo_final,
                    'datos': datos_cotizacion,
                }
            )
        
        return redirect('cotizacion-list')
    
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error al generar la Cotización: {e}"
        }, status=500)
    
class CotizacionListView(ListView):
    model = Cotizacion
    template_name = 'project_app/cotizacion_list.html'
    context_object_name = 'cotizaciones'

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        # Dibujar en la parte inferior derecha
        text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(550, 30, text)

def detalle_cotizacion(request, pk):
    cotizacion = get_object_or_404(Cotizacion, pk=pk)
    datos = cotizacion.datos

    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        leftMargin=50, 
        rightMargin=50, 
        topMargin=160, 
        bottomMargin=50
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    style_material = ParagraphStyle('MatStyle', parent=styles['Normal'], fontSize=9, leading=10)
    style_familia = ParagraphStyle('FamStyle', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')

    def membrete(canvas, doc):
        canvas.saveState()
        logo_path = f"{settings.BASE_DIR}/app/static/img/logo.jpeg"
        try:
            canvas.drawImage(logo_path, 50, 710, width=100, height=50, preserveAspectRatio=True, mask='auto')
        except:
            pass 

        canvas.setFont("Helvetica", 7)
        fecha_gen = cotizacion.fecha_generacion.strftime('%d/%m/%Y')
        canvas.drawRightString(550, 755, f"Fecha generación: {fecha_gen}")
        fecha_mod = cotizacion.fecha_modificacion.strftime('%d/%m/%Y')
        canvas.drawRightString(550, 745, f"Fecha modificación: {fecha_mod}")
        
        y_pos = 690
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(60, y_pos, f"Cotización: {cotizacion.nombre}")
        y_pos -= 15
        canvas.setFont("Helvetica", 10)
        canvas.drawString(60, y_pos, f"Cliente: {datos.get('cliente', 'N/A')}")
        y_pos -= 15
        canvas.drawString(60, y_pos, f"Dirección del Proyecto: {datos.get('direccion_proyecto', 'N/A')}")
        y_pos -= 15
        canvas.drawString(60, y_pos, f"Ingeniero Encargado: {datos.get('ingeniero_encargado', 'N/A')}")
        canvas.restoreState()

    # --- PROCESAMIENTO DE DATOS ---
    materiales_json = datos.get('materiales', {})
    codigos_materiales = list(materiales_json.keys())
    materiales_objs = Material.objects.filter(codigo__in=codigos_materiales)
    materiales_dict = {m.codigo: m for m in materiales_objs}

    materiales_por_familia = defaultdict(list)
    for codigo, info in materiales_json.items():
        obj = materiales_dict.get(codigo)
        familia_nombre = obj.familia if obj else "OTRO"
        materiales_por_familia[familia_nombre].append({
            'codigo': codigo,
            'nombre': obj.nombre if obj else "Desconocido",
            'cantidad': float(info.get('cantidad', 0)),
            'costo': float(info.get('costo_unitario', 0))
        })

    # --- LÓGICA DE ORDENAMIENTO PERSONALIZADO ---
    # Definimos el orden de las familias (en minúsculas para comparar)
    orden_prioridad = ['tuberia', 'anclaje', 'electricidad', 'drenaje']
    
    def prioridad_familia(nombre_familia):
        nombre_normalizado = nombre_familia.lower()
        if nombre_normalizado in orden_prioridad:
            return orden_prioridad.index(nombre_normalizado)
        return len(orden_prioridad) # Las que no están en la lista van al final

    familias_presentes = sorted(materiales_por_familia.keys(), key=prioridad_familia)

    # --- CONSTRUCCIÓN DE LA TABLA ---
    data = [["Código", "Material", "Cantidad", "Costo Unitario ($)", "Precio ($)"]]
    gran_total = 0

    for familia in familias_presentes:
        # Fila de Título de Familia
        data.append(["", Paragraph(familia.upper(), style_familia), "", "", ""])
        
        # Ordenar materiales internamente por código
        lista_materiales = sorted(materiales_por_familia[familia], key=lambda x: x['codigo'])
        
        subtotal_familia = 0
        for mat in lista_materiales:
            precio_linea = mat['cantidad'] * mat['costo']
            subtotal_familia += precio_linea
            
            data.append([
                mat['codigo'],
                Paragraph(mat['nombre'], style_material),
                f"{mat['cantidad']}",
                f"{mat['costo']:.2f}",
                f"{precio_linea:.2f}"
            ])
        
        # Fila de Subtotal
        data.append(["", "", "", f"SUBTOTAL {familia.upper()}", f"{subtotal_familia:.2f}"])
        gran_total += subtotal_familia

    # Espacio y Fila de Total General
    data.append(["", "", "", "", ""]) # Separador visual
    data.append(["", "", "", "TOTAL GENERAL", f"{gran_total:.2f}"])

    # --- ESTILOS ---
    col_widths = [70, 250, 60, 80, 80]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
    ]

    for i, row in enumerate(data):
        # Estilo para las filas de Familia (la segunda columna tiene el Paragraph)
        if row[1] and isinstance(row[1], Paragraph) and row[1].getPlainText() in [f.upper() for f in familias_presentes]:
            t_style.append(('BACKGROUND', (0, i), (-1, i), colors.lightgrey))
        
        # Estilo para Subtotales y Total
        if "SUBTOTAL" in str(row[3]) or "TOTAL GENERAL" in str(row[3]):
            t_style.append(('FONTNAME', (3, i), (4, i), 'Helvetica-Bold'))
            t_style.append(('LINEABOVE', (3, i), (4, i), 0.5, colors.black))

    table.setStyle(TableStyle(t_style))
    elements.append(table)

    doc.build(elements, onFirstPage=membrete, onLaterPages=membrete, canvasmaker=NumberedCanvas)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Cotizacion_{cotizacion.id}.pdf"'
    return response

class CotizacionUpdateView(UpdateView):
    model = Cotizacion
    fields = ['nombre']
    template_name = 'project_app/cotizacion_edit_form.html'
    context_object_name = 'cotizacion'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cotizacion = self.object
        
        # 1. Obtener los códigos de los materiales que YA están en la cotización
        materiales_actuales_dict = cotizacion.datos.get('materiales', {})
        codigos_en_uso = materiales_actuales_dict.keys()
        
        # 2. Filtrar familias solo de esos materiales específicos
        familias_en_uso = Material.objects.filter(
            codigo__in=codigos_en_uso
        ).values_list('familia', flat=True).distinct()
        
        context['familias'] = sorted(list(filter(None, familias_en_uso)))
        context['todos_los_materiales'] = Material.objects.all().order_by('nombre')
        context['materiales_actuales'] = materiales_actuales_dict
        return context

    def form_valid(self, form):
        original = self.get_object()
        nuevo_nombre = form.cleaned_data.get('nombre', original.nombre)

        # Lógica de utilidades dinámicas por familia desde el POST
        utilidades_por_familia = {}
        for key, value in self.request.POST.items():
            if key.startswith('utilidad-'):
                familia_nome = key.replace('utilidad-', '')
                try:
                    utilidades_por_familia[familia_nome] = float(value) / 100
                except ValueError:
                    utilidades_por_familia[familia_nome] = 0.30

        # Procesar nuevos materiales y asignar su utilidad correspondiente
        nuevos_materiales = {}
        for key, value in self.request.POST.items():
            if key.startswith('material-quantity-'):
                try:
                    codigo_mat = key.replace('material-quantity-', '')
                    cantidad = float(value) if value else 0
                    if cantidad > 0:
                        mat_obj = get_object_or_404(Material, codigo=codigo_mat)
                        # Se aplica la utilidad capturada del formulario para su familia
                        utilidad_aplicar = utilidades_por_familia.get(mat_obj.familia, 0.30)
                        
                        nuevos_materiales[codigo_mat] = {
                            'cantidad': cantidad,
                            'costo_unitario': float(mat_obj.costo_unitario) * (1 + utilidad_aplicar)
                        }
                except (ValueError, Material.DoesNotExist):
                    continue

        # Lógica de creación de revisión (mantenida de tu código original)
        m = re.match(r'^(.*?)(?:_rev_(\d+))?$', original.correlativo)
        base_correlativo = m.group(1) if m else original.correlativo
        correlativos_existentes = Cotizacion.objects.filter(correlativo__startswith=base_correlativo).values_list('correlativo', flat=True)
        max_rev = 0
        for c in correlativos_existentes:
            mm = re.search(r'_rev_(\d+)$', c)
            if mm:
                try:
                    max_rev = max(max_rev, int(mm.group(1)))
                except ValueError: continue

        nuevo_correlativo = f"{base_correlativo}_rev_{max_rev + 1}"

        Cotizacion.objects.create(
            corrida=original.corrida,
            nombre=nuevo_nombre,
            correlativo=nuevo_correlativo,
            datos={'cliente': original.datos.get('cliente'), 
                   'ingeniero_encargado': original.datos.get('ingeniero_encargado'),
                   'direccion_proyecto': original.datos.get('direccion_proyecto'),
                   'descripcion': original.datos.get('descripcion'),
                   'materiales': nuevos_materiales}
        )
        return redirect('cotizacion-list')


User = get_user_model()
@transaction.atomic
def generar_obra_desde_cotizacion(request, cotizacion_id):
    # 1. Obtener la cotización y sus datos
    cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id)
    datos = cotizacion.datos
    materiales_json = datos.get('materiales', {})
    
    # 2. Buscar al ingeniero encargado (Asumiendo que el string coincide con username o first_name)
    # Nota: En producción, es mejor usar IDs, pero aquí buscamos por nombre según el JSON
    nombre_ingeniero = datos.get('ingeniero_encargado', '')
    ingeniero = User.objects.filter(username__icontains=nombre_ingeniero).first()
    if not ingeniero:
        # Fallback: intentar buscar por nombre
        ingeniero = User.objects.filter(first_name__icontains=nombre_ingeniero).first()

    # 3. Configuración de Mapeo (Lógica de Negocio)
    # Estructura: Fase -> Tarea -> Lista de Familias que activan esta tarea
    MAPEO_LOGICO = {
        'TRANSPORTE': {
            'tareas': {
                'Izaje': ['IZAJE']
            }
        },
        'MECANICA': {
            'tareas': {
                'Instalación de Anclajes': ['ANCLAJE',],
                'Instalación de Tuberías': ['TUBERIA', 'TUBERIAS', 'TORNILLERIA', 'VALVULAS'],
                'Instalación de Drenajes': ['DRENAJE'],
            }
        },
        'ELECTRICIDAD': {
            'tareas': {
                'Instalación Eléctrica': ['ELECTRICIDAD']
            }
        },
        'VENTILACION': {
            'tareas': {
                'Instalación de Ductos': ['DUCTERIA']
            }
        },
        'ARRANQUE': {
            'tareas': {
                'Pruebas y Arranque': ['REFRIGERANTE']
            }
        }
    }

    # 4. Procesamiento de Materiales y Cálculo de Presupuesto Inicial
    presupuesto_total_obra = Decimal('0.00')
    
    # Diccionario temporal para agrupar materiales por tarea antes de crear objetos DB
    # Estructura: {'NombreFase': {'NombreTarea': [List of (MaterialObj, cantidad, costo_total)]}}
    planificacion = {} 
    
    codigos_materiales = list(materiales_json.keys())
    db_materiales = Material.objects.filter(codigo__in=codigos_materiales)
    material_map = {m.codigo: m for m in db_materiales}

    for codigo, info in materiales_json.items():
        if codigo not in material_map:
            # Opción: Saltar o lanzar error. Aquí saltamos con advertencia en consola.
            print(f"Advertencia: Material {codigo} no encontrado en Base de Datos.")
            continue

        material = material_map[codigo]
        cantidad = Decimal(str(info['cantidad']))
        costo_unitario = Decimal(str(info['costo_unitario']))
        costo_total_item = cantidad * costo_unitario
        
        presupuesto_total_obra += costo_total_item
        familia_upper = material.familia.upper()

        # Determinar a qué fase y tarea pertenece este material
        asignado = False
        for fase_key, fase_data in MAPEO_LOGICO.items():
            for tarea_key, familias_validas in fase_data['tareas'].items():
                if familia_upper in familias_validas:
                    # Inicializar estructuras si no existen
                    if fase_key not in planificacion:
                        planificacion[fase_key] = {}
                    if tarea_key not in planificacion[fase_key]:
                        planificacion[fase_key][tarea_key] = []
                    
                    # Agregar requerimiento a la memoria
                    planificacion[fase_key][tarea_key].append({
                        'material': material,
                        'cantidad': cantidad,
                        'costo': costo_total_item
                    })
                    asignado = True
                    break # Sale del loop de tareas
            if asignado:
                break # Sale del loop de fases

    # 5. Definición de Fechas (Línea de Tiempo)
    fecha_inicio_proyecto = timezone.now().date()
    
    # Duraciones y lógica específica
    duracion_fase_mecanica = 15
    inicio_tuberias_offset = 3 # Días después del inicio de mecánica
    
    # Calculamos fechas base
    # Transporte (Izaje)
    fecha_inicio_izaje = fecha_inicio_proyecto
    fecha_fin_izaje = fecha_inicio_izaje + timedelta(days=1)
    
    # Mecánica
    fecha_inicio_mecanica = fecha_inicio_proyecto # Asumimos inicia con el proyecto (o día 1 si es secuencial estricto post-izaje)
    fecha_fin_mecanica = fecha_inicio_mecanica + timedelta(days=duracion_fase_mecanica)
    
    # Eléctrica y Ventilación (Paralelas después de mecánica)
    fecha_inicio_paralelas = fecha_fin_mecanica
    fecha_fin_paralelas = fecha_inicio_paralelas + timedelta(days=5)
    
    # Arranque (Al final de todo)
    fecha_inicio_arranque = fecha_fin_paralelas
    fecha_fin_arranque = fecha_inicio_arranque + timedelta(days=3)
    
    fecha_fin_obra = fecha_fin_arranque

    # 6. Creación del Objeto Obra
    obra = Obra.objects.create(
        nombre=cotizacion.nombre, # Según requerimiento
        descripcion=datos.get('descripcion', ''),
        direccion=datos.get('direccion_proyecto', ''),
        ingeniero_encargado=ingeniero,
        fecha_inicio=fecha_inicio_proyecto,
        fecha_fin_estimada=fecha_fin_obra,
        presupuesto_inicial=presupuesto_total_obra,
        # centro_servicio se deja null o se asigna lógica personalizada
    )

    # 7. Creación de Fases, Tareas y Asignación de Materiales
    
    # --- FASE TRANSPORTE ---
    if 'TRANSPORTE' in planificacion:
        data_fase = planificacion['TRANSPORTE']
        # Calcular presupuesto de la fase
        presupuesto_fase = sum(sum(item['costo'] for item in items) for items in data_fase.values())
        
        fase_obj = Fase.objects.create(
            nombre="Transporte",
            obra=obra,
            presupuesto_asignado=presupuesto_fase
        )
        
        if 'Izaje' in data_fase:
            crear_tarea_y_reqs(fase_obj, "Izaje", fecha_inicio_izaje, fecha_fin_izaje, data_fase['Izaje'])

    # --- FASE MECÁNICA ---
    if 'MECANICA' in planificacion:
        data_fase = planificacion['MECANICA']
        presupuesto_fase = sum(sum(item['costo'] for item in items) for items in data_fase.values())
        
        fase_obj = Fase.objects.create(
            nombre="Mecánica",
            obra=obra,
            presupuesto_asignado=presupuesto_fase
        )
        
        # Tarea Anclajes (5 días desde inicio)
        if 'Instalación de Anclajes' in data_fase:
            f_fin_anc = fecha_inicio_mecanica + timedelta(days=5)
            crear_tarea_y_reqs(fase_obj, "Instalación de Anclajes", fecha_inicio_mecanica, f_fin_anc, data_fase['Instalación de Anclajes'])
            
        # Tarea Tuberías (Inicia día 3, termina con la fase)
        if 'Instalación de Tuberías' in data_fase:
            f_ini_tub = fecha_inicio_mecanica + timedelta(days=inicio_tuberias_offset)
            crear_tarea_y_reqs(fase_obj, "Instalación de Tuberías", f_ini_tub, fecha_fin_mecanica, data_fase['Instalación de Tuberías'])

        # Tarea Drenajes (Asumiremos sincronizada con Tuberías)
        if 'Instalación de Drenajes' in data_fase:
            f_ini_tub = fecha_inicio_mecanica + timedelta(days=inicio_tuberias_offset)
            crear_tarea_y_reqs(fase_obj, "Instalación de Drenajes", f_ini_tub, fecha_fin_mecanica, data_fase['Instalación de Drenajes'])

    # --- FASE ELECTRICIDAD ---
    if 'ELECTRICIDAD' in planificacion:
        data_fase = planificacion['ELECTRICIDAD']
        presupuesto_fase = sum(sum(item['costo'] for item in items) for items in data_fase.values())
        
        fase_obj = Fase.objects.create(
            nombre="Electricidad",
            obra=obra,
            presupuesto_asignado=presupuesto_fase
        )
        
        if 'Instalación Eléctrica' in data_fase:
            crear_tarea_y_reqs(fase_obj, "Instalación Eléctrica", fecha_inicio_paralelas, fecha_fin_paralelas, data_fase['Instalación Eléctrica'])

    # --- FASE VENTILACIÓN ---
    if 'VENTILACION' in planificacion:
        data_fase = planificacion['VENTILACION']
        presupuesto_fase = sum(sum(item['costo'] for item in items) for items in data_fase.values())
        
        fase_obj = Fase.objects.create(
            nombre="Ventilación",
            obra=obra,
            presupuesto_asignado=presupuesto_fase
        )
        
        if 'Instalación de Ductos' in data_fase:
            crear_tarea_y_reqs(fase_obj, "Instalación de Ductos", fecha_inicio_paralelas, fecha_fin_paralelas, data_fase['Instalación de Ductos'])

    # --- FASE ARRANQUE (Siempre se crea según requerimiento lógico, aunque no tenga materiales directos en el JSON usualmente) ---
    # Si hay materiales asignables (ej. Gas Refrigerante podría ir aqui o en mecánica), ajustar lógica.
    # Aquí creamos la fase y tarea vacía para agendar tiempos.
    fase_arranque = Fase.objects.create(nombre="Arranque", obra=obra, presupuesto_asignado=0)
    Tarea.objects.create(
        nombre="Arranque del Sistema",
        fase=fase_arranque,
        descripcion="Puesta en marcha y pruebas",
        fecha_inicio=fecha_inicio_arranque,
        fecha_fin_estimada=fecha_fin_arranque
    )

    return JsonResponse({
        "status": "success", 
        "message": f"Obra '{obra.nombre}' generada exitosamente con ID {obra.id}",
        "obra_id": obra.id
    })

def crear_tarea_y_reqs(fase_obj, nombre_tarea, f_inicio, f_fin, items_materiales):
    """
    Función auxiliar para crear tarea y sus requerimientos de material en lote
    """
    tarea = Tarea.objects.create(
        nombre=nombre_tarea,
        fase=fase_obj,
        descripcion=f"Generado automáticamente desde cotización para {nombre_tarea}",
        fecha_inicio=f_inicio,
        fecha_fin_estimada=f_fin
    )
    
    requerimientos = []
    for item in items_materiales:
        requerimientos.append(RequerimientoMaterial(
            tarea=tarea,
            material=item['material'],
            cantidad_requerida=item['cantidad']
        ))
    
    # Bulk create para mejor rendimiento
    if requerimientos:
        RequerimientoMaterial.objects.bulk_create(requerimientos)