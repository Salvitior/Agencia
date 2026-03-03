"""
SEO y Compliance Module:
- Generador de sitemap.xml dinámico
- Structured data (JSON-LD) para Google Flights
- Meta tags dinámicos
- Cookie consent (RGPD / LSSI)
- Páginas legales: privacidad, cookies, condiciones
- robots.txt
"""

from flask import Blueprint, request, jsonify, render_template, make_response, url_for
from datetime import datetime, date
import json
import logging

logger = logging.getLogger(__name__)

seo_bp = Blueprint('seo', __name__)


# ================================
# STRUCTURED DATA (JSON-LD)
# ================================

def generar_schema_vuelo(oferta):
    """Genera JSON-LD Schema.org para un vuelo (Google Flights compatible)"""
    try:
        slices = oferta.get('slices', [])
        if not slices:
            return None

        segments = slices[0].get('segments', [])
        if not segments:
            return None

        primer_segmento = segments[0]
        ultimo_segmento = segments[-1]

        schema = {
            "@context": "https://schema.org",
            "@type": "Flight",
            "departureAirport": {
                "@type": "Airport",
                "name": primer_segmento.get('origin', {}).get('name', ''),
                "iataCode": primer_segmento.get('origin', {}).get('iata_code', ''),
            },
            "arrivalAirport": {
                "@type": "Airport",
                "name": ultimo_segmento.get('destination', {}).get('name', ''),
                "iataCode": ultimo_segmento.get('destination', {}).get('iata_code', ''),
            },
            "departureTime": primer_segmento.get('departing_at', ''),
            "arrivalTime": ultimo_segmento.get('arriving_at', ''),
            "flightNumber": primer_segmento.get('marketing_carrier', {}).get('flight_number', ''),
            "provider": {
                "@type": "Organization",
                "name": primer_segmento.get('marketing_carrier', {}).get('name', ''),
            },
            "offers": {
                "@type": "Offer",
                "price": oferta.get('total_amount', ''),
                "priceCurrency": oferta.get('total_currency', 'EUR'),
                "availability": "https://schema.org/InStock",
                "url": request.url if request else '',
            }
        }

        # Añadir escalas si hay más de un segmento
        if len(segments) > 1:
            schema["itinerary"] = {
                "@type": "ItemList",
                "numberOfItems": len(segments),
                "itemListElement": [{
                    "@type": "ListItem",
                    "position": i + 1,
                    "item": {
                        "@type": "Flight",
                        "departureAirport": {
                            "@type": "Airport",
                            "iataCode": seg.get('origin', {}).get('iata_code', ''),
                        },
                        "arrivalAirport": {
                            "@type": "Airport",
                            "iataCode": seg.get('destination', {}).get('iata_code', ''),
                        },
                        "departureTime": seg.get('departing_at', ''),
                        "arrivalTime": seg.get('arriving_at', ''),
                    }
                } for i, seg in enumerate(segments)]
            }

        return schema
    except Exception as e:
        logger.warning(f"Error generando schema vuelo: {e}")
        return None


def generar_schema_agencia():
    """Schema.org para la agencia (TravelAgency)"""
    return {
        "@context": "https://schema.org",
        "@type": "TravelAgency",
        "name": "Viatges Carcaixent",
        "alternateName": "Agencia de Viajes Carcaixent",
        "url": "https://viatgescarcaixent.com",
        "logo": "https://viatgescarcaixent.com/static/imagenes/logo.png",
        "description": "Agencia de viajes especializada en vuelos, cruceros y tours. Reserva online con las mejores tarifas.",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "Calle de ejemplo, 1",
            "addressLocality": "Carcaixent",
            "addressRegion": "Valencia",
            "postalCode": "46740",
            "addressCountry": "ES",
        },
        "telephone": "+34 962 XXX XXX",
        "email": "info@viatgescarcaixent.com",
        "priceRange": "€€",
        "paymentAccepted": "Credit Card, Debit Card",
        "currenciesAccepted": "EUR",
        "openingHours": "Mo-Fr 09:00-19:00, Sa 10:00-13:00",
        "sameAs": [
            "https://www.facebook.com/viatgescarcaixent",
            "https://www.instagram.com/viatgescarcaixent",
        ],
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": "39.1231",
            "longitude": "-0.4392",
        },
        "areaServed": {
            "@type": "Country",
            "name": "Spain",
        },
    }


