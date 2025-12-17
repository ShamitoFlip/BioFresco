from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from django.conf import settings
from django.utils import timezone

# Create your models here.
class Producto(models.Model):
    TIPO_PRODUCTO_CHOICES = [
        ('propio', 'Producto Propio'),
        ('proveedor', 'Producto de Proveedor'),
    ]
    
    CATEGORIA_CHOICES = [
        ('frutas', 'Frutas'),
        ('verduras', 'Verduras'),
        ('frutos_secos', 'Frutos Secos'),
        ('preelaborados', 'Preelaborados'),
    ]
    
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    tipo_producto = models.CharField(max_length=20, choices=TIPO_PRODUCTO_CHOICES, default='propio', verbose_name='Tipo de Producto')
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, null=True, blank=True, verbose_name='Categoría', help_text='Categoría del producto')
    producto_proveedor = models.ForeignKey('ProductoProveedor', on_delete=models.SET_NULL, null=True, blank=True, related_name='productos_inventario', verbose_name='Producto de Proveedor')
    cantidad = models.IntegerField(verbose_name='Cantidad en Stock')
    precio = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='Precio de Venta')
    stock_minimo = models.IntegerField(default=10, verbose_name='Stock Mínimo', help_text='Cantidad mínima antes de alertar')
    costo_promedio_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Costo Promedio Actual', help_text='Costo promedio de compra actual')
    imagen = models.ImageField(upload_to='libros/', verbose_name='Imagen', null=True, blank=True)
    descripcion = models.TextField(verbose_name='Descripción', null=True, blank=True)
    unidad_medida = models.CharField(max_length=50, verbose_name='Unidad de Medida', null=True, blank=True, help_text='Ej: kg, unidades, cajas')
    zona = models.ForeignKey('Zona', on_delete=models.SET_NULL, null=True, blank=True, related_name='productos', verbose_name='Zona', help_text='Zona o ubicación donde se almacena el producto')
    proveedor_habitual = models.ForeignKey('Proveedores', on_delete=models.SET_NULL, null=True, blank=True, related_name='productos_habituales', verbose_name='Proveedor Habitual')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    
    # Campos de auditoría
    usuario_creacion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos_creados', verbose_name='Usuario que creó')
    fecha_creacion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Creación')
    usuario_modificacion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos_modificados', verbose_name='Usuario que modificó')
    fecha_modificacion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Modificación')
    
    @property
    def esta_bajo_stock(self):
        """Verifica si el producto está por debajo del stock mínimo"""
        return self.cantidad < self.stock_minimo
    
    @property
    def beneficio_bruto_estimado(self):
        """Calcula el beneficio bruto estimado (precio venta - costo promedio)"""
        if self.costo_promedio_actual:
            return float(self.precio) - float(self.costo_promedio_actual)
        return float(self.precio)
    
    def calcular_cantidad_desde_entradas(self):
        """Calcula la cantidad total del producto basándose en las entradas de inventario"""
        if self.tipo_producto == 'proveedor':
            # Sumar todas las cantidades de las entradas relacionadas a este producto
            total_entradas = self.entradas.aggregate(
                total=Sum('cantidad')
            )['total']
            return total_entradas if total_entradas is not None else 0
        # Para productos propios, retornar la cantidad actual (no se calcula desde entradas)
        return self.cantidad
    
    @staticmethod
    def calcular_cantidad_por_producto_proveedor(producto_proveedor_id):
        """Calcula la cantidad total de un producto de proveedor basándose en las entradas de inventario"""
        from .models import Producto, EntradaInventario
        # Buscar si ya existe un producto en el inventario relacionado con este producto_proveedor
        producto_existente = Producto.objects.filter(
            producto_proveedor_id=producto_proveedor_id,
            tipo_producto='proveedor',
            activo=True
        ).first()
        
        if producto_existente:
            # Si existe, calcular desde sus entradas
            total_entradas = EntradaInventario.objects.filter(
                producto=producto_existente
            ).aggregate(total=Sum('cantidad'))['total']
            return total_entradas if total_entradas is not None else 0
        else:
            # Si no existe producto en inventario, retornar 0
            return 0

    def __str__(self):
        fila = 'Nombre:' + self.nombre + ' - Descripción: ' + (self.descripcion or '')
        return fila

    def save(self, *args, **kwargs):
        now = timezone.now()
        is_new = self.pk is None
        if is_new and not self.fecha_creacion:
            self.fecha_creacion = now
        self.fecha_modificacion = now

        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add('fecha_modificacion')
            if is_new:
                update_fields.add('fecha_creacion')
            kwargs['update_fields'] = list(update_fields)

        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        # Only attempt to delete the file if a name exists. If `imagen` is empty
        # (null/blank) `self.imagen.name` can be None and FileSystemStorage.delete
        # raises ValueError: "The name must be given to delete()."
        try:
            if self.imagen and getattr(self.imagen, 'name', None):
                self.imagen.storage.delete(self.imagen.name)
        except Exception:
            # Ignore storage deletion errors and continue with model deletion.
            pass

        # Pass through the original parameters to ensure correct DB behavior.
        super().delete(using=using, keep_parents=keep_parents)


