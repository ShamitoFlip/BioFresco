import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventario.settings')
import django
django.setup()

from AppInventario.models import Cliente
from django.contrib.auth.models import User
from django.db import transaction

print("=" * 70)
print("PRUEBA: REGISTRO DE CLIENTE CON CUENTA DE USUARIO")
print("=" * 70)

# Datos del cliente
rut_test = "18064685-k"
nombre_test = "Juan Pérez"
email_test = "juan.perez@example.com"
telefono_test = "+56912345678"
direccion_test = "Calle Principal 123, Apartamento 4"
ciudad_test = "Santiago"
password_test = "SeguraContraseña123!"

print(f"\n[1] Verificando si el cliente ya existe...")
cliente_existe = Cliente.objects.filter(rut=rut_test).exists()
if cliente_existe:
    print(f"    ⚠ Cliente con RUT {rut_test} ya existe en BD")
    cliente_anterior = Cliente.objects.get(rut=rut_test)
    print(f"    Eliminando cliente anterior (ID {cliente_anterior.id})...")
    if cliente_anterior.user:
        cliente_anterior.user.delete()
    cliente_anterior.delete()
    print(f"    ✓ Cliente anterior eliminado")
else:
    print(f"    ✓ RUT {rut_test} disponible")

print(f"\n[2] Creando usuario de Django...")
try:
    with transaction.atomic():
        # Crear usuario
        username = email_test  # Usar email como username
        user = User.objects.create_user(
            username=username,
            email=email_test,
            password=password_test,
            first_name=nombre_test.split()[0],
            last_name=nombre_test.split()[-1] if len(nombre_test.split()) > 1 else ""
        )
        print(f"    ✓ Usuario creado: username={username}")
        print(f"      - Email: {user.email}")
        print(f"      - Nombre: {user.first_name} {user.last_name}")
        
        print(f"\n[3] Creando cliente vinculado al usuario...")
        cliente = Cliente.objects.create(
            user=user,
            nombre=nombre_test,
            rut=rut_test,
            email=email_test,
            telefono=telefono_test,
            direccion=direccion_test,
            ciudad=ciudad_test,
            activo=True
        )
        print(f"    ✓ Cliente creado: ID={cliente.id}")
        print(f"      - Nombre: {cliente.nombre}")
        print(f"      - RUT: {cliente.rut}")
        print(f"      - Email: {cliente.email}")
        print(f"      - Teléfono: {cliente.telefono}")
        print(f"      - Dirección: {cliente.direccion}")
        print(f"      - Ciudad: {cliente.ciudad}")
        print(f"      - Activo: {cliente.activo}")
        print(f"      - Usuario vinculado: {cliente.user.username if cliente.user else 'N/A'}")
        
except Exception as e:
    print(f"    ✗ Error al crear cliente: {e}")
    exit(1)

print(f"\n[4] Validando registro en BD...")
# Recuperar desde BD
cliente_recuperado = Cliente.objects.get(rut=rut_test)
print(f"    ✓ Cliente recuperado de BD:")
print(f"      - ID: {cliente_recuperado.id}")
print(f"      - Nombre: {cliente_recuperado.nombre}")
print(f"      - RUT: {cliente_recuperado.rut}")
print(f"      - Estado: {'Activo' if cliente_recuperado.activo else 'Inactivo'}")

# Verificar usuario vinculado
if cliente_recuperado.user:
    print(f"      - Usuario: {cliente_recuperado.user.username}")
    print(f"      - Email usuario: {cliente_recuperado.user.email}")
else:
    print(f"      - Usuario: No vinculado")

print(f"\n[5] Probando autenticación...")
from django.contrib.auth import authenticate
user_auth = authenticate(username=username, password=password_test)
if user_auth:
    print(f"    ✓ Autenticación exitosa")
    print(f"      - Usuario autenticado: {user_auth.username}")
    print(f"      - Es staff: {user_auth.is_staff}")
    print(f"      - Es superuser: {user_auth.is_superuser}")
else:
    print(f"    ✗ Autenticación fallida")

print(f"\n[6] Estadísticas de clientes...")
total_clientes = Cliente.objects.count()
clientes_activos = Cliente.objects.filter(activo=True).count()
clientes_inactivos = Cliente.objects.filter(activo=False).count()
print(f"    ✓ Total de clientes: {total_clientes}")
print(f"      - Activos: {clientes_activos}")
print(f"      - Inactivos: {clientes_inactivos}")

print(f"\n[7] Listando últimos 5 clientes...")
ultimos = Cliente.objects.order_by('-fecha_registro')[:5]
for c in ultimos:
    estado = "✓ Activo" if c.activo else "✗ Inactivo"
    print(f"    [{c.id}] {c.nombre} ({c.rut}) - {estado}")

print("\n" + "=" * 70)
print("✓ PRUEBA DE REGISTRO DE CLIENTE COMPLETADA EXITOSAMENTE")
print("=" * 70)
