import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventario.settings')
import django
django.setup()

from AppInventario.models import Producto, Cliente, Servicio, Empleado, ServicioRealizado, Compras
from django.utils import timezone
from datetime import datetime, timedelta

print("=" * 80)
print("LOGS DE INGRESOS REALIZADOS HOY")
print("=" * 80)

# Obtener la fecha de hoy
hoy = timezone.now().date()
print(f"\nFecha: {hoy.strftime('%d de %B de %Y')}")
print(f"Hora actual: {timezone.now().strftime('%H:%M:%S')}")

# ===== PRODUCTOS =====
print("\n" + "=" * 80)
print("📦 PRODUCTOS EN BASE DE DATOS")
print("=" * 80)
productos = Producto.objects.all().order_by('id')

if productos.exists():
    print(f"\nTotal: {productos.count()}")
    for idx, p in enumerate(productos, 1):
        print(f"\n[{idx}] ID: {p.id}")
        print(f"    Nombre: {p.nombre}")
        print(f"    Cantidad: {p.cantidad} unidades")
        print(f"    Precio: ${p.precio}")
        print(f"    Descripción: {p.descripcion or 'N/A'}")
else:
    print("\n✗ No hay productos")

# ===== CLIENTES =====
print("\n" + "=" * 80)
print("👤 CLIENTES REGISTRADOS")
print("=" * 80)
clientes = Cliente.objects.all().order_by('fecha_registro')

if clientes.exists():
    print(f"\nTotal: {clientes.count()}")
    for idx, c in enumerate(clientes, 1):
        print(f"\n[{idx}] ID: {c.id}")
        print(f"    Nombre: {c.nombre}")
        print(f"    RUT: {c.rut}")
        print(f"    Email: {c.email}")
        print(f"    Teléfono: {c.telefono}")
        print(f"    Ciudad: {c.ciudad}")
        print(f"    Estado: {'✓ Activo' if c.activo else '✗ Inactivo'}")
        print(f"    Usuario: {c.user.username if c.user else 'Sin usuario'}")
        print(f"    Registrado: {c.fecha_registro.strftime('%d/%m/%Y %H:%M:%S')}")
else:
    print("\n✗ No hay clientes registrados")

# ===== SERVICIOS =====
print("\n" + "=" * 80)
print("🛎️  SERVICIOS DISPONIBLES (CATÁLOGO)")
print("=" * 80)
servicios = Servicio.objects.all().order_by('fecha_creacion')

if servicios.exists():
    print(f"\nTotal: {servicios.count()}")
    for idx, s in enumerate(servicios, 1):
        print(f"\n[{idx}] ID: {s.id}")
        print(f"    Nombre: {s.nombre}")
        print(f"    Precio: ${s.precio}")
        print(f"    Duración: {s.duracion_minutos} minutos" if s.duracion_minutos else "    Duración: N/A")
        print(f"    Descripción: {s.descripcion or 'N/A'}")
        print(f"    Estado: {'✓ Activo' if s.activo else '✗ Inactivo'}")
        print(f"    Creado: {s.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S')}")
else:
    print("\n✗ No hay servicios registrados")

# ===== EMPLEADOS =====
print("\n" + "=" * 80)
print("👨‍💼 EMPLEADOS/ESTILISTAS")
print("=" * 80)
empleados = Empleado.objects.all().order_by('fecha_creacion')

if empleados.exists():
    print(f"\nTotal: {empleados.count()}")
    for idx, e in enumerate(empleados, 1):
        print(f"\n[{idx}] ID: {e.id}")
        print(f"    Nombre: {e.nombre} {e.apellido or ''}")
        print(f"    Email: {e.email}")
        print(f"    Cargo: {e.cargo or 'N/A'}")
        print(f"    Especialidad: {e.especialidad or 'N/A'}")
        print(f"    Experiencia: {e.experiencia_anos} años")
        print(f"    Estado: {'✓ Activo' if e.activo else '✗ Inactivo'}")
        print(f"    Registrado: {e.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S')}")
else:
    print("\n✗ No hay empleados registrados")

# ===== CITAS AGENDADAS =====
print("\n" + "=" * 80)
print("📅 CITAS AGENDADAS")
print("=" * 80)
citas = ServicioRealizado.objects.all().order_by('fecha_registro')

if citas.exists():
    print(f"\nTotal: {citas.count()}")
    for idx, cita in enumerate(citas, 1):
        estado_icon = {'pendiente': '⏳', 'en_progreso': '⏸', 'completado': '✓'}[cita.estado]
        print(f"\n[{idx}] {estado_icon} ID: {cita.id}")
        print(f"    Cliente: {cita.nombre_cliente}")
        print(f"    Email: {cita.email_cliente}")
        print(f"    Servicio: {cita.servicio.nombre if cita.servicio else 'N/A'}")
        print(f"    Estilista: {cita.estilista.nombre if cita.estilista else 'N/A'}")
        print(f"    Fecha de cita: {cita.fecha_servicio}")
        print(f"    Hora: {cita.hora or 'N/A'}")
        print(f"    Costo: ${cita.costo}")
        print(f"    Estado: {cita.estado}")
        print(f"    Registrada: {cita.fecha_registro.strftime('%d/%m/%Y %H:%M:%S')}")
else:
    print("\n✗ No hay citas agendadas")

# ===== COMPRAS =====
print("\n" + "=" * 80)
print("🛒 COMPRAS REALIZADAS")
print("=" * 80)
compras = Compras.objects.all().order_by('fecha_compra')

if compras.exists():
    print(f"\nTotal: {compras.count()}")
    total_ventas = 0
    for idx, comp in enumerate(compras, 1):
        subtotal = comp.cantidad * comp.precio_unitario
        total_ventas += subtotal
        print(f"\n[{idx}] ID: {comp.id}")
        print(f"    Producto: {comp.producto.nombre}")
        print(f"    Cantidad: {comp.cantidad}")
        print(f"    Precio unitario: ${comp.precio_unitario}")
        print(f"    Subtotal: ${subtotal}")
        print(f"    Cliente: {comp.nombre_cliente or 'N/A'}")
        print(f"    Email: {comp.email_cliente or 'N/A'}")
        print(f"    Fecha compra: {comp.fecha_compra.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"\n    💰 TOTAL EN VENTAS: ${total_ventas}")
else:
    print("\n✗ No hay compras registradas")

# ===== RESUMEN TOTAL =====
print("\n" + "=" * 80)
print("📊 RESUMEN TOTAL DE REGISTROS")
print("=" * 80)

total_registros = (
    productos.count() +
    clientes.count() +
    servicios.count() +
    empleados.count() +
    citas.count() +
    compras.count()
)

print(f"\n✓ Productos:        {productos.count()}")
print(f"✓ Clientes:         {clientes.count()}")
print(f"✓ Servicios:        {servicios.count()}")
print(f"✓ Empleados:        {empleados.count()}")
print(f"✓ Citas agendadas:  {citas.count()}")
print(f"✓ Compras:          {compras.count()}")
print(f"\n{'='*80}")
print(f"TOTAL REGISTROS:    {total_registros}")
print(f"{'='*80}\n")
