from django.contrib import admin
from .models import Producto, Proveedores, ServicioRealizado, Compras, Servicio
from .models import Empleado, Especialidad, Cargo, AuditoriaInventario, DetalleAuditoria
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin


class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cantidad', 'precio', 'descripcion')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('precio', 'cantidad')
    ordering = ('nombre',)


class ProveedoresAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'contacto', 'telefono', 'email', 'ciudad', 'fecha_registro')
    search_fields = ('nombre', 'email', 'telefono')
    list_filter = ('ciudad', 'fecha_registro')
    ordering = ('-fecha_registro',)
    readonly_fields = ('fecha_registro',)
    
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'contacto', 'telefono', 'email')
        }),
        ('Ubicación', {
            'fields': ('direccion', 'ciudad')
        }),
        ('Registro', {
            'fields': ('fecha_registro',),
            'classes': ('collapse',)
        }),
    )


class ServicioRealizadoAdmin(admin.ModelAdmin):
    list_display = ('servicio', 'proveedor', 'producto', 'fecha_servicio', 'costo', 'estado')
    search_fields = ('servicio__nombre', 'proveedor__nombre', 'producto__nombre')
    list_filter = ('estado', 'fecha_servicio', 'proveedor')
    ordering = ('-fecha_servicio',)
    readonly_fields = ('fecha_registro',)
    
    fieldsets = (
        ('Información del Servicio', {
            'fields': ('servicio', 'proveedor', 'producto')
        }),
        ('Detalles', {
            'fields': ('fecha_servicio', 'costo', 'estado')
        }),
        ('Registro', {
            'fields': ('fecha_registro',),
            'classes': ('collapse',)
        }),
    )


class ComprasAdmin(admin.ModelAdmin):
    list_display = ('nombre_cliente', 'producto', 'cantidad', 'email_cliente', 'telefono_cliente', 'fecha_compra')
    search_fields = ('nombre_cliente', 'email_cliente', 'producto__nombre')
    list_filter = ('fecha_compra', 'ciudad_cliente')
    ordering = ('-fecha_compra',)
    readonly_fields = ('fecha_compra',)
    
    fieldsets = (
        ('Información de la Compra', {
            'fields': ('producto', 'cantidad', 'precio_unitario', 'proveedor')
        }),
        ('Datos del Cliente', {
            'fields': ('nombre_cliente', 'email_cliente', 'telefono_cliente', 'ciudad_cliente', 'direccion_cliente')
        }),
        ('Registro', {
            'fields': ('fecha_compra',),
            'classes': ('collapse',)
        }),
    )

admin.site.register(Producto, ProductoAdmin)
admin.site.register(Proveedores, ProveedoresAdmin)
admin.site.register(ServicioRealizado, ServicioRealizadoAdmin)
admin.site.register(Compras, ComprasAdmin)


class ServicioAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'duracion_minutos', 'activo')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('activo',)
    ordering = ('nombre',)


admin.site.register(Servicio, ServicioAdmin)


