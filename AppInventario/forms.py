from django import forms
from .models import Producto, Compras, ProductoProveedor, EntradaInventario, SolicitudCompra, Zona
from .models import Empleado, Servicio, AuditoriaInventario, DetalleAuditoria
from django.contrib.auth.models import User
from django import forms as django_forms
from django.core.exceptions import ValidationError



class ProductoForm(forms.ModelForm):
    tipo_producto = forms.ChoiceField(
        choices=[
            ('propio', 'Producto Propio (Producido por la empresa)'),
            ('proveedor', 'Producto de Proveedor'),
        ],
        initial='propio',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Tipo de Producto',
        required=True
    )
    
    proveedor_seleccionado = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='-- Seleccione un proveedor --',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_proveedor_seleccionado'}),
        label='Proveedor',
        help_text='Primero seleccione el proveedor'
    )
    
    producto_proveedor = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='-- Seleccione un producto --',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_producto_proveedor', 'disabled': True}),
        label='Producto de Proveedor',
        help_text='Seleccione un producto del proveedor seleccionado'
    )
    
    class Meta:
        model = Producto
        fields = ['nombre', 'tipo_producto', 'producto_proveedor', 'categoria', 'cantidad', 'precio', 'stock_minimo', 'costo_promedio_actual', 'proveedor_habitual', 'descripcion', 'imagen', 'unidad_medida', 'zona', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto', 'id': 'id_nombre_producto'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0', 'min': '0'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0', 'min': '0', 'step': '1'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '10', 'min': '0'}),
            'costo_promedio_actual': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'min': '0', 'step': '0.01'}),
            'proveedor_habitual': forms.Select(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Descripción del producto'}),
            'imagen': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'zona': forms.Select(attrs={'class': 'form-control', 'id': 'id_zona_select'}),
        }
        error_messages = {
            'nombre': {
                'required': 'El nombre del producto es obligatorio',
            },
            'cantidad': {
                'required': 'La cantidad en stock es obligatoria',
            },
            'precio': {
                'required': 'El precio es obligatorio',
            },
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar proveedores
        from .models import Proveedores, ProductoProveedor
        self.fields['proveedor_seleccionado'].queryset = Proveedores.objects.all().order_by('nombre')
        
        # Cargar zonas activas
        self.fields['zona'].queryset = Zona.objects.filter(activo=True).order_by('nombre')
        self.fields['zona'].empty_label = '-- Seleccione una zona --'
        self.fields['zona'].required = False
        
        # Si es un POST, cargar productos del proveedor seleccionado o incluir el producto seleccionado
        if self.data:
            proveedor_id = self.data.get('proveedor_seleccionado')
            producto_proveedor_id = self.data.get('producto_proveedor')
            
            if proveedor_id:
                try:
                    proveedor = Proveedores.objects.get(id=proveedor_id)
                    # Cargar productos del proveedor seleccionado
                    queryset = ProductoProveedor.objects.filter(
                        proveedor=proveedor,
                        activo=True
                    ).order_by('nombre')
                    
                    # Si hay un producto_proveedor seleccionado, asegurarse de que esté en el queryset
                    if producto_proveedor_id:
                        try:
                            producto_seleccionado = ProductoProveedor.objects.get(id=producto_proveedor_id)
                            # Si el producto no está en el queryset, agregarlo
                            if producto_seleccionado not in queryset:
                                queryset = ProductoProveedor.objects.filter(
                                    id=producto_proveedor_id
                                ) | queryset
                        except ProductoProveedor.DoesNotExist:
                            pass
                    
                    self.fields['producto_proveedor'].queryset = queryset
                except Proveedores.DoesNotExist:
                    # Si el proveedor no existe pero hay un producto_proveedor, cargar solo ese producto
                    if producto_proveedor_id:
                        try:
                            self.fields['producto_proveedor'].queryset = ProductoProveedor.objects.filter(
                                id=producto_proveedor_id,
                                activo=True
                            )
                        except:
                            self.fields['producto_proveedor'].queryset = ProductoProveedor.objects.none()
                    else:
                        self.fields['producto_proveedor'].queryset = ProductoProveedor.objects.none()
            elif producto_proveedor_id:
                # Si hay un producto_proveedor seleccionado pero no hay proveedor, cargar solo ese producto
                try:
                    self.fields['producto_proveedor'].queryset = ProductoProveedor.objects.filter(
                        id=producto_proveedor_id,
                        activo=True
                    )
                except:
                    self.fields['producto_proveedor'].queryset = ProductoProveedor.objects.none()
            else:
                # Inicialmente no hay productos (se cargarán según el proveedor seleccionado)
                self.fields['producto_proveedor'].queryset = ProductoProveedor.objects.none()
        else:
            # Inicialmente no hay productos (se cargarán según el proveedor seleccionado)
            self.fields['producto_proveedor'].queryset = ProductoProveedor.objects.none()
        
        # Si es una instancia existente, determinar el tipo de producto
        if self.instance and self.instance.pk:
            # Usar los nuevos campos del modelo
            if self.instance.tipo_producto == 'proveedor' and self.instance.producto_proveedor:
                self.fields['tipo_producto'].initial = 'proveedor'
                self.fields['proveedor_seleccionado'].initial = self.instance.producto_proveedor.proveedor.id
                # Cargar productos del proveedor
                self.fields['producto_proveedor'].queryset = ProductoProveedor.objects.filter(
                    proveedor=self.instance.producto_proveedor.proveedor, 
                    activo=True
                ).order_by('nombre')
                self.fields['producto_proveedor'].initial = self.instance.producto_proveedor.id
                self.fields['producto_proveedor'].widget.attrs['disabled'] = False
            else:
                self.fields['tipo_producto'].initial = 'propio'
        
        # Asegurar que los campos requeridos tengan mensajes de error personalizados en español
        if 'nombre' in self.fields:
            # El nombre será opcional si viene de proveedor
            self.fields['nombre'].required = False
            self.fields['nombre'].error_messages = self.fields['nombre'].error_messages.copy()
            self.fields['nombre'].error_messages['required'] = 'El nombre del producto es obligatorio'
        if 'cantidad' in self.fields:
            self.fields['cantidad'].required = True
            self.fields['cantidad'].error_messages = self.fields['cantidad'].error_messages.copy()
            self.fields['cantidad'].error_messages['required'] = 'La cantidad en stock es obligatoria'
        if 'precio' in self.fields:
            self.fields['precio'].required = True
            self.fields['precio'].error_messages = self.fields['precio'].error_messages.copy()
            self.fields['precio'].error_messages['required'] = 'El precio es obligatorio'
        # Hacer stock_minimo y costo_promedio_actual opcionales (tienen valores por defecto en el modelo)
        if 'stock_minimo' in self.fields:
            self.fields['stock_minimo'].required = False
        if 'costo_promedio_actual' in self.fields:
            self.fields['costo_promedio_actual'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        tipo_producto = cleaned_data.get('tipo_producto', 'propio')
        proveedor_seleccionado = cleaned_data.get('proveedor_seleccionado')
        producto_proveedor = cleaned_data.get('producto_proveedor')
        nombre = cleaned_data.get('nombre', '').strip() if cleaned_data.get('nombre') else ''
        
        # Establecer valores por defecto si no se proporcionan
        if 'stock_minimo' not in cleaned_data or cleaned_data.get('stock_minimo') is None:
            cleaned_data['stock_minimo'] = 10  # Valor por defecto del modelo
        if 'costo_promedio_actual' not in cleaned_data or cleaned_data.get('costo_promedio_actual') is None:
            cleaned_data['costo_promedio_actual'] = 0  # Valor por defecto del modelo
        
        # Validar según el tipo de producto
        if tipo_producto == 'proveedor':
            if not proveedor_seleccionado:
                raise forms.ValidationError({
                    'proveedor_seleccionado': 'Debe seleccionar un proveedor'
                })
            if not producto_proveedor:
                raise forms.ValidationError({
                    'producto_proveedor': 'Debe seleccionar un producto del proveedor'
                })
            
            # Validar que no exista ya un producto activo con el mismo producto_proveedor
            if producto_proveedor:
                # Obtener el ID del producto actual si estamos editando
                producto_actual_id = None
                if self.instance and self.instance.pk:
                    producto_actual_id = self.instance.pk
                
                # Buscar si ya existe un producto activo con el mismo producto_proveedor
                from .models import Producto
                producto_existente = Producto.objects.filter(
                    producto_proveedor=producto_proveedor,
                    tipo_producto='proveedor',
                    activo=True
                ).exclude(pk=producto_actual_id).first()
                
                if producto_existente:
                    raise forms.ValidationError({
                        'producto_proveedor': f'Ya existe un producto activo en el inventario para "{producto_proveedor.nombre}". No se pueden crear productos duplicados del mismo proveedor.'
                    })
                
                # Si viene de proveedor, usar el nombre del producto de proveedor
                cleaned_data['nombre'] = producto_proveedor.nombre
                cleaned_data['proveedor_habitual'] = producto_proveedor.proveedor
                # Auto-completar descripción y costo si no están llenos
                if not cleaned_data.get('descripcion') and producto_proveedor.descripcion:
                    cleaned_data['descripcion'] = producto_proveedor.descripcion
                if (not cleaned_data.get('costo_promedio_actual') or cleaned_data.get('costo_promedio_actual') == 0) and producto_proveedor.precio_compra_actual:
                    cleaned_data['costo_promedio_actual'] = producto_proveedor.precio_compra_actual
        else:
            # Si es producto propio, el nombre es obligatorio
            if not nombre:
                raise forms.ValidationError({
                    'nombre': 'El nombre del producto es obligatorio para productos propios'
                })
            cleaned_data['nombre'] = nombre
        
        # Asegurar que siempre haya un nombre
        if not cleaned_data.get('nombre'):
            raise forms.ValidationError({
                'nombre': 'El nombre del producto es obligatorio'
            })
        
        return cleaned_data
    
    def save(self, commit=True):
        # Guardar el producto con los nuevos campos
        producto = super().save(commit=False)
        
        # Obtener datos del cleaned_data
        tipo_producto = self.cleaned_data.get('tipo_producto', 'propio')
        producto_proveedor = self.cleaned_data.get('producto_proveedor')
        proveedor_seleccionado = self.cleaned_data.get('proveedor_seleccionado')
        
        # Asegurar que tipo_producto siempre tenga un valor
        if not tipo_producto:
            tipo_producto = 'propio'
        
        # Asignar tipo_producto y producto_proveedor al modelo
        producto.tipo_producto = tipo_producto
        
        # Asegurar que el producto esté activo por defecto
        producto.activo = True
        
        if tipo_producto == 'proveedor' and producto_proveedor:
            producto.producto_proveedor = producto_proveedor
            producto.proveedor_habitual = producto_proveedor.proveedor
            # Asegurar que el nombre esté asignado
            if not producto.nombre:
                producto.nombre = producto_proveedor.nombre
            # Auto-completar descripción y costo desde producto_proveedor si no están llenos
            if not producto.descripcion and producto_proveedor.descripcion:
                producto.descripcion = producto_proveedor.descripcion
            if (not producto.costo_promedio_actual or producto.costo_promedio_actual == 0) and producto_proveedor.precio_compra_actual:
                producto.costo_promedio_actual = producto_proveedor.precio_compra_actual
            
            # Calcular cantidad automáticamente desde las entradas si el producto ya existe
            if producto.pk:
                cantidad_calculada = producto.calcular_cantidad_desde_entradas()
                producto.cantidad = cantidad_calculada
            else:
                # Si es un producto nuevo, la cantidad inicial será 0 (se actualizará cuando haya entradas)
                producto.cantidad = 0
        else:
            producto.producto_proveedor = None
            producto.tipo_producto = 'propio'
            if proveedor_seleccionado:
                producto.proveedor_habitual = proveedor_seleccionado
        
        if commit:
            producto.save()
            # Si viene de proveedor, asociar el ProductoProveedor con este Producto
            if tipo_producto == 'proveedor' and producto_proveedor:
                producto_proveedor.producto = producto
                producto_proveedor.save()
            
            # Si es producto de proveedor, recalcular cantidad después de guardar
            if tipo_producto == 'proveedor':
                cantidad_calculada = producto.calcular_cantidad_desde_entradas()
                if producto.cantidad != cantidad_calculada:
                    producto.cantidad = cantidad_calculada
                    producto.save(update_fields=['cantidad'])
        
        return producto


class ProductoProveedorForm(forms.ModelForm):
    class Meta:
        model = ProductoProveedor
        fields = '__all__'
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-control'}),
            'producto': forms.Select(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción del producto'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01', 'min': '0'}),
            'precio_compra_actual': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01', 'min': '0'}),
            'unidad_medida': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: kg, unidades, cajas'}),
            'codigo_producto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código único del producto'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'proveedor': 'Proveedor',
            'producto': 'Producto del Inventario (Opcional)',
            'nombre': 'Nombre del Producto',
            'descripcion': 'Descripción',
            'precio_unitario': 'Precio Unitario',
            'precio_compra_actual': 'Precio de Compra Actual',
            'unidad_medida': 'Unidad de Medida',
            'codigo_producto': 'Código del Producto',
            'activo': 'Activo',
        }


