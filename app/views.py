import datetime
import json
import re
from datetime import datetime
from decimal import Decimal

# Django
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
from django.contrib.auth.decorators import login_required

# Terceros
from formtools.wizard.views import SessionWizardView

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
    Equipo
)
from .forms import (
    ObraForm,
    ObraPage1Form,
    ObraPage2Form,
    FaseForm,
    TareaForm,
    TareaUpdateProgressForm,
    RequerimientoMaterialFormSet,
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

# --- Nuevo Wizard para el cálculo y guardado de Cotizaciones ---
FORMS = [("1", Pagina1Form), ("2", Pagina2Form), ("3", Pagina3Form)]
TEMPLATES = {
    "1": "project_app/pagina1.html",
    "2": "project_app/pagina2.html",
    "3": "project_app/pagina3.html",
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

class CotizacionWizard(SessionWizardView):
    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def done(self, form_list, **kwargs):
        # Cuando el formulario se completa, procesa los datos
        form_data = [form.cleaned_data for form in form_list]
        
        # Unifica los datos en un solo diccionario
        data = {}
        for d in form_data:
            data.update(d)
        
        # Genera el nombre único para la Corrida
        original_name = data.pop('nombre_proyecto', 'sin nombre')
        date_str = datetime.now().strftime("%y%m%d")
        snake_case_name = to_snake_case(original_name)
        final_name = f"CORR-{date_str}-{snake_case_name}"

        # 'datos' es un campo JSONField
        Corrida.objects.create(nombre=final_name, datos=data)
        
        return redirect('corrida-list') # Redirecciona a una página de confirmación

class CorridaListView(ListView):
    model = Corrida
    template_name = 'project_app/corrida_list.html'
    context_object_name = 'corridas'





# --- Vista para generar Cotización desde una Corrida ---
from collections import defaultdict
from .models import Corrida, Cotizacion, CotizacionEquipo, CotizacionMaterial, ReglaEquipoMaterial, ReglaMaterialMaterial

class GenerarCotizacionView(View):
    def post(self, request, corrida_id):
        corrida = get_object_or_404(Corrida, pk=corrida_id)
        datos = corrida.datos # El JSON de la corrida
        
        # 1. Preparar el cálculo de materiales
        # Usamos defaultdict para consolidar las cantidades por código de material.
        materiales_totales = defaultdict(float)
        
        # Guardar equipos solicitados para la cotización
        equipos_solicitados = {} 
        
        # --- Lógica de la Cotización en una Transacción ---
        with transaction.atomic():
            # Crear la Cotizacion (se actualizará el costo_total al final)
            cotizacion = Cotizacion.objects.create(
                corrida=corrida,
                nombre=f"Cotización {corrida.nombre}",
                datos_corrida_historico=datos
            )

            # 2. Procesar Equipos de la Corrida
            for codigo_equipo, cantidad_equipo in datos.get('equipos', {}).items():
                try:
                    equipo = Equipo.objects.get(modelo=codigo_equipo)
                    equipos_solicitados[equipo.pk] = cantidad_equipo
                    
                    # 2.1. Guardar el detalle de Equipo en la Cotización
                    CotizacionEquipo.objects.create(
                        cotizacion=cotizacion,
                        equipo=equipo,
                        cantidad=cantidad_equipo,
                        costo_unitario=0.00, # Asume un campo de costo unitario si el Equipo lo tiene
                        costo_total_linea=0.00
                    )
                    
                    # 2.2. Aplicar Reglas Equipo -> Material
                    reglas_em = ReglaEquipoMaterial.objects.filter(equipo_origen=equipo)
                    for regla in reglas_em:
                        materiales_totales[regla.material_requerido.codigo] += \
                            regla.cantidad_requerida * cantidad_equipo
                except Equipo.DoesNotExist:
                    # Manejar error si el equipo no existe
                    pass

            # 3. Procesar Materiales Directos de la Corrida
            for codigo_material, cantidad_material in datos.get('tuberias', {}).items():
                # Agregar a los materiales totales para el siguiente paso (Reglas Material -> Material)
                materiales_totales[codigo_material] += cantidad_material 
            
            
            # 4. Aplicar Reglas Material -> Material a los materiales base (directos + los de equipo)
            materiales_adicionales = defaultdict(float)
            for codigo_origen, cantidad_origen in materiales_totales.items():
                try:
                    material_origen = Material.objects.get(codigo=codigo_origen)
                    reglas_mm = ReglaMaterialMaterial.objects.filter(material_origen=material_origen)
                    for regla in reglas_mm:
                        # Se usa materiales_adicionales para evitar aplicar reglas 
                        # sobre los materiales que se acaban de generar en esta iteración.
                        materiales_adicionales[regla.material_requerido.codigo] += \
                            regla.cantidad_requerida * cantidad_origen
                except Material.DoesNotExist:
                    pass
            
            # 5. Consolidar y Guardar Materiales en la Cotización
            materiales_totales_final = materiales_totales
            
            # Agregar los materiales adicionales
            for codigo_add, cantidad_add in materiales_adicionales.items():
                 materiales_totales_final[codigo_add] += cantidad_add
            
            costo_total_cotizacion = 0.00

            for codigo_material, cantidad_total in materiales_totales_final.items():
                try:
                    material = Material.objects.get(codigo=codigo_material)
                    costo_linea = material.costo_unitario * cantidad_total
                    costo_total_cotizacion += costo_linea
                    
                    # Guardar el detalle de Material en la Cotización
                    CotizacionMaterial.objects.create(
                        cotizacion=cotizacion,
                        material=material,
                        cantidad=cantidad_total,
                        costo_unitario=material.costo_unitario,
                        costo_total_linea=costo_linea,
                        origen_regla='Compilado' # Origen es el resultado de la compilación
                    )
                except Material.DoesNotExist:
                    pass

            # 6. Actualizar Costo Total de la Cotización (Incluye Equipos y Materiales)
            # Nota: Debes replicar la lógica de costo para los CotizacionEquipo si lo requieres.
            cotizacion.costo_total = costo_total_cotizacion 
            cotizacion.save()

        # Redirigir a la página de detalle de la cotización
        return redirect('detalle_cotizacion', pk=cotizacion.pk)


# En 'urls.py' de tu aplicación
# from .views import GenerarCotizacionView
# urlpatterns = [
#     path('cotizar/<int:corrida_id>/',  GenerarCotizacionView.as_view(), name='generar_cotizacion'),
#     path('cotizacion/<int:pk>/', DetalleCotizacionView.as_view(), name='detalle_cotizacion'),
# ]