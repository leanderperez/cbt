# Estándar de Python
import datetime
import json
from datetime import datetime
from decimal import Decimal

# Django
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView,
    View
)

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
    Cotizacion
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
    
    # MODIFICADO: Añadimos get_queryset para filtrar por sistema
    def get_queryset(self):
        queryset = super().get_queryset()
        # Obtener el parámetro de la URL (si existe)
        sistema_filtro = self.kwargs.get('sistema') 
        
        if sistema_filtro:
            # Aseguramos que el filtro coincida con las opciones válidas
            # (VRF o CHW que es el alias para Agua Helada)
            if sistema_filtro.upper() in ['VRF', 'CHW']:
                # El filtro se hace sobre el campo 'sistema' del modelo Material
                queryset = queryset.filter(sistema__iexact=sistema_filtro)
                
        return queryset.order_by('nombre') # Ordenamos para consistencia

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['material_form'] = MaterialForm()
        # MODIFICADO: Añadimos las opciones de sistema al contexto
        context['sistemas'] = Material.SISTEMA_CHOICES # Se obtienen de models.py
        # El sistema actualmente seleccionado para mantener el estado
        context['sistema_actual'] = self.kwargs.get('sistema', 'Todos') 
        return context

    def post(self, request, *args, **kwargs):
        # NOTA: La lógica del POST no requiere cambios ya que sigue usando 
        # 'material-list' como la URL de acción del formulario. 
        # La lógica de filtrado se maneja en get_queryset/get_context_data.

        if 'update_costs' in request.POST:
            with transaction.atomic():
                for key, value in request.POST.items():
                    if key.startswith('cost-'):
                        try:
                            material_pk = int(key.split('-')[-1])
                            # Reemplaza la coma por punto para manejar la entrada de decimales
                            costo = float(value.replace(',', '.')) if value else 0.0
                            if costo >= 0: # Permitimos 0 como costo válido
                                Material.objects.filter(pk=material_pk).update(costo_unitario=costo)
                        except (ValueError, IndexError):
                            continue
                            
        # Para que al redirigir se mantenga el filtro activo
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
    tareas = Tarea.objects.filter(fase__obra=obra).order_by('fecha_inicio')
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

FORMS = [("1", Pagina1Form), ("2", Pagina2Form), ("3", Pagina3Form)]
TEMPLATES = {
    "1": "project_app/pagina1.html",
    "2": "project_app/pagina2.html",
    "3": "project_app/pagina3.html",
}

class CalculoWizard(SessionWizardView):
    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def done(self, form_list, **kwargs):
        # Cuando el formulario se completa, procesa los datos
        form_data = [form.cleaned_data for form in form_list]
        
        # Unifica los datos en un solo diccionario
        data = {}
        for d in form_data:
            data.update(d)
        
        # Guarda los datos en la base de datos con un nombre específico
        # Usa el nombre_proyecto para identificar el registro
        nombre = data.pop('nombre_proyecto', 'Proyecto sin nombre')
        Cotizacion.objects.create(nombre=nombre, datos=data) # 'datos' es un campo JSONField
        
        return redirect('confirmacion') # Redirecciona a una página de confirmación

def confirmacion_guardado(request):
    return render(request, 'project_app/confirmacion.html')
    
def editar_proyecto(request, nombre_proyecto):
    proyecto = get_object_or_404(Cotizacion, nombre=nombre_proyecto)
    
    # Supongamos que tienes un solo formulario para la edición
    # que contiene todos los campos
    
    # Combina los datos guardados con los datos del formulario (si aplica)
    form_data = proyecto.datos
    
    if request.method == 'POST':
        form = TuFormularioCompleto(request.POST)
        if form.is_valid():
            proyecto.datos.update(form.cleaned_data)
            proyecto.save()
            return redirect('confirmacion_edicion')
    else:
        form = TuFormularioCompleto(initial=form_data)
        
    return render(request, 'tu_app/editar_proyecto.html', {'form': form, 'proyecto': proyecto})



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
        
        # --- FIX: Obtención de fases por el nombre del checkbox ---
        # El ObraPage2Form (paso 'card_selection') está vacío, pero el request.POST contiene 
        # los datos de los checkboxes bajo el nombre 'fases_seleccionadas'.
        # Se obtiene el array de nombres de fase.
        
        # Primero, aseguramos el nombre en el diccionario de datos del Wizard:
        # Nota: El atributo 'get' puede devolver un string si solo se selecciona una fase, 
        # un list si se seleccionan varias, o None.
        fase_names_raw = self.request.POST.getlist('fases_seleccionadas')
        
        # Si la lista está vacía, la inicializamos a una lista vacía
        fase_names_list = fase_names_raw if fase_names_raw else []
        
        # Output de depuración (CONFIRMARÁ si los checkboxes están funcionando)
        print("---------------------------------------")
        print(f"Lista de Fases (Python): {fase_names_list}")
        print(f"Total de fases a crear: {len(fase_names_list)}")
        print("---------------------------------------")
        
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