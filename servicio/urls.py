from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (crear_reporte, modificar_reporte, acceso_denegado, datatable)

urlpatterns = [
    path('', datatable, name='datatable'),
    path('crear-reporte/', crear_reporte, name='crear_reporte'),
    path('modificar-reporte/<int:pk>/', modificar_reporte, name='modificar_reporte'),
    path('acceso-denegado/', acceso_denegado, name='acceso_denegado'),
    path('datatable/', datatable, name='datatable'),
]