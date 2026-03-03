/**
 * tours-catalog.js
 * Sistema de catálogo de tours con filtros, búsqueda y paginación
 */

// Estado global del catálogo
let catalogState = {
    currentPage: 1,
    perPage: 12,
    totalPages: 1,
    totalTours: 0,
    filters: {
        search: '',
        continente: '',
        pais: '',
        proveedor: '',
        precio_max: 5000,
        duracion_min: 1,
        duracion_max: 30,
        tipo: '',
        categoria: ''
    },
    sort: 'relevancia'
};

// Debounce helper para búsqueda
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Inicializar catálogo en carga de página
 */
function initCatalogo() {
    console.log('🚀 Inicializando catálogo de tours...');

    // Presets por página (ej: cruceros/ofertas)
    const preset = window.TOURS_CATALOG_PRESET || {};
    if (preset.search) catalogState.filters.search = String(preset.search);
    if (preset.sort) catalogState.sort = String(preset.sort);
    if (preset.precio_max) {
        const parsedPrecio = parseInt(preset.precio_max, 10);
        if (!Number.isNaN(parsedPrecio) && parsedPrecio > 0) {
            catalogState.filters.precio_max = parsedPrecio;
        }
    }

    // Configurar event listeners de filtros
    setupFiltros();

    // Configurar búsqueda con debounce
    const searchInput = document.getElementById('search-tours');
    if (searchInput) {
        searchInput.value = catalogState.filters.search || '';
        searchInput.addEventListener('input', debounce(function (e) {
            catalogState.filters.search = e.target.value;
            catalogState.currentPage = 1; // Reset a página 1
            cargarTours();
        }, 300));
    }

    // Configurar ordenamiento
    const sortSelect = document.getElementById('sort-tours');
    if (sortSelect) {
        if (catalogState.sort) sortSelect.value = catalogState.sort;
        sortSelect.addEventListener('change', function (e) {
            catalogState.sort = e.target.value;
            catalogState.currentPage = 1;
            cargarTours();
        });
    }

    // Configurar slider de precio
    const precioSlider = document.getElementById('precio-slider');
    if (precioSlider) {
        const maxFromDom = parseInt(precioSlider.max, 10) || catalogState.filters.precio_max || 5000;
        if (catalogState.filters.precio_max > maxFromDom) {
            catalogState.filters.precio_max = maxFromDom;
        }
        precioSlider.value = catalogState.filters.precio_max;
        const precioDisplay = document.getElementById('precio-display');
        if (precioDisplay) precioDisplay.textContent = String(catalogState.filters.precio_max);

        precioSlider.addEventListener('input', debounce(function (e) {
            catalogState.filters.precio_max = parseInt(e.target.value);
            document.getElementById('precio-display').textContent = e.target.value;
            catalogState.currentPage = 1;
            cargarTours();
        }, 500));
    }

    // Cargar tours iniciales
    cargarTours();

    // Comprobar si hay un tour específico en la URL para abrir modal
    const urlParams = new URLSearchParams(window.location.search);
    const tourIdParam = urlParams.get('tour_id');
    if (tourIdParam) {
        console.log(`🔗 Enlace directo a tour: ${tourIdParam}`);
        // Esperar un poco a que cargue la página base o hacerlo directamente
        setTimeout(() => verTourDetalle(tourIdParam), 500);
    }
}

/**
 * Configurar event listeners de filtros
 */
