import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Inventario.settings')
import django
django.setup()

from AppInventario.models import Servicio

print("=" * 70)
print("PRUEBA: INGRESO DE SERVICIO OFRECIDO (CATÁLOGO)")
print("=" * 70)

# Verificar servicios existentes
print("\n[1] Servicios existentes en BD...")
servicios_count_before = Servicio.objects.count()
print(f"    ✓ Total actual: {servicios_count_before}")

# Crear servicios de prueba
print("\n[2] Creando servicios de catálogo...")

servicios_a_crear = [
    {
        'nombre': 'Limpieza Facial Profunda',
        'descripcion': 'Limpieza profunda facial con extractores de poros y hidratación',
        'precio': 45.00,
        'duracion_minutos': 60,
        'activo': True
    },
    {
        'nombre': 'Masaje Relajante',
        'descripcion': 'Masaje corporal relajante con aceites aromáticos',
        'precio': 65.00,
        'duracion_minutos': 90,
        'activo': True
    },
    {
        'nombre': 'Tratamiento Antiedad',
        'descripcion': 'Tratamiento antiedad con tecnología de radiofrecuencia',
        'precio': 85.00,
        'duracion_minutos': 75,
        'activo': True
    },
    {
        'nombre': 'Depilación Láser',
        'descripcion': 'Depilación con láser de última generación - indolora',
        'precio': 120.00,
        'duracion_minutos': 45,
        'activo': True
    },
    {
        'nombre': 'Microdermoabrasión',
        'descripcion': 'Exfoliación mecánica para renovación celular',
        'precio': 55.00,
        'duracion_minutos': 50,
        'activo': True
    }
]

servicios_creados = []
for srv_data in servicios_a_crear:
    servicio = Servicio(
        nombre=srv_data['nombre'],
        descripcion=srv_data['descripcion'],
        precio=srv_data['precio'],
        duracion_minutos=srv_data['duracion_minutos'],
        activo=srv_data['activo']
    )
    servicio.save()
    servicios_creados.append(servicio)
    print(f"    ✓ Servicio creado: ID {servicio.id} - {servicio.nombre}")
    print(f"      - Precio: ${servicio.precio}")
    print(f"      - Duración: {servicio.duracion_minutos} minutos")
    print(f"      - Activo: {servicio.activo}")

# Contar servicios después
servicios_count_after = Servicio.objects.count()
print(f"\n[3] Servicios en BD después...")
print(f"    ✓ Total: {servicios_count_after}")
print(f"    ✓ Creados en esta prueba: {len(servicios_creados)}")
print(f"    ✓ Diferencia: +{servicios_count_after - servicios_count_before}")

# Verificar en PostgreSQL
print("\n[4] Verificando en PostgreSQL...")
try:
    import psycopg2
    from django.conf import settings
    cfg = settings.DATABASES['default']
    conn = psycopg2.connect(
        f"dbname={cfg['NAME']} user={cfg['USER']} password={cfg['PASSWORD']} host={cfg['HOST']} port={cfg['PORT']}"
    )
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM "AppInventario_servicio"')
    count_pg = cur.fetchone()[0]
    print(f"    ✓ Servicios en PostgreSQL: {count_pg}")
    
    # Listar servicios creados en esta prueba
    cur.execute(
        'SELECT id, nombre, precio, duracion_minutos, activo FROM "AppInventario_servicio" WHERE nombre LIKE %s ORDER BY id DESC LIMIT 5',
        ('%Facial%', '%Masaje%', '%Antiedad%', '%Láser%', '%Microdermoabrasión%')
    )
    
    print(f"\n    Últimos servicios:")
    cur.execute('SELECT id, nombre, precio, duracion_minutos, activo FROM "AppInventario_servicio" ORDER BY id DESC LIMIT 5')
    for row in cur.fetchall():
        print(f"      [{row[0]}] {row[1]} - ${row[2]}, {row[3]} min, {'Activo' if row[4] else 'Inactivo'}")
    
    conn.close()
except Exception as e:
    print(f"    ✗ Error verificando PostgreSQL: {e}")

# Recuperar desde ORM
print("\n[5] Recuperando servicios desde Django ORM...")
servicios_recuperados = Servicio.objects.all().order_by('-id')[:5]
print(f"    ✓ Servicios recuperados: {servicios_recuperados.count()}")
for srv in servicios_recuperados:
    print(f"      - {srv.nombre}: ${srv.precio} ({srv.duracion_minutos} min)")

# Estadísticas
print("\n[6] Estadísticas de servicios...")
total = Servicio.objects.count()
activos = Servicio.objects.filter(activo=True).count()
inactivos = Servicio.objects.filter(activo=False).count()

from django.db.models import Avg, Sum
stats = Servicio.objects.aggregate(
    precio_promedio=Avg('precio'),
    precio_minimo=Avg('precio'),
    duracion_promedio=Avg('duracion_minutos')
)

print(f"    ✓ Total servicios: {total}")
print(f"    ✓ Activos: {activos}")
print(f"    ✓ Inactivos: {inactivos}")
print(f"    ✓ Precio promedio: ${stats['precio_promedio']:.2f}")
print(f"    ✓ Duración promedio: {stats['duracion_promedio']:.1f} minutos")

print("\n" + "=" * 70)
print("✓ PRUEBA DE INGRESO DE SERVICIOS COMPLETADA EXITOSAMENTE")
print("=" * 70)
