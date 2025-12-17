from django.shortcuts import render, redirect
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q, F
from django.db import transaction
from django.utils import timezone
from django.utils.timezone import make_aware, is_naive, localtime
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def _normalize_timestamp(value):
    if not value:
        return None
    if is_naive(value):
        value = make_aware(value, timezone.get_current_timezone())
    return localtime(value)


def registrar_accion_historial(accion, tipo_modelo, nombre_objeto, usuario=None, descripcion=None, objeto_id=None):
    """
    Función helper para registrar una acción en el historial del sistema.
    
    Args:
        accion: 'creado', 'editado' o 'eliminado'
        tipo_modelo: Tipo de modelo (ej: 'producto', 'empleado', etc.)
        nombre_objeto: Nombre del objeto afectado
        usuario: Usuario que realizó la acción (opcional)
        descripcion: Descripción adicional (opcional)
        objeto_id: ID del objeto afectado (opcional)
    """
    try:
        HistorialAccion.objects.create(
            accion=accion,
            tipo_modelo=tipo_modelo,
            nombre_objeto=nombre_objeto,
            usuario=usuario,
            descripcion=descripcion,
            objeto_id=objeto_id
        )
    except Exception as e:
        # Silenciar errores de historial para no interrumpir el flujo principal
        pass


def _get_recent_system_activity():
    """
    Obtiene las 5 últimas acciones realizadas en el sistema desde el historial.
    """
    eventos = []
    
    # Obtener las 5 últimas acciones del historial
    acciones = HistorialAccion.objects.select_related('usuario').order_by('-fecha')[:5]
    
    for accion in acciones:
        timestamp = _normalize_timestamp(accion.fecha)
        if not timestamp:
            continue
        
        # Construir título según la acción
        if accion.accion == 'creado':
            titulo = f'{accion.get_tipo_modelo_display()} creado: {accion.nombre_objeto}'
        elif accion.accion == 'editado':
            titulo = f'{accion.get_tipo_modelo_display()} editado: {accion.nombre_objeto}'
        elif accion.accion == 'eliminado':
            titulo = f'{accion.get_tipo_modelo_display()} eliminado: {accion.nombre_objeto}'
        else:
            titulo = f'{accion.get_tipo_modelo_display()}: {accion.nombre_objeto}'
        
        # Construir descripción
        descripcion = accion.descripcion or f'Se {accion.get_accion_display().lower()} un {accion.get_tipo_modelo_display().lower()} en el sistema.'
        
        # Detalles adicionales
        detalles = []
        if accion.usuario:
            detalles.append(f'Usuario: {accion.usuario.get_full_name() or accion.usuario.username}')
        if accion.objeto_id:
            detalles.append(f'ID: {accion.objeto_id}')
        
        eventos.append({
            'timestamp': timestamp,
            'category': accion.categoria,
            'title': titulo,
            'description': descripcion,
            'author': accion.usuario.get_full_name() if accion.usuario else 'Sistema',
            'details': detalles,
            'icon': accion.icono,
        })
    
    return eventos
from datetime import date, datetime, timedelta
import json

from .models import Producto, Proveedores, ServicioRealizado, Compras, Servicio, Empleado, Especialidad, Cargo, ProductoProveedor, EntradaInventario, SolicitudCompra, Zona, AuditoriaInventario, DetalleAuditoria, EmpleadoHistorial, HistorialAccion
from .forms import ProductoForm, EmpleadoForm, ProductoProveedorForm, EntradaInventarioForm, SolicitudCompraForm, VerificacionRecepcionForm, AuditoriaInventarioForm, DetalleAuditoriaForm
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login

# Create your views here.

def validar_horario_atencion(fecha_servicio, hora_obj):
    """
    Valida que la hora esté dentro del horario de atención según el día de la semana.
    Horarios:
    - Lunes a Viernes: 9:00 AM - 7:00 PM (9:00 - 19:00)
    - Sábado: 10:00 AM - 2:00 PM (10:00 - 14:00)
    - Domingo: Cerrado
    
    Retorna: (es_valido, mensaje_error)
    """
    if not fecha_servicio or not hora_obj:
        return False, 'Fecha y hora son requeridas'
    
    dia_semana = fecha_servicio.weekday()  # 0=Lunes, 6=Domingo
    hora_num = hora_obj.hour
    minuto_num = hora_obj.minute
    
    # Validar intervalos de 30 minutos
    if minuto_num != 0 and minuto_num != 30:
        return False, 'Las horas deben estar en intervalos de 30 minutos (ej: 9:00, 9:30, 10:00).'
    
    # Domingo: Cerrado
    if dia_semana == 6:
        return False, 'Los domingos la clínica está cerrada. Por favor selecciona otro día.'
    
    # Sábado: 10:00 - 14:00
    if dia_semana == 5:
        if hora_num < 10 or hora_num > 14 or (hora_num == 14 and minuto_num > 0):
            return False, 'Los sábados el horario de atención es de 10:00 AM a 2:00 PM.'
    
    # Lunes a Viernes: 9:00 - 19:00
    else:
        if hora_num < 9 or hora_num > 19 or (hora_num == 19 and minuto_num > 0):
            return False, 'El horario de atención de lunes a viernes es de 9:00 AM a 7:00 PM.'
    
    return True, None

def inicio(request):
    return render(request, 'paginas/inicio.html')

def user_login(request):
    if request.method == 'POST':
        # Prefer the 'real_' fields (our real inputs). Fallback to legacy names if needed.
        username = request.POST.get('real_username') or request.POST.get('username')
        password = request.POST.get('real_password') or request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, 'Cuenta suspendida o inactiva. Por favor, ponte en contacto con la administración.')
                return render(request, 'registration/login.html')
            login(request, user)
            return redirect('admin_panel')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    return render(request, 'registration/login.html')

def user_logout(request):
    logout(request)
    return redirect('inicio')

@login_required(login_url='login')
def upload_avatar(request):
    """Vista para subir foto de perfil del usuario."""
    if request.method == 'POST' and request.FILES.get('avatar'):
        try:
            import os
            from django.conf import settings
            
            # Asegurar que el directorio de fotos existe
            foto_dir = os.path.join(settings.MEDIA_ROOT, 'empleados', 'fotos')
            os.makedirs(foto_dir, exist_ok=True)
            
            # Obtener o crear el empleado asociado al usuario
            try:
                empleado = Empleado.objects.get(user=request.user)
            except Empleado.DoesNotExist:
                # Verificar si ya existe un empleado con ese email
                email_usuario = request.user.email
                if email_usuario:
                    empleado_existente = Empleado.objects.filter(email=email_usuario).first()
                    if empleado_existente:
                        # Si existe, asociarlo al usuario actual
                        empleado_existente.user = request.user
                        empleado_existente.save()
                        empleado = empleado_existente
                    else:
                        # Crear nuevo empleado si no existe
                        # Generar email único si es necesario
                        email_base = email_usuario
                        contador = 1
                        while Empleado.objects.filter(email=email_base).exists():
                            email_base = f"{email_usuario.split('@')[0]}{contador}@{email_usuario.split('@')[1] if '@' in email_usuario else 'example.com'}"
                            contador += 1
                        
                        empleado = Empleado.objects.create(
                            user=request.user,
                            nombre=request.user.first_name or request.user.username,
                            apellido=request.user.last_name or '',
                            email=email_base
                        )
                else:
                    # Si no tiene email, crear con email temporal
                    email_temp = f"{request.user.username}@temp.local"
                    contador = 1
                    while Empleado.objects.filter(email=email_temp).exists():
                        email_temp = f"{request.user.username}{contador}@temp.local"
                        contador += 1
                    
                    empleado = Empleado.objects.create(
                        user=request.user,
                        nombre=request.user.first_name or request.user.username,
                        apellido=request.user.last_name or '',
                        email=email_temp
                    )
            
            # Actualizar nombre y email si están vacíos o diferentes
            nombre_actual = request.user.first_name or request.user.username
            apellido_actual = request.user.last_name or ''
            email_actual = request.user.email
            
            if not empleado.nombre or empleado.nombre != nombre_actual:
                empleado.nombre = nombre_actual
            if not empleado.apellido or empleado.apellido != apellido_actual:
                empleado.apellido = apellido_actual
            # Solo actualizar email si no hay conflicto
            if email_actual and (not empleado.email or empleado.email != email_actual):
                # Verificar si el email ya está en uso por otro empleado
                email_en_uso = Empleado.objects.filter(email=email_actual).exclude(id=empleado.id).exists()
                if not email_en_uso:
                    empleado.email = email_actual
                # Si está en uso, mantener el email actual del empleado
            
            # Guardar cambios antes de subir la foto
            empleado.save()
            
            # Eliminar foto anterior si existe
            if empleado.foto:
                try:
                    empleado.foto.delete(save=False)
                except Exception as e:
                    print(f"Error al eliminar foto anterior: {e}")
            
            # Validar tamaño del archivo (max 5MB)
            avatar_file = request.FILES['avatar']
            if avatar_file.size > 5 * 1024 * 1024:
                raise ValueError('La imagen es demasiado grande. El tamaño máximo es 5MB.')
            
            # Validar tipo de archivo
            if not avatar_file.content_type.startswith('image/'):
                raise ValueError('El archivo debe ser una imagen válida.')
            
            # Guardar nueva foto
            empleado.foto = avatar_file
            empleado.save()
            
            # Recargar el objeto para obtener la URL actualizada
            empleado.refresh_from_db()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Foto de perfil actualizada exitosamente',
                    'avatar_url': empleado.foto.url if empleado.foto else ''
                })
            else:
                messages.success(request, 'Foto de perfil actualizada exitosamente')
                return redirect('admin_panel')
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"Error en upload_avatar: {error_detail}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f'Error al subir la foto: {str(e)}'
                }, status=400)
            else:
                messages.error(request, f'Error al subir la foto: {str(e)}')
                return redirect('admin_panel')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'message': 'No se recibió ninguna imagen'
        }, status=400)
    else:
        messages.error(request, 'No se recibió ninguna imagen')
        return redirect('admin_panel')

def password_reset_request(request):
    """Vista para solicitar restablecimiento de contraseña."""
    if request.method == 'POST':
        username_or_email = request.POST.get('username_or_email', '').strip()
        
        if not username_or_email:
            messages.error(request, 'Por favor ingresa tu nombre de usuario o email.')
            return render(request, 'registration/password_reset_request.html')
        
        # Buscar usuario por username o email
        user = None
        try:
            # Intentar buscar por username
            user = User.objects.get(username=username_or_email)
        except User.DoesNotExist:
            try:
                # Intentar buscar por email
                user = User.objects.get(email=username_or_email)
            except User.DoesNotExist:
                pass
        
        if user:
            # Guardar el ID del usuario en la sesión para el siguiente paso
            request.session['password_reset_user_id'] = user.id
            messages.success(request, f'Usuario encontrado. Ahora puedes restablecer tu contraseña.')
            return redirect('password_reset_confirm')
        else:
            messages.error(request, 'No se encontró un usuario con ese nombre de usuario o email. Por favor, contacta al administrador.')
    
    return render(request, 'registration/password_reset_request.html')

def password_reset_confirm(request):
    """Vista para confirmar y cambiar la contraseña."""
    user_id = request.session.get('password_reset_user_id')
    
    if not user_id:
        messages.error(request, 'Sesión expirada. Por favor, inicia el proceso nuevamente.')
        return redirect('password_reset_request')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        del request.session['password_reset_user_id']
        return redirect('password_reset_request')
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        if not new_password or not confirm_password:
            messages.error(request, 'Por favor completa todos los campos.')
            return render(request, 'registration/password_reset_confirm.html', {'user': user})
        
        if new_password != confirm_password:
            messages.error(request, 'Las contraseñas no coinciden.')
            return render(request, 'registration/password_reset_confirm.html', {'user': user})
        
        if len(new_password) < 6:
            messages.error(request, 'La contraseña debe tener al menos 6 caracteres.')
            return render(request, 'registration/password_reset_confirm.html', {'user': user})
        
        # Cambiar la contraseña
        user.set_password(new_password)
        user.save()
        
        # Limpiar la sesión
        del request.session['password_reset_user_id']
        
        messages.success(request, 'Contraseña restablecida exitosamente. Ahora puedes iniciar sesión.')
        return redirect('login')
    
    return render(request, 'registration/password_reset_confirm.html', {'user': user})

# ========== CRUD EMPLEADOS (ADMIN) ==========

@login_required(login_url='login')
def estilistas_lista(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar empleados')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    estilistas = Empleado.objects.all().order_by('nombre', 'apellido')
    
    # Filtros
    nombre_filtro = request.GET.get('nombre', '').strip()
    cargo_filtro = request.GET.get('cargo', '').strip()
    
    if nombre_filtro:
        estilistas = estilistas.filter(
            Q(nombre__icontains=nombre_filtro) | 
            Q(apellido__icontains=nombre_filtro) |
            Q(email__icontains=nombre_filtro)
        )
    
    if cargo_filtro:
        estilistas = estilistas.filter(cargo__nombre__icontains=cargo_filtro)
    
    # Paginación - 7 elementos por página
    paginator = Paginator(estilistas, 7)
    page = request.GET.get('page', 1)
    try:
        estilistas = paginator.page(page)
    except PageNotAnInteger:
        estilistas = paginator.page(1)
    except EmptyPage:
        estilistas = paginator.page(paginator.num_pages)
    
    context = {
        'estilistas': estilistas,
        'nombre_filtro': nombre_filtro,
        'cargo_filtro': cargo_filtro
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'estilistas/lista_fragment.html', context)
    else:
        return render(request, 'estilistas/lista.html', context)


@login_required(login_url='login')
def estilistas_crear(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar empleados')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    # Si es petición AJAX GET, devolver solo el formulario
    if request.method == 'GET' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        formulario = EmpleadoForm()
        return render(request, 'estilistas/crear_fragment.html', {'formulario': formulario})
    
    if request.method == 'POST':
        formulario = EmpleadoForm(request.POST, request.FILES)
        if formulario.is_valid():
            try:
                empleado = formulario.save(commit=False)
                empleado.save()  # Guardar primero para obtener el ID
                # Guardar las relaciones ManyToMany
                formulario.save_m2m()
            except Exception as e:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'errors': {'__all__': [f'Error al guardar el empleado: {str(e)}']}
                    }, status=400)
                messages.error(request, f'Error al guardar el empleado: {str(e)}')
                return render(request, 'estilistas/crear.html', {'formulario': formulario})
            
            # Crear usuario de Django si se solicitó
            crear_usuario = formulario.cleaned_data.get('crear_usuario')
            mensaje_exito = 'Empleado creado exitosamente'
            if crear_usuario:
                username = formulario.cleaned_data.get('username')
                password = formulario.cleaned_data.get('password')
                email = empleado.email
                
                if username and password:
                    try:
                        # Crear usuario de Django
                        user = User.objects.create_user(
                            username=username,
                            password=password,
                            email=email,
                            first_name=empleado.nombre,
                            last_name=empleado.apellido or '',
                            is_staff=True  # Los empleados son staff para acceder al panel
                        )
                        # Asociar el usuario con el empleado
                        empleado.user = user
                        empleado.save()
                        # Registrar acción en el historial (el modelo Empleado ya registra en EmpleadoHistorial, pero también lo registramos en HistorialAccion)
                        registrar_accion_historial(
                            accion='creado',
                            tipo_modelo='empleado',
                            nombre_objeto=str(empleado),
                            usuario=request.user,
                            descripcion=f'Empleado creado con email: {empleado.email}',
                            objeto_id=empleado.id
                        )
                        mensaje_exito = f'Empleado y usuario "{username}" creados exitosamente'
                    except Exception as e:
                        mensaje_exito = f'Empleado creado pero hubo un error al crear el usuario: {str(e)}'
                else:
                    mensaje_exito = 'Empleado creado pero no se pudo crear el usuario (faltan datos)'
            
            # Si es petición AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': mensaje_exito
                })
            
            messages.success(request, mensaje_exito)
            return redirect('empleados_lista')
        else:
            # Si hay errores y es AJAX, devolver JSON con errores
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                for field, field_errors in formulario.errors.items():
                    errors[field] = [str(e) for e in field_errors]
                return JsonResponse({
                    'success': False,
                    'errors': errors
                }, status=400)
            
            # Si hay errores, mostrarlos
            messages.error(request, 'Por favor, corrige los errores en el formulario')
    else:
        formulario = EmpleadoForm()
    return render(request, 'estilistas/crear.html', {'formulario': formulario})


