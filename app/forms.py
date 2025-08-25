from django import forms
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from .models import (
    Obra, Fase, Tarea, RequerimientoMaterial,
    AsignacionMaterial, Material, Personal
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
            'presupuesto_inicial'
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_estimada': forms.DateInput(attrs={'type': 'date'}),
        }

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
            'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fecha_fin_estimada': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class TareaUpdateProgressForm(forms.ModelForm):
    class Meta:
        model = Tarea
        fields = ['nombre', 'descripcion', 'costo_mano_de_obra']

class RequerimientoMaterialForm(forms.ModelForm):
    class Meta:
        model = RequerimientoMaterial
        fields = ['material', 'cantidad_requerida']

class AsignacionMaterialForm(forms.ModelForm):
    class Meta:
        model = AsignacionMaterial
        fields = ['material', 'cantidad']

RequerimientoMaterialFormSet = inlineformset_factory(
    Tarea,
    RequerimientoMaterial,
    form=RequerimientoMaterialForm,
    extra=1,
    can_delete=True
)

AsignacionMaterialFormSet = inlineformset_factory(
    Tarea,
    AsignacionMaterial,
    form=AsignacionMaterialForm,
    extra=1,
    can_delete=True
)

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['nombre', 'unidad', 'descripcion', 'costo_unitario']
        
class PersonalForm(forms.ModelForm):
    class Meta:
        model = Personal
        fields = ['nombre', 'cargo']