class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion_corta', 'cantidad_empleados', 'fecha_creacion')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('fecha_creacion',)
    ordering = ('nombre',)
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion', 'cantidad_empleados')
    
    fieldsets = (
        ('Información de la Especialidad', {
            'fields': ('nombre', 'descripcion'),
            'description': 'Ingresa el nombre y descripción de la especialidad. Esta especialidad podrá ser asignada a los empleados.'
        }),
        ('Estadísticas', {
            'fields': ('cantidad_empleados',),
            'classes': ('collapse',)
        }),
        ('Registro', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    def descripcion_corta(self, obj):
        """Muestra una versión corta de la descripción en la lista."""
        if obj.descripcion:
            return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
        return '-'
    descripcion_corta.short_description = 'Descripción'
    
    def cantidad_empleados(self, obj):
        """Muestra la cantidad de empleados con esta especialidad."""
        if obj.pk:
            return obj.empleado_set.count()
        return 0
    cantidad_empleados.short_description = 'Empleados'


# Registrar Especialidad antes que Empleado para mejor organización
admin.site.register(Especialidad, EspecialidadAdmin)


class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'cargo', 'experiencia_anos', 'email', 'activo')
    search_fields = ('nombre', 'apellido', 'email', 'cargo__nombre', 'especialidades__nombre')
    list_filter = ('activo', 'cargo', 'especialidades')
    ordering = ('nombre',)
    filter_horizontal = ('especialidades',)  # Mejora la interfaz para seleccionar especialidades
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'apellido', 'email', 'telefono')
        }),
        ('Información Profesional', {
            'fields': ('cargo', 'especialidades', 'especialidad', 'experiencia_anos')
        }),
        ('Disponibilidad', {
            'fields': ('disponibilidad', 'activo')
        }),
        ('Registro', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion')

admin.site.register(Empleado, EmpleadoAdmin)


try:
    admin.site.unregister(User)
except Exception:
    pass

# Registrar User con el UserAdmin por defecto (sin acciones personalizadas)
admin.site.register(User, DefaultUserAdmin)


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'puede_agendar', 'puede_gestionar_inventario', 'puede_ver_compras', 'puede_gestionar_empleados_servicios_proveedores')
    list_filter = ('activo', 'puede_agendar', 'puede_gestionar_inventario', 'puede_ver_compras', 'puede_gestionar_empleados_servicios_proveedores')
    search_fields = ('nombre',)
    list_editable = ('activo', 'puede_agendar', 'puede_gestionar_inventario', 'puede_ver_compras', 'puede_gestionar_empleados_servicios_proveedores')


class DetalleAuditoriaInline(admin.TabularInline):
    model = DetalleAuditoria
    extra = 0
    readonly_fields = ('cantidad_sistema', 'diferencia', 'fecha_revision')
    fields = ('producto', 'cantidad_sistema', 'conteo_fisico', 'diferencia', 'tipo_discrepancia', 'revisado', 'fecha_revision', 'observaciones')


@admin.register(AuditoriaInventario)
class AuditoriaInventarioAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_auditoria', 'usuario', 'estado', 'total_productos', 'productos_revisados', 'fecha_creacion')
    list_filter = ('estado', 'fecha_auditoria', 'fecha_creacion')
    search_fields = ('id', 'usuario__username', 'usuario__first_name', 'usuario__last_name', 'observaciones_generales')
    ordering = ('-fecha_creacion',)
    readonly_fields = ('fecha_creacion', 'fecha_actualizacion', 'fecha_completada')
    inlines = [DetalleAuditoriaInline]
    
    fieldsets = (
        ('Información General', {
            'fields': ('fecha_auditoria', 'usuario', 'estado')
        }),
        ('Observaciones', {
            'fields': ('observaciones_generales',)
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion', 'fecha_completada'),
            'classes': ('collapse',)
        }),
    )
    
    def total_productos(self, obj):
        return obj.total_productos
    total_productos.short_description = 'Total Productos'
    
    def productos_revisados(self, obj):
        return f"{obj.productos_revisados}/{obj.total_productos}"
    productos_revisados.short_description = 'Revisados'


@admin.register(DetalleAuditoria)
class DetalleAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'auditoria', 'producto', 'cantidad_sistema', 'conteo_fisico', 'diferencia', 'tipo_discrepancia', 'revisado')
    list_filter = ('revisado', 'tipo_discrepancia', 'auditoria__estado', 'auditoria__fecha_auditoria')
    search_fields = ('producto__nombre', 'auditoria__id', 'observaciones')
    ordering = ('-auditoria__fecha_creacion', 'producto__nombre')
    readonly_fields = ('cantidad_sistema', 'diferencia', 'fecha_revision')
    
    fieldsets = (
        ('Información', {
            'fields': ('auditoria', 'producto')
        }),
        ('Conteo', {
            'fields': ('cantidad_sistema', 'conteo_fisico', 'diferencia', 'revisado', 'fecha_revision')
        }),
        ('Discrepancia', {
            'fields': ('tipo_discrepancia', 'observaciones')
        }),
    )