@login_required(login_url='login')
def editar_mi_perfil(request):
    """Vista para que el usuario actual edite su propio perfil de empleado."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Obtener o crear el empleado asociado al usuario
    try:
        empleado = Empleado.objects.get(user=request.user)
    except Empleado.DoesNotExist:
        # Si no existe, buscar por email
        if request.user.email:
            try:
                empleado = Empleado.objects.get(email=request.user.email)
                # Asociar al usuario si no estaba asociado
                if not empleado.user:
                    empleado.user = request.user
                    empleado.save()
            except Empleado.DoesNotExist:
                # Crear nuevo empleado si no existe
                email_usuario = request.user.email
                if email_usuario:
                    email_base = email_usuario
                    contador = 1
                    while Empleado.objects.filter(email=email_base).exists():
                        email_base = f"{email_usuario.split('@')[0]}{contador}@{email_usuario.split('@')[1] if '@' in email_usuario else 'example.com'}"
                        contador += 1
                else:
                    email_base = f"{request.user.username}@temp.local"
                    contador = 1
                    while Empleado.objects.filter(email=email_base).exists():
                        email_base = f"{request.user.username}{contador}@temp.local"
                        contador += 1
                
                empleado = Empleado.objects.create(
                    user=request.user,
                    nombre=request.user.first_name or request.user.username,
                    apellido=request.user.last_name or '',
                    email=email_base
                )
        else:
            # Si no tiene email, crear con email temporal
            email_temp = f"{request.user.username}@temp.local"
            contador = 1
            while Empleado.objects.filter(email=email_temp).exists():
                email_temp = f"{request.user.username}{contador}@temp.local"
                contador += 1
            
            empleado = Empleado.objects.create(
                user=request.user,
                nombre=request.user.first_name or request.user.username,
                apellido=request.user.last_name or '',
                email=email_temp
            )
    
    if request.method == 'POST':
        formulario = EmpleadoForm(request.POST, request.FILES, instance=empleado)
        if formulario.is_valid():
            try:
                empleado = formulario.save(commit=False)
                # Asegurar que el usuario sigue asociado
                empleado.user = request.user
                # No permitir cambiar el cargo desde esta vista - mantener el cargo original
                empleado_original = Empleado.objects.get(id=empleado.id)
                empleado.cargo = empleado_original.cargo
                empleado.save()
                # Guardar las relaciones ManyToMany
                formulario.save_m2m()
                
                # Actualizar también el usuario de Django
                if request.user.email != empleado.email and empleado.email:
                    # Verificar que el email no esté en uso por otro usuario
                    from django.contrib.auth.models import User
                    if not User.objects.filter(email=empleado.email).exclude(id=request.user.id).exists():
                        request.user.email = empleado.email
                request.user.first_name = empleado.nombre
                request.user.last_name = empleado.apellido or ''
                request.user.save()
                
                # Si es petición AJAX, devolver JSON
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': 'Tu perfil se ha actualizado exitosamente'
                    })
                
                messages.success(request, 'Tu perfil se ha actualizado exitosamente')
                return redirect('admin_panel')
            except Exception as e:
                # Si es petición AJAX, devolver JSON con error
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Error al guardar el perfil: {str(e)}'
                    }, status=400)
                
                messages.error(request, f'Error al guardar el perfil: {str(e)}')
                return render(request, 'estilistas/editar_mi_perfil.html', {'formulario': formulario, 'empleado': empleado})
        else:
            # Si es petición AJAX y hay errores, devolver el fragmento con errores
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return render(request, 'estilistas/editar_mi_perfil_fragment.html', {'formulario': formulario, 'empleado': empleado})
            
            messages.error(request, 'Por favor, corrige los errores en el formulario')
    else:
        formulario = EmpleadoForm(instance=empleado)
        # No permitir cambiar el usuario asociado
        if 'user' in formulario.fields:
            formulario.fields['user'].widget = forms.HiddenInput()
        
        # Ocultar campos que el usuario no debe editar
        campos_no_editables = ['cargo', 'disponibilidad', 
                              'experiencia_anos', 'activo', 'crear_usuario',
                              'username', 'password', 'password_confirm']
        
        for campo in campos_no_editables:
            if campo in formulario.fields:
                formulario.fields[campo].widget = forms.HiddenInput()
                formulario.fields[campo].required = False
    
    # Si es petición AJAX, devolver fragmento
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'estilistas/editar_mi_perfil_fragment.html', {'formulario': formulario, 'empleado': empleado})
    
    return render(request, 'estilistas/editar_mi_perfil.html', {'formulario': formulario, 'empleado': empleado})


@login_required(login_url='login')
def estilistas_editar(request, id):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            # Buscar por user primero, luego por email
            empleado_actual = Empleado.objects.filter(user=request.user).first()
            if not empleado_actual and request.user.email:
                empleado_actual = Empleado.objects.filter(email=request.user.email).first()
            if empleado_actual and empleado_actual.cargo and not empleado_actual.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar empleados')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    try:
        estilista = Empleado.objects.get(id=id)
    except Empleado.DoesNotExist:
        messages.error(request, 'Empleado no encontrado')
        return redirect('empleados_lista')
    except Exception as e:
        messages.error(request, f'Error al cargar el empleado: {str(e)}')
        return redirect('empleados_lista')
    
    if request.method == 'POST':
        formulario = EmpleadoForm(request.POST, request.FILES, instance=estilista)
        if formulario.is_valid():
            try:
                empleado = formulario.save(commit=False)
                empleado.save()  # Guardar primero para obtener el ID
                # Guardar las relaciones ManyToMany
                formulario.save_m2m()
            except Exception as e:
                messages.error(request, f'Error al guardar el empleado: {str(e)}')
                return render(request, 'estilistas/editar.html', {'formulario': formulario, 'estilista': estilista})
            
            # Gestionar usuario de Django
            crear_usuario = formulario.cleaned_data.get('crear_usuario')
            username = formulario.cleaned_data.get('username')
            password = formulario.cleaned_data.get('password')
            
            # Gestionar usuario de Django
            mensaje = 'Empleado actualizado exitosamente'
            if crear_usuario and username:
                try:
                    if empleado.user:
                        # Actualizar usuario existente
                        user = empleado.user
                        user.username = username
                        user.email = empleado.email
                        user.first_name = empleado.nombre
                        user.last_name = empleado.apellido or ''
                        if password:
                            user.set_password(password)
                        user.save()
                        mensaje = f'Empleado y usuario "{username}" actualizados exitosamente'
                    else:
                        # Crear nuevo usuario (requiere contraseña)
                        if password:
                            user = User.objects.create_user(
                                username=username,
                                password=password,
                                email=empleado.email,
                                first_name=empleado.nombre,
                                last_name=empleado.apellido or '',
                                is_staff=True
                            )
                            empleado.user = user
                            empleado.save()
                            mensaje = f'Empleado actualizado y usuario "{username}" creado exitosamente'
                        else:
                            mensaje = 'Empleado actualizado. Para crear un usuario, debes proporcionar una contraseña'
                except Exception as e:
                    mensaje = f'Empleado actualizado pero hubo un error al gestionar el usuario: {str(e)}'
            
            # Registrar acción en el historial (el modelo Empleado ya registra en EmpleadoHistorial, pero también lo registramos en HistorialAccion)
            registrar_accion_historial(
                accion='editado',
                tipo_modelo='empleado',
                nombre_objeto=str(estilista),
                usuario=request.user,
                descripcion=f'Empleado actualizado',
                objeto_id=estilista.id
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': mensaje})
            messages.success(request, mensaje)
            return redirect('empleados_lista')
        else:
            # Si hay errores y es AJAX, devolver el formulario con errores
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return render(request, 'estilistas/editar_fragment.html', {'formulario': formulario, 'estilista': estilista})
            messages.error(request, 'Por favor, corrige los errores en el formulario')
    else:
        formulario = EmpleadoForm(instance=estilista)
        # Pre-llenar datos del usuario si existe
        if estilista.user:
            formulario.fields['crear_usuario'].initial = True
            formulario.fields['username'].initial = estilista.user.username
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'estilistas/editar_fragment.html', {'formulario': formulario, 'estilista': estilista})
    return render(request, 'estilistas/editar.html', {'formulario': formulario, 'estilista': estilista})


@login_required(login_url='login')
def estilistas_eliminar(request, id):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar empleados')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    try:
        estilista = Empleado.objects.get(id=id)
    except Empleado.DoesNotExist:
        messages.error(request, 'Empleado no encontrado')
        return redirect('empleados_lista')
    except Exception as e:
        messages.error(request, f'Error al cargar el empleado: {str(e)}')
        return redirect('empleados_lista')
    
    try:
        nombre_empleado = str(estilista)
        empleado_id = estilista.id
        estilista.delete()
        # Registrar acción en el historial (el modelo Empleado ya registra en EmpleadoHistorial, pero también lo registramos en HistorialAccion)
        registrar_accion_historial(
            accion='eliminado',
            tipo_modelo='empleado',
            nombre_objeto=nombre_empleado,
            usuario=request.user,
            descripcion=f'Empleado eliminado del sistema',
            objeto_id=empleado_id
        )
        messages.success(request, 'Empleado eliminado exitosamente')
    except Exception as e:
        messages.error(request, f'Error al eliminar el empleado: {str(e)}')
    return redirect('empleados_lista')





# ========== CRUD ESPECIALIDADES ==========

@login_required(login_url='login')
def especialidades_lista(request):
    """Lista de especialidades disponibles."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if request.user.is_superuser:
        especialidades = Especialidad.objects.all().order_by('nombre')
    else:
        # Para usuarios normales, verificar permiso de cargo
        puede_acceder = True
        try:
            empleado = Empleado.objects.filter(email=request.user.email).first()
            if empleado and empleado.cargo:
                cargo = empleado.cargo
                # Verificar si el campo existe y si tiene permiso
                if hasattr(cargo, 'puede_gestionar_empleados_servicios_proveedores'):
                    puede_acceder = cargo.puede_gestionar_empleados_servicios_proveedores
        except Exception:
            # Si hay cualquier error, permitir acceso (evitar bloqueos)
            puede_acceder = True
        
        if not puede_acceder:
            messages.error(request, 'No tienes permiso para gestionar especialidades')
            return redirect('admin_panel')
        
        especialidades = Especialidad.objects.all().order_by('nombre')
    
    # Paginación - 6 elementos por página
    paginator = Paginator(especialidades, 6)
    page = request.GET.get('page', 1)
    try:
        especialidades = paginator.page(page)
    except PageNotAnInteger:
        especialidades = paginator.page(1)
    except EmptyPage:
        especialidades = paginator.page(paginator.num_pages)
    
    # Contar empleados por especialidad
    for especialidad in especialidades:
        # Usar empleado_set porque es el related_name por defecto de ManyToManyField
        try:
            especialidad.cantidad_empleados = especialidad.empleado_set.count()
        except Exception:
            especialidad.cantidad_empleados = 0
    
    return render(request, 'especialidades/index.html', {'especialidades': especialidades})


@login_required(login_url='login')
def especialidades_crear(request):
    """Crear nueva especialidad."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.filter(email=request.user.email).first()
            if empleado and empleado.cargo:
                # Verificar si el cargo tiene el permiso
                cargo = empleado.cargo
                if hasattr(cargo, 'puede_gestionar_empleados_servicios_proveedores'):
                    if not cargo.puede_gestionar_empleados_servicios_proveedores:
                        messages.error(request, 'No tienes permiso para gestionar especialidades')
                        return redirect('admin_panel')
        except Exception as e:
            # Cualquier error, permitir acceso para evitar bloqueos
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error verificando permisos en especialidades_crear: {e}")
            pass
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        
        if not nombre:
            messages.error(request, 'El nombre de la especialidad es obligatorio')
            return render(request, 'especialidades/crear.html')
        
        # Verificar si ya existe una especialidad con ese nombre
        if Especialidad.objects.filter(nombre=nombre).exists():
            messages.error(request, 'Ya existe una especialidad con ese nombre')
            return render(request, 'especialidades/crear.html', {
                'nombre': nombre,
                'descripcion': descripcion
            })
        
        try:
            especialidad = Especialidad(
                nombre=nombre,
                descripcion=descripcion
            )
            especialidad.save()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='creado',
                tipo_modelo='especialidad',
                nombre_objeto=especialidad.nombre,
                usuario=request.user,
                descripcion=f'Especialidad creada',
                objeto_id=especialidad.id
            )
            messages.success(request, f'Especialidad "{nombre}" creada exitosamente')
        except Exception as e:
            messages.error(request, f'Error al crear la especialidad: {str(e)}')
        return redirect('especialidades_lista')
    
    return render(request, 'especialidades/crear.html')


@login_required(login_url='login')
def especialidades_editar(request, id):
    """Editar especialidad existente."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.filter(email=request.user.email).first()
            if empleado and empleado.cargo:
                # Verificar si el cargo tiene el permiso
                cargo = empleado.cargo
                if hasattr(cargo, 'puede_gestionar_empleados_servicios_proveedores'):
                    if not cargo.puede_gestionar_empleados_servicios_proveedores:
                        messages.error(request, 'No tienes permiso para gestionar especialidades')
                        return redirect('admin_panel')
        except Exception as e:
            # Cualquier error, permitir acceso para evitar bloqueos
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error verificando permisos en especialidades_editar: {e}")
            pass
    
    try:
        especialidad = Especialidad.objects.get(id=id)
    except Especialidad.DoesNotExist:
        messages.error(request, 'Especialidad no encontrada')
        return redirect('especialidades_lista')
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        
        if not nombre:
            messages.error(request, 'El nombre de la especialidad es obligatorio')
            return render(request, 'especialidades/editar.html', {'especialidad': especialidad})
        
        # Verificar si ya existe otra especialidad con ese nombre (excluyendo la actual)
        if Especialidad.objects.filter(nombre=nombre).exclude(id=id).exists():
            messages.error(request, 'Ya existe otra especialidad con ese nombre')
            return render(request, 'especialidades/editar.html', {'especialidad': especialidad})
        
        try:
            especialidad.nombre = nombre
            especialidad.descripcion = descripcion
            especialidad.save()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='editado',
                tipo_modelo='especialidad',
                nombre_objeto=especialidad.nombre,
                usuario=request.user,
                descripcion=f'Especialidad actualizada',
                objeto_id=especialidad.id
            )
            messages.success(request, f'Especialidad "{nombre}" actualizada exitosamente')
        except Exception as e:
            messages.error(request, f'Error al actualizar la especialidad: {str(e)}')
        return redirect('especialidades_lista')
    
    return render(request, 'especialidades/editar.html', {'especialidad': especialidad})


@login_required(login_url='login')
def especialidades_eliminar(request, id):
    """Eliminar especialidad."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.filter(email=request.user.email).first()
            if empleado and empleado.cargo:
                # Verificar si el cargo tiene el permiso
                cargo = empleado.cargo
                if hasattr(cargo, 'puede_gestionar_empleados_servicios_proveedores'):
                    if not cargo.puede_gestionar_empleados_servicios_proveedores:
                        messages.error(request, 'No tienes permiso para gestionar especialidades')
                        return redirect('admin_panel')
        except Exception as e:
            # Cualquier error, permitir acceso para evitar bloqueos
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error verificando permisos en especialidades_eliminar: {e}")
            pass
    
    try:
        especialidad = Especialidad.objects.get(id=id)
    except Especialidad.DoesNotExist:
        messages.error(request, 'Especialidad no encontrada')
        return redirect('especialidades_lista')
    
    if request.method == 'POST':
        nombre = especialidad.nombre
        # Verificar si hay empleados con esta especialidad
        try:
            cantidad_empleados = especialidad.empleado_set.count()
        except Exception:
            cantidad_empleados = 0
        
        if cantidad_empleados > 0:
            messages.error(request, f'No se puede eliminar la especialidad "{nombre}" porque tiene {cantidad_empleados} empleado(s) asignado(s). Primero desasigna la especialidad de los empleados.')
            return redirect('especialidades_lista')
        
        try:
            especialidad_id = especialidad.id
            especialidad.delete()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='eliminado',
                tipo_modelo='especialidad',
                nombre_objeto=nombre,
                usuario=request.user,
                descripcion=f'Especialidad eliminada del sistema',
                objeto_id=especialidad_id
            )
            messages.success(request, f'Especialidad "{nombre}" eliminada exitosamente')
        except Exception as e:
            messages.error(request, f'Error al eliminar la especialidad: {str(e)}')
        return redirect('especialidades_lista')
    
    # GET: mostrar confirmación
    try:
        cantidad_empleados = especialidad.empleado_set.count()
    except Exception:
        cantidad_empleados = 0
    
    return render(request, 'especialidades/eliminar_confirm.html', {
        'especialidad': especialidad,
        'cantidad_empleados': cantidad_empleados
    })


# ========== CRUD CARGOS ==========

@login_required(login_url='login')
def cargos_lista(request):
    """Lista de cargos disponibles. Solo para superusuarios."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Solo superusuarios pueden gestionar cargos
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden gestionar roles y permisos')
        return redirect('admin_panel')
    
    cargos = Cargo.objects.all().order_by('nombre')
    
    # Paginación - 6 elementos por página
    paginator = Paginator(cargos, 6)
    page = request.GET.get('page', 1)
    try:
        cargos = paginator.page(page)
    except PageNotAnInteger:
        cargos = paginator.page(1)
    except EmptyPage:
        cargos = paginator.page(paginator.num_pages)
    
    # Contar empleados por cargo
    for cargo in cargos:
        try:
            cargo.cantidad_empleados = cargo.empleados.count()
        except Exception:
            cargo.cantidad_empleados = 0
    
    # Verificar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'cargos/index_fragment.html', {'cargos': cargos})
    
    return render(request, 'cargos/index.html', {'cargos': cargos})


@login_required(login_url='login')
def cargos_crear(request):
    """Crear nuevo cargo. Solo para superusuarios."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Solo superusuarios pueden crear cargos
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden crear roles y permisos')
        return redirect('admin_panel')
    
    # Si es petición AJAX GET, devolver solo el formulario
    if request.method == 'GET' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'cargos/crear_fragment.html')
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        puede_agendar = request.POST.get('puede_agendar') == 'on'
        puede_gestionar_inventario = request.POST.get('puede_gestionar_inventario') == 'on'
        puede_ver_compras = request.POST.get('puede_ver_compras') == 'on'
        puede_gestionar_empleados_servicios_proveedores = request.POST.get('puede_gestionar_empleados_servicios_proveedores') == 'on'
        activo = request.POST.get('activo') == 'on'
        
        context_data = {
            'nombre': nombre,
            'descripcion': descripcion,
            'puede_agendar': puede_agendar,
            'puede_gestionar_inventario': puede_gestionar_inventario,
            'puede_ver_compras': puede_ver_compras,
            'puede_gestionar_empleados_servicios_proveedores': puede_gestionar_empleados_servicios_proveedores,
            'activo': activo
        }
        
        if not nombre:
            error_msg = 'El nombre del rol es obligatorio'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': {'nombre': [error_msg]}
                }, status=400)
            messages.error(request, error_msg)
            return render(request, 'cargos/crear.html', context_data)
        
        # Verificar si ya existe un cargo con ese nombre
        if Cargo.objects.filter(nombre=nombre).exists():
            error_msg = 'Ya existe un rol con ese nombre'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': {'nombre': [error_msg]}
                }, status=400)
            messages.error(request, error_msg)
            return render(request, 'cargos/crear.html', context_data)
        
        try:
            cargo = Cargo(
                nombre=nombre,
                descripcion=descripcion,
                puede_agendar=puede_agendar,
                puede_gestionar_inventario=puede_gestionar_inventario,
                puede_ver_compras=puede_ver_compras,
                puede_gestionar_empleados_servicios_proveedores=puede_gestionar_empleados_servicios_proveedores,
                activo=activo
            )
            cargo.save()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='creado',
                tipo_modelo='cargo',
                nombre_objeto=cargo.nombre,
                usuario=request.user,
                descripcion=f'Cargo creado con permisos configurados',
                objeto_id=cargo.id
            )
            success_msg = f'Rol "{nombre}" creado exitosamente'
            
            # Si es AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': success_msg
                })
            
            messages.success(request, success_msg)
            return redirect('cargos_lista')
        except Exception as e:
            error_msg = f'Error al crear el rol: {str(e)}'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': {'__all__': [error_msg]}
                }, status=400)
            messages.error(request, error_msg)
            return render(request, 'cargos/crear.html', context_data)
    
    return render(request, 'cargos/crear.html')


@login_required(login_url='login')
def cargos_editar(request, id):
    """Editar cargo existente. Solo para superusuarios."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Solo superusuarios pueden editar cargos
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden editar roles y permisos')
        return redirect('admin_panel')
    
    try:
        cargo = Cargo.objects.get(id=id)
    except Cargo.DoesNotExist:
        messages.error(request, 'Cargo no encontrado')
        return redirect('cargos_lista')
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        puede_agendar = request.POST.get('puede_agendar') == 'on'
        puede_gestionar_inventario = request.POST.get('puede_gestionar_inventario') == 'on'
        puede_ver_compras = request.POST.get('puede_ver_compras') == 'on'
        puede_gestionar_empleados_servicios_proveedores = request.POST.get('puede_gestionar_empleados_servicios_proveedores') == 'on'
        activo = request.POST.get('activo') == 'on'
        
        if not nombre:
            messages.error(request, 'El nombre del cargo es obligatorio')
            return render(request, 'cargos/editar.html', {'cargo': cargo})
        
        # Verificar si ya existe otro cargo con ese nombre (excluyendo el actual)
        if Cargo.objects.filter(nombre=nombre).exclude(id=id).exists():
            messages.error(request, 'Ya existe otro cargo con ese nombre')
            return render(request, 'cargos/editar.html', {'cargo': cargo})
        
        cargo.nombre = nombre
        cargo.descripcion = descripcion
        cargo.puede_agendar = puede_agendar
        cargo.puede_gestionar_inventario = puede_gestionar_inventario
        cargo.puede_ver_compras = puede_ver_compras
        try:
            cargo.puede_gestionar_empleados_servicios_proveedores = puede_gestionar_empleados_servicios_proveedores
            cargo.activo = activo
            cargo.save()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='editado',
                tipo_modelo='cargo',
                nombre_objeto=cargo.nombre,
                usuario=request.user,
                descripcion=f'Cargo actualizado',
                objeto_id=cargo.id
            )
            messages.success(request, f'Cargo "{nombre}" actualizado exitosamente')
        except Exception as e:
            messages.error(request, f'Error al actualizar el cargo: {str(e)}')
        return redirect('cargos_lista')
    
    return render(request, 'cargos/editar.html', {'cargo': cargo})


@login_required(login_url='login')
def cargos_eliminar(request, id):
    """Eliminar cargo. Solo para superusuarios."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Solo superusuarios pueden eliminar cargos
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden eliminar roles y permisos')
        return redirect('admin_panel')
    
    try:
        cargo = Cargo.objects.get(id=id)
    except Cargo.DoesNotExist:
        messages.error(request, 'Cargo no encontrado')
        return redirect('cargos_lista')
    
    if request.method == 'POST':
        nombre = cargo.nombre
        # Verificar si hay empleados con este cargo
        try:
            cantidad_empleados = cargo.empleados.count()
        except Exception:
            cantidad_empleados = 0
        
        if cantidad_empleados > 0:
            messages.error(request, f'No se puede eliminar el cargo "{nombre}" porque tiene {cantidad_empleados} empleado(s) asignado(s). Primero cambia el cargo de los empleados.')
            return redirect('cargos_lista')
        
        try:
            cargo_id = cargo.id
            cargo.delete()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='eliminado',
                tipo_modelo='cargo',
                nombre_objeto=nombre,
                usuario=request.user,
                descripcion=f'Cargo eliminado del sistema',
                objeto_id=cargo_id
            )
            messages.success(request, f'Cargo "{nombre}" eliminado exitosamente')
        except Exception as e:
            messages.error(request, f'Error al eliminar el cargo: {str(e)}')
        return redirect('cargos_lista')
    
    # GET: mostrar confirmación
    try:
        cantidad_empleados = cargo.empleados.count()
    except Exception:
        cantidad_empleados = 0
    
    return render(request, 'cargos/eliminar_confirm.html', {
        'cargo': cargo,
        'cantidad_empleados': cantidad_empleados
    })


@login_required(login_url='login')
def admin_panel(request):
    """Panel de gestión centralizado para administradores (solo staff)."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')

    # Calcular todas las métricas del dashboard
    proveedores_count = Proveedores.objects.count()
    productos_count = Producto.objects.count()
    
    # Calcular existencias
    from django.db.models import Sum
    existencia_total = Producto.objects.aggregate(total=Sum('cantidad'))['total'] or 0
    
    # Calcular existencia vendida (de compras)
    existencia_vendida = Compras.objects.aggregate(total=Sum('cantidad'))['total'] or 0
    
    # Existencia actual
    existencia_actual = existencia_total - existencia_vendida
    
    # Calcular importes
    importe_vendido = 0
    importe_pagado = 0
    try:
        compras = Compras.objects.all()
        for compra in compras:
            total_compra = float(compra.precio_unitario) * compra.cantidad
            importe_vendido += total_compra
            importe_pagado += total_compra  # Asumiendo que todas están pagadas
    except:
        pass
    
    importe_restante = 0
    beneficio_bruto = importe_vendido * 0.2  # 20% de beneficio estimado
    beneficio_neto = beneficio_bruto
    facturas_count = Compras.objects.count()
    auditorias_pendientes = AuditoriaInventario.objects.filter(estado='en_proceso').count()
    usuarios_activos = User.objects.filter(is_active=True).count()
    
    # Verificar permisos del usuario según su cargo
    if request.user.is_superuser:
        puede_gestionar_empleados_servicios_proveedores = True
        puede_agendar = True
        puede_gestionar_inventario = True
        puede_ver_compras = True
    else:
        puede_gestionar_empleados_servicios_proveedores = True
        puede_agendar = True
        puede_gestionar_inventario = True
        puede_ver_compras = True
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo:
                puede_gestionar_empleados_servicios_proveedores = empleado.cargo.puede_gestionar_empleados_servicios_proveedores
                puede_agendar = empleado.cargo.puede_agendar
                puede_gestionar_inventario = empleado.cargo.puede_gestionar_inventario
                puede_ver_compras = empleado.cargo.puede_ver_compras
        except Empleado.DoesNotExist:
            pass
    
    # Productos con bajo stock (usando stock_minimo)
    productos_bajo_stock = 0
    productos_bajo_stock_lista = []
    solicitudes_pendientes = 0
    
    if puede_gestionar_inventario:
        try:
            productos_bajo_stock = Producto.objects.filter(cantidad__lt=F('stock_minimo')).count()
            productos_bajo_stock_lista = list(Producto.objects.filter(cantidad__lt=F('stock_minimo'))[:5])
            solicitudes_pendientes = SolicitudCompra.objects.filter(estado__in=['borrador', 'enviada', 'aceptada', 'en_proceso']).count()
        except Exception as e:
            productos_bajo_stock = 0
            productos_bajo_stock_lista = []
            solicitudes_pendientes = 0
    
    context = {
        'proveedores_count': proveedores_count,
        'productos_count': productos_count,
        'existencia_total': existencia_total,
        'existencia_vendida': existencia_vendida,
        'existencia_actual': existencia_actual,
        'importe_vendido': f'${int(importe_vendido)}',
        'importe_pagado': f'${int(importe_pagado)}',
        'importe_restante': f'${int(importe_restante)}',
        'beneficio_bruto': f'${int(beneficio_bruto)}',
        'beneficio_neto': f'${int(beneficio_neto)}',
        'facturas_count': facturas_count,
        'auditorias_pendientes': auditorias_pendientes,
        'usuarios_activos': usuarios_activos,
        'recent_activities': _get_recent_system_activity(),
        'productos_bajo_stock': productos_bajo_stock,
        'productos_bajo_stock_lista': productos_bajo_stock_lista,
        'solicitudes_pendientes': solicitudes_pendientes,
        'puede_gestionar_empleados_servicios_proveedores': puede_gestionar_empleados_servicios_proveedores,
        'puede_agendar': puede_agendar,
        'puede_gestionar_inventario': puede_gestionar_inventario,
        'puede_ver_compras': puede_ver_compras,
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'paginas/admin_panel_fragment.html', context)
    else:
        return render(request, 'paginas/admin_panel.html', context)