class EntradaInventarioForm(forms.ModelForm):
    class Meta:
        model = EntradaInventario
        fields = ['producto', 'proveedor', 'cantidad', 'precio_unitario', 'numero_factura', 'observaciones']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-control', 'id': 'id_producto_entrada'}),
            'proveedor': forms.Select(attrs={'class': 'form-control', 'id': 'id_proveedor_entrada'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Cantidad'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00', 'id': 'id_precio_unitario_entrada'}),
            'numero_factura': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de factura (opcional)'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones (opcional)'}),
        }
        labels = {
            'producto': 'Producto',
            'proveedor': 'Proveedor',
            'cantidad': 'Cantidad',
            'precio_unitario': 'Precio Unitario',
            'numero_factura': 'Número de Factura',
            'observaciones': 'Observaciones',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar productos activos
        self.fields['producto'].queryset = Producto.objects.filter(activo=True).order_by('nombre')
        # Si hay una instancia, filtrar productos por proveedor si existe
        if self.instance and self.instance.pk and self.instance.proveedor:
            self.fields['producto'].queryset = Producto.objects.filter(
                activo=True,
                proveedor_habitual=self.instance.proveedor
            ).order_by('nombre')


class ComprasForm(forms.ModelForm):
    tipo_producto = forms.ChoiceField(
        choices=[('propio', 'Producto Propio'), ('proveedor', 'Producto de Proveedor')],
        required=True,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
            'id': 'tipo-producto'
        }),
        label='Tipo de Producto',
        initial='propio'
    )
    
    proveedor = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Seleccione un proveedor",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_proveedor_compra'
        }),
        label='Proveedor'
    )
    
    producto = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Seleccione un producto",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_producto_compra'
        }),
        label='Producto Propio'
    )
    
    producto_proveedor = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Seleccione un producto de proveedor",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_producto_proveedor_compra'
        }),
        label='Producto de Proveedor'
    )
    
    nombre_cliente = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Juan Pérez'
        }),
        error_messages={'required': 'El nombre es obligatorio'}
    )
    email_cliente = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: correo@gmail.com'
        }),
        error_messages={'required': 'El correo electrónico es obligatorio'}
    )
    
    def clean_email_cliente(self):
        """Validar que el email sea Gmail"""
        email = self.cleaned_data.get('email_cliente')
        if not email:
            return email
        
        email_lower = email.lower().strip()
        if not email_lower.endswith('@gmail.com'):
            raise forms.ValidationError('Solo se permiten direcciones de correo de Gmail (@gmail.com)')
        
        return email_lower
    telefono_cliente = forms.CharField(
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 123456789'
        }),
        error_messages={'required': 'El teléfono es obligatorio'}
    )
    direccion_cliente = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa tu dirección completa',
            'rows': 3
        }),
        error_messages={'required': 'La dirección es obligatoria'}
    )
    ciudad_cliente = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: Santiago'
        }),
        error_messages={'required': 'La ciudad es obligatoria'}
    )
    
    class Meta:
        model = Compras
        fields = ['tipo_producto', 'proveedor', 'producto', 'producto_proveedor', 'cantidad', 'precio_unitario', 'nombre_cliente', 'email_cliente', 'telefono_cliente', 'direccion_cliente', 'ciudad_cliente']
        labels = {
            'cantidad': 'Cantidad',
            'precio_unitario': 'Precio Unitario',
            'nombre_cliente': 'Nombre Completo',
            'email_cliente': 'Correo Electrónico',
            'telefono_cliente': 'Teléfono',
            'direccion_cliente': 'Dirección',
            'ciudad_cliente': 'Ciudad'
        }
        widgets = {
            'cantidad': forms.NumberInput(attrs={
                'min': 1, 
                'class': 'form-control',
                'id': 'cantidad-input',
                'placeholder': 'Ingresa la cantidad'
            }),
            'precio_unitario': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'class': 'form-control',
                'id': 'precio-unitario-input',
                'placeholder': '0.00'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from AppInventario.models import Producto, ProductoProveedor, Proveedores
        
        self.fields['producto'].queryset = Producto.objects.all().order_by('nombre')
        self.fields['producto_proveedor'].queryset = ProductoProveedor.objects.filter(activo=True).order_by('proveedor__nombre', 'nombre')
        self.fields['proveedor'].queryset = Proveedores.objects.all().order_by('nombre')


class EmpleadoForm(forms.ModelForm):
    # nuevo campo cargo como ModelChoice
    cargo = forms.ModelChoiceField(queryset=None, required=False, empty_label="-- Sin cargo --")
    
    # Campos para crear usuario de Django
    crear_usuario = forms.BooleanField(
        required=False,
        initial=False,
        label='Crear usuario',
        help_text='Crear usuario con acceso al sistema para este empleado'
    )
    username = forms.CharField(
        max_length=150,
        required=False,
        help_text='Nombre de usuario para iniciar sesión (opcional)',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        required=False,
        help_text='Contraseña para el usuario (opcional, mínimo 8 caracteres)',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        min_length=8
    )
    password_confirm = forms.CharField(
        required=False,
        help_text='Confirma la contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from .models import Cargo
            self.fields['cargo'].queryset = Cargo.objects.filter(activo=True)
        except Exception:
            if 'cargo' in self.fields:
                self.fields['cargo'].widget = forms.HiddenInput()
                self.fields['cargo'].required = False
        
        # Asegurar que el campo foto sea opcional
        if 'foto' in self.fields:
            self.fields['foto'].required = False
        
        # Ocultar campos de especialidades si existen
        if 'especialidades' in self.fields:
            self.fields['especialidades'].widget = forms.HiddenInput()
            self.fields['especialidades'].required = False
        if 'especialidad' in self.fields:
            self.fields['especialidad'].widget = forms.HiddenInput()
            self.fields['especialidad'].required = False
    
    def clean_email(self):
        """Validar que el email sea Gmail y no esté en uso por otro empleado"""
        email = self.cleaned_data.get('email')
        if not email:
            return email
        
        # Validar que sea Gmail
        email_lower = email.lower().strip()
        if not email_lower.endswith('@gmail.com'):
            raise forms.ValidationError('Solo se permiten direcciones de correo de Gmail (@gmail.com)')
        
        # Verificar si el email ya está en uso por otro empleado
        from .models import Empleado
        empleados_con_email = Empleado.objects.filter(email=email_lower)
        
        # Si estamos editando, excluir el empleado actual
        if self.instance.pk:
            empleados_con_email = empleados_con_email.exclude(pk=self.instance.pk)
        
        if empleados_con_email.exists():
            raise forms.ValidationError('Este correo electrónico ya está registrado por otro empleado')
        
        return email_lower
    
    def clean(self):
        """Validar campos de usuario y contraseña"""
        cleaned_data = super().clean()
        crear_usuario = cleaned_data.get('crear_usuario')
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        email = cleaned_data.get('email')
        
        if crear_usuario:
            if not username or not username.strip():
                raise forms.ValidationError('El nombre de usuario es obligatorio si deseas crear un usuario')
            
            from django.contrib.auth.models import User
            
            # En modo edición, si el usuario ya existe, la contraseña es opcional
            if self.instance.pk and hasattr(self.instance, 'user') and self.instance.user:
                # Modo edición con usuario existente: contraseña opcional
                if password:
                    if len(password) < 8:
                        raise forms.ValidationError('La contraseña debe tener al menos 8 caracteres')
                    if password != password_confirm:
                        raise forms.ValidationError('Las contraseñas no coinciden')
                # Verificar si otro usuario tiene ese username
                if User.objects.filter(username=username).exclude(id=self.instance.user.id).exists():
                    raise forms.ValidationError('Este nombre de usuario ya está en uso')
            else:
                # Modo creación o edición sin usuario existente: contraseña obligatoria
                if not password or len(password) < 8:
                    raise forms.ValidationError('La contraseña es obligatoria y debe tener al menos 8 caracteres')
                if password != password_confirm:
                    raise forms.ValidationError('Las contraseñas no coinciden')
                
                # Verificar si el username ya existe
                if self.instance.pk:
                    # Modo edición sin usuario: verificar si otro usuario tiene ese username
                    if User.objects.filter(username=username).exists():
                        raise forms.ValidationError('Este nombre de usuario ya está en uso')
                else:
                    # Modo creación: verificar si el username existe
                    if User.objects.filter(username=username).exists():
                        raise forms.ValidationError('Este nombre de usuario ya está en uso')
            
            # Verificar si el email ya está en uso por otro usuario de Django
            # (esto es adicional a la validación de clean_email que verifica Empleado)
            if email:
                user_id_to_exclude = None
                if self.instance.pk and hasattr(self.instance, 'user') and self.instance.user:
                    user_id_to_exclude = self.instance.user.id
                if User.objects.filter(email=email).exclude(id=user_id_to_exclude).exists():
                    raise forms.ValidationError('Este correo electrónico ya está registrado como usuario en el sistema')
        
        return cleaned_data
    
    class Meta:
        model = Empleado
        fields = ['nombre', 'apellido', 'email', 'telefono', 'experiencia_anos', 'disponibilidad', 'certificado', 'fecha_contrato', 'sueldo', 'activo', 'cargo', 'foto']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Juan'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Pérez'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Ej: juan.perez@gmail.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 56912345678', 'pattern': '[0-9]*', 'inputmode': 'numeric', 'onkeypress': 'return event.charCode >= 48 && event.charCode <= 57'}),
            'sueldo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Ej: 500000'}),
            'especialidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Especialidad legacy (opcional)'}),
            'experiencia_anos': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Ej: 5'}),
            'disponibilidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Lunes a Viernes 9:00-18:00'}),
            'fecha_contrato': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'certificado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'foto': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # quitamos widget de 'cargo' aquí porque ahora es ModelChoiceField fuera de widgets
        }
        labels = {
            'especialidades': 'Especialidades',
            'especialidad': 'Especialidad (legacy)',
        }
        help_texts = {
            'especialidad': 'Campo legacy para compatibilidad. Se recomienda usar el campo Especialidades arriba.',
        }


