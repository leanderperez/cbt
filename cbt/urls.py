from django.contrib import admin
from django.urls import path, include
from app.views import CustomLoginView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', CustomLoginView.as_view(), name='login'),
    path('proyectos/', include('app.urls')),
    path('servicio/', include('servicio.urls'))
]
