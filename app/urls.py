from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import (
    ObraListView, ObraCreateView, ObraUpdateView, ObraDetailView,
    FaseCreateView, TareaCreateView, TareaUpdateView, ObraMedicionesView,
    MaterialListView, MaterialCreateView, PersonalCreateView, 
    PersonalListView, CalculoWizard, ObraWizard, 
    editar_proyecto, gantt_data_view, gantt_chart_view, confirmacion_guardado,
    calculadora_tornilleria, calculadora_velumoide,
    FORMS, FASES_WIZARD_FORMS
)


urlpatterns = [
    # Rutas para Obras
    path('', ObraListView.as_view(), name='obra-list'),
    # path('obra/new/', ObraCreateView.as_view(), name='obra-create'),
    path('obra/new/', ObraWizard.as_view(FASES_WIZARD_FORMS), name='obra-create'),
    path('obra/<int:pk>/edit/', ObraUpdateView.as_view(), name='obra-update'),
    path('obra/<int:pk>/', ObraDetailView.as_view(), name='obra-detail'),
    path('obra/<int:pk>/mediciones/', ObraMedicionesView.as_view(), name='obra-mediciones'),

    # Rutas para Fases
    path('obra/<int:pk>/fase/new/', FaseCreateView.as_view(), name='fase-create'),

    # Rutas para Tareas
    path('fase/<int:pk>/tarea/new/', TareaCreateView.as_view(), name='tarea-create'),
    path('tarea/<int:pk>/edit/', TareaUpdateView.as_view(), name='tarea-update'),

    # Rutas para Materiales
    path('materiales/', MaterialListView.as_view(), name='material-list'),
    path('materiales/<str:sistema>/', MaterialListView.as_view(), name='material-list-filter'),
    path('materiales/new/', MaterialCreateView.as_view(), name='material-create'),

    # Rutas para Personal
    path('personal/', PersonalListView.as_view(), name='personal-list'),
    path('personal/new/', PersonalCreateView.as_view(), name='personal-create'),

    # Ruta para cerrar sesión
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),

    # URL para ver el gráfico de una obra específica
    path('gantt/<int:pk>/', gantt_chart_view, name='gantt_chart'),
    # URL de la API que recibe el ID de la obra
    path('api/gantt_data/<int:pk>/', gantt_data_view, name='gantt_data'),

    # Herramientas
    path('calculadora/velumoide', calculadora_velumoide, name='calculadora_velumoide'),
    path('calculadora/tornilleria', calculadora_tornilleria, name='calculadora_tornilleria'),

    # Cotizaciones 
    path('calculo/', CalculoWizard.as_view(FORMS), name='calculo_wizard'),
    path('confirmado/', confirmacion_guardado, name='confirmacion'), 
    path('editar/<str:nombre_proyecto>/', editar_proyecto, name='editar_proyecto'),
]