from django.db import models
from django.contrib.auth.models import User

class Reporte(models.Model):
    # Campos que puede rellenar el usuario
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='reportes')
    fecha = models.DateField()
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='reportes')
    sucursal = models.CharField(max_length=50)
    clasificacion = models.CharField(max_length=50)
    equipo = models.ForeignKey('app.Equipo', on_delete=models.SET_NULL, blank=True, null=True)
    reporte = models.CharField(max_length=75)
    FALLA_CHOICES = [
        ("Mecánica", "Mecánica"),
        ("Electrica", "Electrica"),
        ("Control", "Control"),
        ("Falso Reporte", "Falso Reporte"),
        ("Preventivo", "Preventivo"),
        ("Mantenimiento", "Mantenimiento"),
    ]
    falla = models.CharField(max_length=50, choices=FALLA_CHOICES)
    ESTATUS_CHOICES = [
        ("En Proceso", "En Proceso"),
        ("Finalizado", "Finalizado"),
    ]
    estatus = models.CharField(max_length=50, choices=ESTATUS_CHOICES)
    URGENCIA_CHOICES = [
        ("Baja", "Baja"),
        ("Media", "Media"),
        ("Alta", "Alta"),
    ]
    urgencia = models.CharField(max_length=50, null=True, choices=URGENCIA_CHOICES)
    
    # Campos para ser llenados por un administrador
    referencia = models.CharField(max_length=50, blank=True, null=True)
    PERSONAL_CHOICES = [
        ("Cuadrilla CBT", "Cuadrilla CBT"),
        ("Centro de Servicio", "Centro de Servicio")
    ]
    personal = models.CharField(max_length=50, blank=True, null=True, choices=PERSONAL_CHOICES)
    encargado = models.CharField(max_length=50, blank=True, null=True)
    REFRIGERANTE_CHOICES = [
        ("R-22", "R-22"),
        ("R-134a", "R-134a"),
        ("R-290", "R-290"),
        ("R-404A", "R-404A"),
        ("R-407C", "R-407C"),
        ("R-410A", "R-410A"),
        ("R-422D", "R-422D"),
        ("R-507", "R-507"),
        ("R-717 (NH3)", "R-717 (NH3)"),
        ("R-718 (H2O)", "R-718 (H2O)"),
        ("R-744 (CO2)", "R-744 (CO2)"),
    ]
    refrigerante = models.CharField(max_length=50, blank=True, null=True, choices=REFRIGERANTE_CHOICES)
    kilos = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fecha_cierre = models.DateField(blank=True, null=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    gasto = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    ods_pdf = models.FileField(upload_to='pdfs/', blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.referencia if self.referencia else f"Reporte {self.id}"

class Cliente(models.Model):
    rif = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    direccion = models.TextField()
    telefono = models.CharField(max_length=20)

    def __str__(self):
        return self.nombre
    
class Sucursal(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='sucursales')
    nombre = models.CharField(max_length=100)
    direccion = models.TextField()
    telefono = models.CharField(max_length=20)

    def __str__(self):
        return self.nombre