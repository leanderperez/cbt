from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import (
    Obra, Fase, Tarea, RequerimientoMaterial, Material, Personal, Equipo,
    ReglaEquipoMaterial, ReglaMaterialMaterial
)

class ObraForm(forms.ModelForm):
    # Se incluye el modelo User para el campo de ingeniero encargado
    ingeniero_encargado = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Ingeniero Encargado"
    )
    
    class Meta:
        model = Obra
        fields = [
            'nombre', 'descripcion', 'direccion', 'centro_servicio',
            'ingeniero_encargado', 'fecha_inicio', 'fecha_fin_estimada',
            'presupuesto_inicial', 'toneladas_frio'
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_estimada': forms.DateInput(attrs={'type': 'date'}),
        }

# Nuevo Formulario para el paso 1 del Wizard
class ObraPage1Form(forms.ModelForm):
    ingeniero_encargado = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Ingeniero Encargado"
    )
    
    class Meta:
        model = Obra
        # Excluimos la descripcion para que no se repita el campo con el widget Textarea
        # La incluiremos de nuevo como CharField para el Wizard, para que se muestre como input normal.
        fields = [
            'nombre', 'descripcion', 'direccion', 'centro_servicio',
            'ingeniero_encargado', 'fecha_inicio', 'fecha_fin_estimada',
            'presupuesto_inicial', 'toneladas_frio'
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_estimada': forms.DateInput(attrs={'type': 'date'})
        }

# Nuevo Formulario para el paso 2 del Wizard (Selección de Cards)
class ObraPage2Form(forms.Form):
    # Ya no se necesitan los campos 'selected_fases' ni 'fase_names', 
    # porque los datos serán enviados directamente por los checkboxes HTML
    pass 

class FaseForm(forms.ModelForm):
    class Meta:
        model = Fase
        fields = ['nombre', 'presupuesto_asignado', 'costo_mano_de_obra']

class TareaForm(forms.ModelForm):
    class Meta:
        model = Tarea
        fields = [
            'nombre', 'descripcion', 'fecha_inicio',
            'fecha_fin_estimada', 'costo_mano_de_obra'
        ]
        widgets = {
            'fecha_inicio': forms.DateInput (
                format='%Y-%m-%d', 
                attrs={'type': 'date'}),
            'fecha_fin_estimada': forms.DateInput (
                format='%Y-%m-%d', 
                attrs={'type': 'date'}),
        }

class TareaUpdateProgressForm(forms.ModelForm):
    class Meta:
        model = Tarea
        fields = ['nombre', 'descripcion', 'costo_mano_de_obra']

class RequerimientoMaterialForm(forms.ModelForm):
    class Meta:
        model = RequerimientoMaterial
        fields = ['material', 'cantidad_requerida']

RequerimientoMaterialFormSet = inlineformset_factory(
    Tarea,
    RequerimientoMaterial,
    form=RequerimientoMaterialForm,
    extra=1,
    can_delete=True
)

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['codigo', 'familia', 'nombre', 'unidad', 'sistema', 'costo_unitario', 'stock']
        
class PersonalForm(forms.ModelForm):
    class Meta:
        model = Personal
        fields = ['rif','empresa', 'nombre', 'especialidad', 'telefono', 'telefono_alternativo', 'email', 'direccion']

# Formulario Multi-step para cotizaciones
class Pagina1Form(forms.Form):
    nombre_proyecto = forms.CharField(max_length=100)
    descripcion = forms.CharField(widget=forms.Textarea)

# --- Paso 2: Equipos (Dinámico) ---
class Pagina2Form(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Obtiene todos los equipos de la base de datos
        equipos = Equipo.objects.all()
        
        # Agrega un campo IntegerField para la cantidad de cada equipo
        for equipo in equipos:
            # Usamos el código o ID como nombre del campo (ej: 'MT51255')
            field_name = equipo.modelo # Asume que tienes un campo 'codigo' en tu modelo Equipo
            
            self.fields[field_name] = forms.IntegerField(
                required=False,
                initial=0,
                min_value=0,
                # Usa una etiqueta descriptiva para el template
                label=f"{equipo.nombre} ({equipo.modelo})", 
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )

# --- Paso 3: Tuberías (Dinámico) ---
class Pagina3Form(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        codigos_deseados = [
            'TCF0014','TCF0038','TCF0012','TCF0058','TCF0034','TCF0078',
            'TCR0038','TCR0012','TCR0058','TCR0034','TCR0078',
            'TCR0118','TCR0138','TCR0158','TCR0218'
        ]
        tuberias_dict = {t.codigo: t for t in Material.objects.filter(codigo__in=codigos_deseados)}
        
        # Agrega los campos en el orden de codigos_deseados
        for codigo in codigos_deseados:
            tuberia = tuberias_dict.get(codigo)
            if tuberia:
                self.fields[codigo] = forms.IntegerField(
                    required=False,
                    initial=0,
                    min_value=0,
                    label=f"[{tuberia.codigo}] {tuberia.nombre}",
                    widget=forms.NumberInput(attrs={'class': 'form-control'})
                )

class MaterialesRequeridosField(forms.Field):
    """
    Campo personalizado para ingresar una lista de materiales requeridos y cantidades.
    El valor debe ser una lista de dicts: [{'codigo': 'MAT001', 'cantidad': 5}, ...]
    """
    def to_python(self, value):
        import json
        if not value:
            return []
        if isinstance(value, list):
            return value
        try:
            return json.loads(value)
        except Exception:
            raise forms.ValidationError("Formato inválido. Debe ser una lista de dicts en JSON.")

    def validate(self, value):
        super().validate(value)
        if not isinstance(value, list):
            raise forms.ValidationError("Debe ser una lista.")
        for item in value:
            if not isinstance(item, dict) or 'codigo' not in item or 'cantidad' not in item:
                raise forms.ValidationError("Cada elemento debe ser un dict con 'codigo' y 'cantidad'.")

class ReglaEquipoMaterialForm(forms.ModelForm):
    materiales_requeridos = MaterialesRequeridosField(
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': '[{"codigo": "MAT001", "cantidad": 5}]'}),
        help_text="Ingresa una lista en formato JSON: [{'codigo': 'MAT001', 'cantidad': 5}, ...]"
    )

    class Meta:
        model = ReglaEquipoMaterial
        fields = ['equipo_origen', 'materiales_requeridos']

class ReglaMaterialMaterialForm(forms.ModelForm):
    materiales_requeridos = MaterialesRequeridosField(
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': '[{"codigo": "MAT002", "cantidad": 2}]'}),
        help_text="Ingresa una lista en formato JSON: [{'codigo': 'MAT002', 'cantidad': 2}, ...]"
    )

    class Meta:
        model = ReglaMaterialMaterial
        fields = ['material_origen', 'materiales_requeridos']