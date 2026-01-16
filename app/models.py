from django.db import models
from django.db.models import Sum, JSONField
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User


class Personal(models.Model):
    ESPECIALIDAD_CHOICES = [
    ('Instalación VRF', 'Instalación VRF'),
    ('Instalación CHW', 'Instalación CHW'),
    ('Mantenimiento', 'Mantenimiento'),
    ('Ductería P3', 'Ductería P3'),
    ('Ductería Galvanizada', 'Ductería Galvanizada'),
    ('Obra Civil', 'Obra Civil'),
    ('Eléctricidad', 'Electricidad'),
    ('Izaje', 'Izaje')
    ]
    rif = models.CharField(max_length=20, unique=True, verbose_name="RIF")
    empresa = models.CharField(max_length=200, verbose_name="Empresa")
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    especialidad = models.CharField(max_length=50, choices=ESPECIALIDAD_CHOICES, verbose_name="Especialidad")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    telefono_alternativo = models.CharField(max_length=20, blank=True, verbose_name="Teléfono Alternativo")
    email = models.EmailField(verbose_name="Correo Electrónico")
    direccion = models.CharField(max_length=255, verbose_name="Dirección")

    def __str__(self):
        return self.empresa

class Obra(models.Model):
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Obra")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    direccion = models.CharField(max_length=255, verbose_name="Dirección de la Obra")
    centro_servicio = models.ForeignKey(
        Personal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='obras_centro_servicio',
        verbose_name="Centro de Servicio (Personal Técnico)"
    )
    ingeniero_encargado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='obras_ingeniero',
        verbose_name="Ingeniero Encargado"
    )
    toneladas_frio = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Toneladas de Frío", blank=True, null=True)
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin_estimada = models.DateField(verbose_name="Fecha Fin Estimada")
    presupuesto_inicial = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Presupuesto Inicial")

    def __str__(self):
        return self.nombre

    def get_presupuesto_ejecutado(self):
        return sum(fase.costo_ejecutado for fase in self.fase_set.all())

    def get_porcentaje_ejecutado(self):
        if self.presupuesto_inicial > 0:
            ejecutado = self.get_presupuesto_ejecutado()
            return (ejecutado / self.presupuesto_inicial) * 100
        return 0
    
    @property
    def porcentaje_avance(self):
        fases_con_tareas = [fase for fase in self.fase_set.all() if fase.tarea_set.exists()]
        if not fases_con_tareas:
            return Decimal('0.00')
        total_porcentaje = sum(fase.porcentaje_avance for fase in fases_con_tareas)
        return total_porcentaje / len(fases_con_tareas)

class Fase(models.Model):
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Fase")
    obra = models.ForeignKey(Obra, on_delete=models.CASCADE, verbose_name="Obra")
    presupuesto_asignado = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Presupuesto Asignado")
    costo_mano_de_obra = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name="Costo de Mano de Obra (Fase)"
    )

    def __str__(self):
        return f"{self.nombre} - {self.obra.nombre}"

    @property
    def costo_ejecutado(self):
        costo_tareas = sum(tarea.costo_ejecutado for tarea in self.tarea_set.all())
        costo_propio = self.costo_mano_de_obra if self.costo_mano_de_obra is not None else 0
        return costo_tareas + costo_propio

    @property
    def porcentaje_ejecutado(self):
        if self.presupuesto_asignado > 0:
            return (self.costo_ejecutado / self.presupuesto_asignado) * 100
        return 0

    @property
    def porcentaje_avance(self):
        tareas_con_requerimientos = [tarea for tarea in self.tarea_set.all() if tarea.requerimientomaterial_set.exists()]
        if not tareas_con_requerimientos:
            return Decimal('0.00')
        total_porcentaje = sum(tarea.porcentaje_avance for tarea in tareas_con_requerimientos)
        return total_porcentaje / len(tareas_con_requerimientos)

class Tarea(models.Model):
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Tarea")
    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, verbose_name="Fase")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin_estimada = models.DateField(verbose_name="Fecha Fin Estimada")
    costo_mano_de_obra = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name="Costo de Mano de Obra (Tarea)"
    )

    def __str__(self):
        return f"{self.nombre} - {self.fase.nombre}"

    @property
    def costo_ejecutado(self):
        # Suma los costos de las asignaciones de materiales y mano de obra
        costo_material = sum(medicion.costo_total for medicion in self.medicionmaterial_set.all())
        costo_mano_de_obra_propio = self.costo_mano_de_obra if self.costo_mano_de_obra is not None else 0
        return costo_material + costo_mano_de_obra_propio

    @property
    def porcentaje_avance(self):
        total_requerido = sum(req.cantidad_requerida for req in self.requerimientomaterial_set.all())
        # Suma las cantidades de todas las mediciones de material para esta tarea
        total_instalado = sum(medicion.cantidad for medicion in self.medicionmaterial_set.all())
        
        if total_requerido > 0:
            return (total_instalado / total_requerido) * 100
        return Decimal('0.00')