class Zona(models.Model):
    """Modelo para gestionar las zonas de almacenamiento"""
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True, verbose_name='Nombre de la Zona')
    descripcion = models.TextField(null=True, blank=True, verbose_name='Descripción')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Zona'
        verbose_name_plural = 'Zonas'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Proveedores(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    contacto = models.CharField(max_length=100, null=True, blank=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    direccion = models.TextField(null=True, blank=True)
    ciudad = models.CharField(max_length=100, null=True, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Proveedores'

    def __str__(self):
        return self.nombre


class ProductoProveedor(models.Model):
    """Modelo para productos que se pueden encargar a proveedores"""
    id = models.AutoField(primary_key=True)
    proveedor = models.ForeignKey(Proveedores, on_delete=models.CASCADE, related_name='productos', verbose_name='Proveedor')
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE, null=True, blank=True, related_name='proveedores_disponibles', verbose_name='Producto del Inventario')
    nombre = models.CharField(max_length=200, verbose_name='Nombre del Producto')
    descripcion = models.TextField(verbose_name='Descripción', null=True, blank=True)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio Unitario', null=True, blank=True)
    precio_compra_actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Precio de Compra Actual', help_text='Precio actual que cobra este proveedor')
    unidad_medida = models.CharField(max_length=50, verbose_name='Unidad de Medida', null=True, blank=True, help_text='Ej: kg, unidades, cajas')
    codigo_producto = models.CharField(max_length=100, verbose_name='Código del Producto', null=True, blank=True, unique=True)
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto de Proveedor'
        verbose_name_plural = 'Productos de Proveedores'
        ordering = ['proveedor__nombre', 'nombre']

    def __str__(self):
        return f"{self.nombre} - {self.proveedor.nombre}"


class Especialidad(models.Model):
    """Modelo para gestionar las especialidades de los empleados."""
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=200, unique=True, verbose_name='Nombre')
    descripcion = models.TextField(null=True, blank=True, verbose_name='Descripción')
    activo = models.BooleanField(default=True)  # ✅ AGREGAR ESTE CAMPO
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Especialidades'
        ordering = ('nombre',)

    def __str__(self):
        return self.nombre


class Cargo(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(null=True, blank=True)
    puede_agendar = models.BooleanField(default=False, help_text="Puede crear/agendar citas")
    puede_gestionar_inventario = models.BooleanField(default=False, help_text="Acceso/gestión del inventario")
    puede_ver_compras = models.BooleanField(default=False, help_text="Puede ver historial de compras")
    puede_gestionar_empleados_servicios_proveedores = models.BooleanField(default=False, help_text="Puede gestionar empleados, servicios, proveedores y especialidades")
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cargo'
        verbose_name_plural = 'Cargos'
        ordering = ('nombre',)

    def __str__(self):
        return self.nombre


class Empleado(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20, null=True, blank=True)
    especialidad = models.CharField(max_length=150, null=True, blank=True, help_text='Ej.: Corte, Color, Peinados')
    especialidades = models.ManyToManyField(Especialidad, blank=True)
    experiencia_anos = models.PositiveIntegerField(default=0)
    disponibilidad = models.CharField(max_length=100, null=True, blank=True, help_text='Horario o días disponibles')
    certificado = models.BooleanField(default=False)
    fecha_contrato = models.DateField(null=True, blank=True, verbose_name='Fecha de Contratación')
    sueldo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Sueldo', help_text='Sueldo del empleado')
    activo = models.BooleanField(default=True)
    # cambiado: de CharField a FK a Cargo
    cargo = models.ForeignKey(Cargo, null=True, blank=True, on_delete=models.SET_NULL, related_name='empleados')
    # Relación con User de Django para permitir inicio de sesión
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='empleado')
    foto = models.ImageField(upload_to='empleados/fotos/', verbose_name='Foto de Perfil', null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Empleados'

    def __str__(self):
        ap = f" {self.apellido}" if self.apellido else ''
        cargo_name = f" ({self.cargo.nombre})" if self.cargo else ''
        if self.especialidades.exists():
            especialidades_str = ', '.join([esp.nombre for esp in self.especialidades.all()[:3]])
            esp = f" - {especialidades_str}"
        else:
            esp = f" - {self.especialidad}" if self.especialidad else ''
        return f"{self.nombre}{ap}{cargo_name}{esp}"

    def clean(self):
        # validación de máximo 3 especialidades
        if self.pk:
            if self.especialidades.count() > 3:
                raise ValidationError("Un empleado no puede tener más de 3 especialidades.")

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        super().save(*args, **kwargs)
        accion = EmpleadoHistorial.Accion.CREADO if is_new else EmpleadoHistorial.Accion.ACTUALIZADO
        descripcion = 'Empleado registrado en el sistema.' if is_new else 'Datos del empleado actualizados.'
        EmpleadoHistorial.objects.create(
            empleado=self,
            accion=accion,
            descripcion=descripcion
        )

    def delete(self, *args, **kwargs):
        EmpleadoHistorial.objects.create(
            empleado=self,
            accion=EmpleadoHistorial.Accion.ELIMINADO,
            descripcion='Empleado eliminado del sistema.'
        )
        return super().delete(*args, **kwargs)

    # Propiedades de conveniencia para chequear permisos según el cargo
    @property
    def puede_agendar(self):
        return bool(self.cargo and self.cargo.puede_agendar)

    @property
    def puede_gestionar_inventario(self):
        return bool(self.cargo and self.cargo.puede_gestionar_inventario)

    @property
    def puede_ver_compras(self):
        return bool(self.cargo and self.cargo.puede_ver_compras)

    @property
    def puede_gestionar_empleados_servicios_proveedores(self):
        return bool(self.cargo and self.cargo.puede_gestionar_empleados_servicios_proveedores)


class EmpleadoHistorial(models.Model):
    class Accion(models.TextChoices):
        CREADO = 'creado', 'Creado'
        ACTUALIZADO = 'actualizado', 'Actualizado'
        ELIMINADO = 'eliminado', 'Eliminado'

    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='historial')
    accion = models.CharField(max_length=20, choices=Accion.choices)
    descripcion = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ('-fecha',)

    def __str__(self):
        return f'{self.empleado} - {self.get_accion_display()}'


class ServicioRealizado(models.Model):
    id = models.AutoField(primary_key=True)
    # Se elimina el campo descripcion
    # Hacer opcionales proveedor y producto: no son obligatorios al agendar una cita
    proveedor = models.ForeignKey(Proveedores, on_delete=models.PROTECT, null=True, blank=True, related_name='servicios')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, null=True, blank=True, related_name='servicios')
    servicio = models.ForeignKey('Servicio', on_delete=models.PROTECT, null=False, blank=False, related_name='agendados')
    fecha_servicio = models.DateField(null=False, blank=False)
    hora = models.TimeField(null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False, default=0)
    estado = models.CharField(
        max_length=50,
        choices=[
            ('pendiente', 'Pendiente'),
            ('en_progreso', 'En Progreso'),
            ('completado', 'Completado'),
        ],
        default='pendiente'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    nombre_cliente = models.CharField(max_length=200, null=False, blank=False, default='')
    email_cliente = models.EmailField(null=False, blank=False, default='')
    telefono_cliente = models.CharField(max_length=20, null=False, blank=False, default='')

    estilista = models.ForeignKey('Empleado', on_delete=models.PROTECT, null=False, blank=False, related_name='servicios', default=1)

    class Meta:
        verbose_name_plural = 'Servicios Realizados'

    def __str__(self):
        fecha_str = self.fecha_servicio.strftime("%d/%m/%Y") if self.fecha_servicio else ''
        hora_str = self.hora.strftime("%H:%M") if self.hora else ''
        return f'{self.servicio.nombre if self.servicio else ""} - {fecha_str} {hora_str}'


class EntradaInventario(models.Model):
    """Modelo para registrar entradas de productos al inventario"""
    id = models.AutoField(primary_key=True)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='entradas')
    proveedor = models.ForeignKey(Proveedores, on_delete=models.SET_NULL, null=True, blank=True, related_name='entradas')
    cantidad = models.PositiveIntegerField(verbose_name='Cantidad')
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio Unitario')
    numero_factura = models.CharField(max_length=100, null=True, blank=True, verbose_name='Número de Factura')
    observaciones = models.TextField(null=True, blank=True, verbose_name='Observaciones')
    fecha_entrada = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Entrada')
    usuario_registro = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='entradas_registradas', verbose_name='Usuario que registró')

    class Meta:
        verbose_name = 'Entrada de Inventario'
        verbose_name_plural = 'Entradas de Inventario'
        ordering = ['-fecha_entrada']

    def __str__(self):
        return f'Entrada: {self.cantidad} x {self.producto.nombre} - {self.fecha_entrada.strftime("%d/%m/%Y")}'
    
    def save(self, *args, **kwargs):
        """Al guardar una entrada, actualizar el stock del producto"""
        # Guardar la cantidad anterior si es una actualización
        cantidad_anterior = 0
        if self.pk:
            try:
                entrada_anterior = EntradaInventario.objects.get(pk=self.pk)
                cantidad_anterior = entrada_anterior.cantidad
            except EntradaInventario.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Si es un producto de proveedor, recalcular la cantidad desde todas las entradas
        if self.producto.tipo_producto == 'proveedor':
            cantidad_calculada = self.producto.calcular_cantidad_desde_entradas()
            self.producto.cantidad = cantidad_calculada
            self.producto.save(update_fields=['cantidad'])
        else:
            # Para productos propios, mantener la lógica anterior (sumar/restar)
            if cantidad_anterior > 0:
                # Es una actualización: restar la cantidad anterior y sumar la nueva
                self.producto.cantidad = self.producto.cantidad - cantidad_anterior + self.cantidad
            else:
                # Es una nueva entrada: sumar la cantidad
                self.producto.cantidad += self.cantidad
            self.producto.save(update_fields=['cantidad'])


