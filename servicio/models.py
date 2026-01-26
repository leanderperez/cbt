from django.db import models
from django.contrib.auth.models import User

class Reporte(models.Model):
    # Campos que puede rellenar el usuario
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='reportes')
    fecha = models.DateField()
    cliente = models.CharField(max_length=100)
    sucursal = models.CharField(max_length=50)
    clasificacion = models.CharField(max_length=50)
    equipo = models.CharField(max_length=50)
    reporte = models.CharField(max_length=75)
    falla = models.CharField(max_length=50)
    coordinador = models.CharField(max_length=50)
    estatus = models.BooleanField(default=False)
    urgencia = models.CharField(max_length=50, null=True)
    
    # Campos para ser llenados por un administrador
    referencia = models.CharField(max_length=50, blank=True, null=True)
    personal = models.CharField(max_length=50, blank=True, null=True)
    encargado = models.CharField(max_length=50, blank=True, null=True)
    refrigerante = models.CharField(max_length=50, blank=True, null=True)
    kilos = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fecha_cierre = models.DateField(blank=True, null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    gasto = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    ods_pdf = models.FileField(upload_to='pdfs/', blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.referencia if self.referencia else f"Reporte {self.id}"