@login_required(login_url='login')
def historial_completo(request):
    """Vista para mostrar el historial completo de acciones del sistema con paginación y filtros."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Obtener todas las acciones del historial
    acciones = HistorialAccion.objects.select_related('usuario').order_by('-fecha')
    
    # Filtros
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    tipo_modelo_filtro = request.GET.get('tipo_modelo', '').strip()
    accion_filtro = request.GET.get('accion', '').strip()
    usuario_filtro = request.GET.get('usuario', '').strip()
    
    # Aplicar filtros
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            acciones = acciones.filter(fecha__date__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            # Incluir todo el día hasta las 23:59:59
            fecha_hasta_obj = fecha_hasta_obj + timedelta(days=1)
            acciones = acciones.filter(fecha__date__lt=fecha_hasta_obj)
        except ValueError:
            pass
    
    if tipo_modelo_filtro:
        acciones = acciones.filter(tipo_modelo=tipo_modelo_filtro)
    
    if accion_filtro:
        acciones = acciones.filter(accion=accion_filtro)
    
    if usuario_filtro:
        try:
            usuario_id = int(usuario_filtro)
            acciones = acciones.filter(usuario_id=usuario_id)
        except ValueError:
            pass
    
    # Convertir acciones a formato de eventos para el template
    eventos = []
    for accion in acciones:
        timestamp = _normalize_timestamp(accion.fecha)
        if not timestamp:
            continue
        
        # Construir título según la acción
        if accion.accion == 'creado':
            titulo = f'{accion.get_tipo_modelo_display()} creado: {accion.nombre_objeto}'
        elif accion.accion == 'editado':
            titulo = f'{accion.get_tipo_modelo_display()} editado: {accion.nombre_objeto}'
        elif accion.accion == 'eliminado':
            titulo = f'{accion.get_tipo_modelo_display()} eliminado: {accion.nombre_objeto}'
        else:
            titulo = f'{accion.get_tipo_modelo_display()}: {accion.nombre_objeto}'
        
        # Construir descripción
        descripcion = accion.descripcion or f'Se {accion.get_accion_display().lower()} un {accion.get_tipo_modelo_display().lower()} en el sistema.'
        
        # Detalles adicionales
        detalles = []
        if accion.usuario:
            detalles.append(f'Usuario: {accion.usuario.get_full_name() or accion.usuario.username}')
        if accion.objeto_id:
            detalles.append(f'ID: {accion.objeto_id}')
        
        eventos.append({
            'timestamp': timestamp,
            'category': accion.categoria,
            'title': titulo,
            'description': descripcion,
            'author': accion.usuario.get_full_name() if accion.usuario else 'Sistema',
            'details': detalles,
            'icon': accion.icono,
            'accion': accion.accion,
            'tipo_modelo': accion.tipo_modelo,
        })
    
    # Paginación - 6 elementos por página
    paginator = Paginator(eventos, 6)
    page = request.GET.get('page', 1)
    
    try:
        eventos_paginados = paginator.page(page)
    except PageNotAnInteger:
        eventos_paginados = paginator.page(1)
    except EmptyPage:
        eventos_paginados = paginator.page(paginator.num_pages)
    
    # Obtener opciones para los filtros
    tipos_modelo = HistorialAccion.TipoModelo.choices
    acciones_choices = HistorialAccion.Accion.choices
    usuarios = User.objects.filter(acciones_realizadas__isnull=False).distinct().order_by('username')
    
    context = {
        'eventos': eventos_paginados,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'tipo_modelo_filtro': tipo_modelo_filtro,
        'accion_filtro': accion_filtro,
        'usuario_filtro': usuario_filtro,
        'tipos_modelo': tipos_modelo,
        'acciones_choices': acciones_choices,
        'usuarios': usuarios,
        'total_eventos': paginator.count,
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'paginas/historial_completo_fragment.html', context)
    else:
        return render(request, 'paginas/historial_completo.html', context)


# ========== SERVICIOS PÚBLICOS (SIN LOGIN) ==========

def servicios_publicos(request):
    """Vista pública para mostrar servicios ofrecidos por la clínica de forma informativa."""
    # Leer servicios desde la base de datos si existen (muestra solo activos)
    # Servicio ya importado a nivel de módulo
    qs = Servicio.objects.filter(activo=True).order_by('nombre')
    servicios_info = []
    for s in qs:
        servicios_info.append({
            'id': s.id,
            'nombre': s.nombre,
            'descripcion': s.descripcion or '',
            'precio': s.precio,
            'duracion_minutos': s.duracion_minutos,
            'imagen': s.imagen.url if s.imagen else None,
            'icono': 'fa-concierge-bell',
            'color': 'primary',
            'detalle': ''
        })

    # Si no hay servicios en BD, mostrar la lista informativa por defecto
    if not servicios_info:
        servicios_info = [
            {'id': 1, 'titulo': 'Rejuvenecimiento Facial', 'descripcion': 'Restaura la juventud de tu piel con nuestros tratamientos faciales avanzados. Utilizamos técnicas modernas para eliminar arrugas y líneas de expresión.', 'icono': 'fa-spa', 'color': 'primary', 'detalle': 'Con profesionales certificados', 'precio': 0, 'duracion_minutos': None},
            {'id': 2, 'titulo': 'Depilación Láser', 'descripcion': 'Elimina vello permanentemente con tecnología láser de última generación. Resultados duraderos, piel suave y sin irritación.', 'icono': 'fa-bolt', 'color': 'success', 'detalle': 'Tratamiento indoloro y efectivo', 'precio': 0, 'duracion_minutos': None},
            {'id': 3, 'titulo': 'Tratamientos Corporales', 'descripcion': 'Moldea y define tu figura con nuestros tratamientos corporales efectivos. Reduce medidas y mejora la elasticidad de tu piel.', 'icono': 'fa-heartbeat', 'color': 'danger', 'detalle': 'Resultados visibles en poco tiempo', 'precio': 0, 'duracion_minutos': None},
            {'id': 4, 'titulo': 'Aumento de Labios', 'descripcion': 'Potencia tu sonrisa con nuestros tratamientos de aumento de labios. Resultados naturales y proporcionales con materiales de calidad premium.', 'icono': 'fa-lips', 'color': 'info', 'detalle': 'Resultados naturales garantizados', 'precio': 0, 'duracion_minutos': None},
            {'id': 5, 'titulo': 'Tratamiento de Ojeras', 'descripcion': 'Elimina las ojeras y bolsas bajo los ojos. Recupera una mirada fresca y descansada con nuestros tratamientos especializados.', 'icono': 'fa-eye', 'color': 'warning', 'detalle': 'Rejuvenecimiento del contorno de ojos', 'precio': 0, 'duracion_minutos': None},
            {'id': 6, 'titulo': 'Peeling Químico', 'descripcion': 'Exfoliación profunda que renueva tu piel. Elimina manchas, cicatrices y mejora la textura general de tu rostro.', 'icono': 'fa-gem', 'color': 'secondary', 'detalle': 'Renovación celular efectiva', 'precio': 0, 'duracion_minutos': None},
        ]

    return render(request, 'servicios/publicos.html', {'servicios': servicios_info})


# ========== CRUD SERVICIOS REALIZADOS ==========

# ========== CRUD SERVICIOS OFRECIDOS (ADMIN) ==========

@login_required(login_url='login')
def servicios_ofrecidos_lista(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar servicios')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    # Servicio ya importado a nivel de módulo
    servicios = Servicio.objects.all().order_by('nombre')
    
    # Paginación - 6 elementos por página
    paginator = Paginator(servicios, 6)
    page = request.GET.get('page', 1)
    try:
        servicios = paginator.page(page)
    except PageNotAnInteger:
        servicios = paginator.page(1)
    except EmptyPage:
        servicios = paginator.page(paginator.num_pages)
    
    return render(request, 'servicios/ofrecidos_index.html', {'servicios': servicios})


@login_required(login_url='login')
def servicios_ofrecidos_crear(request):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar servicios')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    from .forms import ServicioForm
    if request.method == 'POST':
        form = ServicioForm(request.POST, request.FILES)
        if form.is_valid():
            servicio = form.save()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='creado',
                tipo_modelo='servicio',
                nombre_objeto=servicio.nombre,
                usuario=request.user,
                descripcion=f'Servicio creado con precio: ${servicio.precio}',
                objeto_id=servicio.id
            )
            messages.success(request, 'Servicio creado correctamente')
            return redirect('servicios_ofrecidos')
    else:
        form = ServicioForm()
    return render(request, 'servicios/ofrecidos_crear.html', {'formulario': form})


@login_required(login_url='login')
def servicios_ofrecidos_editar(request, id):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar servicios')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    # Servicio ya importado a nivel de módulo
    from .forms import ServicioForm
    try:
        servicio = Servicio.objects.get(id=id)
    except Servicio.DoesNotExist:
        messages.error(request, 'Servicio no encontrado')
        return redirect('servicios_ofrecidos')
    except Exception as e:
        messages.error(request, f'Error al cargar el servicio: {str(e)}')
        return redirect('servicios_ofrecidos')
    
    if request.method == 'POST':
        form = ServicioForm(request.POST, instance=servicio)
        if form.is_valid():
            servicio = form.save()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='editado',
                tipo_modelo='servicio',
                nombre_objeto=servicio.nombre,
                usuario=request.user,
                descripcion=f'Servicio actualizado',
                objeto_id=servicio.id
            )
            messages.success(request, 'Servicio actualizado correctamente')
            return redirect('servicios_ofrecidos')
    else:
        form = ServicioForm(instance=servicio)
    return render(request, 'servicios/ofrecidos_editar.html', {'formulario': form, 'servicio': servicio})


@login_required(login_url='login')
def servicios_ofrecidos_eliminar(request, id):
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar servicios')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    try:
        servicio = Servicio.objects.get(id=id)
    except Servicio.DoesNotExist:
        messages.error(request, 'Servicio no encontrado')
        return redirect('servicios_ofrecidos')
    except Exception as e:
        messages.error(request, f'Error al cargar el servicio: {str(e)}')
        return redirect('servicios_ofrecidos')
    
    try:
        nombre_servicio = servicio.nombre
        servicio_id = servicio.id
        servicio.delete()
        # Registrar acción en el historial
        registrar_accion_historial(
            accion='eliminado',
            tipo_modelo='servicio',
            nombre_objeto=nombre_servicio,
            usuario=request.user,
            descripcion=f'Servicio eliminado del sistema',
            objeto_id=servicio_id
        )
        messages.success(request, 'Servicio eliminado correctamente')
    except Exception as e:
        messages.error(request, f'Error al eliminar el servicio: {str(e)}')
    return redirect('servicios_ofrecidos')

@login_required(login_url='login')
def servicios_crear(request):
    # Solo administradores pueden crear servicios desde el panel
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')

    proveedores = Proveedores.objects.all()
    productos = Producto.objects.all()
    servicios = Servicio.objects.filter(activo=True)
    # Solo empleados con especialidades activas pueden aparecer en crear servicios
    empleados = Empleado.objects.filter(activo=True).annotate(
        num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
    ).filter(num_especialidades__gt=0).distinct().order_by('nombre')

    if request.method == 'POST':
        descripcion = request.POST.get('descripcion') or ''
        proveedor_id = request.POST.get('proveedor') or ''
        producto_id = request.POST.get('producto') or ''
        servicio_id = request.POST.get('servicio') or ''
        empleado_id = request.POST.get('empleado') or ''
        fecha_servicio = request.POST.get('fecha_servicio') or ''
        hora = request.POST.get('hora') or ''
        costo = request.POST.get('costo') or ''
        estado = request.POST.get('estado') or 'pendiente'
        
        # Obtener datos del cliente desde el formulario
        nombre_cliente = request.POST.get('nombre_cliente', '').strip()
        email_cliente = request.POST.get('email_cliente', '').strip()
        telefono_cliente = request.POST.get('telefono_cliente', '').strip()

        # Ya no se requiere descripción ni proveedor/producto obligatoriamente.
        # Si proveedor/producto vienen vacíos, se guardará la cita sin esos FKs (ahora son opcionales).

        # Resolver proveedor/producto sólo si vienen valores numéricos válidos
        proveedor = None
        if proveedor_id and proveedor_id.strip() != '':
            try:
                proveedor = Proveedores.objects.get(id=int(proveedor_id))
            except (Proveedores.DoesNotExist, ValueError):
                messages.error(request, 'Proveedor seleccionado no válido')
                return render(request, 'servicios/crear.html', {
                    'proveedores': proveedores,
                    'productos': productos,
                    'servicios': servicios,
                    'empleados': empleados,
                })

        producto = None
        if producto_id and str(producto_id).strip() != '':
            try:
                producto = Producto.objects.get(id=int(producto_id))
            except (Producto.DoesNotExist, ValueError):
                messages.error(request, 'Producto seleccionado no válido')
                return render(request, 'servicios/crear.html', {
                    'proveedores': proveedores,
                    'productos': productos,
                    'servicios': servicios,
                    'empleados': empleados,
                })

        # Resolver servicio catálogo si fue enviado
        servicio_obj = None
        if servicio_id and str(servicio_id).strip() != '':
            # Servicio ya importado a nivel de módulo
            try:
                servicio_obj = Servicio.objects.get(id=int(servicio_id))
            except (Servicio.DoesNotExist, ValueError):
                messages.error(request, 'Servicio seleccionado no válido')
                return render(request, 'servicios/crear.html', {
                    'proveedores': proveedores,
                    'productos': productos,
                    'servicios': servicios,
                    'empleados': empleados,
                })


        # Costo: validar número si fue entregado
        costo_val = None
        if costo and str(costo).strip() != '':
            try:
                costo_val = float(costo)
            except ValueError:
                messages.error(request, 'Costo inválido. Debe ser un número.')
                return render(request, 'servicios/crear.html', {
                    'proveedores': proveedores,
                    'productos': productos,
                    'servicios': servicios,
                    'empleados': empleados,
                })
        
        # Validación básica de campos obligatorios del formulario admin
        missing = []
        if not nombre_cliente or nombre_cliente.strip() == '':
            missing.append('nombre del cliente')
        if not servicio_id or servicio_id.strip() == '':
            missing.append('servicio')
        if not empleado_id or empleado_id.strip() == '':
            missing.append('estilista')
        if not fecha_servicio or fecha_servicio.strip() == '':
            missing.append('fecha')
        if not hora or hora.strip() == '':
            missing.append('hora')
        if missing:
            messages.error(request, 'Faltan datos por ingresar: ' + ', '.join(missing))
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })

        # Validar fecha: debe ser desde hoy hasta máximo 1 mes
        fecha_val = None
        if fecha_servicio and str(fecha_servicio).strip() != '':
            try:
                fecha_servicio_obj = datetime.strptime(fecha_servicio, '%Y-%m-%d').date()
                hoy = date.today()
                fecha_maxima = hoy + timedelta(days=30)  # 1 mes desde hoy
                
                if fecha_servicio_obj < hoy:
                    messages.error(request, 'La fecha de la cita no puede ser anterior a hoy.')
                    return render(request, 'servicios/crear.html', {
                        'proveedores': proveedores,
                        'productos': productos,
                        'servicios': servicios,
                        'empleados': empleados,
                    })
                
                if fecha_servicio_obj > fecha_maxima:
                    messages.error(request, 'La fecha de la cita no puede ser más de 1 mes en el futuro.')
                    return render(request, 'servicios/crear.html', {
                        'proveedores': proveedores,
                        'productos': productos,
                        'servicios': servicios,
                        'empleados': empleados,
                    })
                
                # Validar que no sea domingo
                dia_semana = fecha_servicio_obj.weekday()  # 0=Lunes, 6=Domingo
                if dia_semana == 6:
                    messages.error(request, 'Los domingos la clínica está cerrada. Por favor selecciona otro día.')
                    return render(request, 'servicios/crear.html', {
                        'proveedores': proveedores,
                        'productos': productos,
                        'servicios': servicios,
                        'empleados': empleados,
                    })
                
                # Validar hora: debe estar en horario de atención según el día de la semana
                if hora and str(hora).strip() != '':
                    try:
                        hora_obj = datetime.strptime(hora, '%H:%M').time()
                        
                        # Validar horario de atención según el día de la semana
                        es_valido, mensaje_error = validar_horario_atencion(fecha_servicio_obj, hora_obj)
                        if not es_valido:
                            messages.error(request, mensaje_error)
                            return render(request, 'servicios/crear.html', {
                                'proveedores': proveedores,
                                'productos': productos,
                                'servicios': servicios,
                                'empleados': empleados,
                            })
                        
                        # Si la fecha es hoy, validar que la hora sea posterior a la hora actual
                        if fecha_servicio_obj == hoy:
                            ahora = datetime.now()
                            hora_actual_num = ahora.hour
                            minuto_actual_num = ahora.minute
                            
                            # Redondear la hora actual al siguiente intervalo de 30 minutos
                            # Si está en :00 exacto, puede usar esa hora; si está en :30 exacto, puede usar esa hora
                            # Si está entre :01 y :30, debe usar :30; si está entre :31 y :59, debe usar la siguiente hora :00
                            if minuto_actual_num > 30:
                                hora_minima_hora = hora_actual_num + 1
                                hora_minima_minuto = 0
                            elif minuto_actual_num > 0:
                                hora_minima_hora = hora_actual_num
                                hora_minima_minuto = 30
                            else:
                                # Si está en :00 exacto, puede usar esa hora
                                hora_minima_hora = hora_actual_num
                                hora_minima_minuto = 0
                            
                            # Extraer hora y minuto de la hora seleccionada
                            hora_num = hora_obj.hour
                            minuto_num = hora_obj.minute
                            
                            # Crear objeto time para comparar
                            hora_minima_permitida = hora_minima_hora * 60 + hora_minima_minuto
                            hora_seleccionada_minutos = hora_num * 60 + minuto_num
                            
                            # Si la hora seleccionada es menor a la mínima permitida, rechazar
                            if hora_seleccionada_minutos < hora_minima_permitida:
                                hora_minima_str = f"{hora_minima_hora}:{str(hora_minima_minuto).zfill(2)}"
                                messages.error(request, f'Si la cita es para hoy, la hora debe ser posterior a la hora actual. La hora mínima permitida es {hora_minima_str}.')
                                return render(request, 'servicios/crear.html', {
                                    'proveedores': proveedores,
                                    'productos': productos,
                                    'servicios': servicios,
                                    'empleados': empleados,
                                })
                    except ValueError:
                        messages.error(request, 'Hora inválida. Formato correcto: HH:MM')
                        return render(request, 'servicios/crear.html', {
                            'proveedores': proveedores,
                            'productos': productos,
                            'servicios': servicios,
                            'empleados': empleados,
                        })
                
                fecha_val = fecha_servicio_obj
            except ValueError:
                messages.error(request, 'Fecha inválida. Formato correcto: YYYY-MM-DD')
                return render(request, 'servicios/crear.html', {
                    'proveedores': proveedores,
                    'productos': productos,
                    'servicios': servicios,
                    'empleados': empleados,
                })

        # Validar que los campos obligatorios estén presentes
        if fecha_val is None:
            messages.error(request, 'La fecha del servicio es obligatoria')
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })
        
        if servicio_obj is None:
            messages.error(request, 'Debe seleccionar un servicio')
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })
        
        if not empleado_id or str(empleado_id).strip() == '':
            messages.error(request, 'Debe seleccionar un estilista')
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })
        
        # Resolver estilista (empleado) - obligatorio
        estilista_obj = None
        try:
            estilista_obj = Empleado.objects.get(id=int(empleado_id))
            
            # Validar que el empleado tenga las especialidades requeridas del servicio
            if servicio_obj and servicio_obj.especialidades_requeridas.exists():
                especialidades_requeridas = servicio_obj.especialidades_requeridas.filter(activo=True)
                especialidades_empleado = estilista_obj.especialidades.filter(activo=True)
                tiene_especialidad = especialidades_requeridas.filter(id__in=especialidades_empleado.values_list('id', flat=True)).exists()
                
                if not tiene_especialidad:
                    messages.error(request, f'El empleado seleccionado no tiene las especialidades requeridas para realizar el servicio "{servicio_obj.nombre}".')
                    return render(request, 'servicios/crear.html', {
                        'proveedores': proveedores,
                        'productos': productos,
                        'servicios': servicios,
                        'empleados': empleados,
                    })
        except (Empleado.DoesNotExist, ValueError):
            messages.error(request, 'Estilista seleccionado no válido')
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })
        
        if estilista_obj is None:
            messages.error(request, 'No se pudo obtener el estilista seleccionado')
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })
        
        # Validar costo - debe ser Decimal
        from decimal import Decimal
        if costo_val is None:
            # Si no se proporciona costo, usar el precio del servicio
            if servicio_obj:
                costo_val = Decimal(str(servicio_obj.precio))
            else:
                costo_val = Decimal('0.00')
        else:
            # Asegurar que costo_val sea Decimal
            try:
                costo_val = Decimal(str(costo_val))
            except (ValueError, TypeError):
                costo_val = Decimal('0.00')
        
        servicio_kwargs = {
            'fecha_servicio': fecha_val,
            'hora': hora if hora and str(hora).strip() != '' else None,
            'costo': costo_val,
            'estado': estado,
            'nombre_cliente': nombre_cliente,
            'email_cliente': email_cliente,
            'telefono_cliente': telefono_cliente,
            'servicio': servicio_obj,
            'estilista': estilista_obj
        }
        if proveedor is not None:
            servicio_kwargs['proveedor'] = proveedor
        if producto is not None:
            servicio_kwargs['producto'] = producto

        # Validar que todos los campos requeridos estén presentes
        if not nombre_cliente or nombre_cliente.strip() == '':
            messages.error(request, 'El nombre del cliente es obligatorio')
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })
        
        if not email_cliente or email_cliente.strip() == '':
            messages.error(request, 'El email del cliente es obligatorio')
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })
        
        if not telefono_cliente or telefono_cliente.strip() == '':
            messages.error(request, 'El teléfono del cliente es obligatorio')
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })
        
        # Convertir hora string a objeto time si es necesario
        hora_obj_final = None
        if hora and str(hora).strip() != '':
            try:
                hora_obj_final = datetime.strptime(hora, '%H:%M').time()
            except (ValueError, TypeError):
                hora_obj_final = None
        
        servicio_kwargs['hora'] = hora_obj_final
        
        # Validar que no haya conflicto de horario con el mismo especialista
        if fecha_val and hora_obj_final and estilista_obj:
            cita_existente = ServicioRealizado.objects.filter(
                estilista=estilista_obj,
                fecha_servicio=fecha_val,
                hora=hora_obj_final,
                estado__in=['pendiente', 'en_progreso']  # Solo verificar citas activas
            ).first()
            
            if cita_existente:
                messages.error(request, f'El especialista {estilista_obj.nombre} ya tiene una cita agendada para el {fecha_val.strftime("%d/%m/%Y")} a las {hora_obj_final.strftime("%H:%M")}. Por favor selecciona otra fecha u hora.')
                return render(request, 'servicios/crear.html', {
                    'proveedores': proveedores,
                    'productos': productos,
                    'servicios': servicios,
                    'empleados': empleados,
                })
        
        try:
            servicio = ServicioRealizado(**servicio_kwargs)
            servicio.full_clean()  # Validar el modelo antes de guardar
            servicio.save()
            messages.success(request, 'Servicio creado exitosamente')
        except Exception as e:
            import traceback
            error_details = str(e)
            # Si es un error de validación de Django, mostrar los detalles
            if hasattr(e, 'error_dict'):
                error_messages = []
                for field, errors in e.error_dict.items():
                    for error in errors:
                        error_messages.append(f"{field}: {error}")
                error_details = "; ".join(error_messages)
            
            messages.error(request, f'Error al crear el servicio: {error_details}')
            # Log del error completo para debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error al crear servicio: {traceback.format_exc()}')
            
            return render(request, 'servicios/crear.html', {
                'proveedores': proveedores,
                'productos': productos,
                'servicios': servicios,
                'empleados': empleados,
                'clientes': clientes_activos
            })
        return redirect('admin_panel')
    
    return render(request, 'servicios/crear.html', {
        'proveedores': proveedores,
        'productos': productos,
        'servicios': servicios,
        'empleados': empleados,
        'clientes': clientes_activos
    })


def _preparar_contexto_agendar(empleados, servicios, admin_mode=False):
    """Función auxiliar para preparar el contexto completo para agendar.html"""
    import json
    
    # Preparar datos JSON para el frontend
    servicios_json = []
    for servicio in servicios:
        especialidades_ids = []
        if hasattr(servicio, 'especialidades_requeridas'):
            try:
                especialidades_ids = list(servicio.especialidades_requeridas.filter(activo=True).values_list('id', flat=True))
            except Exception:
                especialidades_ids = []
        servicios_json.append({
            'id': servicio.id,
            'nombre': servicio.nombre,
            'precio': str(servicio.precio),
            'descripcion': servicio.descripcion or '',
            'especialidades_ids': especialidades_ids
        })
    
    empleados_json = []
    for empleado in empleados:
        empleados_json.append({
            'id': empleado.id,
            'nombre': empleado.nombre + (' ' + empleado.apellido if empleado.apellido else ''),
            'especialidades_ids': list(empleado.especialidades.filter(activo=True).values_list('id', flat=True)),
            'especialidades': ', '.join([esp.nombre for esp in empleado.especialidades.filter(activo=True)[:3]])
        })
    
    return {
        'empleados': empleados,
        'servicios': servicios,
        'servicios_json': json.dumps(servicios_json),
        'empleados_json': json.dumps(empleados_json),
        'fecha_nacimiento_cliente': None,
        'ultimo_mes_descuento': '',
        'admin_mode': admin_mode
    }

@login_required(login_url='login')
def agendar_cita(request):
    """Vista para que un cliente autenticado agende una cita y elija un empleado."""
    if request.method == 'POST':
        # No se toma descripción libre del cliente; se usará el nombre del servicio seleccionado
        empleado_id = request.POST.get('empleado')
        servicio_id = request.POST.get('servicio')
        fecha_servicio = request.POST.get('fecha_servicio')
        hora = request.POST.get('hora')
        costo = request.POST.get('costo') or 0
        nombre_cliente_post = request.POST.get('nombre_cliente')
        email_cliente_post = request.POST.get('email_cliente')

        # Validación: campos obligatorios
        missing = []
        if not nombre_cliente_post or nombre_cliente_post.strip() == '':
            missing.append('nombre')
        if not email_cliente_post or email_cliente_post.strip() == '':
            missing.append('email')
        if not servicio_id or servicio_id.strip() == '':
            missing.append('servicio')
        if not empleado_id or empleado_id.strip() == '':
            missing.append('estilista')
        if not fecha_servicio or fecha_servicio.strip() == '':
            missing.append('fecha')
        if not hora or hora.strip() == '':
            missing.append('hora')

        if missing:
            messages.error(request, 'Faltan datos por ingresar: ' + ', '.join(missing))
            # Solo empleados con especialidades activas pueden aparecer en agendar cita
            empleados = Empleado.objects.filter(activo=True).annotate(
                num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
            ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
            servicios = Servicio.objects.filter(activo=True).order_by('nombre')
            return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, False))
        # Validación servidor: evitar pasar cadena vacía a DateField/hora
        if not fecha_servicio or fecha_servicio.strip() == '' or not hora or hora.strip() == '':
            messages.error(request, 'Debes seleccionar fecha y hora para la cita')
            # Re-renderizar el formulario con los mismos empleados/servicios para corregir
            # Solo empleados con especialidades activas pueden aparecer en agendar cita
            empleados = Empleado.objects.filter(activo=True).annotate(
                num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
            ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
            servicios = Servicio.objects.filter(activo=True).order_by('nombre')
            return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, False))
        
        # Validar fecha: debe ser desde hoy hasta máximo 1 mes
        if fecha_servicio and str(fecha_servicio).strip() != '':
            try:
                fecha_servicio_obj = datetime.strptime(fecha_servicio, '%Y-%m-%d').date()
                hoy = date.today()
                fecha_maxima = hoy + timedelta(days=30)  # 1 mes desde hoy
                
                if fecha_servicio_obj < hoy:
                    messages.error(request, 'La fecha de la cita no puede ser anterior a hoy.')
                    empleados = Empleado.objects.filter(activo=True).annotate(
                        num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                    ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                    servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                    cliente_prefill = None
                    try:
                        cliente_prefill = request.user.cliente
                    except Exception:
                        cliente_prefill = None
                    return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))
                
                if fecha_servicio_obj > fecha_maxima:
                    messages.error(request, 'La fecha de la cita no puede ser más de 1 mes en el futuro.')
                    empleados = Empleado.objects.filter(activo=True).annotate(
                        num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                    ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                    servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                    cliente_prefill = None
                    try:
                        cliente_prefill = request.user.cliente
                    except Exception:
                        cliente_prefill = None
                    return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))
                
                # Validar que no sea domingo
                dia_semana = fecha_servicio_obj.weekday()  # 0=Lunes, 6=Domingo
                if dia_semana == 6:
                    messages.error(request, 'Los domingos la clínica está cerrada. Por favor selecciona otro día.')
                    empleados = Empleado.objects.filter(activo=True).annotate(
                        num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                    ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                    servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                    cliente_prefill = None
                    try:
                        cliente_prefill = request.user.cliente
                    except Exception:
                        cliente_prefill = None
                    return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))
                
                # Validar hora: debe estar en horario de atención según el día de la semana
                if hora and str(hora).strip() != '':
                    try:
                        hora_obj = datetime.strptime(hora, '%H:%M').time()
                        
                        # Validar horario de atención según el día de la semana
                        es_valido, mensaje_error = validar_horario_atencion(fecha_servicio_obj, hora_obj)
                        if not es_valido:
                            messages.error(request, mensaje_error)
                            empleados = Empleado.objects.filter(activo=True).annotate(
                                num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                            ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                            servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                            cliente_prefill = None
                            try:
                                cliente_prefill = request.user.cliente
                            except Exception:
                                cliente_prefill = None
                            return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))
                            empleados = Empleado.objects.filter(activo=True).annotate(
                                num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                            ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                            servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                            cliente_prefill = None
                            try:
                                cliente_prefill = request.user.cliente
                            except Exception:
                                cliente_prefill = None
                            return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))
                        
                        # Si la fecha es hoy, validar que la hora sea posterior a la hora actual
                        if fecha_servicio_obj == hoy:
                            ahora = datetime.now()
                            hora_actual_num = ahora.hour
                            minuto_actual_num = ahora.minute
                            
                            # Extraer hora y minuto de la hora seleccionada
                            hora_num = hora_obj.hour
                            minuto_num = hora_obj.minute
                            
                            # Redondear la hora actual al siguiente intervalo de 30 minutos
                            if minuto_actual_num > 30:
                                hora_minima_hora = hora_actual_num + 1
                                hora_minima_minuto = 0
                            elif minuto_actual_num > 0:
                                hora_minima_hora = hora_actual_num
                                hora_minima_minuto = 30
                            else:
                                hora_minima_hora = hora_actual_num
                                hora_minima_minuto = 0
                            
                            # Crear objeto time para comparar
                            hora_minima_permitida = hora_minima_hora * 60 + hora_minima_minuto
                            hora_seleccionada_minutos = hora_num * 60 + minuto_num
                            
                            # Si la hora seleccionada es menor a la mínima permitida, rechazar
                            if hora_seleccionada_minutos < hora_minima_permitida:
                                hora_minima_str = f"{hora_minima_hora}:{str(hora_minima_minuto).zfill(2)}"
                                messages.error(request, f'Si la cita es para hoy, la hora debe ser posterior a la hora actual. La hora mínima permitida es {hora_minima_str}.')
                                empleados = Empleado.objects.filter(activo=True).annotate(
                                    num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                                ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                                servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                                cliente_prefill = None
                                try:
                                    cliente_prefill = request.user.cliente
                                except Exception:
                                    cliente_prefill = None
                                return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))
                    except ValueError:
                        messages.error(request, 'Hora inválida. Formato correcto: HH:MM')
                        empleados = Empleado.objects.filter(activo=True).annotate(
                            num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                        ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                        servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                        cliente_prefill = None
                        try:
                            cliente_prefill = request.user.cliente
                        except Exception:
                            cliente_prefill = None
                        return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))
            except ValueError:
                messages.error(request, 'Fecha inválida. Formato correcto: YYYY-MM-DD')
                empleados = Empleado.objects.filter(activo=True).annotate(
                    num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                cliente_prefill = None
                try:
                    cliente_prefill = request.user.cliente
                except Exception:
                    cliente_prefill = None
                return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))
        
        # Obtener datos del formulario
        nombre_cliente = request.POST.get('nombre_cliente')
        email_cliente = request.POST.get('email_cliente')
        telefono_cliente = request.POST.get('telefono_cliente')

        # Resolver empleado y validar especialidades requeridas
        empleado = None
        if empleado_id:
            try:
                empleado = Empleado.objects.get(id=empleado_id)
            except Empleado.DoesNotExist:
                empleado = None

        # servicio seleccionado del catálogo
        servicio_obj = None
        if servicio_id:
            # Servicio ya importado a nivel de módulo
            try:
                servicio_obj = Servicio.objects.get(id=servicio_id)
                # si hay, usar su precio por defecto
                costo = servicio_obj.precio
            except Servicio.DoesNotExist:
                servicio_obj = None
        
        # Validar que el empleado tenga las especialidades requeridas del servicio
        if empleado and servicio_obj and servicio_obj.especialidades_requeridas.exists():
            especialidades_requeridas = servicio_obj.especialidades_requeridas.filter(activo=True)
            especialidades_empleado = empleado.especialidades.filter(activo=True)
            tiene_especialidad = especialidades_requeridas.filter(id__in=especialidades_empleado.values_list('id', flat=True)).exists()
            
            if not tiene_especialidad:
                messages.error(request, f'El empleado seleccionado no tiene las especialidades requeridas para realizar el servicio "{servicio_obj.nombre}".')
                empleados = Empleado.objects.filter(activo=True).annotate(
                    num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                cliente_prefill = None
                try:
                    cliente_prefill = request.user.cliente
                except Exception:
                    cliente_prefill = None
                return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))

        # Validar que no haya conflicto de horario con el mismo especialista
        if empleado and fecha_servicio and hora:
            try:
                fecha_servicio_obj = datetime.strptime(fecha_servicio, '%Y-%m-%d').date()
                hora_obj = datetime.strptime(hora, '%H:%M').time()
                
                cita_existente = ServicioRealizado.objects.filter(
                    estilista=empleado,
                    fecha_servicio=fecha_servicio_obj,
                    hora=hora_obj,
                    estado__in=['pendiente', 'en_progreso']  # Solo verificar citas activas
                ).first()
                
                if cita_existente:
                    messages.error(request, f'El especialista {empleado.nombre} ya tiene una cita agendada para el {fecha_servicio_obj.strftime("%d/%m/%Y")} a las {hora_obj.strftime("%H:%M")}. Por favor selecciona otra fecha u hora.')
                    empleados = Empleado.objects.filter(activo=True).annotate(
                        num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                    ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                    servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                    cliente_prefill = None
                    try:
                        cliente_prefill = request.user.cliente
                    except Exception:
                        cliente_prefill = None
                    return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, cliente_prefill, False))
            except (ValueError, TypeError):
                pass  # Si hay error al parsear, continuar (ya se validó antes)
        
        # Crear servicio con proveedor/producto omitidos para dejar que el modelo aplique
        # su valor por defecto (evita asignar explícitamente None a FK no nulos)
        servicio_kwargs = {
            'fecha_servicio': fecha_servicio,
            'hora': hora,
            'costo': costo,
            'estado': 'pendiente',
            'nombre_cliente': nombre_cliente,
            'email_cliente': email_cliente,
            'telefono_cliente': telefono_cliente,
            'estilista': empleado,
            'servicio': servicio_obj
        }
        try:
            servicio = ServicioRealizado(**servicio_kwargs)
            # Intentar guardar y capturar errores de base de datos (p. ej. migraciones faltantes)
            servicio.save()
        except Exception as e:
            from django.db import OperationalError
            if isinstance(e, OperationalError) or 'no such column' in str(e).lower() or 'no such table' in str(e).lower():
                messages.error(request, 'Error de base de datos: parece faltar una migración. Ejecuta `python manage.py makemigrations` y `python manage.py migrate` y vuelve a intentar.')
                # Solo empleados con especialidades activas pueden aparecer en agendar cita
                empleados = Empleado.objects.filter(activo=True).annotate(
                    num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
                ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
                servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, False))
            # re-raise unexpected exceptions
            raise
        messages.success(request, 'Cita agendada correctamente. Nos contactaremos contigo pronto.')
        return redirect('inicio')

    # GET: mostrar formulario con empleados disponibles
    # Solo empleados con especialidades activas pueden aparecer en agendar cita
    empleados = Empleado.objects.filter(activo=True).annotate(
        num_especialidades=Count('especialidades', filter=Q(especialidades__activo=True))
    ).filter(num_especialidades__gt=0).distinct().order_by('nombre')
    # Pasar servicios activos del catálogo
    servicios = Servicio.objects.filter(activo=True).prefetch_related('especialidades_requeridas').order_by('nombre')
    
    return render(request, 'servicios/agendar.html', _preparar_contexto_agendar(empleados, servicios, False))


@login_required(login_url='login')
def servicios_editar(request, id):
    try:
        servicio = ServicioRealizado.objects.get(id=id)
    except ServicioRealizado.DoesNotExist:
        messages.error(request, 'Servicio no encontrado')
        return redirect('admin_panel')
    except Exception as e:
        messages.error(request, f'Error al cargar el servicio: {str(e)}')
        return redirect('admin_panel')

    # Permitir editar solo a staff (admin)
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')

    if request.method == 'POST':
        proveedor_id = request.POST.get('proveedor')
        producto_id = request.POST.get('producto')
        servicio_id = request.POST.get('servicio')
        fecha_post = request.POST.get('fecha_servicio')
        hora_post = request.POST.get('hora')
        estado_post = request.POST.get('estado')
        nombre_cliente = request.POST.get('nombre_cliente')
        email_cliente = request.POST.get('email_cliente')
        telefono_cliente = request.POST.get('telefono_cliente')
        empleado_id = request.POST.get('empleado')

        # Validación obligatoria
        missing = []
        if not nombre_cliente or nombre_cliente.strip() == '':
            missing.append('nombre')
        if not email_cliente or email_cliente.strip() == '':
            missing.append('email')
        if not servicio_id or servicio_id.strip() == '':
            missing.append('servicio')
        if not empleado_id or empleado_id.strip() == '':
            missing.append('estilista')
        if not fecha_post or fecha_post.strip() == '':
            missing.append('fecha')
        if not hora_post or hora_post.strip() == '':
            missing.append('hora')
        if missing:
            messages.error(request, 'Faltan datos por ingresar: ' + ', '.join(missing))
            # Obtener empleados activos, pero incluir el empleado actual si existe
            empleados = Empleado.objects.filter(activo=True).order_by('nombre')
            if servicio.estilista and servicio.estilista not in empleados:
                empleados = list(empleados) + [servicio.estilista]
            servicios = Servicio.objects.filter(activo=True).order_by('nombre')
            return render(request, 'servicios/editar.html', {
                'servicio': servicio,
                'empleados': empleados,
                'servicios': servicios,
                'admin_mode': True
            })

        # Actualizar campos
        if proveedor_id and proveedor_id.strip() != '':
            try:
                servicio.proveedor = Proveedores.objects.get(id=proveedor_id)
            except (Proveedores.DoesNotExist, ValueError):
                messages.error(request, 'Proveedor seleccionado no válido')
        # If no proveedor_id provided, keep the existing proveedor (ahora opcional)
        if producto_id and str(producto_id).strip() != '':
            try:
                servicio.producto = Producto.objects.get(id=producto_id)
            except (Producto.DoesNotExist, ValueError):
                messages.error(request, 'Producto seleccionado no válido')
        # If no producto_id provided, keep the existing producto (ahora opcional)
        # Convertir fecha y hora antes de validar
        fecha_servicio_obj_editar = None
        hora_obj_editar = None
        if fecha_post and str(fecha_post).strip() != '':
            try:
                fecha_servicio_obj_editar = datetime.strptime(fecha_post, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                messages.error(request, 'Formato de fecha inválido')
                empleados = Empleado.objects.filter(activo=True).order_by('nombre')
                if servicio.estilista and servicio.estilista not in empleados:
                    empleados = list(empleados) + [servicio.estilista]
                servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                return render(request, 'servicios/editar.html', {
                    'servicio': servicio,
                    'empleados': empleados,
                    'servicios': servicios,
                    'admin_mode': True
                })
        
        if hora_post and str(hora_post).strip() != '':
            try:
                hora_obj_editar = datetime.strptime(hora_post, '%H:%M').time()
            except (ValueError, TypeError):
                # Si hay error, intentar parsear otros formatos o mantener el valor actual
                try:
                    hora_obj_editar = datetime.strptime(hora_post, '%H:%M:%S').time()
                except (ValueError, TypeError):
                    messages.error(request, 'Formato de hora inválido')
                    empleados = Empleado.objects.filter(activo=True).order_by('nombre')
                    if servicio.estilista and servicio.estilista not in empleados:
                        empleados = list(empleados) + [servicio.estilista]
                    servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                    return render(request, 'servicios/editar.html', {
                        'servicio': servicio,
                        'empleados': empleados,
                        'servicios': servicios,
                        'admin_mode': True
                    })
        
        # Validar que no haya conflicto de horario con el mismo especialista (excluyendo la cita actual)
        if fecha_servicio_obj_editar and hora_obj_editar and empleado_id:
            try:
                empleado_editar = Empleado.objects.get(id=int(empleado_id))
                cita_existente = ServicioRealizado.objects.filter(
                    estilista=empleado_editar,
                    fecha_servicio=fecha_servicio_obj_editar,
                    hora=hora_obj_editar,
                    estado__in=['pendiente', 'en_progreso']  # Solo verificar citas activas
                ).exclude(id=servicio.id).first()  # Excluir la cita que se está editando
                
                if cita_existente:
                    messages.error(request, f'El especialista {empleado_editar.nombre} ya tiene una cita agendada para el {fecha_servicio_obj_editar.strftime("%d/%m/%Y")} a las {hora_obj_editar.strftime("%H:%M")}. Por favor selecciona otra fecha u hora.')
                    empleados = Empleado.objects.filter(activo=True).order_by('nombre')
                    if servicio.estilista and servicio.estilista not in empleados:
                        empleados = list(empleados) + [servicio.estilista]
                    servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                    return render(request, 'servicios/editar.html', {
                        'servicio': servicio,
                        'empleados': empleados,
                        'servicios': servicios,
                        'admin_mode': True
                    })
            except (Empleado.DoesNotExist, ValueError):
                pass  # Si hay error, continuar
        
        servicio.fecha_servicio = fecha_servicio_obj_editar if fecha_servicio_obj_editar else fecha_post
        servicio.hora = hora_obj_editar
        servicio.estado = estado_post
        servicio.nombre_cliente = nombre_cliente
        servicio.email_cliente = email_cliente
        servicio.telefono_cliente = telefono_cliente
        
        # Actualizar empleado (estilista) - OBLIGATORIO
        if empleado_id and empleado_id.strip() != '':
            try:
                empleado = Empleado.objects.get(id=int(empleado_id))
                servicio.estilista = empleado
            except (Empleado.DoesNotExist, ValueError):
                messages.error(request, 'Empleado seleccionado no válido')
                empleados = Empleado.objects.filter(activo=True).order_by('nombre')
                if servicio.estilista and servicio.estilista not in empleados:
                    empleados = list(empleados) + [servicio.estilista]
                servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                return render(request, 'servicios/editar.html', {
                    'servicio': servicio,
                    'empleados': empleados,
                    'servicios': servicios,
                    'admin_mode': True
                })
        else:
            # Si no se proporciona empleado_id, mantener el actual
            pass
        
        # Actualizar servicio y costo
        if servicio_id:
            try:
                servicio_obj = Servicio.objects.get(id=servicio_id)
                servicio.servicio = servicio_obj
                servicio.costo = servicio_obj.precio
            except Servicio.DoesNotExist:
                messages.error(request, 'Servicio seleccionado no válido')
                empleados = Empleado.objects.filter(activo=True).order_by('nombre')
                if servicio.estilista and servicio.estilista not in empleados:
                    empleados = list(empleados) + [servicio.estilista]
                servicios = Servicio.objects.filter(activo=True).order_by('nombre')
                return render(request, 'servicios/editar.html', {
                    'servicio': servicio,
                    'empleados': empleados,
                    'servicios': servicios,
                    'admin_mode': True
                })
        
        try:
            servicio.save()
            messages.success(request, 'Servicio actualizado exitosamente')
        except Exception as e:
            messages.error(request, f'Error al actualizar el servicio: {str(e)}')
        return redirect('admin_panel')

    # GET: Obtener empleados activos, pero incluir el empleado actual si existe
    empleados = Empleado.objects.filter(activo=True).order_by('nombre')
    # Si el empleado actual no está en la lista (porque está inactivo o no cumple filtros), agregarlo
    if servicio.estilista and servicio.estilista not in empleados:
        empleados = list(empleados) + [servicio.estilista]
    
    servicios = Servicio.objects.filter(activo=True).order_by('nombre')
    # Si el servicio actual no está activo, agregarlo a la lista
    if servicio.servicio and servicio.servicio not in servicios:
        servicios = list(servicios) + [servicio.servicio]
    
    clientes = Cliente.objects.all().order_by('nombre')
    return render(request, 'servicios/editar.html', {
        'servicio': servicio,
        'empleados': empleados,
        'servicios': servicios,
        'clientes': clientes,
        'admin_mode': True
    })

@login_required(login_url='login')
def servicios_eliminar(request, id):
    # Solo administradores pueden eliminar
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')

    try:
        servicio = ServicioRealizado.objects.get(id=id)
    except ServicioRealizado.DoesNotExist:
        messages.error(request, 'Servicio no encontrado')
        return redirect('admin_panel')
    except Exception as e:
        messages.error(request, f'Error al cargar el servicio: {str(e)}')
        return redirect('admin_panel')
    
    try:
        servicio.delete()
        messages.success(request, 'Servicio eliminado exitosamente')
    except Exception as e:
        messages.error(request, f'Error al eliminar el servicio: {str(e)}')
    return redirect('servicios_historial')


@login_required(login_url='login')
def servicios_marcar_completado(request, id):
    """Marca una cita como 'completado' (solo staff)."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')

    try:
        servicio = ServicioRealizado.objects.get(id=id)
    except ServicioRealizado.DoesNotExist:
        messages.error(request, 'Cita no encontrada')
        return redirect('admin_panel')

    try:
        servicio.estado = 'completado'
        servicio.save()
        messages.success(request, f'Cita {servicio.id} marcada como completada')
    except Exception as e:
        messages.error(request, f'Error al marcar la cita como completada: {str(e)}')
    return redirect('servicios_historial')


