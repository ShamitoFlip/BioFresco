import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventario.settings')
import django
django.setup()

from AppInventario.models import Cliente
from django.contrib.auth.models import User

print("=" * 70)
print("PRUEBA: ACTIVACIÓN/SUSPENSIÓN DE CLIENTES")
print("=" * 70)

# Obtener el cliente creado anteriormente
print("\n[1] Obteniendo cliente de prueba...")
try:
    cliente = Cliente.objects.get(rut="18064685-k")
    print(f"    ✓ Cliente encontrado: {cliente.nombre} (ID {cliente.id})")
    print(f"      - RUT: {cliente.rut}")
    print(f"      - Estado actual: {'Activo' if cliente.activo else 'Inactivo'}")
    print(f"      - Usuario vinculado: {cliente.user.username if cliente.user else 'Sin usuario'}")
except Cliente.DoesNotExist:
    print(f"    ✗ Cliente no encontrado")
    exit(1)

# Suspender cliente
print("\n[2] Suspendiendo cliente...")
cliente.activo = False
cliente.save()
if cliente.user:
    cliente.user.is_active = False
    cliente.user.save()
    print(f"    ✓ Cliente suspendido")
    print(f"      - Cliente activo: {cliente.activo}")
    print(f"      - Usuario activo: {cliente.user.is_active}")

# Intentar autenticarse
print("\n[3] Intentando autenticación con cliente suspendido...")
from django.contrib.auth import authenticate
user_auth = authenticate(username=cliente.user.username, password="SeguraContraseña123!")
if user_auth:
    if user_auth.is_active:
        print(f"    ✗ Usuario se autenticó (debería estar inactivo)")
    else:
        print(f"    ✓ Usuario autenticado pero INACTIVO (correcto)")
else:
    print(f"    ✓ Autenticación rechazada correctamente")

# Reactivar cliente
print("\n[4] Reactivando cliente...")
cliente.activo = True
cliente.save()
if cliente.user:
    cliente.user.is_active = True
    cliente.user.save()
    print(f"    ✓ Cliente reactivado")
    print(f"      - Cliente activo: {cliente.activo}")
    print(f"      - Usuario activo: {cliente.user.is_active}")

# Intentar autenticarse nuevamente
print("\n[5] Probando autenticación con cliente reactivado...")
user_auth = authenticate(username=cliente.user.username, password="SeguraContraseña123!")
if user_auth and user_auth.is_active:
    print(f"    ✓ Autenticación exitosa")
    print(f"      - Usuario: {user_auth.username}")
    print(f"      - Activo: {user_auth.is_active}")
else:
    print(f"    ✗ Autenticación fallida")

# Estadísticas finales
print("\n[6] Estadísticas de clientes...")
total = Cliente.objects.count()
activos = Cliente.objects.filter(activo=True).count()
inactivos = Cliente.objects.filter(activo=False).count()
print(f"    ✓ Total: {total}")
print(f"    ✓ Activos: {activos}")
print(f"    ✓ Inactivos: {inactivos}")

print("\n" + "=" * 70)
print("✓ PRUEBA DE ACTIVACIÓN/SUSPENSIÓN COMPLETADA")
print("=" * 70)