def generar_schema_faq():
    """Schema.org FAQ para las preguntas más frecuentes"""
    faqs = [
        {
            "pregunta": "¿Cómo puedo reservar un vuelo?",
            "respuesta": "Busca tu vuelo en nuestro buscador, selecciona la opción que prefieras, introduce los datos de los pasajeros y realiza el pago con tarjeta de crédito o débito."
        },
        {
            "pregunta": "¿Puedo cancelar mi reserva?",
            "respuesta": "Sí, puedes solicitar la cancelación desde tu área de cliente o contactando con nosotros. Las condiciones de reembolso dependen de la tarifa contratada."
        },
        {
            "pregunta": "¿Cuándo recibiré mi billete electrónico?",
            "respuesta": "Recibirás tu e-ticket por email inmediatamente después de confirmar el pago. También puedes descargarlo desde tu área de cliente."
        },
        {
            "pregunta": "¿Qué documentación necesito para viajar?",
            "respuesta": "Para vuelos nacionales necesitas DNI o pasaporte en vigor. Para vuelos internacionales fuera de la UE, pasaporte con al menos 6 meses de validez."
        },
        {
            "pregunta": "¿Puedo añadir equipaje extra después de reservar?",
            "respuesta": "Sí, puedes añadir equipaje facturado, selección de asiento y otros extras desde tu área de cliente hasta 48 horas antes del vuelo."
        },
    ]

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question",
            "name": faq["pregunta"],
            "acceptedAnswer": {
                "@type": "Answer",
                "text": faq["respuesta"],
            }
        } for faq in faqs]
    }


def generar_meta_tags(titulo=None, descripcion=None, imagen=None, url=None, tipo='website'):
    """Genera meta tags para SEO y Open Graph"""
    titulo = titulo or 'Viatges Carcaixent - Vuelos, Cruceros y Tours al mejor precio'
    descripcion = descripcion or 'Reserva vuelos baratos, cruceros y tours organizados con Viatges Carcaixent. Agencia de viajes online con las mejores tarifas.'
    imagen = imagen or '/static/imagenes/og-default.jpg'
    url = url or request.url if request else 'https://viatgescarcaixent.com'

    return {
        'title': titulo,
        'description': descripcion,
        'og': {
            'title': titulo,
            'description': descripcion,
            'image': imagen,
            'url': url,
            'type': tipo,
            'site_name': 'Viatges Carcaixent',
            'locale': 'es_ES',
        },
        'twitter': {
            'card': 'summary_large_image',
            'title': titulo,
            'description': descripcion,
            'image': imagen,
        },
        'canonical': url,
    }


# ================================
# DESTINOS CON SLUGS
# ================================

DESTINOS_SEO = {
    'vuelos-madrid': {
        'titulo': 'Vuelos baratos a Madrid',
        'descripcion': 'Encuentra vuelos baratos a Madrid desde Valencia. Compara precios y reserva online.',
        'iata': 'MAD',
        'h1': 'Vuelos a Madrid',
    },
    'vuelos-barcelona': {
        'titulo': 'Vuelos baratos a Barcelona',
        'descripcion': 'Vuelos económicos a Barcelona-El Prat. Las mejores ofertas de vuelos.',
        'iata': 'BCN',
        'h1': 'Vuelos a Barcelona',
    },
    'vuelos-paris': {
        'titulo': 'Vuelos baratos a París',
        'descripcion': 'Vuelos a París CDG y Orly al mejor precio. Reserva online.',
        'iata': 'CDG',
        'h1': 'Vuelos a París',
    },
    'vuelos-londres': {
        'titulo': 'Vuelos baratos a Londres',
        'descripcion': 'Vuelos a Londres Heathrow, Gatwick y Stansted. Mejores precios.',
        'iata': 'LHR',
        'h1': 'Vuelos a Londres',
    },
    'vuelos-roma': {
        'titulo': 'Vuelos baratos a Roma',
        'descripcion': 'Vuelos a Roma Fiumicino. Compara tarifas y reserva tu viaje a Italia.',
        'iata': 'FCO',
        'h1': 'Vuelos a Roma',
    },
    'vuelos-nueva-york': {
        'titulo': 'Vuelos baratos a Nueva York',
        'descripcion': 'Vuelos a Nueva York JFK. Encuentra las mejores tarifas para volar a NYC.',
        'iata': 'JFK',
        'h1': 'Vuelos a Nueva York',
    },
}


def init_seo_blueprint():
    """Inicializa las rutas SEO"""

    @seo_bp.route('/robots.txt')
    def robots_txt():
        """robots.txt dinámico"""
        content = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /cliente/api/
Disallow: /api/
Disallow: /checkout
Disallow: /pago/