@require_http_methods(["GET"])
def obtener_horas_ocupadas(request):
    """Vista AJAX para obtener las horas ocupadas de un empleado en una fecha específica."""
    empleado_id = request.GET.get('empleado_id', '').strip()
    fecha_str = request.GET.get('fecha', '').strip()
    
    if not empleado_id or not fecha_str:
        return JsonResponse({'horas_ocupadas': []})
    
    try:
        empleado = Empleado.objects.get(id=int(empleado_id))
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        # Buscar citas del empleado en esa fecha con estado pendiente o en_progreso
        citas_ocupadas = ServicioRealizado.objects.filter(
            estilista=empleado,
            fecha_servicio=fecha_obj,
            estado__in=['pendiente', 'en_progreso']
        )
        
        # Extraer las horas ocupadas en formato 'HH:MM'
        horas_ocupadas = []
        for cita in citas_ocupadas:
            if cita.hora:
                hora_str = cita.hora.strftime('%H:%M')
                horas_ocupadas.append(hora_str)
        
        return JsonResponse({'horas_ocupadas': horas_ocupadas})
    except (Empleado.DoesNotExist, ValueError, TypeError) as e:
        return JsonResponse({'horas_ocupadas': [], 'error': str(e)})
    except Exception as e:
        return JsonResponse({'horas_ocupadas': [], 'error': str(e)})


