/**
 * Admin AJAX Navigation - BioFresco
 * Maneja la navegación AJAX en el panel de administración
 */

(function($) {
    'use strict';

    const CONFIG = {
        contentSelector: '#main-content-area',
        navSelector: '#main-navigation, .admin-nav',
        linkSelector: '.nav-link-ajax',
        activeClass: 'active',
        ajaxHeader: 'X-Requested-With',
        ajaxHeaderValue: 'XMLHttpRequest'
    };

    /**
     * Inicialización
     */
    $(document).ready(function() {
        // Inicializar dropdowns PRIMERO para que tengan prioridad
        initDropdownMenus();
        initAjaxNavigation();
        handleBrowserBackForward();
        initProfileDropdown();
        initNavToggle();
        initAvatarUpload();
    });

    /**
     * Inicializa la navegación AJAX
     */
    function initAjaxNavigation() {
        // Interceptar clics en enlaces de navegación
        // Excluir enlaces dropdown para que no interfieran
        $(CONFIG.navSelector).on('click', CONFIG.linkSelector + ':not(.nav-link-dropdown)', function(e) {
            e.preventDefault();
            
            const $link = $(this);
            const url = $link.data('url') || $link.attr('href');
            
            // Ignorar enlaces vacíos
            if (!url || url === '#' || url === '') {
                return;
            }

            // Cargar contenido vía AJAX
            loadContent(url, $link);
        });

        // Interceptar clics en botones internos con clase ajax-link
        $(CONFIG.contentSelector).on('click', 'a.ajax-link', function(e) {
            e.preventDefault();
            const $link = $(this);
            const url = $link.data('url') || $link.attr('href');
            if (url && url !== '#') {
                loadContent(url, null);
            }
        });
    }

    /**
     * Carga contenido vía AJAX
     */
    function loadContent(url, $activeLink) {
        const $contentArea = $(CONFIG.contentSelector);
        
        // Mostrar indicador de carga
        showLoading($contentArea);
        
        // Actualizar clase activa en navegación
        if ($activeLink) {
            updateActiveLink($activeLink);
        }

        // Realizar petición AJAX
        $.ajax({
            url: url,
            type: 'GET',
            headers: {
                [CONFIG.ajaxHeader]: CONFIG.ajaxHeaderValue
            },
            dataType: 'html',
            success: function(response) {
                hideLoading($contentArea);
                
                // Inyectar nuevo contenido
                $contentArea.html(response);
                
                // Actualizar URL en el navegador
                updateBrowserUrl(url);
                
                // Reinicializar scripts
                reinitializeScripts();
                
                // Actualizar dropdowns
                updateDropdowns();
                
                // Scroll al inicio
                window.scrollTo({ top: 0, behavior: 'smooth' });
            },
            error: function(xhr, status, error) {
                hideLoading($contentArea);
                showError('Error al cargar el contenido. Por favor, intenta nuevamente.');
                console.error('AJAX Error:', error);
            }
        });
    }

    /**
     * Muestra indicador de carga
     */
    function showLoading($container) {
        const loadingHtml = `
            <div class="ajax-loading">
                <div class="spinner-border text-success" role="status">
                    <span class="visually-hidden">Cargando...</span>
                </div>
                <p>Cargando contenido...</p>
            </div>
        `;
        $container.html(loadingHtml);
    }

    /**
     * Oculta indicador de carga
     */
    function hideLoading($container) {
        $container.find('.ajax-loading').remove();
    }

    /**
     * Actualiza el enlace activo en la navegación
     */
    function updateActiveLink($activeLink) {
        // Remover clase activa de todos los enlaces
        $(CONFIG.navSelector).find(CONFIG.linkSelector).removeClass(CONFIG.activeClass);
        
        // Agregar clase activa al enlace actual
        $activeLink.addClass(CONFIG.activeClass);
    }

    /**
     * Actualiza la URL del navegador usando History API
     */
    function updateBrowserUrl(url) {
        if (window.history && window.history.pushState) {
            window.history.pushState({url: url}, '', url);
        }
    }

    /**
     * Maneja los botones de atrás/adelante del navegador
     */
    function handleBrowserBackForward() {
        $(window).on('popstate', function(e) {
            if (e.originalEvent.state && e.originalEvent.state.url) {
                loadContent(e.originalEvent.state.url, null);
            } else {
                window.location.reload();
            }
        });
    }

    /**
     * Inicializa los menús desplegables
     */
    function initDropdownMenus() {
        // Usar delegación de eventos directamente en document para máxima compatibilidad
        $(document).off('click', '.nav-link-dropdown').on('click', '.nav-link-dropdown', function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            
            const $link = $(this);
            const $dropdown = $link.closest('.nav-item-dropdown');
            
            if ($dropdown.length === 0) {
                console.error('Dropdown container not found');
                return false;
            }
            
            // Cerrar otros dropdowns
            $('.nav-item-dropdown').not($dropdown).removeClass('open');
            
            // Toggle del dropdown actual
            const isCurrentlyOpen = $dropdown.hasClass('open');
            $dropdown.toggleClass('open');
            
            // Debug
            console.log('Dropdown toggled:', {
                isOpen: !isCurrentlyOpen,
                dropdown: $dropdown[0],
                submenu: $dropdown.find('.nav-submenu').length
            });
            
            return false;
        });

        // Prevenir que los clics en submenú cierren el dropdown
        $(document).off('click', '.nav-submenu-link').on('click', '.nav-submenu-link', function(e) {
            e.stopPropagation();
            // Permitir que el AJAX funcione normalmente
        });

        // Cerrar dropdown al hacer clic fuera
        $(document).off('click.dropdown').on('click.dropdown', function(e) {
            if (!$(e.target).closest('.nav-item-dropdown').length) {
                $('.nav-item-dropdown').removeClass('open');
            }
        });

        // Abrir dropdown si hay un enlace activo dentro
        function checkActiveDropdowns() {
            $('.nav-item-dropdown').each(function() {
                const $dropdown = $(this);
                const hasActive = $dropdown.find('.nav-submenu-link.active').length > 0;
                if (hasActive) {
                    $dropdown.addClass('open');
                }
            });
        }
        
        // Verificar al cargar (con múltiples intentos para asegurar que el DOM esté listo)
        setTimeout(checkActiveDropdowns, 50);
        setTimeout(checkActiveDropdowns, 200);
        setTimeout(checkActiveDropdowns, 500);
        
        // Verificar después de cargar contenido AJAX
        $(document).on('contentLoaded', function() {
            setTimeout(checkActiveDropdowns, 100);
        });
    }

    /**
     * Actualiza el estado de los dropdowns después de cargar contenido
     */
    function updateDropdowns() {
        $('.nav-item-dropdown').each(function() {
            const $dropdown = $(this);
            if ($dropdown.find('.nav-submenu-link.active').length > 0) {
                $dropdown.addClass('open');
            }
        });
    }

    /**
     * Reinicializa scripts después de cargar contenido AJAX
     */
    function reinitializeScripts() {
        // Reinicializar tooltips de Bootstrap
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function(tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }

        // Reinicializar popovers de Bootstrap
        if (typeof bootstrap !== 'undefined' && bootstrap.Popover) {
            const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
            popoverTriggerList.map(function(popoverTriggerEl) {
                return new bootstrap.Popover(popoverTriggerEl);
            });
        }

        // Disparar evento personalizado
        $(document).trigger('contentLoaded');
    }

    /**
     * Muestra mensaje de error
     */
    function showError(message) {
        const errorHtml = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        $(CONFIG.contentSelector).prepend(errorHtml);
    }

    /**
     * Inicializa el acordeón del perfil de usuario
     */
    function initProfileDropdown() {
        const $accordion = $('#user-info-accordion');
        const $header = $('#user-info-header');
        const $dropdownBtn = $('#profile-dropdown-btn');
        const $details = $('#user-info-details');

        if ($accordion.length && $header.length && $dropdownBtn.length) {
            // Event listener en el header completo y en el botón de flecha
            $header.on('click', function(e) {
                // No expandir si se hace clic en el avatar (tiene su propio handler)
                if ($(e.target).closest('#profile-avatar, .profile-avatar-overlay').length) {
                    return;
                }
                e.stopPropagation();
                toggleUserAccordion();
            });

            $dropdownBtn.on('click', function(e) {
                e.stopPropagation();
                toggleUserAccordion();
            });

            function toggleUserAccordion() {
                $accordion.toggleClass('expanded');
                
                // Guardar estado en localStorage
                const isExpanded = $accordion.hasClass('expanded');
                localStorage.setItem('user-info-expanded', isExpanded);
            }

            // Restaurar estado guardado
            const savedState = localStorage.getItem('user-info-expanded');
            if (savedState === 'true') {
                $accordion.addClass('expanded');
            }

            // Manejar botón de editar perfil
            $('#edit-profile-btn').on('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                // Redirigir a la página de edición de perfil
                window.location.href = '/estilistas/editar-mi-perfil/';
            });
        }
    }

    /**
     * Inicializa el toggle de navegación
     */
    function initNavToggle() {
        const $navToggle = $('#nav-toggle');
        const $navLinks = $('#nav-links-container');

        if ($navToggle.length && $navLinks.length) {
            // Guardar estado en localStorage
            const savedState = localStorage.getItem('nav-collapsed');
            if (savedState === 'true') {
                $navToggle.addClass('collapsed');
            }

            $navToggle.on('click', function() {
                $navToggle.toggleClass('collapsed');
                localStorage.setItem('nav-collapsed', $navToggle.hasClass('collapsed'));
            });
        }
    }

    /**
     * Obtiene el valor de una cookie
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /**
     * Inicializa la subida de avatar
     */
    function initAvatarUpload() {
        const $avatar = $('#profile-avatar');
        const $avatarUpload = $('#avatar-upload');
        const $avatarImg = $('#avatar-img');

        if ($avatar.length && $avatarUpload.length) {
            $avatar.on('click', function(e) {
                e.stopPropagation(); // Prevenir que active el acordeón
                $avatarUpload.click();
            });

            $avatarUpload.on('change', function(e) {
                const file = e.target.files[0];
                if (file) {
                    // Validar tipo de archivo
                    if (!file.type.startsWith('image/')) {
                        alert('Por favor, selecciona una imagen válida.');
                        return;
                    }

                    // Validar tamaño (max 5MB)
                    if (file.size > 5 * 1024 * 1024) {
                        alert('La imagen debe ser menor a 5MB.');
                        return;
                    }

                    // Mostrar preview inmediato
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        $avatarImg.attr('src', e.target.result);
                    };
                    reader.readAsDataURL(file);

                    // Subir archivo al servidor
                    const formData = new FormData();
                    formData.append('avatar', file);
                    
                    // Obtener CSRF token
                    let csrfToken = typeof csrftoken !== 'undefined' ? csrftoken : '';
                    if (!csrfToken) {
                        // Intentar obtener del cookie
                        csrfToken = getCookie('csrftoken');
                    }
                    if (!csrfToken) {
                        // Intentar obtener del meta tag
                        const metaToken = $('meta[name=csrf-token]').attr('content');
                        if (metaToken) csrfToken = metaToken;
                    }

                    // Mostrar indicador de carga
                    const originalOverlay = $avatar.find('.profile-avatar-overlay').html();
                    $avatar.find('.profile-avatar-overlay').html('<i class="fas fa-spinner fa-spin"></i><span>Subiendo...</span>');

                    $.ajax({
                        url: '/admin/upload-avatar/',
                        type: 'POST',
                        data: formData,
                        processData: false,
                        contentType: false,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': csrfToken
                        },
                        beforeSend: function(xhr) {
                            if (csrfToken) {
                                xhr.setRequestHeader('X-CSRFToken', csrfToken);
                            }
                        },
                        success: function(response) {
                            if (response && response.success) {
                                // Actualizar imagen con la URL del servidor
                                if (response.avatar_url) {
                                    $avatarImg.attr('src', response.avatar_url + '?t=' + new Date().getTime());
                                }
                                // Mostrar mensaje de éxito
                                $avatar.find('.profile-avatar-overlay').html('<i class="fas fa-check"></i><span>¡Actualizado!</span>');
                                setTimeout(function() {
                                    $avatar.find('.profile-avatar-overlay').html(originalOverlay);
                                }, 2000);
                            } else {
                                const errorMsg = (response && response.message) ? response.message : 'Error desconocido al subir la imagen';
                                alert('Error: ' + errorMsg);
                                $avatar.find('.profile-avatar-overlay').html(originalOverlay);
                            }
                        },
                        error: function(xhr) {
                            let errorMsg = 'Error al subir la imagen. Por favor, intenta nuevamente.';
                            if (xhr.responseJSON && xhr.responseJSON.message) {
                                errorMsg = xhr.responseJSON.message;
                            } else if (xhr.responseText) {
                                try {
                                    const response = JSON.parse(xhr.responseText);
                                    if (response.message) {
                                        errorMsg = response.message;
                                    }
                                } catch (e) {
                                    console.error('Error parsing response:', e);
                                }
                            }
                            console.error('Error uploading avatar:', xhr.status, xhr.responseText);
                            alert(errorMsg);
                            $avatar.find('.profile-avatar-overlay').html(originalOverlay);
                            // No restaurar imagen anterior, mantener el preview
                        }
                    });
                }
            });
        }
    }

    /**
     * API Pública
     */
    window.AdminAjax = {
        loadContent: function(url, callback) {
            const $contentArea = $(CONFIG.contentSelector);
            showLoading($contentArea);
            
            $.ajax({
                url: url,
                type: 'GET',
                headers: {
                    [CONFIG.ajaxHeader]: CONFIG.ajaxHeaderValue
                },
                dataType: 'html',
                success: function(response) {
                    hideLoading($contentArea);
                    $contentArea.html(response);
                    updateBrowserUrl(url);
                    reinitializeScripts();
                    updateDropdowns();
                    if (callback && typeof callback === 'function') {
                        callback(response);
                    }
                },
                error: function(xhr, status, error) {
                    hideLoading($contentArea);
                    showError('Error al cargar el contenido.');
                    if (callback && typeof callback === 'function') {
                        callback(null, error);
                    }
                }
            });
        }
    };

})(jQuery);