function setupFiltros() {
    // Checkboxes de continente
    document.querySelectorAll('.filtro-continente').forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            // Solo permitir un continente a la vez
            document.querySelectorAll('.filtro-continente').forEach(cb => {
                if (cb !== this) cb.checked = false;
            });
            catalogState.filters.continente = this.checked ? this.value : '';
            catalogState.currentPage = 1;
            cargarTours();
        });
    });

    // Select de proveedor
    const proveedorSelect = document.getElementById('filtro-proveedor');
    if (proveedorSelect) {
        proveedorSelect.addEventListener('change', function () {
            catalogState.filters.proveedor = this.value;
            catalogState.currentPage = 1;
            cargarTours();
        });
    }

    // Checkboxes de tipo de viaje
    document.querySelectorAll('.filtro-tipo').forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            // Solo permitir un tipo a la vez
            document.querySelectorAll('.filtro-tipo').forEach(cb => {
                if (cb !== this) cb.checked = false;
            });
            catalogState.filters.tipo = this.checked ? this.value : '';
            catalogState.currentPage = 1;
            cargarTours();
        });
    });

    // Rangos de duración
    const duracionInputs = document.querySelectorAll('input[name="duracion"]');
    duracionInputs.forEach(radio => {
        radio.addEventListener('change', function () {
            const [min, max] = this.value.split('-').map(Number);
            catalogState.filters.duracion_min = min;
            catalogState.filters.duracion_max = max || 999;
            catalogState.currentPage = 1;
            cargarTours();
        });
    });
}

/**
 * Cargar tours desde API
 */
async function cargarTours() {
    try {
        // Mostrar loading
        document.getElementById('tours-container').innerHTML = `
            <div class="loading-spinner">
                <div class="spinner"></div>
                <p>Buscando tours perfectos para ti...</p>
            </div>
        `;

        // Construir query params
        const params = new URLSearchParams();
        params.append('page', catalogState.currentPage);
        params.append('per_page', catalogState.perPage);
        params.append('sort', catalogState.sort);

        // Añadir filtros activos
        Object.keys(catalogState.filters).forEach(key => {
            const value = catalogState.filters[key];
            if (value && value !== '') {
                params.append(key, value);
            }
        });

        console.log(`📡 Cargando tours: /api/tours/buscar?${params.toString()}`);

        const response = await fetch(`/api/tours/buscar?${params.toString()}`);
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        // Actualizar estado
        catalogState.totalTours = data.total;
        catalogState.totalPages = data.total_pages;
        catalogState.currentPage = data.page;

        // Renderizar tours
        renderizarTours(data.tours);

        // Actualizar paginación
        renderizarPaginacion();

        // Actualizar contador de resultados
        document.getElementById('results-count').textContent =
            `Mostrando ${data.tours.length} de ${data.total} tours`;

        // ❌ DESACTIVADO: Evitar scroll automático al cargar la página
        // document.getElementById('tours-container').scrollIntoView({
        //     behavior: 'smooth',
        //     block: 'start'
        // });

    } catch (error) {
        console.error('Error cargando tours:', error);
        document.getElementById('tours-container').innerHTML = `
            <div class="error-message">
                <h3>😔 Ops, algo salió mal</h3>
                <p>No pudimos cargar los tours. Por favor, intenta de nuevo.</p>
                <button onclick="cargarTours()" class="btn-retry">Reintentar</button>
            </div>
        `;
    }
}

/**
 * Renderizar lista de tours
 */