Sitemap: https://viatgescarcaixent.com/sitemap.xml
"""
        response = make_response(content, 200)
        response.headers['Content-Type'] = 'text/plain'
        return response

    @seo_bp.route('/sitemap.xml')
    def sitemap_xml():
        """Sitemap XML dinámico"""
        pages = [
            {'loc': '/', 'priority': '1.0', 'changefreq': 'daily'},
            {'loc': '/vuelos', 'priority': '0.9', 'changefreq': 'daily'},
            {'loc': '/cruceros', 'priority': '0.8', 'changefreq': 'weekly'},
            {'loc': '/tours', 'priority': '0.8', 'changefreq': 'weekly'},
            {'loc': '/destinos', 'priority': '0.7', 'changefreq': 'weekly'},
            {'loc': '/contacto', 'priority': '0.5', 'changefreq': 'monthly'},
            {'loc': '/legal/privacidad', 'priority': '0.3', 'changefreq': 'yearly'},
            {'loc': '/legal/cookies', 'priority': '0.3', 'changefreq': 'yearly'},
            {'loc': '/legal/condiciones-compra', 'priority': '0.3', 'changefreq': 'yearly'},
            {'loc': '/legal/politica-cancelacion', 'priority': '0.3', 'changefreq': 'yearly'},
            {'loc': '/checkin', 'priority': '0.6', 'changefreq': 'monthly'},
        ]

        # Añadir destinos SEO
        for slug in DESTINOS_SEO:
            pages.append({
                'loc': f'/destinos/{slug}',
                'priority': '0.7',
                'changefreq': 'weekly',
            })

        # Añadir tours dinámicamente
        try:
            from database import Tour, get_db_session
            session = get_db_session()
            tours = session.query(Tour).filter_by(estado='activo').all()
            for tour in tours:
                slug = tour.nombre.lower().replace(' ', '-').replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
                pages.append({
                    'loc': f'/tours/{tour.id}/{slug}',
                    'priority': '0.6',
                    'changefreq': 'weekly',
                })
            session.close()
        except Exception:
            pass

        base_url = 'https://viatgescarcaixent.com'
        today = date.today().isoformat()

        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for p in pages:
            xml += '  <url>\n'
            xml += f'    <loc>{base_url}{p["loc"]}</loc>\n'
            xml += f'    <lastmod>{today}</lastmod>\n'
            xml += f'    <changefreq>{p["changefreq"]}</changefreq>\n'
            xml += f'    <priority>{p["priority"]}</priority>\n'
            xml += '  </url>\n'
        xml += '</urlset>'

        response = make_response(xml, 200)
        response.headers['Content-Type'] = 'application/xml'
        return response

    @seo_bp.route('/destinos/<slug>')
    def destino_seo(slug):
        """Landing pages por destino con SEO"""
        destino = DESTINOS_SEO.get(slug)
        if not destino:
            return render_template('404.html'), 404

        meta = generar_meta_tags(
            titulo=destino['titulo'],
            descripcion=destino['descripcion'],
        )
        schema_agencia = generar_schema_agencia()

        return render_template('destino_seo.html',
                               destino=destino,
                               meta=meta,
                               schema_agencia=json.dumps(schema_agencia),
                               slug=slug)

    # ================================
    # LEGAL PAGES
    # ================================

    @seo_bp.route('/legal/privacidad')
    def politica_privacidad():
        """Política de privacidad RGPD"""
        meta = generar_meta_tags(
            titulo='Política de Privacidad - Viatges Carcaixent',
            descripcion='Política de privacidad y protección de datos personales según el RGPD.',
        )
        return render_template('legal_privacidad.html', meta=meta)

    @seo_bp.route('/legal/cookies')
    def politica_cookies():
        """Política de cookies"""
        meta = generar_meta_tags(
            titulo='Política de Cookies - Viatges Carcaixent',
            descripcion='Información sobre las cookies utilizadas en nuestro sitio web.',
        )
        return render_template('legal_cookies.html', meta=meta)

    @seo_bp.route('/legal/condiciones-compra')
    def condiciones_compra():
        """Condiciones generales de compra"""
        meta = generar_meta_tags(
            titulo='Condiciones de Compra - Viatges Carcaixent',
            descripcion='Condiciones generales de compra y contratación de servicios turísticos.',
        )
        return render_template('legal_condiciones.html', meta=meta)

    @seo_bp.route('/legal/politica-cancelacion')
    def politica_cancelacion():
        """Política de cancelación y reembolsos"""
        meta = generar_meta_tags(
            titulo='Política de Cancelación - Viatges Carcaixent',
            descripcion='Política de cancelación, cambios y reembolsos para vuelos, tours y cruceros.',
        )
        return render_template('legal_cancelacion.html', meta=meta)

    @seo_bp.route('/legal/aviso-legal')
    def aviso_legal():
        """Aviso legal LSSI"""
        meta = generar_meta_tags(
            titulo='Aviso Legal - Viatges Carcaixent',
            descripcion='Aviso legal e información sobre el titular del sitio web.',
        )
        return render_template('legal_aviso.html', meta=meta)

    # ================================
    # COOKIE CONSENT API
    # ================================

    @seo_bp.route('/api/cookies/consent', methods=['POST'])
    def guardar_consentimiento_cookies():
        """Guardar consentimiento de cookies (RGPD/LSSI)"""
        data = request.json or {}
        session = None
        try:
            from database import get_db_session
            from database.models_clientes import ConsentimientoCookies

            session = get_db_session()
            consentimiento = ConsentimientoCookies(
                cookies_necesarias=True,  # Siempre activas
                cookies_analiticas=bool(data.get('analiticas', False)),
                cookies_marketing=bool(data.get('marketing', False)),
                cookies_funcionales=bool(data.get('funcionales', True)),
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string[:500] if request.user_agent else None,
            )
            session.add(consentimiento)
            session.commit()

            return jsonify({'success': True})
        except Exception as e:
            logger.warning(f"Error guardando consentimiento cookies: {e}")
            if session:
                session.rollback()
            return jsonify({'success': True})  # No bloquear al usuario por error de cookies
        finally:
            if session:
                session.close()

    return seo_bp
