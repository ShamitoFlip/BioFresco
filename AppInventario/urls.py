from . import views
from django.conf import settings
from django.contrib.staticfiles.urls import static
from django.urls import path

urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('password-reset/', views.password_reset_request, name='password_reset_request'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    path('', views.inicio, name='inicio'),
    # Rutas Historial de Servicios
    path('servicios/historial/', views.servicios_historial, name='servicios_historial'),
    
    # Rutas Servicios
    path('servicios/', views.servicios_publicos, name='servicios_publicos'),
    # CRUD para servicios ofrecidos (administración)
    path('servicios/ofrecidos/', views.servicios_ofrecidos_lista, name='servicios_ofrecidos'),
    path('servicios/ofrecidos/crear/', views.servicios_ofrecidos_crear, name='servicios_ofrecidos_crear'),
    path('servicios/ofrecidos/editar/<int:id>/', views.servicios_ofrecidos_editar, name='servicios_ofrecidos_editar'),
    path('servicios/ofrecidos/eliminar/<int:id>/', views.servicios_ofrecidos_eliminar, name='servicios_ofrecidos_eliminar'),
    path('servicios/crear/', views.servicios_crear, name='servicios_crear'),
    path('servicios/agendar/', views.agendar_cita, name='agendar_cita'),
    path('servicios/editar/<int:id>/', views.servicios_editar, name='servicios_editar'),
    path('servicios/eliminar/<int:id>/', views.servicios_eliminar, name='servicios_eliminar'),
    path('servicios/marcar-completado/<int:id>/', views.servicios_marcar_completado, name='servicios_marcar_completado'),
    
    # Rutas Empleados (admin CRUD)
    path('empleados/', views.estilistas_lista, name='empleados_lista'),
    path('empleados/crear/', views.estilistas_crear, name='empleados_crear'),
    path('empleados/editar/<int:id>/', views.estilistas_editar, name='empleados_editar'),
    path('empleados/eliminar/<int:id>/', views.estilistas_eliminar, name='empleados_eliminar'),
    
    # Rutas Especialidades (admin CRUD)
    path('especialidades/', views.especialidades_lista, name='especialidades_lista'),
    path('especialidades/crear/', views.especialidades_crear, name='especialidades_crear'),
    path('especialidades/editar/<int:id>/', views.especialidades_editar, name='especialidades_editar'),
    path('especialidades/eliminar/<int:id>/', views.especialidades_eliminar, name='especialidades_eliminar'),
    
    # Rutas Cargos (admin CRUD)
    path('cargos/', views.cargos_lista, name='cargos_lista'),
    path('cargos/crear/', views.cargos_crear, name='cargos_crear'),
    path('cargos/editar/<int:id>/', views.cargos_editar, name='cargos_editar'),
    path('cargos/eliminar/<int:id>/', views.cargos_eliminar, name='cargos_eliminar'),
    
    # Panel administrador (no usar prefijo 'admin/' para evitar conflicto con el admin de Django)
    path('panel-admin/', views.admin_panel, name='admin_panel'),
    path('historial-completo/', views.historial_completo, name='historial_completo'),
    path('admin/upload-avatar/', views.upload_avatar, name='upload_avatar'),
    path('servicios/horas-ocupadas/', views.obtener_horas_ocupadas, name='obtener_horas_ocupadas'),
    
    # Rutas Gestión de Existencias - Entradas
    path('existencias/entradas/', views.entradas_lista, name='entradas_lista'),
    path('existencias/entradas/crear/', views.entradas_crear, name='entradas_crear'),
    path('existencias/entradas/editar/<int:id>/', views.entradas_editar, name='entradas_editar'),
    path('existencias/entradas/eliminar/<int:id>/', views.entradas_eliminar, name='entradas_eliminar'),
    
    # Rutas Gestión de Existencias - Salidas
    # Eliminada: path('existencias/salidas/', views.salidas_lista, name='salidas_lista'),
    
    # Rutas Solicitudes de Compra
    path('solicitudes-compra/', views.solicitudes_compra_lista, name='solicitudes_compra_lista'),
    path('solicitudes-compra/crear/', views.solicitudes_compra_crear, name='solicitudes_compra_crear'),
    path('solicitudes-compra/crear/<int:producto_id>/', views.solicitudes_compra_crear, name='solicitudes_compra_crear_producto'),
    path('solicitudes-compra/<int:id>/cambiar-estado/<str:nuevo_estado>/', views.solicitudes_compra_cambiar_estado, name='solicitudes_compra_cambiar_estado'),
    path('solicitudes-compra/<int:id>/verificar-recepcion/', views.solicitudes_compra_verificar_recepcion, name='solicitudes_compra_verificar_recepcion'),
    path('solicitudes-compra/<int:id>/detalle/', views.solicitudes_compra_detalle, name='solicitudes_compra_detalle'),
    
    # Rutas Proveedores (admin CRUD)
    path('proveedores/', views.proveedores_lista, name='proveedores_lista'),
    path('proveedores/crear/', views.proveedores_crear, name='proveedores_crear'),
    path('proveedores/editar/<int:id>/', views.proveedores_editar, name='proveedores_editar'),
    path('proveedores/eliminar/<int:id>/', views.proveedores_eliminar, name='proveedores_eliminar'),
    
    # Rutas Productos de Proveedores (admin CRUD)
    path('productos-proveedor/', views.productos_proveedor_lista, name='productos_proveedor_lista'),
    path('productos-proveedor/crear/', views.productos_proveedor_crear, name='productos_proveedor_crear'),
    path('productos-proveedor/editar/<int:id>/', views.productos_proveedor_editar, name='productos_proveedor_editar'),
    path('productos-proveedor/eliminar/<int:id>/', views.productos_proveedor_eliminar, name='productos_proveedor_eliminar'),
    
    # Rutas Inventario Unificado (admin CRUD)
    path('inventario/', views.inventario_lista, name='inventario_lista'),
    path('inventario/crear/', views.inventario_crear, name='inventario_crear'),
    path('inventario/crear-proveedor/', views.inventario_crear_proveedor, name='inventario_crear_proveedor'),
    path('inventario/editar/<int:id>/', views.inventario_editar, name='inventario_editar'),
    path('inventario/eliminar/<int:id>/', views.inventario_eliminar, name='inventario_eliminar'),
    path('inventario/activar/<int:id>/', views.inventario_activar, name='inventario_activar'),
    path('inventario/suspender/<int:id>/', views.inventario_suspender, name='inventario_suspender'),
    path('inventario/toggle-estado/<int:id>/', views.inventario_toggle_estado, name='inventario_toggle_estado'),
    path('api/inventario/productos-proveedor/', views.inventario_productos_proveedor_ajax, name='inventario_productos_proveedor_ajax'),
    path('api/inventario/cantidad-producto-proveedor/', views.inventario_cantidad_producto_proveedor_ajax, name='inventario_cantidad_producto_proveedor_ajax'),
    path('api/entradas/productos-proveedor/', views.entradas_productos_por_proveedor_ajax, name='entradas_productos_por_proveedor_ajax'),
    path('api/entradas/productos-inventario-proveedor/', views.entradas_productos_inventario_por_proveedor_ajax, name='entradas_productos_inventario_por_proveedor_ajax'),
    
    # Rutas Zonas (AJAX)
    path('api/zonas/crear/', views.zona_crear_ajax, name='zona_crear_ajax'),
    path('api/zonas/lista/', views.zonas_lista_ajax, name='zonas_lista_ajax'),
    
    # Rutas Auditoría de Inventario
    path('auditoria/', views.auditoria_lista, name='auditoria_lista'),
    path('auditoria/revisiones/', views.auditoria_revisiones, name='auditoria_revisiones'),
    path('auditoria/crear/', views.auditoria_crear, name='auditoria_crear'),
    path('auditoria/<int:id>/', views.auditoria_detalle, name='auditoria_detalle'),
    path('auditoria/<int:auditoria_id>/editar-detalle/<int:detalle_id>/', views.auditoria_editar_detalle, name='auditoria_editar_detalle'),
    path('auditoria/<int:id>/completar/', views.auditoria_completar, name='auditoria_completar'),
    path('auditoria/<int:id>/cancelar/', views.auditoria_cancelar, name='auditoria_cancelar'),
    path('auditoria/<int:id>/eliminar/', views.auditoria_eliminar, name='auditoria_eliminar'),
    path('api/auditoria/marcar-revisado/<int:detalle_id>/', views.auditoria_marcar_revisado, name='auditoria_marcar_revisado'),
    path('api/auditoria/actualizar-conteo/<int:detalle_id>/', views.auditoria_actualizar_conteo_ajax, name='auditoria_actualizar_conteo_ajax'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