class ServicioForm(forms.ModelForm):
    especialidades_requeridas = forms.ModelMultipleChoiceField(
        queryset=None,  # Se inicializará en __init__
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text='Selecciona las especialidades requeridas para realizar este servicio. Solo los empleados con estas especialidades podrán ser asignados a este servicio.'
    )
    
    class Meta:
        model = Servicio
        fields = ['nombre', 'descripcion', 'precio', 'duracion_minutos', 'imagen', 'activo', 'especialidades_requeridas']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'duracion_minutos': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'imagen': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from .models import Especialidad
            self.fields['especialidades_requeridas'].queryset = Especialidad.objects.filter(activo=True).order_by('nombre')
            # Si estamos editando, establecer las especialidades seleccionadas
            if self.instance and self.instance.pk:
                self.fields['especialidades_requeridas'].initial = self.instance.especialidades_requeridas.all()
        except Exception:
            pass


class SolicitudCompraForm(forms.ModelForm):
    class Meta:
        model = SolicitudCompra
        fields = ['producto', 'proveedor', 'cantidad', 'precio_unitario', 'observaciones']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-control', 'id': 'id_producto_solicitud'}),
            'proveedor': forms.Select(attrs={'class': 'form-control', 'id': 'id_proveedor_solicitud'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Cantidad a solicitar'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00', 'id': 'id_precio_unitario'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Observaciones (opcional)'}),
        }
        labels = {
            'producto': 'Producto',
            'proveedor': 'Proveedor',
            'cantidad': 'Cantidad Solicitada',
            'precio_unitario': 'Precio Unitario',
            'observaciones': 'Observaciones',
        }


class VerificacionRecepcionForm(forms.ModelForm):
    class Meta:
        model = SolicitudCompra
        fields = ['cantidad_recibida', 'precio_final', 'numero_factura']
        widgets = {
            'cantidad_recibida': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Cantidad recibida'}),
            'precio_final': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'numero_factura': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de factura (opcional)'}),
        }
        labels = {
            'cantidad_recibida': 'Cantidad Recibida',
            'precio_final': 'Precio Final',
            'numero_factura': 'Número de Factura',
        }




class AuditoriaInventarioForm(forms.ModelForm):
    class Meta:
        model = AuditoriaInventario
        fields = ['observaciones_generales']  # fecha_auditoria se establece automáticamente
        widgets = {
            'observaciones_generales': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Observaciones generales sobre la auditoría (opcional)'
            }),
        }
        labels = {
            'observaciones_generales': 'Observaciones Generales',
        }


class DetalleAuditoriaForm(forms.ModelForm):
    class Meta:
        model = DetalleAuditoria
        fields = ['conteo_fisico', 'tipo_discrepancia', 'observaciones', 'revisado']
        widgets = {
            'conteo_fisico': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'required': True
            }),
            'tipo_discrepancia': forms.Select(attrs={
                'class': 'form-control'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Observaciones sobre la discrepancia (opcional)'
            }),
            'revisado': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'conteo_fisico': 'Conteo Físico',
            'tipo_discrepancia': 'Tipo de Discrepancia',
            'observaciones': 'Observaciones',
            'revisado': 'Revisado',
        }