@login_required(login_url='login')
def productos_proveedor_ajax(request):
    """Vista AJAX para obtener productos de un proveedor"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    
    proveedor_id = request.GET.get('proveedor_id')
    if not proveedor_id:
        return JsonResponse({'error': 'Proveedor ID requerido'}, status=400)
    
    try:
        productos = ProductoProveedor.objects.filter(
            proveedor_id=proveedor_id,
            activo=True
        ).order_by('nombre')
        
        productos_data = [{
            'id': p.id,
            'nombre': p.nombre,
            'descripcion': p.descripcion or '',
            'precio_unitario': float(p.precio_unitario) if p.precio_unitario else None,
            'precio_compra_actual': float(p.precio_compra_actual) if p.precio_compra_actual else None,
            'unidad_medida': p.unidad_medida or '',
            'codigo_producto': p.codigo_producto or '',
            'producto_id': p.producto.id if p.producto else None,
        } for p in productos]
        
        return JsonResponse({'productos': productos_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='login')
def producto_precio_ajax(request):
    """Vista AJAX para obtener precio de un producto propio"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    
    producto_id = request.GET.get('producto_id')
    if not producto_id:
        return JsonResponse({'error': 'Producto ID requerido'}, status=400)
    
    try:
        producto = Producto.objects.get(id=producto_id)
        return JsonResponse({
            'precio': float(producto.precio),
            'nombre': producto.nombre,
            'stock': producto.cantidad
        })
    except Producto.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='login')
def servicios_historial(request):
    """Vista para mostrar el historial de servicios completados (ventas)."""
    # Solo staff puede ver el historial
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        # El recepcionista puede ver el historial si tiene permiso de agendar o ver clientes
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo:
                puede_acceder = empleado.cargo.puede_agendar or empleado.cargo.puede_ver_clientes
                if not puede_acceder:
                    messages.error(request, 'No tienes permiso para ver el historial de servicios')
                    return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    # Filtrar solo servicios completados
    servicios = ServicioRealizado.objects.filter(estado='completado')
    
    # Filtros por rango de fechas
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            servicios = servicios.filter(fecha_servicio__gte=fecha_desde_obj)
        except ValueError:
            pass  # Si la fecha es inválida, ignorar el filtro
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            # Incluir todo el día hasta las 23:59:59
            fecha_hasta_obj = fecha_hasta_obj + timedelta(days=1)
            servicios = servicios.filter(fecha_servicio__lt=fecha_hasta_obj)
        except ValueError:
            pass  # Si la fecha es inválida, ignorar el filtro
    
    # Filtro por servicio
    servicio_id = request.GET.get('servicio_id')
    if servicio_id:
        try:
            servicios = servicios.filter(servicio_id=int(servicio_id))
        except ValueError:
            pass
    
    # Filtro por empleado (estilista)
    empleado_id = request.GET.get('empleado_id')
    if empleado_id:
        try:
            servicios = servicios.filter(estilista_id=int(empleado_id))
        except ValueError:
            pass
    
    servicios = servicios.order_by('-fecha_servicio', '-hora')
    
    # Obtener todos los servicios disponibles para el selector
    servicios_disponibles = Servicio.objects.filter(activo=True).order_by('nombre')
    
    # Obtener todos los empleados para el selector
    empleados_disponibles = Empleado.objects.filter(activo=True).order_by('nombre')
    
    # Estadísticas
    total_servicios = servicios.count()
    total_ingresos = sum(servicio.costo for servicio in servicios)
    
    context = {
        'servicios': servicios,
        'total_servicios': total_servicios,
        'total_ingresos': total_ingresos,
        'fecha_desde': fecha_desde or '',
        'fecha_hasta': fecha_hasta or '',
        'servicios_disponibles': servicios_disponibles,
        'empleados_disponibles': empleados_disponibles,
        'servicio_id_seleccionado': servicio_id or '',
        'empleado_id_seleccionado': empleado_id or ''
    }
    return render(request, 'servicios/historial.html', context)


# ========== GESTIÓN DE EXISTENCIAS - ENTRADAS ==========

@login_required(login_url='login')
def entradas_lista(request):
    """Lista de entradas de inventario"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    entradas = EntradaInventario.objects.all().order_by('-fecha_entrada')
    
    # Filtros
    producto_filtro = request.GET.get('producto', '').strip()
    proveedor_filtro = request.GET.get('proveedor', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    
    if producto_filtro:
        entradas = entradas.filter(producto__nombre__icontains=producto_filtro)
    
    if proveedor_filtro:
        entradas = entradas.filter(proveedor__nombre__icontains=proveedor_filtro)
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            entradas = entradas.filter(fecha_entrada__date__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            fecha_hasta_obj = fecha_hasta_obj + timedelta(days=1)
            entradas = entradas.filter(fecha_entrada__date__lt=fecha_hasta_obj)
        except ValueError:
            pass
    
    # Calcular totales antes de paginar (de todos los resultados)
    total_entradas = entradas.count()
    total_cantidad = sum(entrada.cantidad for entrada in entradas)
    total_valor = sum(float(entrada.cantidad * entrada.precio_unitario) for entrada in entradas)
    
    # Paginación - 6 elementos por página
    paginator = Paginator(entradas, 6)
    page = request.GET.get('page', 1)
    try:
        entradas = paginator.page(page)
    except PageNotAnInteger:
        entradas = paginator.page(1)
    except EmptyPage:
        entradas = paginator.page(paginator.num_pages)
    
    # Agregar total calculado a cada entrada para el template
    for entrada in entradas:
        entrada.total = float(entrada.cantidad * entrada.precio_unitario)
    
    context = {
        'entradas': entradas,
        'total_entradas': total_entradas,
        'total_cantidad': total_cantidad,
        'total_valor': total_valor,
        'producto_filtro': producto_filtro,
        'proveedor_filtro': proveedor_filtro,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'entradas/lista_fragment.html', context)
    else:
        return render(request, 'entradas/lista.html', context)


@login_required(login_url='login')
def entradas_crear(request):
    """Crear nueva entrada de inventario"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    if request.method == 'POST':
        post_data = request.POST.copy()
        
        # Verificar si el producto viene con formato "pp_{id}" (ProductoProveedor sin Producto)
        producto_id = post_data.get('producto', '').strip()
        if producto_id.startswith('pp_'):
            # Extraer el ID del ProductoProveedor
            producto_proveedor_id = producto_id.replace('pp_', '')
            try:
                from .models import ProductoProveedor, Producto
                producto_proveedor = ProductoProveedor.objects.get(id=producto_proveedor_id, activo=True)
                
                # Verificar si ya existe un producto en el inventario para este ProductoProveedor
                producto_existente = Producto.objects.filter(
                    producto_proveedor=producto_proveedor,
                    tipo_producto='proveedor',
                    activo=True
                ).first()
                
                if producto_existente:
                    # Si ya existe, usar ese producto
                    post_data['producto'] = producto_existente.id
                else:
                    # Crear un nuevo producto en el inventario para este ProductoProveedor
                    nuevo_producto = Producto.objects.create(
                        nombre=producto_proveedor.nombre,
                        tipo_producto='proveedor',
                        producto_proveedor=producto_proveedor,
                        cantidad=0,  # Se calculará desde las entradas
                        precio=0,  # Se puede actualizar después
                        stock_minimo=10,
                        costo_promedio_actual=producto_proveedor.precio_compra_actual or producto_proveedor.precio_unitario or 0,
                        descripcion=producto_proveedor.descripcion or '',
                        unidad_medida=producto_proveedor.unidad_medida or '',
                        proveedor_habitual=producto_proveedor.proveedor,
                        activo=True,
                        usuario_creacion=request.user
                    )
                    
                    # Asociar el ProductoProveedor con el nuevo Producto
                    producto_proveedor.producto = nuevo_producto
                    producto_proveedor.save(update_fields=['producto'])
                    
                    post_data['producto'] = nuevo_producto.id
                    messages.info(request, f'Se creó automáticamente el producto "{nuevo_producto.nombre}" en el inventario')
            except ProductoProveedor.DoesNotExist:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'producto': ['Producto de proveedor no encontrado']}}, status=400)
                messages.error(request, 'Producto de proveedor no encontrado')
                form = EntradaInventarioForm(post_data)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return render(request, 'entradas/crear_fragment.html', {'form': form})
                return render(request, 'entradas/crear.html', {'form': form})
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Error al crear producto automáticamente: {str(e)}', exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'__all__': [f'Error al crear producto: {str(e)}']}}, status=400)
                messages.error(request, f'Error al crear producto: {str(e)}')
                form = EntradaInventarioForm(post_data)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return render(request, 'entradas/crear_fragment.html', {'form': form})
                return render(request, 'entradas/crear.html', {'form': form})
        
        form = EntradaInventarioForm(post_data)
        if form.is_valid():
            entrada = form.save(commit=False)
            entrada.usuario_registro = request.user
            entrada.save()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='creado',
                tipo_modelo='entrada_inventario',
                nombre_objeto=f'Entrada: {entrada.cantidad} × {entrada.producto.nombre}',
                usuario=request.user,
                descripcion=f'Entrada de {entrada.cantidad} unidades de {entrada.producto.nombre}',
                objeto_id=entrada.id
            )
            messages.success(request, 'Entrada de inventario registrada exitosamente')
            # Si es AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Entrada registrada exitosamente'})
            return redirect('entradas_lista')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = EntradaInventarioForm()
    
    # Si es AJAX GET, devolver fragmento
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'entradas/crear_fragment.html', {'form': form})
    
    return render(request, 'entradas/crear.html', {'form': form})


@login_required(login_url='login')
def entradas_editar(request, id):
    """Editar entrada de inventario"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        entrada = EntradaInventario.objects.get(id=id)
    except EntradaInventario.DoesNotExist:
        messages.error(request, 'Entrada no encontrada')
        return redirect('entradas_lista')
    
    # Guardar valores originales para ajustar stock
    cantidad_original = entrada.cantidad
    
    if request.method == 'POST':
        form = EntradaInventarioForm(request.POST, instance=entrada)
        if form.is_valid():
            producto = entrada.producto
            form.save()
            
            # Si es un producto de proveedor, recalcular la cantidad desde todas las entradas
            if producto.tipo_producto == 'proveedor':
                cantidad_calculada = producto.calcular_cantidad_desde_entradas()
                producto.cantidad = cantidad_calculada
                producto.save(update_fields=['cantidad'])
            else:
                # Para productos propios, ajustar stock: restar cantidad original y sumar nueva cantidad
                producto.cantidad -= cantidad_original
                producto.cantidad += form.cleaned_data['cantidad']
                producto.save(update_fields=['cantidad'])
            
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='editado',
                tipo_modelo='entrada_inventario',
                nombre_objeto=f'Entrada: {entrada.cantidad} × {entrada.producto.nombre}',
                usuario=request.user,
                descripcion=f'Entrada actualizada. Cantidad: {entrada.cantidad} unidades',
                objeto_id=entrada.id
            )
            
            messages.success(request, 'Entrada actualizada exitosamente')
            return redirect('entradas_lista')
    else:
        form = EntradaInventarioForm(instance=entrada)
    
    return render(request, 'entradas/editar.html', {'form': form, 'entrada': entrada})


@login_required(login_url='login')
def entradas_eliminar(request, id):
    """Eliminar entrada de inventario"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        entrada = EntradaInventario.objects.get(id=id)
    except EntradaInventario.DoesNotExist:
        messages.error(request, 'Entrada no encontrada')
        return redirect('entradas_lista')
    
    if request.method == 'POST':
        producto = entrada.producto
        cantidad_eliminada = entrada.cantidad
        nombre_entrada = f'Entrada: {cantidad_eliminada} × {producto.nombre}'
        entrada_id = entrada.id
        entrada.delete()
        
        # Registrar acción en el historial
        registrar_accion_historial(
            accion='eliminado',
            tipo_modelo='entrada_inventario',
            nombre_objeto=nombre_entrada,
            usuario=request.user,
            descripcion=f'Entrada eliminada del sistema',
            objeto_id=entrada_id
        )
        
        # Si es un producto de proveedor, recalcular la cantidad desde todas las entradas
        if producto.tipo_producto == 'proveedor':
            cantidad_calculada = producto.calcular_cantidad_desde_entradas()
            producto.cantidad = cantidad_calculada
            producto.save(update_fields=['cantidad'])
        else:
            # Para productos propios, restar la cantidad de la entrada
            producto.cantidad -= cantidad_eliminada
            producto.save(update_fields=['cantidad'])
        
        messages.success(request, 'Entrada eliminada exitosamente')
        return redirect('entradas_lista')
    
    return render(request, 'entradas/eliminar_confirm.html', {'entrada': entrada})