class Compras(models.Model):
    id = models.AutoField(primary_key=True)
    # Producto propio de la empresa (opcional si se usa producto_proveedor)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='compras', null=True, blank=True)
    # Producto de proveedor (opcional si se usa producto)
    producto_proveedor = models.ForeignKey('ProductoProveedor', on_delete=models.CASCADE, related_name='compras', null=True, blank=True, verbose_name='Producto de Proveedor')
    proveedor = models.ForeignKey(Proveedores, on_delete=models.SET_NULL, null=True, blank=True, related_name='compras')
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Datos del cliente
    nombre_cliente = models.CharField(max_length=200, null=True, blank=True)
    email_cliente = models.EmailField(null=True, blank=True)
    telefono_cliente = models.CharField(max_length=20, null=True, blank=True)
    direccion_cliente = models.TextField(null=True, blank=True)
    ciudad_cliente = models.CharField(max_length=100, null=True, blank=True)
    
    fecha_compra = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Compras'

    def clean(self):
        """Validar que al menos uno de los productos esté presente"""
        if not self.producto and not self.producto_proveedor:
            raise ValidationError('Debe seleccionar un producto propio o un producto de proveedor')
        if self.producto and self.producto_proveedor:
            raise ValidationError('Solo puede seleccionar un producto propio o un producto de proveedor, no ambos')

    def save(self, *args, **kwargs):
        """Validar antes de guardar"""
        self.clean()
        # Si es producto de proveedor, establecer el proveedor automáticamente
        if self.producto_proveedor and not self.proveedor:
            self.proveedor = self.producto_proveedor.proveedor
        super().save(*args, **kwargs)

    @property
    def nombre_producto(self):
        """Retorna el nombre del producto (propio o de proveedor)"""
        if self.producto:
            return self.producto.nombre
        elif self.producto_proveedor:
            return self.producto_proveedor.nombre
        return 'Sin producto'

    @property
    def tipo_producto(self):
        """Retorna el tipo de producto"""
        if self.producto:
            return 'propio'
        elif self.producto_proveedor:
            return 'proveedor'
        return 'desconocido'

    def __str__(self):
        producto_nombre = self.nombre_producto
        return f'Compra de {self.nombre_cliente} - {self.cantidad} x {producto_nombre} el {self.fecha_compra.strftime("%d/%m/%Y")}'


