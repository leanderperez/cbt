from django.contrib import admin
from .models import Reporte, Cliente, Sucursal


# --- MODELOS ADMIN ---

@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ('referencia', 'fecha', 'sucursal', 'clasificacion', 'equipo', 'reporte', 'falla', 'usuario', 'estatus', 'urgencia', 'observaciones')
    search_fields = ('referencia', 'sucursal', 'clasificacion', 'equipo', 'reporte', 'falla', 'usuario__username', 'estatus')
    list_filter = ('estatus', 'urgencia', 'fecha') 

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('rif', 'nombre', 'direccion', 'telefono')
    search_fields = ('rif', 'nombre')

@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'nombre', 'direccion', 'telefono')
    search_fields = ('cliente__nombre', 'nombre')
