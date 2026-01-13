import datetime
import json
import re
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

# Django
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView,
    View
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

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

# --- Nuevo Wizard para la creación de Obra y Fases ---
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

# --- Wizard para el cálculo y guardado de Cotizaciones ---
FORMS = [("1", Pagina1Form), ("2", Pagina2Form), ("3", Pagina3Form)]
TEMPLATES = {
    "1": "project_app/corrida1.html",
    "2": "project_app/corrida2.html",
    "3": "project_app/corrida3.html",
}

def to_snake_case(name):
    """Convierte una cadena a formato snake_case (e.g., 'Mi Proyecto' -> 'mi_proyecto')."""
    # 1. Reemplazar cualquier cosa que no sea letra o número por un espacio
    s1 = re.sub(r'[^a-zA-Z0-9]', ' ', name)
    # 2. Convertir a Mayúsculas
    s2 = s1.upper()
    # 3. Reemplazar grupos de espacios por un solo guion bajo y limpiar guiones iniciales/finales
    s3 = re.sub(r'\s+', '_', s2).strip('_')
    return s3

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
        # Extrae el nombre del proyecto para el nombre de la instancia (y lo quita de 'data')
        original_name = data.pop('nombre_proyecto', 'sin nombre') 
        
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
                # Convierte el valor a entero.
                num_value = int(value) 
            except (TypeError, ValueError):
                # Ignora si no es un número válido
                continue 

            # Si el valor es mayor que cero, clasifica y guarda
            if num_value > 0:
                if key in codigos_equipos:
                    # El campo corresponde a un equipo
                    datos_finales["equipos"][key] = num_value
                elif key in codigos_tuberias:
                    # El campo corresponde a una tubería
                    datos_finales["tuberias"][key] = num_value

        # 4. Finaliza el guardado
        date_str = datetime.now().strftime("%y%m%d")
        snake_case_name = to_snake_case(original_name) 
        final_name = f"CORR-{date_str}-{snake_case_name}"

        # Guarda la Corrida
        # NOTA: Los datos a guardar son 'datos_finales'
        Corrida.objects.create(nombre=final_name, datos=datos_finales)
        print(f"Corrida '{final_name}' creada con datos: {datos_finales}")
        
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
    Toma una Corrida por su ID, aplica las reglas y genera una Cotizacion.
    """
    try:
        corrida = get_object_or_404(Corrida, id=corrida_id)
    except Exception as e:
        return JsonResponse({"error": f"Corrida no encontrada o error: {e}"}, status=404)

    # 1. Obtener los datos de la Corrida
    datos_corrida = corrida.datos
    
    # Inicializar el total de materiales con las tuberías (que son materiales)
    # **IMPORTANTE: Mantenemos el resultado como Decimal hasta el final.**
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
    
    materiales_finales = {}
    
    # 5. Reestructurar el JSON final y calcular totales (opcional)
    for codigo, cantidad_dec in materiales_requeridos_con_decimales.items():
        costo_unitario = costos_unitarios.get(codigo, Decimal('0.00')) # Usa 0 si no se encuentra el material

        # Convertir Decimal a float para el JSON final que se guarda/retorna
        materiales_finales[codigo] = {
            'cantidad': float(cantidad_dec),
            'costo_unitario': float(costo_unitario)
        }

    # 6. Preparar el JSON de salida y la Cotización
    # El JSON de la Cotización debe ser solo de materiales
    datos_cotizacion = {
        'cliente': datos_corrida.get('cliente', ''),
        'direccion_proyecto': datos_corrida.get('direccion_proyecto', ''),
        'descripcion': datos_corrida.get('descripcion', ''),
        'ingeniero_encargado': datos_corrida.get('ingeniero_encargado', ''),
        'materiales': materiales_finales
        }
    
    # ... (Generar el nombre de la cotización - se mantiene igual) ...
    fecha_str = datetime.now().strftime("%y%m%d")
    nombre_base = corrida.nombre.replace('CORR-', '')
    partes = nombre_base.split('-', 1)
    if len(partes) > 1 and partes[0].isdigit() and len(partes[0]) == 6:
        sufijo_nombre = partes[1]
    else:
        sufijo_nombre = nombre_base
    nombre_cotizacion = f"COT-{fecha_str}-{sufijo_nombre}"

    try:
        # 7. Guardar la Cotización
        cotizacion, created = Cotizacion.objects.update_or_create(
            corrida=corrida,
            defaults={
                'nombre': nombre_cotizacion,
                'datos': datos_cotizacion,
            }
        )
        
        # 8. Redireccionar a la lista de cotizaciones
        return redirect('cotizacion-list')

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error al generar o guardar la Cotización: {e}",
            "nombre_propuesto": nombre_cotizacion,
            "datos_generados": datos_cotizacion
        }, status=500)
    
class CotizacionListView(ListView):
    model = Cotizacion
    template_name = 'project_app/cotizacion_list.html'
    context_object_name = 'cotizaciones'

# --- Clase para manejar la numeración "X de Y" ---
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
        fecha_gen = timezone.now().strftime('%d/%m/%Y %H:%M')
        canvas.drawRightString(550, 755, f"Fecha generación: {fecha_gen}")
        
        y_pos = 690
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(60, y_pos, f"Cotización: {cotizacion.nombre}")
        y_pos -= 15
        canvas.setFont("Helvetica", 10)
        canvas.drawString(60, y_pos, f"Cliente: {datos.get('cliente', 'N/A')}")
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

    doc.build(elements, onFirstPage=membrete, onLaterPages=membrete)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Cotizacion_{cotizacion.id}.pdf"'
    return response