class Servicio(models.Model):
    """Servicios que ofrece la clínica (catálogo)."""
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(null=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duracion_minutos = models.PositiveIntegerField(null=True, blank=True, help_text='Duración estimada en minutos')
    imagen = models.ImageField(upload_to='servicios/', verbose_name='Imagen', null=True, blank=True)
    activo = models.BooleanField(default=True)
    # Especialidades requeridas para realizar este servicio
    especialidades_requeridas = models.ManyToManyField(Especialidad, blank=True, related_name='servicios', help_text='Especialidades necesarias para realizar este servicio')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Servicios'

    def __str__(self):
        return f"{self.nombre} - ${self.precio}"
    
    def get_empleados_disponibles(self):
        """Retorna los empleados que tienen al menos una de las especialidades requeridas."""
        if not self.especialidades_requeridas.exists():
            # Si no hay especialidades requeridas, todos los empleados activos con especialidades están disponibles
            return Empleado.objects.filter(activo=True).annotate(
                num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
            ).filter(num_especialidades__gt=0).distinct()
        
        # Filtrar empleados que tienen al menos una de las especialidades requeridas
        return Empleado.objects.filter(
            activo=True,
            especialidades__in=self.especialidades_requeridas.filter(activo=True)
        ).distinct()


class Agenda(models.Model):
    """Modelo para gestionar la agenda de la clínica."""
    id = models.AutoField(primary_key=True)
    servicio_realizado = models.ForeignKey(ServicioRealizado, on_delete=models.CASCADE, related_name='agendas')
    fecha = models.DateField(null=False, blank=False)
    hora_inicio = models.TimeField(null=False, blank=False)
    hora_fin = models.TimeField(null=False, blank=False)
    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, null=False, blank=False, related_name='agendas')
    estado = models.CharField(
        max_length=50,
        choices=[
            ('confirmado', 'Confirmado'),
            ('cancelado', 'Cancelado'),
            ('pendiente', 'Pendiente'),
        ],
        default='pendiente'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Agendas'
        ordering = ('fecha', 'hora_inicio')

    def __str__(self):
        return f"Agenda {self.id} - {self.fecha} {self.hora_inicio}"


class SolicitudCompra(models.Model):
    """Modelo para gestionar solicitudes de compra a proveedores"""
    ESTADOS_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviada', 'Enviada/Pendiente'),
        ('aceptada', 'Aceptada'),
        ('en_proceso', 'En Proceso'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    
    id = models.AutoField(primary_key=True)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='solicitudes_compra', verbose_name='Producto')
    proveedor = models.ForeignKey(Proveedores, on_delete=models.CASCADE, related_name='solicitudes_compra', verbose_name='Proveedor')
    cantidad = models.PositiveIntegerField(verbose_name='Cantidad Solicitada')
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Precio Unitario')
    costo_total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Costo Total', help_text='Cantidad × Precio Unitario')
    estado = models.CharField(max_length=20, choices=ESTADOS_CHOICES, default='borrador', verbose_name='Estado')
    observaciones = models.TextField(null=True, blank=True, verbose_name='Observaciones')
    fecha_solicitud = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Solicitud')
    fecha_aceptacion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Aceptación')
    fecha_completada = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Completada')
    usuario_solicitante = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_creadas', verbose_name='Usuario Solicitante')
    numero_factura = models.CharField(max_length=100, null=True, blank=True, verbose_name='Número de Factura')
    
    # Campos para verificación de recepción
    cantidad_recibida = models.PositiveIntegerField(null=True, blank=True, verbose_name='Cantidad Recibida')
    precio_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Precio Final')
    fecha_recepcion = models.DateTimeField(null=True, blank=True, verbose_name='Fecha de Recepción')
    usuario_recepcion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitudes_recibidas', verbose_name='Usuario que Recibió')
    
    class Meta:
        verbose_name = 'Solicitud de Compra'
        verbose_name_plural = 'Solicitudes de Compra'
        ordering = ['-fecha_solicitud']
    
    def __str__(self):
        return f'Solicitud #{self.id} - {self.producto.nombre} - {self.get_estado_display()}'
    
    def save(self, *args, **kwargs):
        """Calcular costo total automáticamente"""
        if self.cantidad and self.precio_unitario:
            self.costo_total = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
    
    def puede_cambiar_estado(self, nuevo_estado):
        """Verifica si se puede cambiar al nuevo estado"""
        estados_validos = {
            'borrador': ['enviada', 'cancelada'],
            'enviada': ['aceptada', 'cancelada'],
            'aceptada': ['en_proceso', 'cancelada'],
            'en_proceso': ['completada', 'cancelada'],
            'completada': [],
            'cancelada': [],
        }
        return nuevo_estado in estados_validos.get(self.estado, [])


# ========== INVENTARIO PERSONAL ==========

class ItemPersonal(models.Model):
    """Catálogo general de objetos personales para el inventario personal"""
    
    class ItemType(models.TextChoices):
        ARMA = 'ARMA', 'Arma'
        ARMADURA = 'ARMADURA', 'Armadura'
        CONSUMIBLE = 'CONSUMIBLE', 'Consumible'
        MATERIAL = 'MATERIAL', 'Material'
        MISION = 'MISION', 'Misión'
        OTRO = 'OTRO', 'Otro'
    
    item_name = models.CharField(max_length=100, verbose_name='Nombre del Item')
    description = models.TextField(blank=True, null=True, verbose_name='Descripción')
    max_stack_size = models.PositiveIntegerField(default=1, verbose_name='Tamaño Máximo de Pila', help_text='Cantidad máxima que se puede apilar')
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.OTRO, verbose_name='Tipo de Item')
    image_url = models.CharField(max_length=255, blank=True, null=True, verbose_name='URL de Imagen', help_text='Ruta del ícono/imagen en el frontend')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Item Personal'
        verbose_name_plural = 'Items Personales'
        ordering = ['item_name']
    
    def __str__(self):
        return self.item_name