function renderizarTours(tours) {
    const container = document.getElementById('tours-container');

    if (tours.length === 0) {
        container.innerHTML = `
            <div class="no-results">
                <h3>🔍 No encontramos tours</h3>
                <p>Intenta ajustar tus filtros o realiza una búsqueda diferente.</p>
                <button onclick="resetearFiltros()" class="btn-reset">
                    🔄 Limpiar Filtros
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = tours.map(tour => `
        <article class="tour-card" onclick="verTourDetalle(${tour.id})" data-aos="fade-up">
            <div class="tour-image">
                <img src="${tour.imagen_url || 'https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=800&q=80'}" 
                     alt="${tour.titulo}"
                     class="tour-card-image"
                     loading="lazy"
                     onerror="this.onerror=null;this.src='https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=800&q=80'">
                ${tour.destacado ? '<span class="badge-destacado">⭐ TOP</span>' : ''}

            </div>
            
            <div class="tour-body">
                <h3 class="tour-title">${tour.titulo}</h3>
                
                <div class="tour-meta">
                    ${tour.destino ? `<span>📍 ${tour.destino}</span>` : ''}
                    ${tour.duracion_dias ? `<span>⏱️ ${tour.duracion_dias} días</span>` : ''}
                    ${tour.tipo_viaje ? `<span>🎯 ${tour.tipo_viaje}</span>` : ''}
                </div>
                
                <p class="tour-description">${truncarTexto(tour.descripcion, 100)}</p>
                
                <div class="tour-footer">
                    <div class="tour-price">
                        <small>Desde</small>
                        <strong>${tour.precio_desde}€</strong>
                        <small>/persona</small>
                    </div>
                    <button class="btn-ver-tour">
                        VER DETALLES →
                    </button>
                </div>
            </div>
        </article>
    `).join('');
}

/**
 * Renderizar controles de paginación
 */
function renderizarPaginacion() {
    const container = document.getElementById('pagination-container');
    if (!container) return;

    let html = '';

    // Botón primera página
    if (catalogState.currentPage > 1) {
        html += `<button onclick="cambiarPagina(1)" class="btn-page">« Primera</button>`;
        html += `<button onclick="cambiarPagina(${catalogState.currentPage - 1})" class="btn-page">‹ Anterior</button>`;
    }

    // Números de página (mostrar 5 alrededor de la actual)
    const start = Math.max(1, catalogState.currentPage - 2);
    const end = Math.min(catalogState.totalPages, catalogState.currentPage + 2);

    for (let i = start; i <= end; i++) {
        const activeClass = i === catalogState.currentPage ? 'active' : '';
        html += `<button onclick="cambiarPagina(${i})" class="btn-page ${activeClass}">${i}</button>`;
    }

    // Botón última página
    if (catalogState.currentPage < catalogState.totalPages) {
        html += `<button onclick="cambiarPagina(${catalogState.currentPage + 1})" class="btn-page">Siguiente ›</button>`;
        html += `<button onclick="cambiarPagina(${catalogState.totalPages})" class="btn-page">Última »</button>`;
    }

    container.innerHTML = html;
}

/**
 * Cambiar página de resultados
 */
function cambiarPagina(page) {
    catalogState.currentPage = page;
    cargarTours();
}

/**
 * Resetear todos los filtros
 */
function resetearFiltros() {
    const precioSlider = document.getElementById('precio-slider');
    const maxPriceFromDom = precioSlider ? (parseInt(precioSlider.max, 10) || 5000) : 5000;

    // Limpiar estado
    catalogState.filters = {
        search: '',
        continente: '',
        pais: '',
        proveedor: '',
        precio_max: maxPriceFromDom,
        duracion_min: 1,
        duracion_max: 30,
        tipo: '',
        categoria: ''
    };
    catalogState.currentPage = 1;
    catalogState.sort = 'relevancia';

    // Limpiar UI
    document.getElementById('search-tours').value = '';
    document.querySelectorAll('.filtro-continente, .filtro-tipo').forEach(cb => cb.checked = false);
    const proveedorSelect = document.getElementById('filtro-proveedor');
    if (proveedorSelect) proveedorSelect.value = '';

    const sortSelect = document.getElementById('sort-tours');
    if (sortSelect) sortSelect.value = 'relevancia';

    if (precioSlider) {
        precioSlider.value = String(maxPriceFromDom);
        document.getElementById('precio-display').textContent = String(maxPriceFromDom);
    }

    // Recargar
    cargarTours();
}

/**
 * Ver detalles completos de un tour (modal)
 */
async function verTourDetalle(tourId) {
    try {
        // Abrir modal
        const modal = document.getElementById('modal-tour-detalle');
        if (!modal) {
            console.error('Modal no encontrado');
            return;
        }

        modal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Mostrar loading en modal
        document.getElementById('modal-content').innerHTML = `
            <div class="loading-spinner">
                <div class="spinner"></div>
                <p>Cargando detalles...</p>
            </div>
        `;

        // Fetch detalles completos
        const response = await fetch(`/api/tours/${tourId}/completo`);
        const tour = await response.json();

        if (tour.error) {
            throw new Error(tour.error);
        }

        // Renderizar contenido completo
        renderizarModalDetalle(tour);

    } catch (error) {
        console.error('Error cargando detalle:', error);
        document.getElementById('modal-content').innerHTML = `
            <div class="error-message">
                <p>Error cargando detalles del tour</p>
            </div>
        `;
    }
}

// Helpers para renderizado modal
function formatearLista(jsonStr, titulo, clase) {
    if (!jsonStr) return '';
    try {
        let items = jsonStr;
        // Si es string, intentar parsear
        if (typeof jsonStr === 'string') {
            // Caso especial: string "[]" vacío
            if (jsonStr.trim() === '[]') return '';

            try {
                items = JSON.parse(jsonStr);
            } catch (e) {
                // Si falla parseo, es texto plano - dividir por frases
                const frases = jsonStr
                    .split('.')
                    .map(f => f.trim())
                    .filter(f => f.length > 0);

                return `
                    <div class="${clase}">
                        <h2>${titulo}</h2>
                        <ul>
                            ${frases.map(frase => `<li>${frase}</li>`).join('')}
                        </ul>
                    </div>
                `;
            }
        }

        // Si es array vacío
        if (Array.isArray(items) && items.length === 0) return '';

        // Si es array con cosas
        if (Array.isArray(items)) {
            return `
                <div class="${clase}">
                    <h2>${titulo}</h2>
                    <ul class="lista-check">
                        ${items.map(item => `<li>${item}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        return '';
    } catch (e) {
        console.error("Error formateando lista:", e);
        return '';
    }
}

function renderizarItinerario(itinerarioStr) {
    if (!itinerarioStr) return '';
    if (itinerarioStr === '[]') return '';

    try {
        let dias = [];

        // Intentar parsear como JSON primero (formato antiguo)
        if (itinerarioStr.startsWith('[') || itinerarioStr.startsWith('{')) {
            try {
                const itinerario = JSON.parse(itinerarioStr);
                if (Array.isArray(itinerario) && itinerario.length > 0) {
                    dias = itinerario.map((dia, index) => {
                        let contenido = '';
                        if (typeof dia === 'string') {
                            contenido = dia;
                        } else if (typeof dia === 'object') {
                            contenido = dia.descripcion || dia.contenido || dia.titulo || dia.text || JSON.stringify(dia);
                        }
                        return {
                            numero: index + 1,
                            titulo: dia.titulo || `Día ${index + 1}`,
                            contenido: contenido
                        };
                    });
                }
            } catch (e) {
                // Si falla, intentar como texto plano
            }
        }

        // Si no es JSON o falló, procesar como texto plano (formato Saraya PDF)
        if (dias.length === 0) {
            // Dividir por "Día X" manteniendo el patrón
            const textoLimpio = itinerarioStr.trim();
            const partes = textoLimpio.split(/(?=Día \d+)/i);

            partes.forEach(parte => {
                parte = parte.trim();
                if (!parte) return;

                // Extraer "Día X - TITULO"
                const match = parte.match(/^Día (\d+)[:\-\s]+([^\n]+)\n?([\s\S]*)/i);
                if (match) {
                    const [, numero, titulo, contenido] = match;
                    dias.push({
                        numero: parseInt(numero),
                        titulo: titulo.trim(),
                        contenido: contenido.trim()
                    });
                }
            });
        }

        if (dias.length === 0) return '';

        return `
            <div class="tour-itinerario">
                <h2>📅 Itinerario Detallado</h2>
                <div class="timeline-itinerario">
                ${dias.map(dia => `
                    <div class="itinerario-dia">
                        <div class="dia-badge">Día ${dia.numero}</div>
                        <div class="dia-content">
                            <h3>${dia.titulo}</h3>
                            <p>${dia.contenido}</p>
                        </div>
                    </div>
                `).join('')}
                </div>
            </div>
        `;
    } catch (e) {
        console.error("Error renderizando itinerario:", e);
        return '';
    }
}

/**
 * Renderizar contenido del modal de detalles
 */
function renderizarModalDetalle(tour) {

    const html = `
        <button class="modal-close" onclick="cerrarModal()">&times;</button>
        
        <div class="modal-header">
            <img src="${tour.imagen_url || 'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=800&q=80'}" alt="${tour.titulo}" class="modal-hero-image">
            <div class="modal-header-overlay">
                <h1>${tour.titulo}</h1>
                <p class="tour-subtitle">${tour.destino} • ${tour.duracion_dias} días</p>
            </div>
        </div>
        
        <div class="modal-body">
            <div class="tour-highlights">
                ${tour.tipo_viaje ? `<span class="highlight-badge">${tour.tipo_viaje}</span>` : ''}
                ${tour.nivel_confort ? `<span class="highlight-badge">${tour.nivel_confort}</span>` : ''}
                ${tour.continente ? `<span class="highlight-badge">${tour.continente}</span>` : ''}
            </div>
            
            <div class="tour-description-full">
                <h2>Descripción</h2>
                <div class="tour-description-text">${tour.descripcion}</div>
            </div>
            
            ${formatearLista(tour.incluye, '✅ Qué Incluye', 'tour-incluye')}
            ${formatearLista(tour.no_incluye, '❌ No Incluye', 'tour-no-incluye')}
            
            ${renderizarItinerario(tour.itinerario)}
            

            ${tour.salidas && tour.salidas.length > 0 ? `
                <div class="tour-salidas">
                    <h2>📆 Próximas Salidas</h2>
                    ${tour.salidas.map(s => `
                        <div class="salida-item ${s.plazas_disponibles === 0 ? 'completo' : ''}">
                            <span class="salida-fecha">${formatearFecha(s.fecha_salida)}</span>
                            <span class="salida-plazas">
                                ${s.plazas_disponibles > 0
            ? `${s.plazas_disponibles} plazas disponibles`
            : '❌ Completo'
        }
                            </span>
                            ${s.precio_especial ? `<span class="salida-precio">${s.precio_especial}€</span>` : ''}
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            
            <div class="modal-footer">
                <div class="price-box-large">
                    <span class="price-label">Desde</span>
                    <span class="price-amount">${tour.precio_desde}€</span>
                    <span class="price-unit">/persona</span>
                </div>
                <button onclick="consultarDisponibilidad(${tour.id})" class="btn-consultar-large">
                    CONSULTAR DISPONIBILIDAD
                </button>
            </div>
            

        </div >
            `;

    document.getElementById('modal-content').innerHTML = html;
}

/**
 * Cerrar modal
 */
function cerrarModal() {
    const modal = document.getElementById('modal-tour-detalle');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

/**
 * Consultar disponibilidad (abre modal de solicitud)
 */
function consultarDisponibilidad(tourId) {
    cerrarModal();
    // Reutilizar la función del cruceros.html si existe
    if (typeof abrirModalReserva === 'function') {
        // Obtener datos del tour desde el DOM o hacer otro fetch
        fetch(`/api/tours/${tourId}/completo`)
            .then(r => r.json())
            .then(tour => {
                abrirModalReserva(tour.id, tour.titulo, tour.precio_desde);
            });
    } else {
        alert('Contacta con nosotros para reservar este tour');
    }
}

/**
 * Utilidades
 */
function limpiarHTML(html) {
    if (!html) return '';

    // 1. Decodificar entidades HTML primero (si vienen &lt;div&gt;)
    const txt = document.createElement('textarea');
    txt.innerHTML = html;
    const decodedHtml = txt.value;

    // 2. Parsear el HTML decodificado para extraer texto
    const temp = document.createElement('div');
    temp.innerHTML = decodedHtml;

    // 3. Extraer solo el texto (elimina etiquetas)
    return temp.textContent || temp.innerText || '';
}

function truncarTexto(texto, maxLength) {
    if (!texto) return '';
    // Limpiar HTML primero
    const textoLimpio = limpiarHTML(texto);
    return textoLimpio.length > maxLength ? textoLimpio.substring(0, maxLength) + '...' : textoLimpio;
}

function formatearFecha(fechaISO) {
    if (!fechaISO) return '';
    const fecha = new Date(fechaISO);
    return fecha.toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// Inicializar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCatalogo);
} else {
    initCatalogo();
}
