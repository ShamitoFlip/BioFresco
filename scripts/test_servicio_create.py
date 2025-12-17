import os
import sys
import django
from datetime import datetime

# Ajustar ruta del proyecto si es necesario
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventario.settings')
django.setup()

from django.utils import timezone
from AppInventario.models import Servicio, Empleado, ServicioRealizado

# Crear o conseguir un servicio de catálogo de prueba
servicio_obj, _ = Servicio.objects.get_or_create(
    nombre='Servicio de Prueba Automatizado',
    defaults={'precio': 59990}
)

# Crear o conseguir un estilista de prueba
estilista_obj, created = Empleado.objects.get_or_create(
    email='autoprueba_estilista@example.com',
    defaults={'nombre': 'Estilista Prueba'}
)

# Preparar fecha (aware)
dt = datetime(2025, 12, 1, 10, 0)
try:
    aware_dt = timezone.make_aware(dt)
except Exception:
    aware_dt = dt

# Crear ServicioRealizado de prueba
sr = ServicioRealizado.objects.create(
    servicio=servicio_obj,
    fecha_servicio=aware_dt,
    costo=servicio_obj.precio,
    estado='pendiente',
    nombre_cliente='Cliente Prueba',
    email_cliente='cliente.prueba@example.com',
    telefono_cliente='+56912345678',
    estilista=estilista_obj
)

print('CREATED_ID:', sr.id)
print('NOMBRE:', sr.nombre_cliente)
print('EMAIL:', sr.email_cliente)
print('TELEFONO:', sr.telefono_cliente)
print('ESTILISTA_ID:', sr.estilista.id)
print('SERVICIO_ID:', sr.servicio.id)