@login_required(login_url='login')
def salidas_lista(request):
    """Lista de salidas de inventario (compras/facturas)"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Reutilizar la vista de compras_lista pero con otro template
    compras = Compras.objects.all()
    
    # Filtros por rango de fechas
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            compras = compras.filter(fecha_compra__date__gte=fecha_desde_obj)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            fecha_hasta_obj = fecha_hasta_obj + timedelta(days=1)
            compras = compras.filter(fecha_compra__date__lt=fecha_hasta_obj)
        except ValueError:
            pass
    
    compras = compras.order_by('-fecha_compra')
    
    # Calcular totales antes de paginar
    total_compras = compras.count()
    compras_list = list(compras)
    for compra in compras_list:
        compra.total = compra.cantidad * compra.precio_unitario
    total_ingresos = sum(compra.total for compra in compras_list)
    
    # Paginación - 6 elementos por página
    paginator = Paginator(compras, 6)
    page = request.GET.get('page', 1)
    try:
        compras = paginator.page(page)
    except PageNotAnInteger:
        compras = paginator.page(1)
    except EmptyPage:
        compras = paginator.page(paginator.num_pages)
    
    # Calcular total por compra para la página actual
    for compra in compras:
        compra.total = compra.cantidad * compra.precio_unitario
    
    context = {
        'compras': compras,
        'total_compras': total_compras,
        'total_ingresos': total_ingresos,
        'fecha_desde': fecha_desde or '',
        'fecha_hasta': fecha_hasta or ''
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'salidas/lista_fragment.html', context)
    else:
        return render(request, 'salidas/lista.html', context)


# ========== GESTIÓN DE SOLICITUDES DE COMPRA ==========

@login_required(login_url='login')
def solicitudes_compra_lista(request):
    """Lista de solicitudes de compra"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    solicitudes = SolicitudCompra.objects.all().order_by('-fecha_solicitud')
    
    # Filtros
    estado_filtro = request.GET.get('estado', '').strip()
    producto_filtro = request.GET.get('producto', '').strip()
    proveedor_filtro = request.GET.get('proveedor', '').strip()
    
    if estado_filtro:
        solicitudes = solicitudes.filter(estado=estado_filtro)
    
    if producto_filtro:
        solicitudes = solicitudes.filter(producto__nombre__icontains=producto_filtro)
    
    if proveedor_filtro:
        solicitudes = solicitudes.filter(proveedor__nombre__icontains=proveedor_filtro)
    
    # Estadísticas (antes de paginar)
    total_solicitudes = solicitudes.count()
    solicitudes_borrador = solicitudes.filter(estado='borrador').count()
    solicitudes_pendientes = solicitudes.filter(estado__in=['enviada', 'aceptada', 'en_proceso']).count()
    solicitudes_completadas = solicitudes.filter(estado='completada').count()
    costo_total_pendiente = sum(float(s.costo_total) for s in solicitudes.filter(estado__in=['aceptada', 'en_proceso']))
    
    # Paginación - 6 elementos por página
    paginator = Paginator(solicitudes, 6)
    page = request.GET.get('page', 1)
    try:
        solicitudes = paginator.page(page)
    except PageNotAnInteger:
        solicitudes = paginator.page(1)
    except EmptyPage:
        solicitudes = paginator.page(paginator.num_pages)
    
    context = {
        'solicitudes': solicitudes,
        'total_solicitudes': total_solicitudes,
        'solicitudes_borrador': solicitudes_borrador,
        'solicitudes_pendientes': solicitudes_pendientes,
        'solicitudes_completadas': solicitudes_completadas,
        'costo_total_pendiente': costo_total_pendiente,
        'estado_filtro': estado_filtro,
        'producto_filtro': producto_filtro,
        'proveedor_filtro': proveedor_filtro,
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'solicitudes/lista_fragment.html', context)
    else:
        return render(request, 'solicitudes/lista.html', context)


@login_required(login_url='login')
def solicitudes_compra_crear(request, producto_id=None):
    """Crear nueva solicitud de compra"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    if request.method == 'POST':
        form = SolicitudCompraForm(request.POST)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.usuario_solicitante = request.user
            solicitud.estado = 'borrador'
            solicitud.save()
            messages.success(request, 'Solicitud de compra creada exitosamente')
            # Si es AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Solicitud creada exitosamente'})
            return redirect('solicitudes_compra_lista')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = SolicitudCompraForm()
        # Si se pasa producto_id, precargar datos
        if producto_id:
            try:
                producto = Producto.objects.get(id=producto_id)
                form.fields['producto'].initial = producto.id
                # Precargar proveedor habitual
                if producto.proveedor_habitual:
                    form.fields['proveedor'].initial = producto.proveedor_habitual.id
                    # Buscar precio de compra actual
                    producto_proveedor = ProductoProveedor.objects.filter(
                        producto=producto,
                        proveedor=producto.proveedor_habitual,
                        activo=True
                    ).first()
                    if producto_proveedor and producto_proveedor.precio_compra_actual:
                        form.fields['precio_unitario'].initial = producto_proveedor.precio_compra_actual
                    elif producto_proveedor and producto_proveedor.precio_unitario:
                        form.fields['precio_unitario'].initial = producto_proveedor.precio_unitario
            except Producto.DoesNotExist:
                pass
    
    # Si es AJAX GET, devolver fragmento
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'solicitudes/crear_fragment.html', {'form': form, 'producto_id': producto_id})
    
    return render(request, 'solicitudes/crear.html', {'form': form, 'producto_id': producto_id})


@login_required(login_url='login')
def solicitudes_compra_cambiar_estado(request, id, nuevo_estado):
    """Cambiar el estado de una solicitud de compra"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        solicitud = SolicitudCompra.objects.get(id=id)
    except SolicitudCompra.DoesNotExist:
        messages.error(request, 'Solicitud no encontrada')
        return redirect('solicitudes_compra_lista')
    
    # Validar cambio de estado
    if not solicitud.puede_cambiar_estado(nuevo_estado):
        messages.error(request, f'No se puede cambiar de {solicitud.get_estado_display()} a {dict(solicitud.ESTADOS_CHOICES).get(nuevo_estado, nuevo_estado)}')
        return redirect('solicitudes_compra_lista')
    
    from django.utils import timezone
    
    # Cambiar estado y actualizar fechas
    estado_anterior = solicitud.estado
    solicitud.estado = nuevo_estado
    
    if nuevo_estado == 'aceptada':
        solicitud.fecha_aceptacion = timezone.now()
        # Aquí se podría implementar el impacto financiero (descuento de caja)
        # Por ahora solo registramos la fecha
    
    if nuevo_estado == 'completada':
        solicitud.fecha_completada = timezone.now()
    
    solicitud.save()
    
    messages.success(request, f'Solicitud actualizada a: {solicitud.get_estado_display()}')
    
    # Si es AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': f'Estado actualizado a {solicitud.get_estado_display()}'})
    
    return redirect('solicitudes_compra_lista')


@login_required(login_url='login')
def solicitudes_compra_verificar_recepcion(request, id):
    """Verificar recepción de una solicitud de compra completada"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        solicitud = SolicitudCompra.objects.get(id=id)
    except SolicitudCompra.DoesNotExist:
        messages.error(request, 'Solicitud no encontrada')
        return redirect('solicitudes_compra_lista')
    
    if solicitud.estado != 'en_proceso':
        messages.error(request, 'Solo se puede verificar la recepción de solicitudes en proceso')
        return redirect('solicitudes_compra_lista')
    
    if request.method == 'POST':
        form = VerificacionRecepcionForm(request.POST, instance=solicitud)
        if form.is_valid():
            from django.utils import timezone
            
            # Actualizar campos de recepción
            solicitud.cantidad_recibida = form.cleaned_data['cantidad_recibida']
            solicitud.precio_final = form.cleaned_data['precio_final'] or solicitud.precio_unitario
            solicitud.numero_factura = form.cleaned_data['numero_factura']
            solicitud.fecha_recepcion = timezone.now()
            solicitud.usuario_recepcion = request.user
            solicitud.estado = 'completada'
            solicitud.fecha_completada = timezone.now()
            solicitud.save()
            
            # Crear entrada de inventario automáticamente
            entrada = EntradaInventario.objects.create(
                producto=solicitud.producto,
                proveedor=solicitud.proveedor,
                cantidad=solicitud.cantidad_recibida,
                precio_unitario=solicitud.precio_final,
                numero_factura=solicitud.numero_factura,
                observaciones=f'Recepción de Solicitud de Compra #{solicitud.id}',
                usuario_registro=request.user
            )
            
            # Actualizar costo promedio del producto
            # Calcular nuevo costo promedio basado en todas las entradas
            entradas_producto = EntradaInventario.objects.filter(producto=solicitud.producto)
            if entradas_producto.exists():
                total_cantidad = sum(e.cantidad for e in entradas_producto)
                total_costo = sum(float(e.cantidad * e.precio_unitario) for e in entradas_producto)
                if total_cantidad > 0:
                    solicitud.producto.costo_promedio_actual = total_costo / total_cantidad
                    solicitud.producto.save()
            
            messages.success(request, 'Recepción verificada y stock actualizado exitosamente')
            
            # Si es AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Recepción verificada exitosamente'})
            
            return redirect('solicitudes_compra_lista')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors})
    else:
        # Precargar valores
        form = VerificacionRecepcionForm(instance=solicitud)
        form.fields['cantidad_recibida'].initial = solicitud.cantidad
        form.fields['precio_final'].initial = solicitud.precio_unitario
    
    # Si es AJAX GET, devolver fragmento
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'solicitudes/verificar_recepcion_fragment.html', {'form': form, 'solicitud': solicitud})
    
    return render(request, 'solicitudes/verificar_recepcion.html', {'form': form, 'solicitud': solicitud})


@login_required(login_url='login')
def solicitudes_compra_detalle(request, id):
    """Ver detalles de una solicitud de compra"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        solicitud = SolicitudCompra.objects.get(id=id)
    except SolicitudCompra.DoesNotExist:
        messages.error(request, 'Solicitud no encontrada')
        return redirect('solicitudes_compra_lista')
    
    context = {
        'solicitud': solicitud,
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'solicitudes/detalle_fragment.html', context)
    else:
        return render(request, 'solicitudes/detalle.html', context)


# ========== CRUD PROVEEDORES (ADMIN) ==========

@login_required(login_url='login')
def proveedores_lista(request):
    """Lista de proveedores."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar proveedores')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    proveedores = Proveedores.objects.all().order_by('nombre')
    
    # Filtros
    nombre_filtro = request.GET.get('nombre', '').strip()
    contacto_filtro = request.GET.get('contacto', '').strip()
    telefono_filtro = request.GET.get('telefono', '').strip()
    email_filtro = request.GET.get('email', '').strip()
    ciudad_filtro = request.GET.get('ciudad', '').strip()
    
    if nombre_filtro:
        proveedores = proveedores.filter(nombre__icontains=nombre_filtro)
    
    if contacto_filtro:
        proveedores = proveedores.filter(contacto__icontains=contacto_filtro)
    
    if telefono_filtro:
        proveedores = proveedores.filter(telefono__icontains=telefono_filtro)
    
    if email_filtro:
        proveedores = proveedores.filter(email__icontains=email_filtro)
    
    if ciudad_filtro:
        proveedores = proveedores.filter(ciudad__icontains=ciudad_filtro)
    
    # Paginación - 6 elementos por página
    paginator = Paginator(proveedores, 6)
    page = request.GET.get('page', 1)
    try:
        proveedores = paginator.page(page)
    except PageNotAnInteger:
        proveedores = paginator.page(1)
    except EmptyPage:
        proveedores = paginator.page(paginator.num_pages)
    
    context = {
        'proveedores': proveedores,
        'nombre_filtro': nombre_filtro,
        'contacto_filtro': contacto_filtro,
        'telefono_filtro': telefono_filtro,
        'email_filtro': email_filtro,
        'ciudad_filtro': ciudad_filtro
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'proveedores/lista_fragment.html', context)
    else:
        return render(request, 'proveedores/lista.html', context)


@login_required(login_url='login')
def proveedores_crear(request):
    """Crear nuevo proveedor."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para crear proveedores')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        contacto = request.POST.get('contacto', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        ciudad = request.POST.get('ciudad', '').strip()
        
        # Validar email si se proporciona
        if email:
            email_lower = email.lower().strip()
            if not email_lower.endswith('@gmail.com'):
                error_msg = 'Solo se permiten direcciones de correo de Gmail (@gmail.com)'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'email': [error_msg]}}, status=400)
                messages.error(request, error_msg)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return render(request, 'proveedores/crear_fragment.html')
                else:
                    return render(request, 'proveedores/crear.html')
            email = email_lower
        
        if not nombre:
            error_msg = 'El nombre es obligatorio'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': {'nombre': [error_msg]}}, status=400)
            messages.error(request, error_msg)
        else:
            try:
                proveedor = Proveedores.objects.create(
                    nombre=nombre,
                    contacto=contacto if contacto else None,
                    telefono=telefono if telefono else None,
                    email=email if email else None,
                    direccion=direccion if direccion else None,
                    ciudad=ciudad if ciudad else None
                )
                # Registrar acción en el historial
                registrar_accion_historial(
                    accion='creado',
                    tipo_modelo='proveedor',
                    nombre_objeto=proveedor.nombre,
                    usuario=request.user,
                    descripcion=f'Proveedor creado con contacto: {proveedor.contacto or "N/A"}',
                    objeto_id=proveedor.id
                )
                success_msg = 'Proveedor creado exitosamente'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': success_msg})
                messages.success(request, success_msg)
                return redirect('proveedores_lista')
            except Exception as e:
                error_msg = f'Error al crear el proveedor: {str(e)}'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'__all__': [error_msg]}}, status=400)
                messages.error(request, error_msg)
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'proveedores/crear_fragment.html')
    else:
        return render(request, 'proveedores/crear.html')


@login_required(login_url='login')
def proveedores_editar(request, id):
    """Editar proveedor existente."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para editar proveedores')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    try:
        proveedor = Proveedores.objects.get(id=id)
    except Proveedores.DoesNotExist:
        error_msg = 'Proveedor no encontrado'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': {'__all__': [error_msg]}}, status=404)
        messages.error(request, error_msg)
        return redirect('proveedores_lista')
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        contacto = request.POST.get('contacto', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email = request.POST.get('email', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        ciudad = request.POST.get('ciudad', '').strip()
        
        # Validar email si se proporciona
        if email:
            email_lower = email.lower().strip()
            if not email_lower.endswith('@gmail.com'):
                error_msg = 'Solo se permiten direcciones de correo de Gmail (@gmail.com)'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'email': [error_msg]}}, status=400)
                messages.error(request, error_msg)
                context = {'proveedor': proveedor}
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return render(request, 'proveedores/editar_fragment.html', context)
                else:
                    return render(request, 'proveedores/editar.html', context)
            email = email_lower
        
        if not nombre:
            error_msg = 'El nombre es obligatorio'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': {'nombre': [error_msg]}}, status=400)
            messages.error(request, error_msg)
        else:
            try:
                proveedor.nombre = nombre
                proveedor.contacto = contacto if contacto else None
                proveedor.telefono = telefono if telefono else None
                proveedor.email = email if email else None
                proveedor.direccion = direccion if direccion else None
                proveedor.ciudad = ciudad if ciudad else None
                proveedor.save()
                # Registrar acción en el historial
                registrar_accion_historial(
                    accion='editado',
                    tipo_modelo='proveedor',
                    nombre_objeto=proveedor.nombre,
                    usuario=request.user,
                    descripcion=f'Proveedor actualizado',
                    objeto_id=proveedor.id
                )
                success_msg = 'Proveedor actualizado exitosamente'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': success_msg})
                messages.success(request, success_msg)
                return redirect('proveedores_lista')
            except Exception as e:
                error_msg = f'Error al actualizar el proveedor: {str(e)}'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'__all__': [error_msg]}}, status=400)
                messages.error(request, error_msg)
    
    context = {'proveedor': proveedor}
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'proveedores/editar_fragment.html', context)
    else:
        return render(request, 'proveedores/editar.html', context)


@login_required(login_url='login')
def proveedores_eliminar(request, id):
    """Eliminar proveedor."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para eliminar proveedores')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    try:
        proveedor = Proveedores.objects.get(id=id)
        nombre_proveedor = proveedor.nombre
        proveedor_id = proveedor.id
        proveedor.delete()
        # Registrar acción en el historial
        registrar_accion_historial(
            accion='eliminado',
            tipo_modelo='proveedor',
            nombre_objeto=nombre_proveedor,
            usuario=request.user,
            descripcion=f'Proveedor eliminado del sistema',
            objeto_id=proveedor_id
        )
        messages.success(request, 'Proveedor eliminado exitosamente')
    except Proveedores.DoesNotExist:
        messages.error(request, 'Proveedor no encontrado')
    except Exception as e:
        messages.error(request, f'Error al eliminar el proveedor: {str(e)}')
    
    return redirect('proveedores_lista')


# ========== CRUD PRODUCTOS DE PROVEEDORES (ADMIN) ==========

@login_required(login_url='login')
def productos_proveedor_lista(request):
    """Lista de productos de proveedores."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para gestionar productos de proveedores')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    productos_proveedor = ProductoProveedor.objects.all().select_related('proveedor', 'producto').order_by('proveedor__nombre', 'nombre')
    
    # Filtros
    nombre_filtro = request.GET.get('nombre', '').strip()
    codigo_filtro = request.GET.get('codigo', '').strip()
    proveedor_id = request.GET.get('proveedor', '').strip()
    proveedor_filtro = None
    
    if nombre_filtro:
        productos_proveedor = productos_proveedor.filter(nombre__icontains=nombre_filtro)
    
    if codigo_filtro:
        productos_proveedor = productos_proveedor.filter(codigo_producto__icontains=codigo_filtro)
    
    if proveedor_id:
        try:
            productos_proveedor = productos_proveedor.filter(proveedor_id=int(proveedor_id))
            proveedor_filtro = proveedor_id
        except ValueError:
            pass
    
    proveedores = Proveedores.objects.all().order_by('nombre')
    
    # Paginación - 6 elementos por página
    paginator = Paginator(productos_proveedor, 6)
    page = request.GET.get('page', 1)
    try:
        productos_proveedor = paginator.page(page)
    except PageNotAnInteger:
        productos_proveedor = paginator.page(1)
    except EmptyPage:
        productos_proveedor = paginator.page(paginator.num_pages)
    
    context = {
        'productos_proveedor': productos_proveedor,
        'proveedores': proveedores,
        'proveedor_filtro': proveedor_filtro,
        'nombre_filtro': nombre_filtro,
        'codigo_filtro': codigo_filtro,
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'productos_proveedor/lista_fragment.html', context)
    else:
        return render(request, 'productos_proveedor/lista.html', context)


@login_required(login_url='login')
def productos_proveedor_crear(request):
    """Crear nuevo producto de proveedor."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para crear productos de proveedores')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    if request.method == 'POST':
        proveedor_id = request.POST.get('proveedor', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        precio_unitario = request.POST.get('precio_unitario', '').strip()
        precio_compra_actual = request.POST.get('precio_compra_actual', '').strip()
        unidad_medida = request.POST.get('unidad_medida', '').strip()
        codigo_producto = request.POST.get('codigo_producto', '').strip()
        activo = request.POST.get('activo') == 'on'
        
        if not proveedor_id:
            error_msg = 'El proveedor es obligatorio'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': {'proveedor': [error_msg]}}, status=400)
            messages.error(request, error_msg)
        elif not nombre:
            error_msg = 'El nombre del producto es obligatorio'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': {'nombre': [error_msg]}}, status=400)
            messages.error(request, error_msg)
        else:
            try:
                proveedor = Proveedores.objects.get(id=int(proveedor_id))
                
                # Validar código único si se proporciona
                if codigo_producto:
                    if ProductoProveedor.objects.filter(codigo_producto=codigo_producto).exists():
                        error_msg = 'El código de producto ya existe'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'success': False, 'errors': {'codigo_producto': [error_msg]}}, status=400)
                        messages.error(request, error_msg)
                        proveedores = Proveedores.objects.all().order_by('nombre')
                        context = {
                            'proveedores': proveedores,
                            'proveedor_id': proveedor_id,
                            'nombre': nombre,
                            'descripcion': descripcion,
                            'precio_unitario': precio_unitario,
                            'precio_compra_actual': precio_compra_actual,
                            'unidad_medida': unidad_medida,
                            'codigo_producto': codigo_producto
                        }
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return render(request, 'productos_proveedor/crear_fragment.html', context)
                        return render(request, 'productos_proveedor/crear.html', context)
                
                producto_proveedor = ProductoProveedor.objects.create(
                    proveedor=proveedor,
                    nombre=nombre,
                    descripcion=descripcion if descripcion else None,
                    precio_unitario=float(precio_unitario) if precio_unitario else None,
                    precio_compra_actual=float(precio_compra_actual) if precio_compra_actual else None,
                    unidad_medida=unidad_medida if unidad_medida else None,
                    codigo_producto=codigo_producto if codigo_producto else None,
                    activo=activo
                )
                
                # Registrar acción en el historial
                registrar_accion_historial(
                    accion='creado',
                    tipo_modelo='producto_proveedor',
                    nombre_objeto=producto_proveedor.nombre,
                    usuario=request.user,
                    descripcion=f'Producto de proveedor creado para {proveedor.nombre}',
                    objeto_id=producto_proveedor.id
                )
                
                success_msg = 'Producto de proveedor creado exitosamente'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': success_msg})
                messages.success(request, success_msg)
                return redirect('productos_proveedor_lista')
            except Proveedores.DoesNotExist:
                error_msg = 'Proveedor no encontrado'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'proveedor': [error_msg]}}, status=400)
                messages.error(request, error_msg)
            except ValueError:
                error_msg = 'Error en los datos proporcionados'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'__all__': [error_msg]}}, status=400)
                messages.error(request, error_msg)
            except Exception as e:
                error_msg = f'Error al crear el producto: {str(e)}'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'__all__': [error_msg]}}, status=400)
                messages.error(request, error_msg)
    
    proveedores = Proveedores.objects.all().order_by('nombre')
    context = {
        'proveedores': proveedores
    }
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'productos_proveedor/crear_fragment.html', context)
    else:
        return render(request, 'productos_proveedor/crear.html', context)


@login_required(login_url='login')
def productos_proveedor_editar(request, id):
    """Editar producto de proveedor existente."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para editar productos de proveedores')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    try:
        producto_proveedor = ProductoProveedor.objects.get(id=id)
    except ProductoProveedor.DoesNotExist:
        error_msg = 'Producto de proveedor no encontrado'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': {'__all__': [error_msg]}}, status=404)
        messages.error(request, error_msg)
        return redirect('productos_proveedor_lista')
    
    if request.method == 'POST':
        proveedor_id = request.POST.get('proveedor', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        precio_unitario = request.POST.get('precio_unitario', '').strip()
        precio_compra_actual = request.POST.get('precio_compra_actual', '').strip()
        unidad_medida = request.POST.get('unidad_medida', '').strip()
        codigo_producto = request.POST.get('codigo_producto', '').strip()
        activo = request.POST.get('activo') == 'on'
        
        if not proveedor_id:
            error_msg = 'El proveedor es obligatorio'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': {'proveedor': [error_msg]}}, status=400)
            messages.error(request, error_msg)
        elif not nombre:
            error_msg = 'El nombre del producto es obligatorio'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': {'nombre': [error_msg]}}, status=400)
            messages.error(request, error_msg)
        else:
            try:
                proveedor = Proveedores.objects.get(id=int(proveedor_id))
                
                # Validar código único si se proporciona y cambió
                if codigo_producto and codigo_producto != producto_proveedor.codigo_producto:
                    if ProductoProveedor.objects.filter(codigo_producto=codigo_producto).exclude(id=id).exists():
                        error_msg = 'El código de producto ya existe'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({'success': False, 'errors': {'codigo_producto': [error_msg]}}, status=400)
                        messages.error(request, error_msg)
                        proveedores = Proveedores.objects.all().order_by('nombre')
                        context = {
                            'producto_proveedor': producto_proveedor,
                            'proveedores': proveedores
                        }
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return render(request, 'productos_proveedor/editar_fragment.html', context)
                        return render(request, 'productos_proveedor/editar.html', context)
                
                producto_proveedor.proveedor = proveedor
                producto_proveedor.nombre = nombre
                producto_proveedor.descripcion = descripcion if descripcion else None
                producto_proveedor.precio_unitario = float(precio_unitario) if precio_unitario else None
                producto_proveedor.precio_compra_actual = float(precio_compra_actual) if precio_compra_actual else None
                producto_proveedor.unidad_medida = unidad_medida if unidad_medida else None
                producto_proveedor.codigo_producto = codigo_producto if codigo_producto else None
                producto_proveedor.activo = activo
                producto_proveedor.producto = None  # No permitir relacionar con inventario desde aquí
                
                producto_proveedor.save()
                # Registrar acción en el historial
                registrar_accion_historial(
                    accion='editado',
                    tipo_modelo='producto_proveedor',
                    nombre_objeto=producto_proveedor.nombre,
                    usuario=request.user,
                    descripcion=f'Producto de proveedor actualizado',
                    objeto_id=producto_proveedor.id
                )
                success_msg = 'Producto de proveedor actualizado exitosamente'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': success_msg})
                messages.success(request, success_msg)
                return redirect('productos_proveedor_lista')
            except Proveedores.DoesNotExist:
                error_msg = 'Proveedor no encontrado'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'proveedor': [error_msg]}}, status=400)
                messages.error(request, error_msg)
            except ValueError:
                error_msg = 'Error en los datos proporcionados'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'__all__': [error_msg]}}, status=400)
                messages.error(request, error_msg)
            except Exception as e:
                error_msg = f'Error al actualizar el producto: {str(e)}'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'errors': {'__all__': [error_msg]}}, status=400)
                messages.error(request, error_msg)
    
    proveedores = Proveedores.objects.all().order_by('nombre')
    context = {
        'producto_proveedor': producto_proveedor,
        'proveedores': proveedores
    }
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'productos_proveedor/editar_fragment.html', context)
    else:
        return render(request, 'productos_proveedor/editar.html', context)


@login_required(login_url='login')
def productos_proveedor_eliminar(request, id):
    """Eliminar producto de proveedor."""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Si es superuser, tiene acceso total
    if not request.user.is_superuser:
        # Verificar permiso de cargo si el usuario es empleado
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_empleados_servicios_proveedores:
                messages.error(request, 'No tienes permiso para eliminar productos de proveedores')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass  # Si no es empleado, permitir acceso (es staff)
    
    try:
        producto_proveedor = ProductoProveedor.objects.get(id=id)
        nombre_producto = producto_proveedor.nombre
        producto_id = producto_proveedor.id
        producto_proveedor.delete()
        # Registrar acción en el historial
        registrar_accion_historial(
            accion='eliminado',
            tipo_modelo='producto_proveedor',
            nombre_objeto=nombre_producto,
            usuario=request.user,
            descripcion=f'Producto de proveedor eliminado del sistema',
            objeto_id=producto_id
        )
        messages.success(request, 'Producto de proveedor eliminado exitosamente')
    except ProductoProveedor.DoesNotExist:
        messages.error(request, 'Producto de proveedor no encontrado')
    except Exception as e:
        messages.error(request, f'Error al eliminar el producto: {str(e)}')
    
    return redirect('productos_proveedor_lista')


# ========== CRUD INVENTARIO UNIFICADO ==========

@login_required(login_url='login')
def inventario_lista(request):
    """Lista de productos del inventario unificado"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Verificar permisos (simplificado - solo verificar si es staff)
    # La verificación de permisos por cargo se puede agregar después si es necesario
    
    # Mostrar todos los productos (activos e inactivos) para que los suspendidos sigan visibles
    productos = Producto.objects.all().select_related('producto_proveedor', 'proveedor_habitual', 'producto_proveedor__proveedor', 'zona').order_by('-id')
    
    # Filtros
    tipo_filtro = request.GET.get('tipo', '').strip()
    nombre_filtro = request.GET.get('nombre', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    categoria_filtro = request.GET.get('categoria', '').strip()
    zona_filtro = request.GET.get('zona', '').strip()
    
    if tipo_filtro:
        productos = productos.filter(tipo_producto=tipo_filtro)
    
    if nombre_filtro:
        productos = productos.filter(nombre__icontains=nombre_filtro)
    
    # Filtro por categoría
    if categoria_filtro:
        productos = productos.filter(categoria=categoria_filtro)
    
    # Filtro por estado
    if estado_filtro:
        if estado_filtro == 'activo':
            # Activo: activo=True, cantidad >= stock_minimo, cantidad > 0
            productos = productos.filter(activo=True, cantidad__gte=F('stock_minimo'), cantidad__gt=0)
        elif estado_filtro == 'bajo_stock':
            # Bajo Stock: activo=True, cantidad < stock_minimo, cantidad > 0
            productos = productos.filter(activo=True, cantidad__lt=F('stock_minimo'), cantidad__gt=0)
        elif estado_filtro == 'agotado':
            # Agotado: activo=True, cantidad = 0
            productos = productos.filter(activo=True, cantidad=0)
        elif estado_filtro == 'inactivo':
            # Inactivo: activo=False
            productos = productos.filter(activo=False)
    
    if zona_filtro:
        try:
            zona_id = int(zona_filtro)
            productos = productos.filter(zona_id=zona_id)
        except (ValueError, TypeError):
            pass
    
    # Estadísticas
    total_productos = productos.count()
    productos_propios = productos.filter(tipo_producto='propio').count()
    productos_proveedor_count = productos.filter(tipo_producto='proveedor').count()
    productos_bajo_stock = productos.filter(activo=True, cantidad__lt=F('stock_minimo'), cantidad__gt=0).count()
    productos_agotados = productos.filter(activo=True, cantidad=0).count()
    
    # Obtener zonas activas para el filtro
    zonas = Zona.objects.filter(activo=True).order_by('nombre')
    
    # Paginación - 5 elementos por página
    paginator = Paginator(productos, 5)
    page = request.GET.get('page', 1)
    try:
        productos = paginator.page(page)
    except PageNotAnInteger:
        productos = paginator.page(1)
    except EmptyPage:
        productos = paginator.page(paginator.num_pages)
    
    context = {
        'productos': productos,
        'total_productos': total_productos,
        'productos_propios': productos_propios,
        'productos_proveedor': productos_proveedor_count,
        'productos_bajo_stock': productos_bajo_stock,
        'productos_agotados': productos_agotados,
        'tipo_filtro': tipo_filtro,
        'nombre_filtro': nombre_filtro,
        'estado_filtro': estado_filtro,
        'categoria_filtro': categoria_filtro,
        'zona_filtro': zona_filtro,
        'zonas': zonas,
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'inventario/lista_fragment.html', context)
    else:
        return render(request, 'inventario/lista.html', context)


@login_required(login_url='login')
def inventario_crear(request):
    """Crear nuevo producto propio en el inventario"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Verificar permisos (simplificado)
    # if not request.user.is_superuser:
    #     try:
    #         empleado = Empleado.objects.get(email=request.user.email)
    #         if empleado.cargo and not empleado.cargo.puede_gestionar_inventario:
    #             messages.error(request, 'No tienes permiso para crear productos')
    #             return redirect('admin_panel')
    #     except Empleado.DoesNotExist:
    #         pass
    
    if request.method == 'POST':
        post_data = request.POST.copy()
        # Debug: Log de datos recibidos
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'Datos POST recibidos: {dict(post_data)}')
        logger.info(f'Tipo producto: {post_data.get("tipo_producto")}')
        
        form = ProductoForm(post_data, request.FILES)
        
        # Debug: Log de errores de validación
        if not form.is_valid():
            logger.error(f'Errores de validación del formulario: {form.errors}')
            logger.error(f'Datos POST recibidos: {dict(post_data)}')
            logger.error(f'Datos FILES recibidos: {dict(request.FILES)}')
        
        if form.is_valid():
            try:
                producto = form.save()
                logger.info(f'Producto guardado exitosamente: {producto.id} - {producto.nombre}')
                # Registrar acción en el historial
                registrar_accion_historial(
                    accion='creado',
                    tipo_modelo='producto',
                    nombre_objeto=producto.nombre,
                    usuario=request.user,
                    descripcion=f'Producto creado con {producto.cantidad} unidades en stock',
                    objeto_id=producto.id
                )
                messages.success(request, f'Producto "{producto.nombre}" agregado al inventario exitosamente')
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Producto "{producto.nombre}" agregado exitosamente'
                    })
                return redirect('inventario_lista')
            except Exception as e:
                import traceback
                error_msg = f'Error al guardar el producto: {str(e)}'
                error_traceback = traceback.format_exc()
                logger.error(f'Error al guardar producto: {error_msg}\n{error_traceback}')
                messages.error(request, error_msg)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'errors': {'__all__': [error_msg]},
                        'error_message': error_msg,
                        'traceback': error_traceback
                    }, status=400)
        else:
            # Formulario inválido - retornar errores de validación detallados
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Convertir errores de formulario a formato legible
                errors_dict = {}
                for field, errors in form.errors.items():
                    if isinstance(errors, list):
                        errors_dict[field] = errors
                    else:
                        errors_dict[field] = [str(errors)]
                
                return JsonResponse({
                    'success': False,
                    'errors': errors_dict,
                    'error_message': 'Por favor, corrige los errores en el formulario'
                }, status=400)
    else:
        form = ProductoForm()
        # Establecer el valor inicial del radio button
        initial_tipo = request.GET.get('tipo_producto', 'propio')
        form.fields['tipo_producto'].initial = initial_tipo
    
    # Obtener proveedores para el formulario de proveedor
    from .models import Proveedores
    proveedores = Proveedores.objects.all().order_by('nombre')
    
    # Obtener zonas activas
    zonas = Zona.objects.filter(activo=True).order_by('nombre')
    
    context = {
        'form': form, 
        'tipo_producto': form.fields['tipo_producto'].initial,
        'proveedores': proveedores,
        'zonas': zonas
    }
    
    # Si es AJAX GET, retornar fragment principal con radio buttons
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'inventario/crear_fragment.html', context)
    
    # Para requests no-AJAX, retornar página completa
    return render(request, 'inventario/crear.html', context)


@login_required(login_url='login')
def inventario_crear_proveedor(request):
    """Traer producto de proveedor al inventario"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Verificar permisos
    if not request.user.is_superuser:
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            if empleado.cargo and not empleado.cargo.puede_gestionar_inventario:
                messages.error(request, 'No tienes permiso para crear productos')
                return redirect('admin_panel')
        except Empleado.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)
        # Forzar tipo_producto a 'proveedor' para este endpoint
        if form.is_valid():
            try:
                producto = form.save()
                # Registrar acción en el historial
                registrar_accion_historial(
                    accion='creado',
                    tipo_modelo='producto',
                    nombre_objeto=producto.nombre,
                    usuario=request.user,
                    descripcion=f'Producto de proveedor agregado con {producto.cantidad} unidades',
                    objeto_id=producto.id
                )
                messages.success(request, f'Producto "{producto.nombre}" agregado al inventario exitosamente')
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Producto "{producto.nombre}" agregado exitosamente'
                    })
                return redirect('inventario_lista')
            except Exception as e:
                error_msg = f'Error al guardar el producto: {str(e)}'
                messages.error(request, error_msg)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'errors': {'__all__': [error_msg]}
                    }, status=400)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
    else:
        form = ProductoForm()
        form.fields['tipo_producto'].initial = 'proveedor'
    
    context = {'form': form, 'tipo_producto': 'proveedor'}
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'productos/crear_proveedor_fragment.html', context)
    else:
        return render(request, 'productos/crear.html', context)


@login_required(login_url='login')
def inventario_editar(request, id):
    """Editar producto del inventario"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Verificar permisos (simplificado)
    # if not request.user.is_superuser:
    #     try:
    #         empleado = Empleado.objects.get(email=request.user.email)
    #         if empleado.cargo and not empleado.cargo.puede_gestionar_inventario:
    #             messages.error(request, 'No tienes permiso para editar productos')
    #             return redirect('admin_panel')
    #     except Empleado.DoesNotExist:
    #         pass
    
    try:
        producto = Producto.objects.get(id=id)
    except Producto.DoesNotExist:
        messages.error(request, 'Producto no encontrado')
        return redirect('inventario_lista')
    
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            producto = form.save()
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='editado',
                tipo_modelo='producto',
                nombre_objeto=producto.nombre,
                usuario=request.user,
                descripcion=f'Producto actualizado. Stock actual: {producto.cantidad} unidades',
                objeto_id=producto.id
            )
            messages.success(request, f'Producto "{producto.nombre}" actualizado exitosamente')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Producto "{producto.nombre}" actualizado exitosamente'
                })
            return redirect('inventario_lista')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
    else:
        form = ProductoForm(instance=producto)
    
    # Obtener proveedores para el formulario de proveedor
    from .models import Proveedores
    proveedores = Proveedores.objects.all().order_by('nombre')
    
    # Obtener zonas activas
    zonas = Zona.objects.filter(activo=True).order_by('nombre')
    
    context = {
        'form': form,
        'producto': producto,
        'proveedores': proveedores,
        'zonas': zonas
    }
    
    # Si es petición AJAX, retornar solo el fragment
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'inventario/editar_fragment.html', context)
    else:
        # Si es carga directa, retornar la página completa con drawer
        return render(request, 'inventario/editar_fragment.html', context)


@login_required(login_url='login')
def inventario_eliminar(request, id):
    """Eliminar producto del inventario"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    # Verificar permisos (simplificado)
    # if not request.user.is_superuser:
    #     try:
    #         empleado = Empleado.objects.get(email=request.user.email)
    #         if empleado.cargo and not empleado.cargo.puede_gestionar_inventario:
    #             messages.error(request, 'No tienes permiso para eliminar productos')
    #             return redirect('admin_panel')
    #     except Empleado.DoesNotExist:
    #         pass
    
    try:
        producto = Producto.objects.get(id=id)
    except Producto.DoesNotExist:
        messages.error(request, 'Producto no encontrado')
        return redirect('inventario_lista')
    
    if request.method == 'POST':
        nombre_producto = producto.nombre
        producto_id = producto.id
        try:
            # Registrar acción en el historial antes de eliminar
            registrar_accion_historial(
                accion='eliminado',
                tipo_modelo='producto',
                nombre_objeto=nombre_producto,
                usuario=request.user,
                descripcion=f'Producto eliminado del inventario',
                objeto_id=producto_id
            )
            # Si es un producto de proveedor, limpiar la relación en ProductoProveedor antes de eliminar
            if producto.tipo_producto == 'proveedor' and producto.producto_proveedor:
                producto_proveedor = producto.producto_proveedor
                producto_proveedor.producto = None
                producto_proveedor.save(update_fields=['producto'])
            
            producto.delete()
            messages.success(request, f'Producto "{nombre_producto}" eliminado exitosamente')
            
            # Si es petición AJAX, retornar JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({
                    'success': True,
                    'message': f'Producto "{nombre_producto}" eliminado exitosamente'
                })
            
            return redirect('inventario_lista')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error al eliminar producto: {str(e)}', exc_info=True)
            error_msg = f'Error al eliminar el producto: {str(e)}'
            messages.error(request, error_msg)
            
    return redirect('inventario_lista')


@login_required(login_url='login')
def inventario_activar(request, id):
    """Activar un producto del inventario (mantener para compatibilidad)"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    if request.method != 'POST':
        messages.error(request, 'Método no permitido')
        return redirect('inventario_lista')
    
    try:
        producto = Producto.objects.get(id=id)
        producto.activo = True
        producto.save()
        messages.success(request, f'Producto "{producto.nombre}" activado exitosamente')
        
        # Si es petición AJAX, retornar JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({
                'success': True,
                'message': f'Producto "{producto.nombre}" activado exitosamente',
                'activo': True
            })
        
        return redirect('inventario_lista')
    except Producto.DoesNotExist:
        messages.error(request, 'Producto no encontrado')
        return redirect('inventario_lista')
    except Exception as e:
        messages.error(request, f'Error al activar el producto: {str(e)}')
        return redirect('inventario_lista')


@login_required(login_url='login')
def inventario_toggle_estado(request, id):
    """Alternar el estado activo/inactivo de un producto"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Acceso denegado'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        producto = Producto.objects.get(id=id)
        estado_anterior = producto.activo
        
        # Alternar el estado
        producto.activo = not producto.activo
        producto.save()
        
        estado_texto = 'activado' if producto.activo else 'suspendido'
        messages.success(request, f'Producto "{producto.nombre}" {estado_texto} exitosamente')
        
        # Si es petición AJAX, retornar JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Calcular el estado visual del producto
            estado_visual = 'inactivo'
            if producto.activo:
                if producto.cantidad == 0:
                    estado_visual = 'agotado'
                elif producto.cantidad < producto.stock_minimo:
                    estado_visual = 'bajo_stock'
                else:
                    estado_visual = 'activo'
            
            return JsonResponse({
                'success': True,
                'message': f'Producto "{producto.nombre}" {estado_texto} exitosamente',
                'activo': producto.activo,
                'estado_anterior': estado_anterior,
                'cantidad': producto.cantidad,
                'stock_minimo': producto.stock_minimo,
                'estado_visual': estado_visual
            })
        
        return redirect('inventario_lista')
    except Producto.DoesNotExist:
        error_msg = 'Producto no encontrado'
        messages.error(request, error_msg)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg}, status=404)
        return redirect('inventario_lista')
    except Exception as e:
        import traceback
        error_msg = f'Error al cambiar el estado del producto: {str(e)}'
        error_trace = traceback.format_exc()
        print(f'Error en inventario_toggle_estado: {error_msg}')
        print(f'Traceback: {error_trace}')
        messages.error(request, error_msg)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        return redirect('inventario_lista')


@login_required(login_url='login')
def zona_crear_ajax(request):
    """Crear una nueva zona vía AJAX desde el inventario"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Acceso denegado'}, status=403)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        
        if not nombre:
            return JsonResponse({'success': False, 'error': 'El nombre de la zona es obligatorio'}, status=400)
        
        # Verificar si ya existe una zona con ese nombre
        if Zona.objects.filter(nombre__iexact=nombre, activo=True).exists():
            return JsonResponse({'success': False, 'error': 'Ya existe una zona activa con ese nombre'}, status=400)
        
        try:
            zona = Zona.objects.create(
                nombre=nombre,
                descripcion=descripcion if descripcion else None,
                activo=True
            )
            return JsonResponse({
                'success': True,
                'zona': {
                    'id': zona.id,
                    'nombre': zona.nombre,
                    'descripcion': zona.descripcion
                },
                'message': f'Zona "{zona.nombre}" creada exitosamente'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error al crear la zona: {str(e)}'}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)


@login_required(login_url='login')
def zonas_lista_ajax(request):
    """Obtener lista de zonas activas vía AJAX"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Acceso denegado'}, status=403)
    
    zonas = Zona.objects.filter(activo=True).order_by('nombre')
    zonas_data = [{'id': zona.id, 'nombre': zona.nombre} for zona in zonas]
    
    return JsonResponse({'success': True, 'zonas': zonas_data})


@login_required(login_url='login')
def inventario_suspender(request, id):
    """Suspender (inactivar) un producto del inventario (mantener para compatibilidad)"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    if request.method != 'POST':
        messages.error(request, 'Método no permitido')
        return redirect('inventario_lista')
    
    try:
        producto = Producto.objects.get(id=id)
        producto.activo = False
        producto.save()
        messages.success(request, f'Producto "{producto.nombre}" suspendido exitosamente')
        
        # Si es petición AJAX, retornar JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({
                'success': True,
                'message': f'Producto "{producto.nombre}" suspendido exitosamente',
                'activo': False
            })
        
        return redirect('inventario_lista')
    except Producto.DoesNotExist:
        messages.error(request, 'Producto no encontrado')
        return redirect('inventario_lista')
    except Exception as e:
        messages.error(request, f'Error al suspender el producto: {str(e)}')
        return redirect('inventario_lista')


@login_required(login_url='login')
def inventario_productos_proveedor_ajax(request):
    """API AJAX para obtener productos de un proveedor"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    
    proveedor_id = request.GET.get('proveedor_id')
    if not proveedor_id:
        return JsonResponse({'error': 'ID de proveedor requerido'}, status=400)
    
    try:
        proveedor = Proveedores.objects.get(id=proveedor_id)
        # Obtener todos los productos del proveedor (activos e inactivos para debug)
        productos = ProductoProveedor.objects.filter(
            proveedor=proveedor
        ).order_by('nombre')
        
        # Filtrar solo activos
        productos_activos = productos.filter(activo=True)
        
        productos_data = []
        for producto in productos_activos:
            # Calcular cantidad desde entradas si existe un producto en inventario
            cantidad = Producto.calcular_cantidad_por_producto_proveedor(producto.id)
            
            productos_data.append({
                'id': producto.id,
                'nombre': producto.nombre,
                'descripcion': producto.descripcion or '',
                'precio_unitario': str(producto.precio_unitario) if producto.precio_unitario else '',
                'precio_compra_actual': str(producto.precio_compra_actual) if producto.precio_compra_actual else '',
                'unidad_medida': producto.unidad_medida or '',
                'codigo_producto': producto.codigo_producto or '',
                'cantidad': cantidad,  # Agregar cantidad calculada
            })
        
        return JsonResponse({
            'productos': productos_data,
            'total': productos_activos.count(),
            'proveedor_nombre': proveedor.nombre
        })
    except Proveedores.DoesNotExist:
        return JsonResponse({'error': 'Proveedor no encontrado'}, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@login_required(login_url='login')
def inventario_cantidad_producto_proveedor_ajax(request):
    """API AJAX para obtener la cantidad de un producto de proveedor basándose en las entradas"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    
    producto_proveedor_id = request.GET.get('producto_proveedor_id')
    if not producto_proveedor_id:
        return JsonResponse({'error': 'ID de producto de proveedor requerido'}, status=400)
    
    try:
        cantidad = Producto.calcular_cantidad_por_producto_proveedor(producto_proveedor_id)
        return JsonResponse({
            'cantidad': cantidad,
            'producto_proveedor_id': producto_proveedor_id
        })
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@login_required(login_url='login')
def entradas_productos_por_proveedor_ajax(request):
    """API AJAX para obtener productos de proveedor (ProductoProveedor) y sus productos del inventario relacionados"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    
    proveedor_id = request.GET.get('proveedor_id')
    if not proveedor_id:
        return JsonResponse({'error': 'ID de proveedor requerido'}, status=400)
    
    try:
        proveedor = Proveedores.objects.get(id=proveedor_id)
        # Obtener productos de proveedor (ProductoProveedor) activos
        productos_proveedor = ProductoProveedor.objects.filter(
            proveedor=proveedor,
            activo=True
        ).order_by('nombre')
        
        # Obtener productos del inventario relacionados con estos ProductoProveedor
        productos_inventario = Producto.objects.filter(
            activo=True,
            producto_proveedor__proveedor=proveedor,
            producto_proveedor__activo=True
        ).select_related('producto_proveedor').order_by('nombre')
        
        # Crear un mapa de producto_proveedor_id -> producto_inventario
        inventario_map = {}
        for producto in productos_inventario:
            if producto.producto_proveedor:
                inventario_map[producto.producto_proveedor.id] = producto
        
        productos_data = []
        for producto_proveedor in productos_proveedor:
            # Obtener el precio de compra actual o precio unitario
            precio_unitario = 0
            if producto_proveedor.precio_compra_actual:
                precio_unitario = float(producto_proveedor.precio_compra_actual)
            elif producto_proveedor.precio_unitario:
                precio_unitario = float(producto_proveedor.precio_unitario)
            
            # Buscar si existe un producto en el inventario relacionado
            producto_inventario = inventario_map.get(producto_proveedor.id)
            
            productos_data.append({
                'id': producto_proveedor.id,
                'nombre': producto_proveedor.nombre,
                'precio_unitario': precio_unitario,
                'precio_compra_actual': float(producto_proveedor.precio_compra_actual) if producto_proveedor.precio_compra_actual else 0,
                'descripcion': producto_proveedor.descripcion or '',
                'unidad_medida': producto_proveedor.unidad_medida or '',
                # Información del producto del inventario si existe
                'producto_inventario_id': producto_inventario.id if producto_inventario else None,
                'tiene_inventario': producto_inventario is not None,
            })
        
        return JsonResponse({
            'productos': productos_data,
            'total': productos_proveedor.count(),
            'proveedor_nombre': proveedor.nombre
        })
    except Proveedores.DoesNotExist:
        return JsonResponse({'error': 'Proveedor no encontrado'}, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@login_required(login_url='login')
def entradas_productos_inventario_por_proveedor_ajax(request):
    """API AJAX para obtener productos del inventario (Producto) relacionados con ProductoProveedor de un proveedor"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    
    proveedor_id = request.GET.get('proveedor_id')
    if not proveedor_id:
        return JsonResponse({'error': 'ID de proveedor requerido'}, status=400)
    
    try:
        proveedor = Proveedores.objects.get(id=proveedor_id)
        # Obtener productos del inventario que están relacionados con ProductoProveedor de este proveedor
        productos = Producto.objects.filter(
            activo=True,
            producto_proveedor__proveedor=proveedor,
            producto_proveedor__activo=True
        ).select_related('producto_proveedor').order_by('nombre')
        
        productos_data = []
        for producto in productos:
            productos_data.append({
                'id': producto.id,
                'nombre': producto.nombre,
                'producto_proveedor_id': producto.producto_proveedor.id if producto.producto_proveedor else None,
            })
        
        return JsonResponse({
            'productos': productos_data,
            'total': productos.count(),
            'proveedor_nombre': proveedor.nombre
        })
    except Proveedores.DoesNotExist:
        return JsonResponse({'error': 'Proveedor no encontrado'}, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


# ========== AUDITORÍA DE INVENTARIO ==========

@login_required(login_url='login')
def auditoria_lista(request):
    """Lista de auditorías de inventario (Historial completo)"""
    try:
        if not request.user.is_staff:
            messages.error(request, 'Acceso denegado')
            return redirect('inicio')
        
        auditorias = AuditoriaInventario.objects.all().select_related('usuario').order_by('-fecha_creacion')
        
        # Filtros
        estado_filtro = request.GET.get('estado', '').strip()
        fecha_desde = request.GET.get('fecha_desde', '').strip()
        fecha_hasta = request.GET.get('fecha_hasta', '').strip()
        
        if estado_filtro:
            auditorias = auditorias.filter(estado=estado_filtro)
        
        if fecha_desde:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                auditorias = auditorias.filter(fecha_auditoria__gte=fecha_desde_obj)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                auditorias = auditorias.filter(fecha_auditoria__lte=fecha_hasta_obj)
            except ValueError:
                pass
        
        # Estadísticas (antes de paginar)
        total_auditorias = auditorias.count()
        en_proceso = auditorias.filter(estado='en_proceso').count()
        completadas = auditorias.filter(estado='completada').count()
        canceladas = auditorias.filter(estado='cancelada').count()
        
        # Paginación - 6 elementos por página
        paginator = Paginator(auditorias, 6)
        page = request.GET.get('page', 1)
        try:
            auditorias = paginator.page(page)
        except PageNotAnInteger:
            auditorias = paginator.page(1)
        except EmptyPage:
            auditorias = paginator.page(paginator.num_pages)
        
        context = {
            'auditorias': auditorias,
            'total_auditorias': total_auditorias,
            'en_proceso': en_proceso,
            'completadas': completadas,
            'canceladas': canceladas,
            'estado_filtro': estado_filtro,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'es_historial': True,
        }
        
        # Detectar si es petición AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(request, 'auditoria/lista_fragment.html', context)
        else:
            return render(request, 'auditoria/lista.html', context)
    except Exception as e:
        import traceback
        messages.error(request, f'Error al cargar las auditorías: {str(e)}')
        print(f"Error en auditoria_lista: {str(e)}")
        print(traceback.format_exc())
        return redirect('admin_panel')


@login_required(login_url='login')
def auditoria_revisiones(request):
    """Lista de auditorías en proceso para revisar"""
    try:
        if not request.user.is_staff:
            messages.error(request, 'Acceso denegado')
            return redirect('inicio')
        
        # Solo mostrar auditorías en proceso
        auditorias = AuditoriaInventario.objects.filter(estado='en_proceso').select_related('usuario').order_by('-fecha_creacion')
        
        # Filtros
        fecha_desde = request.GET.get('fecha_desde', '').strip()
        fecha_hasta = request.GET.get('fecha_hasta', '').strip()
        
        if fecha_desde:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                auditorias = auditorias.filter(fecha_auditoria__gte=fecha_desde_obj)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                auditorias = auditorias.filter(fecha_auditoria__lte=fecha_hasta_obj)
            except ValueError:
                pass
        
        # Estadísticas
        total_auditorias = auditorias.count()
        productos_pendientes_total = 0
        productos_revisados_total = 0
        
        for auditoria in auditorias:
            productos_pendientes_total += auditoria.productos_pendientes
            productos_revisados_total += auditoria.productos_revisados
        
        context = {
            'auditorias': auditorias,
            'total_auditorias': total_auditorias,
            'productos_pendientes_total': productos_pendientes_total,
            'productos_revisados_total': productos_revisados_total,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'es_revisiones': True,
        }
        
        # Detectar si es petición AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(request, 'auditoria/revisiones_fragment.html', context)
        else:
            return render(request, 'auditoria/revisiones.html', context)
    except Exception as e:
        import traceback
        messages.error(request, f'Error al cargar las revisiones: {str(e)}')
        print(f"Error en auditoria_revisiones: {str(e)}")
        print(traceback.format_exc())
        return redirect('admin_panel')


@login_required(login_url='login')
def auditoria_crear(request):
    """Crear nueva auditoría de inventario"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    if request.method == 'POST':
        form = AuditoriaInventarioForm(request.POST)
        if form.is_valid():
            auditoria = form.save(commit=False)
            auditoria.usuario = request.user
            # Establecer fecha automáticamente del sistema en zona horaria de Chile
            # timezone.localtime() convierte a la zona horaria configurada (America/Santiago)
            fecha_chile = timezone.localtime(timezone.now())
            auditoria.fecha_auditoria = fecha_chile.date()
            auditoria.save()
            
            # Agregar todos los productos activos a la auditoría
            productos = Producto.objects.filter(activo=True).order_by('nombre')
            for producto in productos:
                DetalleAuditoria.objects.create(
                    auditoria=auditoria,
                    producto=producto,
                    cantidad_sistema=producto.cantidad,
                    conteo_fisico=0,
                    diferencia=-producto.cantidad  # Inicialmente negativo porque no se ha contado
                )
            
            # Registrar acción en el historial
            registrar_accion_historial(
                accion='creado',
                tipo_modelo='auditoria',
                nombre_objeto=f'Auditoría #{auditoria.id}',
                usuario=request.user,
                descripcion=f'Auditoría creada para {auditoria.fecha_auditoria.strftime("%d/%m/%Y")} con {productos.count()} productos',
                objeto_id=auditoria.id
            )
            
            messages.success(request, f'Auditoría #{auditoria.id} creada exitosamente')
            return redirect('auditoria_detalle', id=auditoria.id)
    else:
        form = AuditoriaInventarioForm()
    
    # Obtener fecha y hora actual en zona horaria de Chile para mostrar en el formulario
    # timezone.localtime() convierte automáticamente a la zona horaria configurada en settings (America/Santiago)
    fecha_actual = timezone.localtime(timezone.now())
    
    context = {
        'form': form,
        'fecha_actual': fecha_actual,
    }
    
    # Detectar si es petición AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'auditoria/crear_fragment.html', context)
    else:
        return render(request, 'auditoria/crear.html', context)


@login_required(login_url='login')
def auditoria_detalle(request, id):
    """Detalle de una auditoría con sus productos - Lista tickeable"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        auditoria = AuditoriaInventario.objects.get(id=id)
        detalles = auditoria.detalles.all().select_related('producto').order_by('producto__nombre')
        
        # Estadísticas
        total_productos = detalles.count()
        productos_revisados = detalles.filter(revisado=True).count()
        productos_pendientes = detalles.filter(revisado=False).count()
        productos_con_discrepancia = detalles.exclude(diferencia=0).count()
        
        context = {
            'auditoria': auditoria,
            'detalles': detalles,
            'total_productos': total_productos,
            'productos_revisados': productos_revisados,
            'productos_pendientes': productos_pendientes,
            'productos_con_discrepancia': productos_con_discrepancia,
        }
        
        # Detectar si es petición AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(request, 'auditoria/detalle_fragment.html', context)
        else:
            return render(request, 'auditoria/detalle.html', context)
    except AuditoriaInventario.DoesNotExist:
        messages.error(request, 'Auditoría no encontrada')
        return redirect('auditoria_lista')


@login_required(login_url='login')
def auditoria_editar_detalle(request, auditoria_id, detalle_id):
    """Editar un detalle específico de la auditoría (conteo físico)"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        auditoria = AuditoriaInventario.objects.get(id=auditoria_id)
        if auditoria.estado != 'en_proceso':
            messages.error(request, 'Solo se pueden editar auditorías en proceso')
            return redirect('auditoria_detalle', id=auditoria_id)
        
        detalle = DetalleAuditoria.objects.get(id=detalle_id, auditoria=auditoria)
        
        if request.method == 'POST':
            form = DetalleAuditoriaForm(request.POST, instance=detalle)
            if form.is_valid():
                detalle = form.save(commit=False)
                # Calcular diferencia automáticamente
                detalle.diferencia = detalle.conteo_fisico - detalle.cantidad_sistema
                
                # Si hay diferencia, sugerir tipo de discrepancia si no está definido
                if detalle.diferencia != 0 and not detalle.tipo_discrepancia:
                    if detalle.diferencia < 0:
                        detalle.tipo_discrepancia = 'desaparecido'
                    else:
                        detalle.tipo_discrepancia = 'sobrante'
                
                # Marcar como revisado si tiene conteo físico
                if detalle.conteo_fisico >= 0:
                    from django.utils import timezone
                    detalle.revisado = True
                    detalle.fecha_revision = timezone.now()
                
                detalle.save()
                messages.success(request, f'Conteo físico actualizado para {detalle.producto.nombre}')
                return redirect('auditoria_detalle', id=auditoria_id)
        else:
            form = DetalleAuditoriaForm(instance=detalle)
        
        context = {
            'auditoria': auditoria,
            'detalle': detalle,
            'form': form,
        }
        
        # Detectar si es petición AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(request, 'auditoria/editar_detalle_fragment.html', context)
        else:
            return render(request, 'auditoria/editar_detalle.html', context)
    except AuditoriaInventario.DoesNotExist:
        messages.error(request, 'Auditoría no encontrada')
        return redirect('auditoria_lista')
    except DetalleAuditoria.DoesNotExist:
        messages.error(request, 'Detalle de auditoría no encontrado')
        return redirect('auditoria_detalle', id=auditoria_id)


@login_required(login_url='login')
def auditoria_marcar_revisado(request, detalle_id):
    """API para marcar un producto como revisado (AJAX)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        detalle = DetalleAuditoria.objects.get(id=detalle_id)
        if detalle.auditoria.estado != 'en_proceso':
            return JsonResponse({'error': 'La auditoría no está en proceso'}, status=400)
        
        detalle.marcar_revisado()
        
        return JsonResponse({
            'success': True,
            'revisado': detalle.revisado,
            'fecha_revision': detalle.fecha_revision.strftime('%d/%m/%Y %H:%M') if detalle.fecha_revision else None
        })
    except DetalleAuditoria.DoesNotExist:
        return JsonResponse({'error': 'Detalle no encontrado'}, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@login_required(login_url='login')
def auditoria_actualizar_conteo_ajax(request, detalle_id):
    """API AJAX para actualizar el conteo físico de un detalle"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Acceso denegado'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        detalle = DetalleAuditoria.objects.get(id=detalle_id)
        if detalle.auditoria.estado != 'en_proceso':
            return JsonResponse({'error': 'La auditoría no está en proceso'}, status=400)
        
        conteo_fisico = int(request.POST.get('conteo_fisico', 0))
        tipo_discrepancia = request.POST.get('tipo_discrepancia', '')
        observaciones = request.POST.get('observaciones', '')
        
        detalle.conteo_fisico = conteo_fisico
        detalle.diferencia = conteo_fisico - detalle.cantidad_sistema
        
        if tipo_discrepancia:
            detalle.tipo_discrepancia = tipo_discrepancia
        elif detalle.diferencia == 0:
            # Si no hay diferencia, establecer como "sin cambios"
            detalle.tipo_discrepancia = 'sin_cambios'
        elif detalle.diferencia != 0:
            # Auto-sugerir tipo de discrepancia solo si no hay diferencia
            if detalle.diferencia < 0:
                detalle.tipo_discrepancia = 'desaparecido'
            else:
                detalle.tipo_discrepancia = 'sobrante'
        
        if observaciones:
            detalle.observaciones = observaciones
        
        # Marcar como revisado solo si tiene conteo físico mayor a 0
        from django.utils import timezone
        if conteo_fisico > 0:
            detalle.revisado = True
            detalle.fecha_revision = timezone.now()
        
        detalle.save()
        
        return JsonResponse({
            'success': True,
            'diferencia': detalle.diferencia,
            'revisado': detalle.revisado,
            'tipo_discrepancia': detalle.tipo_discrepancia or '',
        })
    except DetalleAuditoria.DoesNotExist:
        return JsonResponse({'error': 'Detalle no encontrado'}, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@login_required(login_url='login')
def auditoria_completar(request, id):
    """Completar una auditoría y actualizar el inventario automáticamente"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        auditoria = AuditoriaInventario.objects.get(id=id)
        if auditoria.estado != 'en_proceso':
            messages.error(request, 'Solo se pueden completar auditorías en proceso')
            return redirect('auditoria_detalle', id=id)
        
        # Verificar que todos los productos estén revisados
        productos_pendientes = auditoria.detalles.filter(revisado=False).count()
        if productos_pendientes > 0:
            messages.warning(request, f'Hay {productos_pendientes} productos pendientes de revisar. ¿Desea completar la auditoría de todas formas?')
            # Permitir completar de todas formas, pero mostrar advertencia
        
        # Actualizar el inventario con los conteos físicos
        with transaction.atomic():
            detalles_actualizados = 0
            productos_actualizados = []
            
            for detalle in auditoria.detalles.all():
                # Solo actualizar si tiene conteo físico (revisado)
                if detalle.revisado and detalle.conteo_fisico is not None:
                    producto = detalle.producto
                    cantidad_anterior = producto.cantidad
                    cantidad_nueva = detalle.conteo_fisico
                    
                    # Actualizar la cantidad del producto con el conteo físico
                    producto.cantidad = cantidad_nueva
                    producto.save()
                    
                    detalles_actualizados += 1
                    productos_actualizados.append({
                        'nombre': producto.nombre,
                        'anterior': cantidad_anterior,
                        'nueva': cantidad_nueva,
                        'diferencia': cantidad_nueva - cantidad_anterior
                    })
            
            # Completar la auditoría
            auditoria.completar()
            
            # Mensaje de éxito con detalles
            if detalles_actualizados > 0:
                mensaje = f'Auditoría #{auditoria.id} completada exitosamente. Se actualizaron {detalles_actualizados} producto(s) en el inventario.'
                messages.success(request, mensaje)
            else:
                messages.success(request, f'Auditoría #{auditoria.id} completada exitosamente. No se actualizó ningún producto (ninguno tenía conteo físico).')
        
        return redirect('auditoria_detalle', id=id)
    except AuditoriaInventario.DoesNotExist:
        messages.error(request, 'Auditoría no encontrada')
        return redirect('auditoria_lista')
    except Exception as e:
        import traceback
        messages.error(request, f'Error al completar la auditoría: {str(e)}')
        print(f"Error en auditoria_completar: {str(e)}")
        print(traceback.format_exc())
        return redirect('auditoria_detalle', id=id)


@login_required(login_url='login')
def auditoria_cancelar(request, id):
    """Cancelar una auditoría"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        auditoria = AuditoriaInventario.objects.get(id=id)
        if auditoria.estado == 'completada':
            messages.error(request, 'No se puede cancelar una auditoría completada')
            return redirect('auditoria_detalle', id=id)
        
        auditoria.estado = 'cancelada'
        auditoria.save()
        messages.success(request, f'Auditoría #{auditoria.id} cancelada')
        return redirect('auditoria_lista')
    except AuditoriaInventario.DoesNotExist:
        messages.error(request, 'Auditoría no encontrada')
        return redirect('auditoria_lista')


@login_required(login_url='login')
def auditoria_eliminar(request, id):
    """Eliminar una auditoría del historial"""
    if not request.user.is_staff:
        messages.error(request, 'Acceso denegado')
        return redirect('inicio')
    
    try:
        auditoria = AuditoriaInventario.objects.get(id=id)
        
        # Solo permitir eliminar auditorías completadas o canceladas (no en proceso)
        if auditoria.estado == 'en_proceso':
            messages.error(request, 'No se puede eliminar una auditoría en proceso. Debe completarla o cancelarla primero.')
            return redirect('auditoria_detalle', id=id)
        
        # Eliminar la auditoría y sus detalles (CASCADE se encarga de los detalles)
        auditoria_id = auditoria.id
        nombre_auditoria = f'Auditoría #{auditoria_id}'
        auditoria.delete()
        
        # Registrar acción en el historial
        registrar_accion_historial(
            accion='eliminado',
            tipo_modelo='auditoria',
            nombre_objeto=nombre_auditoria,
            usuario=request.user,
            descripcion=f'Auditoría eliminada del sistema',
            objeto_id=auditoria_id
        )
        
        messages.success(request, f'Auditoría #{auditoria_id} eliminada exitosamente')
        return redirect('auditoria_lista')
    except AuditoriaInventario.DoesNotExist:
        messages.error(request, 'Auditoría no encontrada')
        return redirect('auditoria_lista')
    except Exception as e:
        import traceback
        messages.error(request, f'Error al eliminar la auditoría: {str(e)}')
        print(f"Error en auditoria_eliminar: {str(e)}")
        print(traceback.format_exc())
        return redirect('auditoria_lista')

