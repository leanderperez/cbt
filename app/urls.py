from django.urls import path
from .views import (
    ObraListView, ObraCreateView, ObraUpdateView, ObraDetailView,
    FaseCreateView, TareaCreateView, TareaUpdateView, ObraMedicionesView,
    MaterialListView, MaterialCreateView, PersonalCreateView, PersonalListView
)

urlpatterns = [
    # Rutas para Obras
    path('', ObraListView.as_view(), name='obra-list'),
    path('obra/new/', ObraCreateView.as_view(), name='obra-create'),
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
    path('materiales/new/', MaterialCreateView.as_view(), name='material-create'),

    # Rutas para Personal
    path('personal/', PersonalListView.as_view(), name='personal-list'),
    path('personal/new/', PersonalCreateView.as_view(), name='personal-create'),
]
