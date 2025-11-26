from django.contrib import admin
from .models import (
    Obra, Fase, Tarea, Personal, AsignacionPersonal, Material, Equipo, 
    RequerimientoMaterial, ReglaEquipoMaterial, ReglaMaterialMaterial # Añadido Reglas
)

# --- INLINES ---

class RequerimientoMaterialInline(admin.TabularInline):
    model = RequerimientoMaterial
    extra = 1

# Definición del Inline para las nuevas reglas
class ReglaEquipoMaterialInline(admin.TabularInline):
    model = ReglaEquipoMaterial
    fk_name = 'equipo_origen'
    extra = 1

class ReglaMaterialMaterialInline(admin.TabularInline):
    model = ReglaMaterialMaterial
    fk_name = 'material_origen'
    extra = 1


# --- MODELOS ADMIN ---

@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion', 'fecha_inicio', 'fecha_fin_estimada', 'ingeniero_encargado', 'centro_servicio', 'presupuesto_inicial')
    list_filter = ('fecha_inicio', 'fecha_fin_estimada')
    search_fields = ('nombre', 'direccion')

@admin.register(Fase)
class FaseAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'obra', 'presupuesto_asignado', 'costo_mano_de_obra')
    list_filter = ('obra',)
    search_fields = ('nombre',)

@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fase', 'fecha_inicio', 'fecha_fin_estimada', 'costo_mano_de_obra', 'porcentaje_avance')
    list_filter = ('fase',)
    search_fields = ('nombre',)
    inlines = [RequerimientoMaterialInline]

@admin.register(Personal)
class PersonalAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'nombre', 'telefono', 'telefono_alternativo', 'email', 'direccion')
    search_fields = ('nombre', 'empresa', 'email')

@admin.register(AsignacionPersonal)
class AsignacionPersonalAdmin(admin.ModelAdmin):
    list_display = ('tarea', 'personal', 'horas_trabajadas', 'costo_total')
    list_filter = ('personal',)

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    # Asume que quieres mantener la lista simple, pero podrías agregar inlines de ReglaMaterialMaterial aquí.
    list_display = ('nombre', 'unidad', 'costo_unitario')
    search_fields = ('nombre',)
    inlines = [ReglaMaterialMaterialInline]
    

# DEFINICIÓN UNIFICADA Y CORREGIDA DE EQUIPOADMIN
@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'modelo', 'sistema', 'capacidad', 'mca', 'mfa') 
    search_fields = ('nombre', 'modelo')
    # Añadimos el nuevo inline de reglas
    inlines = [ReglaEquipoMaterialInline] 

# Opcional: Registra los modelos de Regla (si no quieres gestionarlos como inline)
admin.site.register(ReglaEquipoMaterial)
admin.site.register(ReglaMaterialMaterial)
