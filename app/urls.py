from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    ObraListView, ObraCreateView, ObraUpdateView, ObraDetailView,
    FaseCreateView, TareaCreateView, TareaUpdateView, ObraMedicionesView,
    MaterialListView, MaterialCreateView, PersonalCreateView, 
    PersonalListView, CorridaWizard, ObraWizard, CorridaListView, CotizacionListView, CotizacionUpdateView,
    CotizacionCreateView, gantt_data_view, gantt_chart_view, detalle_cotizacion, generar_obra_desde_cotizacion,
    calculadora_tornilleria, calculadora_velumoide,
    FORMS, FASES_WIZARD_FORMS
)


urlpatterns = [
    # Obras
    path('', ObraListView.as_view(), name='obra-list'),
    path('obra/new/', ObraWizard.as_view(FASES_WIZARD_FORMS), name='obra-create'),
    path('obra/<int:pk>/edit/', ObraUpdateView.as_view(), name='obra-update'),
    path('obra/<int:pk>/', ObraDetailView.as_view(), name='obra-detail'),
    path('obra/<int:pk>/mediciones/', ObraMedicionesView.as_view(), name='obra-mediciones'),

    # Fases y Tareas
    path('obra/<int:pk>/fase/new/', FaseCreateView.as_view(), name='fase-create'),
    path('fase/<int:pk>/tarea/new/', TareaCreateView.as_view(), name='tarea-create'),
    path('tarea/<int:pk>/edit/', TareaUpdateView.as_view(), name='tarea-update'),

    # Materiales
    path('materiales/', MaterialListView.as_view(), name='material-list'),
    path('materiales/<str:sistema>/', MaterialListView.as_view(), name='material-list-filter'),
    path('materiales/new/', MaterialCreateView.as_view(), name='material-create'),

    # Personal
    path('personal/', PersonalListView.as_view(), name='personal-list'),
    path('personal/new/', PersonalCreateView.as_view(), name='personal-create'),

    # Ruta para cerrar sesión
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    # Diagrama de Gantt
    path('gantt/<int:pk>/', gantt_chart_view, name='gantt_chart'),
    path('api/gantt_data/<int:pk>/', gantt_data_view, name='gantt_data'),

    # Herramientas
    path('calculadora/velumoide', calculadora_velumoide, name='calculadora_velumoide'),
    path('calculadora/tornilleria', calculadora_tornilleria, name='calculadora_tornilleria'),

    # Cotizaciones 
    path('cotizacion/', CorridaWizard.as_view(FORMS), name='corrida_wizard'),
    path('corridas/', CorridaListView.as_view(), name='corrida-list'),
    path('cotizacion/generar/<int:corrida_id>/', CotizacionCreateView, name='generar_cotizacion'),
    path('cotizacion/editar/<int:pk>/', CotizacionUpdateView.as_view(), name='cotizacion-edit'),
    path('cotizaciones/', CotizacionListView.as_view(), name='cotizacion-list'),
    path('cotizacion/<int:pk>/pdf/', detalle_cotizacion, name='detalle_cotizacion'),
    path('cotizacion/<int:cotizacion_id>/generar-obra/', generar_obra_desde_cotizacion, name='generar_obra'),

]