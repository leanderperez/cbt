from django.contrib import admin
from .models import Reporte


# --- MODELOS ADMIN ---

@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ('referencia', 'fecha', 'sucursal', 'clasificacion', 'equipo', 'reporte', 'falla', 'usuario', 'estatus', 'urgencia', 'observaciones')
    search_fields = ('referencia', 'sucursal', 'clasificacion', 'equipo', 'reporte', 'falla', 'usuario__username', 'estatus')
    list_filter = ('estatus', 'urgencia', 'fecha') 
