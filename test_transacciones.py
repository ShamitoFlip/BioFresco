import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventario.settings')
import django
django.setup()

from AppInventario.models import Producto
from django.db import transaction

print("=" * 70)
print("PRUEBA AVANZADA: TRANSACCIONES Y MANEJO DE ERRORES")
print("=" * 70)

# ===== TRANSACCIÓN EXITOSA =====
print("\n[1] Transacción exitosa (múltiples productos)...")
try:
    with transaction.atomic():
        p1 = Producto(nombre="Producto TX1", cantidad=10, precio=15.00)
        p1.save()
        
        p2 = Producto(nombre="Producto TX2", cantidad=20, precio=25.00)
        p2.save()
        
        p3 = Producto(nombre="Producto TX3", cantidad=30, precio=35.00)
        p3.save()
    
    print(f"    ✓ Transacción exitosa: 3 productos creados")
    print(f"    IDs: {p1.id}, {p2.id}, {p3.id}")
except Exception as e:
    print(f"    ✗ Error: {e}")

# ===== TRANSACCIÓN CON ROLLBACK =====
print("\n[2] Transacción con rollback (error intencional)...")
count_before = Producto.objects.count()
try:
    with transaction.atomic():
        p_error = Producto(nombre="Producto Fallido", cantidad=5, precio=10.00)
        p_error.save()
        print(f"    - Producto creado con ID {p_error.id}")
        
        # Forzar error: intentar asignar precio inválido
        raise ValueError("Error intencional para prueba de rollback")
except ValueError as e:
    print(f"    ✓ Error capturado (esperado): {e}")
except Exception as e:
    print(f"    ! Error inesperado: {e}")

count_after = Producto.objects.count()
if count_before == count_after:
    print(f"    ✓ Rollback exitoso: BD sin cambios (antes: {count_before}, después: {count_after})")
else:
    print(f"    ✗ Error: datos se guardaron aunque hubo error (antes: {count_before}, después: {count_after})")

# ===== VALIDACIÓN DE DATOS =====
print("\n[3] Validación de datos...")
all_productos = Producto.objects.all()
print(f"    ✓ Total de productos: {all_productos.count()}")

# Verificar que todos tienen precio > 0
invalid = all_productos.filter(precio__lte=0)
if invalid.exists():
    print(f"    ✗ {invalid.count()} producto(s) con precio <= 0")
else:
    print(f"    ✓ Todos los productos tienen precio válido")

# ===== ESTADÍSTICAS =====
print("\n[4] Estadísticas de productos...")
from django.db.models import Sum, Avg, Count

stats = Producto.objects.aggregate(
    total_productos=Count('id'),
    stock_total=Sum('cantidad'),
    precio_promedio=Avg('precio'),
    precio_minimo=Avg('precio')
)

print(f"    ✓ Total de productos: {stats['total_productos']}")
print(f"    ✓ Stock total: {stats['stock_total']} unidades")
print(f"    ✓ Precio promedio: ${stats['precio_promedio']:.2f}")

# ===== CONEXIÓN A BD =====
print("\n[5] Verificación de conexión a PostgreSQL...")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        if 'PostgreSQL' in version:
            print(f"    ✓ Conectado a PostgreSQL")
            print(f"    Version: {version.split(',')[0]}")
        else:
            print(f"    ✗ No es PostgreSQL: {version}")
except Exception as e:
    print(f"    ✗ Error de conexión: {e}")

# ===== SUMMARY =====
print("\n" + "=" * 70)
print("✓ PRUEBAS AVANZADAS COMPLETADAS")
print("=" * 70)
