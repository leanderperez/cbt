from django.contrib import admin
from .models import Obra, Fase, Tarea, Personal, AsignacionPersonal, Material, Equipo, RequerimientoMaterial

@admin.register(Obra)
class ObraAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'direccion', 'fecha_inicio', 'fecha_fin_estimada', 'ingeniero_encargado', 'centro_servicio', 'presupuesto_inicial')
    list_filter = ('fecha_inicio', 'fecha_fin_estimada')
    search_fields = ('nombre', 'direccion')

class RequerimientoMaterialInline(admin.TabularInline):
    model = RequerimientoMaterial
    extra = 1

"""
class AsignacionMaterialInline(admin.TabularInline):
    model = AsignacionMaterial
    extra = 1
"""

@admin.register(Fase)
class FaseAdmin(admin.ModelAdmin):
    # Se agregó el nuevo campo a la vista de lista
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
    list_display = ('nombre', 'unidad', 'costo_unitario')
    search_fields = ('nombre',)

@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'modelo', 'sistema', 'capacidad', 'mca', 'mcc')
    search_fields = ('nombre', 'modelo')