class UserInventorySlot(models.Model):
    """Ranura de inventario por usuario para el inventario personal"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inventory_slots', verbose_name='Usuario')
    item = models.ForeignKey(ItemPersonal, on_delete=models.SET_NULL, null=True, blank=True, related_name='slots', verbose_name='Item')
    quantity = models.PositiveIntegerField(default=0, verbose_name='Cantidad')
    slot_index = models.IntegerField(verbose_name='Índice de Ranura', help_text='Posición o índice de la ranura (0-19 para 20 slots)')
    
    class Meta:
        verbose_name = 'Ranura de Inventario Personal'
        verbose_name_plural = 'Ranuras de Inventario Personal'
        unique_together = ('user', 'slot_index')
        ordering = ['user', 'slot_index']
    
    def __str__(self):
        if self.item:
            return f"{self.user.username} - Slot {self.slot_index}: {self.item.item_name} x{self.quantity}"
        return f"{self.user.username} - Slot {self.slot_index}: Vacío"
    
    def is_empty(self):
        """Verifica si la ranura está vacía"""
        return self.item is None or self.quantity <= 0


class AuditoriaInventario(models.Model):
    """Modelo para gestionar auditorías de inventario (conteo físico)"""
    ESTADO_CHOICES = [
        ('en_proceso', 'En Proceso'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]
    
    id = models.AutoField(primary_key=True)
    fecha_auditoria = models.DateField(verbose_name='Fecha de Auditoría')
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='en_proceso',
        verbose_name='Estado'
    )
    observaciones_generales = models.TextField(
        null=True,
        blank=True,
        verbose_name='Observaciones Generales'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_completada = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Finalización'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias_realizadas',
        verbose_name='Usuario que realiza la auditoría'
    )
    
    class Meta:
        verbose_name = 'Auditoría de Inventario'
        verbose_name_plural = 'Auditorías de Inventario'
        ordering = ['-fecha_auditoria', '-fecha_creacion']
    
    def __str__(self):
        return f'Auditoría #{self.id} - {self.fecha_auditoria.strftime("%d/%m/%Y")} - {self.get_estado_display()}'
    
    @property
    def total_productos(self):
        """Retorna el total de productos en la auditoría"""
        return self.detalles.count()
    
    @property
    def productos_revisados(self):
        """Retorna la cantidad de productos revisados"""
        return self.detalles.filter(revisado=True).count()
    
    @property
    def productos_pendientes(self):
        """Retorna la cantidad de productos pendientes de revisar"""
        return self.detalles.filter(revisado=False).count()
    
    @property
    def tiene_discrepancias(self):
        """Verifica si hay discrepancias en la auditoría"""
        return self.detalles.exclude(diferencia=0).exists()
    
    def completar(self):
        """Marca la auditoría como completada"""
        from django.utils import timezone
        self.estado = 'completada'
        self.fecha_completada = timezone.now()
        self.save()


class DetalleAuditoria(models.Model):
    """Modelo para los detalles de cada producto en una auditoría"""
    TIPO_DISCREPANCIA_CHOICES = [
        ('sin_cambios', 'Sin Cambios'),
        ('desaparecido', 'Desaparecido'),
        ('vencido', 'Vencido'),
        ('merma', 'Merma/Deterioro'),
        ('sobrante', 'Sobrante'),
        ('otro', 'Otro'),
    ]
    
    id = models.AutoField(primary_key=True)
    auditoria = models.ForeignKey(
        AuditoriaInventario,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Auditoría'
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='auditorias',
        verbose_name='Producto'
    )
    cantidad_sistema = models.IntegerField(
        help_text='Cantidad registrada en el sistema',
        verbose_name='Cantidad en Sistema'
    )
    conteo_fisico = models.IntegerField(
        help_text='Cantidad encontrada físicamente',
        verbose_name='Conteo Físico',
        default=0
    )
    diferencia = models.IntegerField(
        help_text='Diferencia entre sistema y físico (automático)',
        verbose_name='Diferencia',
        default=0
    )
    tipo_discrepancia = models.CharField(
        max_length=20,
        choices=TIPO_DISCREPANCIA_CHOICES,
        null=True,
        blank=True,
        verbose_name='Tipo de Discrepancia'
    )
    observaciones = models.TextField(
        null=True,
        blank=True,
        verbose_name='Observaciones'
    )
    revisado = models.BooleanField(
        default=False,
        help_text='Indica si el producto fue revisado en el conteo físico',
        verbose_name='Revisado'
    )
    fecha_revision = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Revisión'
    )
    
    class Meta:
        verbose_name = 'Detalle de Auditoría'
        verbose_name_plural = 'Detalles de Auditoría'
        ordering = ['producto__nombre']
        unique_together = ('auditoria', 'producto')
    
    def __str__(self):
        return f'{self.producto.nombre} - Sistema: {self.cantidad_sistema}, Físico: {self.conteo_fisico}'
    
    def save(self, *args, **kwargs):
        """Calcula la diferencia automáticamente al guardar"""
        self.diferencia = self.conteo_fisico - self.cantidad_sistema
        super().save(*args, **kwargs)
    
    def marcar_revisado(self):
        """Marca el detalle como revisado"""
        from django.utils import timezone
        self.revisado = True
        self.fecha_revision = timezone.now()
        self.save()


class HistorialAccion(models.Model):
    """Modelo genérico para registrar todas las acciones realizadas en el sistema"""
    class Accion(models.TextChoices):
        CREADO = 'creado', 'Creado'
        EDITADO = 'editado', 'Editado'
        ELIMINADO = 'eliminado', 'Eliminado'
    
    class TipoModelo(models.TextChoices):
        PRODUCTO = 'producto', 'Producto'
        PROVEEDOR = 'proveedor', 'Proveedor'
        EMPLEADO = 'empleado', 'Empleado'
        SERVICIO = 'servicio', 'Servicio'
        CARGO = 'cargo', 'Cargo'
        ESPECIALIDAD = 'especialidad', 'Especialidad'
        ENTRADA_INVENTARIO = 'entrada_inventario', 'Entrada de Inventario'
        SOLICITUD_COMPRA = 'solicitud_compra', 'Solicitud de Compra'
        PRODUCTO_PROVEEDOR = 'producto_proveedor', 'Producto de Proveedor'
        ZONA = 'zona', 'Zona'
        AUDITORIA = 'auditoria', 'Auditoría'
    
    accion = models.CharField(max_length=20, choices=Accion.choices, verbose_name='Acción')
    tipo_modelo = models.CharField(max_length=30, choices=TipoModelo.choices, verbose_name='Tipo de Modelo')
    nombre_objeto = models.CharField(max_length=200, verbose_name='Nombre del Objeto')
    descripcion = models.TextField(blank=True, null=True, verbose_name='Descripción')
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='acciones_realizadas', verbose_name='Usuario')
    fecha = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')
    objeto_id = models.IntegerField(null=True, blank=True, verbose_name='ID del Objeto', help_text='ID del objeto afectado para referencia')
    
    class Meta:
        verbose_name = 'Historial de Acción'
        verbose_name_plural = 'Historial de Acciones'
        ordering = ('-fecha',)
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['tipo_modelo', 'accion']),
        ]
    
    def __str__(self):
        return f'{self.get_tipo_modelo_display()} - {self.get_accion_display()}: {self.nombre_objeto}'
    
    @property
    def icono(self):
        """Retorna el icono según el tipo de modelo"""
        iconos = {
            'producto': 'fas fa-box',
            'proveedor': 'fas fa-truck',
            'empleado': 'fas fa-user-tie',
            'servicio': 'fas fa-concierge-bell',
            'cargo': 'fas fa-briefcase',
            'especialidad': 'fas fa-certificate',
            'entrada_inventario': 'fas fa-arrow-down',
            'solicitud_compra': 'fas fa-shopping-cart',
            'producto_proveedor': 'fas fa-box-open',
            'zona': 'fas fa-map-marker-alt',
            'auditoria': 'fas fa-clipboard-check',
        }
        return iconos.get(self.tipo_modelo, 'fas fa-info-circle')
    
    @property
    def categoria(self):
        """Retorna la categoría para mostrar en el dashboard"""
        categorias = {
            'producto': 'Inventario',
            'proveedor': 'Proveedor',
            'empleado': 'Empleado',
            'servicio': 'Servicio',
            'cargo': 'Cargo',
            'especialidad': 'Especialidad',
            'entrada_inventario': 'Entradas',
            'solicitud_compra': 'Solicitud',
            'producto_proveedor': 'Producto Proveedor',
            'zona': 'Zona',
            'auditoria': 'Auditoría',
        }
        return categorias.get(self.tipo_modelo, 'Sistema')