class AsignacionPersonal(models.Model):
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, verbose_name="Tarea")
    personal = models.ForeignKey(Personal, on_delete=models.CASCADE, verbose_name="Personal")
    horas_trabajadas = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Horas Trabajadas")

    def __str__(self):
        return f"{self.personal.nombre} asignado a {self.tarea.nombre}"

    @property
    def costo_total(self):
        return Decimal('0.00')

class Material(models.Model):
    SISTEMA_CHOICES = [
    ('VRF', 'VRF'),
    ('CHW', 'Agua Helada (Chilled Water)')
    ]
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código del Material")
    familia = models.CharField(max_length=100, verbose_name="Familia del Material")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Material")
    unidad = models.CharField(max_length=50, verbose_name="Unidad de Medida")
    sistema = models.CharField(max_length=3, choices=SISTEMA_CHOICES, default='VRF', verbose_name='Tipo de Sistema')
    costo_unitario = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Costo Unitario")
    stock = models.IntegerField(default=0, verbose_name="Stock Disponible")
    
    def __str__(self):
        return f"{self.nombre} ({self.unidad})"

class Equipo(models.Model):
    SISTEMA_CHOICES = [
    ('VRF', 'VRF'),
    ('Compacto', 'Compacto'),
    ('Chiller', 'Chiller'),
    ('fancoil', 'Fan Coil'),
    ('UMA', 'Unidad Manejadora de Aire'),
    ]
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Equipo")
    modelo = models.CharField(max_length=50, unique=True, verbose_name="Código del Equipo")
    descripcion = models.TextField(blank=True, verbose_name="Descripción del Equipo")
    sistema = models.CharField(max_length=10, choices=SISTEMA_CHOICES, default='VRF', verbose_name='Tipo de Sistema')
    capacidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Capacidad del Equipo (TR)")
    mca = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="mca (A)")
    mfa = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="mcc (A)")

    def __str__(self):
        return self.nombre

class RequerimientoMaterial(models.Model):
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, verbose_name="Tarea")
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Material")
    cantidad_requerida = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Cantidad Requerida")

    def __str__(self):
        return f"Requerimiento para {self.tarea.nombre}: {self.cantidad_requerida} {self.material.unidad} de {self.material.nombre}"

class MedicionMaterial(models.Model):
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, verbose_name="Tarea")
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Material")
    cantidad = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Cantidad Medida")
    fecha_medicion = models.DateField(verbose_name="Fecha de Medición")

    def __str__(self):
        return f"Medición de {self.cantidad} {self.material.unidad} en {self.tarea.nombre} el {self.fecha_medicion}"
    
    @property
    def costo_total(self):
        return self.cantidad * self.material.costo_unitario
    
class Corrida(models.Model):
    correlativo = models.CharField(max_length=100, unique=True)
    nombre = models.CharField(max_length=255, unique=True)
    datos = JSONField() # Aquí se guardan todas las variables
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    

    def __str__(self):
        return self.nombre
    
class ReglaEquipoMaterial(models.Model):
    """Regla: Un Equipo requiere ciertos Materiales."""
    equipo_origen = models.ForeignKey(
        'Equipo', 
        on_delete=models.CASCADE, 
        related_name='reglas_materiales',
        verbose_name="Equipo de Origen",
        to_field='modelo'
    )
    materiales_requeridos = models.JSONField(
        verbose_name="Materiales Requeridos",
        help_text="Lista de dicts: [{'codigo': 'MAT001', 'cantidad': 5}, ...]"
    )

    class Meta:
        verbose_name = "Regla Equipo a Material"
        verbose_name_plural = "Reglas Equipo a Materiales"

    def __str__(self):
        return f"Equipo {self.equipo_origen.modelo} requiere varios materiales"

class ReglaMaterialMaterial(models.Model):
    """Regla: Un Material (Origen) requiere otros Materiales (Requeridos)."""
    material_origen = models.ForeignKey(
        'Material', 
        on_delete=models.CASCADE, 
        related_name='reglas_materiales_origen',
        verbose_name="Material de Origen",
        to_field='codigo'
    )
    materiales_requeridos = models.JSONField(
        verbose_name="Materiales Requeridos",
        help_text="Lista de dicts: [{'codigo': 'MAT002', 'cantidad': 2}, ...]"
    )

    class Meta:
        verbose_name = "Regla Material a Material"
        verbose_name_plural = "Reglas Material a Materiales"

    def __str__(self):
        return f"Material {self.material_origen.codigo} requiere varios materiales"

class Cotizacion(models.Model):
    correlativo = models.CharField(max_length=100, unique=True)
    corrida = models.OneToOneField(
        'Corrida', 
        on_delete=models.CASCADE, 
        verbose_name="Corrida Origen"
    )
    nombre = models.CharField(max_length=255, unique=True, verbose_name="Nombre de la Cotización")
    datos = JSONField()
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre
