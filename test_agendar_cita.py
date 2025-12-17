import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventario.settings')
import django
django.setup()

from AppInventario.models import ServicioRealizado, Servicio, Cliente, Empleado
from datetime import datetime, timedelta

print("=" * 70)
print("PRUEBA: AGENDAR CITA (SERVICIO REALIZADO)")
print("=" * 70)

# Obtener cliente existente
print("\n[1] Buscando cliente...")
try:
    cliente = Cliente.objects.get(rut="18064685-k")
    print(f"    ✓ Cliente encontrado: {cliente.nombre}")
except Cliente.DoesNotExist:
    print(f"    ✗ Cliente no encontrado")
    exit(1)

# Crear un empleado (estilista) para la cita
print("\n[2] Creando empleado/estilista...")
empleado, created = Empleado.objects.get_or_create(
    nombre="María",
    defaults={
        'apellido': 'González',
        'email': 'maria.gonzalez@clinica.cl',
        'telefono': '+56987654321',
        'especialidad': 'Cosmetología y Estética',
        'experiencia_anos': 5,
        'disponibilidad': 'Lun-Vie 9:00-17:00',
        'certificado': True,
        'activo': True,
        'cargo': 'Estilista'
    }
)
if created:
    print(f"    ✓ Empleado creado: {empleado.nombre} ({empleado.cargo})")
else:
    print(f"    ✓ Empleado existente: {empleado.nombre}")

# Obtener servicio
print("\n[3] Seleccionando servicio...")
try:
    servicio = Servicio.objects.get(nombre="Limpieza Facial Profunda")
    print(f"    ✓ Servicio: {servicio.nombre}")
    print(f"      - Precio: ${servicio.precio}")
    print(f"      - Duración: {servicio.duracion_minutos} minutos")
except Servicio.DoesNotExist:
    print(f"    ✗ Servicio no encontrado")
    exit(1)

# Agendar cita
print("\n[4] Agendando cita...")
fecha_cita = datetime.now() + timedelta(days=3)  # 3 días después
hora_cita = "14:30"

cita = ServicioRealizado(
    nombre_cliente=cliente.nombre,
    email_cliente=cliente.email,
    telefono_cliente=cliente.telefono,
    fecha_servicio=fecha_cita.date(),
    hora=hora_cita,
    costo=servicio.precio,
    estado='pendiente',
    servicio=servicio,
    estilista=empleado
)
cita.save()
print(f"    ✓ Cita agendada: ID {cita.id}")
print(f"      - Cliente: {cita.nombre_cliente}")
print(f"      - Servicio: {cita.servicio.nombre}")
print(f"      - Fecha: {cita.fecha_servicio}")
print(f"      - Hora: {cita.hora}")
print(f"      - Estilista: {cita.estilista.nombre}")
print(f"      - Costo: ${cita.costo}")
print(f"      - Estado: {cita.estado}")

# Verificar en BD
print("\n[5] Recuperando cita desde BD...")
cita_recuperada = ServicioRealizado.objects.get(id=cita.id)
print(f"    ✓ Cita encontrada:")
print(f"      - Nombre cliente: {cita_recuperada.nombre_cliente}")
print(f"      - Servicio: {cita_recuperada.servicio.nombre if cita_recuperada.servicio else 'N/A'}")
print(f"      - Estado: {cita_recuperada.estado}")
print(f"      - Registrado: {cita_recuperada.fecha_registro}")

# Cambiar estado de cita
print("\n[6] Actualizando estado de cita...")
print(f"    Estado anterior: {cita.estado}")
cita.estado = 'en_progreso'
cita.save()
print(f"    ✓ Estado actualizado a: {cita.estado}")

cita.estado = 'completado'
cita.save()
print(f"    ✓ Estado final: {cita.estado}")

# Estadísticas
print("\n[7] Estadísticas de citas...")
total_citas = ServicioRealizado.objects.count()
pendientes = ServicioRealizado.objects.filter(estado='pendiente').count()
en_progreso = ServicioRealizado.objects.filter(estado='en_progreso').count()
completadas = ServicioRealizado.objects.filter(estado='completado').count()

print(f"    ✓ Total citas: {total_citas}")
print(f"    ✓ Pendientes: {pendientes}")
print(f"    ✓ En progreso: {en_progreso}")
print(f"    ✓ Completadas: {completadas}")

# Listar citas
print("\n[8] Listando últimas 5 citas...")
citas = ServicioRealizado.objects.order_by('-id')[:5]
for c in citas:
    estado_str = {'pendiente': '⏳', 'en_progreso': '⏸', 'completado': '✓'}[c.estado]
    print(f"    {estado_str} [{c.id}] {c.nombre_cliente} - {c.servicio.nombre if c.servicio else 'N/A'} ({c.fecha_servicio})")

print("\n" + "=" * 70)
print("✓ PRUEBA DE AGENDAR CITA COMPLETADA EXITOSAMENTE")
print("=" * 70)
