import os
import requests
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from dotenv import load_dotenv

# Configuración de Logging
logger = logging.getLogger(__name__)

load_dotenv()

class MotorBusqueda:
    """
    Motor de búsqueda optimizado para Duffel API.
    Soporta:
    - Búsqueda de vuelos (sin simulación)
    - Autocompletado de aeropuertos
    - Gestión de Órdenes (Creación, Cancelación)
    - Servicios Extra (Maletas)
    - Pagos (Payment Intents)
    """
    
    BASE_URL = "https://api.duffel.com"
    DUFFEL_VERSION = "v2"
    CLASE_MAP = {
        'economy': 'economy',
        'premium': 'premium_economy',
        'business': 'business',
        'first': 'first'
    }
    
    def __init__(self):
        self.duffel_token = os.getenv('DUFFEL_API_TOKEN')
        self.cache = {}
        self.TIEMPO_CACHE_MINUTOS = int(os.getenv('CACHE_DURATION_MINUTES', 5))
        self.rate_limited_until = None
        
        # FASE 5: Métricas de caché
        self.cache_hits = 0
        self.cache_misses = 0
        self.max_cache_size = 100  # Limitar caché a 100 entradas
        
        # Markup de Agencia (Comisión)
        try:
            self.markup_percent = Decimal(os.getenv('AGENCY_MARKUP_PERCENT', '0.0'))
        except (ValueError, TypeError, Exception):
            self.markup_percent = Decimal('0.0')
        
        # Máximo de ofertas a devolver por búsqueda (ordenadas por mejor precio)
        try:
            self.search_results_limit = int(os.getenv('SEARCH_RESULTS_LIMIT', '10'))
        except Exception:
            self.search_results_limit = 10
        
        if not self.duffel_token:
            logger.critical("❌ DUFFEL_API_TOKEN no encontrado en variables de entorno.")
        else:
            logger.info(f"✅ MotorBusqueda inicializado con {self.markup_percent}% de markup, caché {self.TIEMPO_CACHE_MINUTOS}min.")

    def _limpiar_cache_antiguo(self):
        """FASE 5: Limpia entradas de caché expiradas y limita tamaño."""
        if len(self.cache) < self.max_cache_size:
            return
        
        ahora = datetime.now()
        keys_to_remove = []
        
        for key, (data, timestamp) in list(self.cache.items()):
            if ahora - timestamp >= timedelta(minutes=self.TIEMPO_CACHE_MINUTOS):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
        
        # Si aún está lleno, eliminar las entradas más antiguas
        if len(self.cache) >= self.max_cache_size:
            sorted_keys = sorted(self.cache.items(), key=lambda x: x[1][1])
            for key, _ in sorted_keys[:len(sorted_keys)//2]:  # Eliminar la mitad más antigua
                del self.cache[key]
        
        if keys_to_remove:
            logger.info(f"🧹 Cache limpiado: {len(keys_to_remove)} entradas eliminadas, {len(self.cache)} restantes")

    def get_cache_stats(self):
        """FASE 5: Retorna estadísticas del caché."""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'size': len(self.cache),
            'max_size': self.max_cache_size
        }

    def apply_markup(self, amount):
        """Aplica la comisión de agencia a un importe (Decimal)."""
        if self.markup_percent > 0:
            return (amount * (1 + self.markup_percent / 100)).quantize(Decimal('0.01'))
        return amount

    @staticmethod
    def _parse_iso(dt_string):
        """Convierte ISO datetime string (con posible 'Z') a datetime."""
        return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))

    @staticmethod
    def _build_passengers(adultos, ninos=0, bebes=0):
        """Construye lista de pasajeros para payload Duffel."""
        return ([{"type": "adult"}] * adultos +
                [{"type": "child"}] * ninos +
                [{"type": "infant_without_seat"}] * bebes)

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.duffel_token}",
            "Duffel-Version": self.DUFFEL_VERSION,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip"
        }

    def _duffel_get(self, url, params=None, default=None, label="API"):
        """GET genérico contra Duffel con manejo de errores estándar."""
        try:
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=10)
            if response.status_code == 200:
                return response.json()['data']
            logger.error(f"❌ Error {label}: {response.text}")
            return default
        except Exception as e:
            logger.error(f"❌ Excepción {label}: {e}")
            return default

    def is_rate_limited(self):
        return bool(self.rate_limited_until and datetime.utcnow() < self.rate_limited_until)

    def get_rate_limit_remaining_seconds(self):
        if not self.is_rate_limited():
            return 0
        delta = self.rate_limited_until - datetime.utcnow()
        return max(1, int(delta.total_seconds()))

    def _set_rate_limit_cooldown(self, response):
        retry_seconds = 30
        reset_header = (
            response.headers.get('ratelimit-reset')
            or response.headers.get('x-ratelimit-reset')
            or response.headers.get('Retry-After')
            or response.headers.get('retry-after')
        )

        if reset_header:
            try:
                raw_value = int(float(reset_header))
                now_ts = int(time.time())
                if raw_value > now_ts + 1:
                    retry_seconds = max(1, raw_value - now_ts)
                else:
                    retry_seconds = max(1, raw_value)
            except (TypeError, ValueError):
                retry_seconds = 30

        self.rate_limited_until = datetime.utcnow() + timedelta(seconds=retry_seconds)
        logger.warning(f"⏳ Duffel rate-limited. Cooldown activo {retry_seconds}s hasta {self.rate_limited_until.isoformat()}Z")

    # ==========================================
    # 1. AUTOCOMPLETE (PLACES API)
    # ==========================================
    def autocompletar_aeropuerto(self, query):
        """
        Busca aeropuertos y ciudades en Duffel Places Suggestions.
        Retorna lista de diccionarios {'label': ..., 'value': ...}
        """
        if not self.duffel_token or not query or len(query) < 2:
            return []

        try:
            url = f"{self.BASE_URL}/places/suggestions"
            params = {'query': query}
            
            # Logger debug reducido para no saturar
            logger.debug(f"🔍 Duffel Autocomplete: {query}")
            
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json().get('data', [])
                sugerencias = []
                
                for item in data:
                    # Filtramos resultados irrelevantes si fuera necesario
                    nombre = item.get('name', '').title()
                    iata = item.get('iata_code') or item.get('iata_city_code')
                    
                    if not iata: continue
                    
                    tipo = item.get('type')
                    # Formato amigable: "Madrid (MAD)" o "London Heathrow (LHR)"
                    if tipo == 'city':
                        label = f"{nombre} ({iata})" # Icono ciudad
                    else:
                        city_name = item.get('city_name')
                        if city_name and city_name not in nombre:
                            label = f"{nombre}, {city_name} ({iata})"
                        else:
                            label = f"{nombre} ({iata})"
                            
                    sugerencias.append({'label': label, 'value': iata})
                    
                return sugerencias[:10] # Top 10
            else:
                logger.error(f"⚠️ Error Duffel Autocomplete ({response.status_code}): {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Excepción en Autocomplete: {str(e)}")
            return []

    # ==========================================
    # 2. BÚSQUEDA DE VUELOS (OFFER REQUESTS)
    # ==========================================
    def buscar_vuelos(self, origen, destino, fecha, adultos=1, ninos=0, bebes=0, clase='economy'):
        """
        Realiza una búsqueda REAL en Duffel.
        NO usa simulaciones. 
        """
        if not self.duffel_token:
            logger.error("Intento de búsqueda sin Token Duffel.")
            return []

        # 1. Normalizar fecha (YYYY-MM-DD)
        if "/" in fecha:
            try:
                fecha = datetime.strptime(fecha, "%d/%m/%Y").strftime("%Y-%m-%d")
            except ValueError:
                logger.error(f"Formato de fecha inválido: {fecha}")
                return []

        # 2. Caché (prevenir llamadas idénticas)
        cache_key = f"{origen}_{destino}_{fecha}_{adultos}_{ninos}_{bebes}_{clase}"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(minutes=self.TIEMPO_CACHE_MINUTOS):
                # FASE 5: Registrar cache hit
                self.cache_hits += 1
                logger.info(f"⚡ Cache HIT para {cache_key} (hits: {self.cache_hits}, misses: {self.cache_misses})")
                return cached_data

        if self.is_rate_limited():
            remaining = self.get_rate_limit_remaining_seconds()
            logger.warning(f"⏳ Duffel en cooldown ({remaining}s restantes). Saltando llamada {origen}->{destino} ({fecha})")
            self.cache[cache_key] = ([], datetime.now())
            return []
        
        # FASE 5: Cache miss
        self.cache_misses += 1
        logger.info(f"📡 Cache MISS - Solicitando vuelos a Duffel: {origen}->{destino} ({fecha})")
        
        # FASE 5: Limpiar caché si está lleno
        self._limpiar_cache_antiguo()

        # 3. Construir Payload Duffel Standard
        payload = {
            "data": {
                "slices": [{
                    "origin": origen,
                    "destination": destino,
                    "departure_date": fecha
                }],
                "passengers": self._build_passengers(adultos, ninos, bebes),
                "cabin_class": self.CLASE_MAP.get(clase, 'economy'),
            }
        }

        try:
            # Query param return_offers=true para obtener ofertas en la misma llamada (más rápido)
            url = f"{self.BASE_URL}/air/offer_requests?return_offers=true&supplier_timeout=15000"
            
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=20)
            
            if response.status_code == 201:
                data = response.json().get('data', {})
                offers = data.get('offers', [])
                
                logger.info(f"✅ Duffel retornó {len(offers)} ofertas crudas.")
                
                resultados_procesados = self._procesar_ofertas(offers, origen, destino)
                resultados_procesados = resultados_procesados[:self.search_results_limit]
                logger.info(f"✅ Duffel top aplicado: {len(resultados_procesados)} ofertas (límite={self.search_results_limit}).")
                
                self.cache[cache_key] = (resultados_procesados, datetime.now())
                    
                return resultados_procesados
            elif response.status_code == 429:
                self._set_rate_limit_cooldown(response)
                self.cache[cache_key] = ([], datetime.now())
                logger.error(f"❌ Error API Duffel Search (429): {response.text}")
                return []
            else:
                logger.error(f"❌ Error API Duffel Search ({response.status_code}): {response.text}")
                self.cache[cache_key] = ([], datetime.now())
                return []
                
        except Exception as e:
            logger.error(f"❌ Excepción crítica en buscar_vuelos: {str(e)}")
            return []

    def _clasificar_familia_tarifaria(self, offer):
        """Clasifica una oferta en familia tarifaria: Basic, Comfort, Premium"""
        condiciones = offer.get('conditions', {})
        available_services = offer.get('available_services') or []
        
        # Detectar si incluye maleta
        has_checked_bag = any(
            any(token in str(s.get('type', '')).lower() for token in ['baggage', 'bag', 'luggage'])
            for s in available_services
        )
        
        # Analizar condiciones de cambio y reembolso
        change_before = condiciones.get('change_before_departure', {})
        refund_before = condiciones.get('refund_before_departure', {})
        
        permite_cambios = change_before.get('allowed', False)
        permite_reembolso = refund_before.get('allowed', False)
        
        # Penalizaciones (si existen)
        change_penalty = 0
        refund_penalty = 0
        try:
            if change_before.get('penalty_amount'):
                change_penalty = float(change_before['penalty_amount'])
            if refund_before.get('penalty_amount'):
                refund_penalty = float(refund_before['penalty_amount'])
        except (ValueError, TypeError):
            pass
        
        # Lógica de clasificación
        # Premium: Reembolsable + maleta + cambios permitidos con bajo costo
        if permite_reembolso and has_checked_bag and permite_cambios:
            if refund_penalty <= 50 and change_penalty <= 50:
                return 'Premium'
        
        # Comfort: Maleta incluida O reembolsable/cambios permitidos
        if has_checked_bag or permite_reembolso or permite_cambios:
            return 'Comfort'
        
        # Basic: Tarifas restrictivas
        return 'Basic'

    def _agrupar_ofertas_por_vuelo(self, ofertas_procesadas):
        """
        Agrupa ofertas que corresponden al mismo vuelo base (mismos segmentos/horarios).
        Retorna: { 'clave_vuelo': [oferta1, oferta2, ...], ... }
        """
        grupos = {}
        
        for oferta in ofertas_procesadas:
            # Crear clave única por vuelo: origen-destino-hora_salida-hora_llegada-escalas
            segmentos = oferta.get('segmentos', [])
            if not segmentos:
                continue
                
            # Construir clave basada en los números de vuelo y horarios
            vuelos_nums = '-'.join([s.get('vuelo', 'NA') for s in segmentos])
            clave = f"{oferta['origen']}-{oferta['destino']}-{vuelos_nums}"
            
            if clave not in grupos:
                grupos[clave] = []
            grupos[clave].append(oferta)
        
        return grupos

    def _procesar_ofertas(self, offers, origen_req, destino_req):
        """Transforma la respuesta cruda de Duffel en un formato limpio para el frontend."""
        resultados = []
        
        for offer in offers:
            try:
                # Datos principales
                offer_id = offer['id']
                currency = offer['total_currency']
                amount_base = Decimal(offer['total_amount'])
                amount_final = self.apply_markup(amount_base)
                
                owner = offer.get('owner', {})
                aerolinea_nombre = owner.get('name', 'Desconocida')
                iata_carrier = owner.get('iata_code', 'XX')
                
                trayectos = []
                
                # SOPORTE MULTI-SLICE (Multi-City / Nomad)
                for slice_data in (offer.get('slices') or []):
                    slice_duration = self._parse_duration(slice_data['duration'])
                    
                    segmentos = []
                    segments_raw = slice_data.get('segments') or []
                    
                    for i, seg in enumerate(segments_raw):
                        tiempo_escala = None
                        if i < len(segments_raw) - 1:
                            llegada = self._parse_iso(seg['arriving_at'])
                            siguiente_salida = self._parse_iso(segments_raw[i+1]['departing_at'])
                            delta = siguiente_salida - llegada
                            hours, remainder = divmod(delta.seconds, 3600)
                            minutes = remainder // 60
                            tiempo_escala = f"{hours}h {minutes}m"

                        dt_salida = self._parse_iso(seg['departing_at'])
                        dt_llegada = self._parse_iso(seg['arriving_at'])

                        segmentos.append({
                            'salida': seg['origin']['iata_code'],
                            'llegada': seg['destination']['iata_code'],
                            'ciudad_salida': seg['origin'].get('city_name', seg['origin']['name']),
                            'ciudad_llegada': seg['destination'].get('city_name', seg['destination']['name']),
                            'hora_salida': dt_salida.strftime("%H:%M"),
                            'hora_llegada': dt_llegada.strftime("%H:%M"),
                            'fecha_salida': dt_salida.strftime("%d %b"),
                            'fecha_llegada': dt_llegada.strftime("%d %b"),
                            'aerolinea': (seg.get('operating_carrier') or {}).get('name', aerolinea_nombre),
                            'vuelo': seg.get('operating_carrier_flight_number', 'N/A'),
                            'duracion': self._parse_duration(seg['duration']),
                            'avion': (seg.get('aircraft') or {}).get('name', 'Avión'),
                            'img_logo': f"https://pics.avs.io/64/64/{(seg.get('operating_carrier') or {}).get('iata_code', 'XX')}.png",
                            'escala_duracion': tiempo_escala
                        })
                    
                    trayectos.append({
                        'origen': slice_data['origin']['iata_code'],
                        'destino': slice_data['destination']['iata_code'],
                        'duracion': slice_duration,
                        'segmentos': segmentos
                    })

                # Condiciones (Cambios/Reembolsos)
                condiciones = offer.get('conditions', {})
                
                available_services = offer.get('available_services') or []
                has_checked_bag = any(
                    any(token in str(s.get('type', '')).lower() for token in ['baggage', 'bag', 'luggage'])
                    for s in available_services
                )

                # Clasificar familia tarifaria
                familia_tarifaria = self._clasificar_familia_tarifaria(offer)

                # Para mantener compatibilidad con cards que esperan un solo trayecto
                main_segmentos = trayectos[0]['segmentos'] if trayectos else []

                resultados.append({
                    'id': offer_id,
                    'source': 'Duffel',
                    'aerolinea': aerolinea_nombre,
                    'img_logo': f"https://pics.avs.io/200/200/{iata_carrier}.png",
                    'origen': trayectos[0]['origen'] if trayectos else origen_req,
                    'destino': trayectos[-1]['destino'] if trayectos else destino_req,
                    'trayectos': trayectos,
                    # Fallback para UI simple:
                    'hora_salida': main_segmentos[0]['hora_salida'] if main_segmentos else "N/A",
                    'hora_llegada': main_segmentos[-1]['hora_llegada'] if main_segmentos else "N/A",
                    'duracion': trayectos[0]['duracion'] if trayectos else "N/A",
                    'precio_base': float(amount_base),
                    'precio': float(amount_final), 
                    'currency': currency,
                    'escala': len(main_segmentos) - 1 if main_segmentos else 0,
                    'segmentos': main_segmentos,
                    'passengers': offer['passengers'],
                    'condiciones': condiciones,
                    'con_maleta': has_checked_bag,
                    'available_services': available_services,
                    'familia_tarifaria': familia_tarifaria
                })
                
            except Exception as e:
                logger.warning(f"⚠️ Error procesando oferta {offer.get('id', 'unknown')}: {e}")
                continue
                
        resultados.sort(key=lambda x: x['precio'])
        return resultados

    # ==========================================
    # 3. GESTIÓN DE ÓRDENES (CREATE, CANCEL)
    # ==========================================
    def crear_order_duffel(self, offer_id, pasajeros_data, services=None, order_type='instant', payments=None):
        """
        Crea una orden en Duffel.
        - offer_id: ID de la oferta seleccionada
        - pasajeros_data: Lista de pasajeros con sus datos (y IDs de Duffel)
        - services: Lista de servicios extra [{'id': '...', 'quantity': 1}]
        - order_type: 'instant' (pago inmediato) o 'hold' (reserva sin pago)
        - payments: Lista de pagos (si order_type='instant')
        """
        if not self.duffel_token: return {'success': False, 'error': 'Token no configurado'}

        try:
            payload = {
                "data": {
                    "selected_offers": [offer_id],
                    "passengers": pasajeros_data,
                    "type": order_type
                }
            }
            
            if services:
                payload["data"]["services"] = services
                
            if payments and order_type == 'instant':
                payload["data"]["payments"] = payments

            logger.info(f"📤 Creando Order Duffel (Type: {order_type}, Services: {len(services) if services else 0})")
            
            url = f"{self.BASE_URL}/air/orders"
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=30)
            
            if response.status_code == 201:
                data = response.json()['data']
                return {
                    'success': True,
                    'order_id': data['id'],
                    'booking_reference': data.get('booking_reference', 'PENDING'),
                    'order_data': data
                }
            else:
                logger.error(f"❌ Error Create Order: {response.text}")
                return {'success': False, 'error': f"API Error: {response.text}"}

        except Exception as e:
            logger.error(f"❌ Excepción Create Order: {e}")
            return {'success': False, 'error': str(e)}

    def cancelar_orden(self, order_id):
        """
        Cancela una orden existente usando el flujo correcto de Duffel:
        PASO 1: POST /air/order_cancellations → crea cancellation quote
        PASO 2: POST /air/order_cancellations/{id}/actions/confirm → confirma
        """
        if not self.duffel_token: return {'success': False, 'error': 'Token no configurado'}
        
        try:
            # PASO 1: Crear order cancellation (quote)
            url_create = f"{self.BASE_URL}/air/order_cancellations"
            payload = {"data": {"order_id": order_id}}
            response = requests.post(url_create, headers=self._get_headers(), json=payload, timeout=15)
            
            if response.status_code != 201:
                error_msg = response.text
                logger.error(f"❌ Error creando order_cancellation: {error_msg}")
                return {'success': False, 'error': error_msg}
            
            cancellation_data = response.json()['data']
            cancellation_id = cancellation_data['id']
            refund_amount = cancellation_data.get('refund_amount', '0')
            refund_currency = cancellation_data.get('refund_currency', 'EUR')
            
            logger.info(f"📋 Cancellation quote creada: {cancellation_id} (reembolso: {refund_amount} {refund_currency})")
            
            # PASO 2: Confirmar la cancelación
            url_confirm = f"{self.BASE_URL}/air/order_cancellations/{cancellation_id}/actions/confirm"
            response_confirm = requests.post(url_confirm, headers=self._get_headers(), timeout=15)
            
            if response_confirm.status_code == 200:
                confirmed_data = response_confirm.json()['data']
                logger.info(f"✅ Orden {order_id} cancelada exitosamente")
                return {
                    'success': True, 
                    'data': confirmed_data,
                    'refund_amount': refund_amount,
                    'refund_currency': refund_currency
                }
            else:
                logger.error(f"❌ Error confirmando cancelación: {response_confirm.text}")
                return {'success': False, 'error': response_confirm.text}
        
        except Exception as e:
            logger.error(f"❌ Exception Cancelling Order: {e}")
            return {'success': False, 'error': str(e)}

    # ==========================================
    # 4. MERCANCÍAS Y ASIENTOS
    # ==========================================
    def get_offer_details(self, offer_id):
        """Obtiene detalles + servicios disponibles (Maletas)"""
        return self._duffel_get(
            f"{self.BASE_URL}/air/offers/{offer_id}?return_available_services=true",
            label="Offer Details"
        )

    def get_seat_maps(self, offer_id):
        """Obtiene mapas de asientos"""
        return self._duffel_get(
            f"{self.BASE_URL}/air/seat_maps",
            params={'offer_id': offer_id},
            label="Seat Maps"
        )

    # ==========================================
    # 5. PAGOS (DUFFEL PAYMENTS)
    # ==========================================
    def crear_payment_intent(self, amount, currency):
        """amount debe ser string o number correcto. Se recomienda Decimal."""
        try:
            url = f"{self.BASE_URL}/payments/payment_intents"
            # Si amount es Decimal, asegurar markup si no se aplicó antes (aunque debería venir ya con él)
            # Nota: En el flujo de checkout, app.py recibe el precio que el frontend leyó (que ya tiene markup)
            amount_val = Decimal(amount) if not isinstance(amount, Decimal) else amount
            amount_str = f"{amount_val:.2f}"
            
            payload = {
                "data": {
                    "amount": amount_str,
                    "currency": currency
                }
            }
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)
            
            if response.status_code == 201:
                return {'success': True, 'data': response.json()['data']}
            else:
                return {'success': False, 'error': response.text}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def confirmar_payment_intent(self, payment_intent_id):
        """
        Confirma un Payment Intent en Duffel.
        POST /payments/payment_intents/{id}/actions/confirm
        No requiere body — la confirmación se hace automáticamente cuando
        el frontend tokeniza la tarjeta vía Duffel Components SDK.
        """
        try:
            url = f"{self.BASE_URL}/payments/payment_intents/{payment_intent_id}/actions/confirm"
            response = requests.post(url, headers=self._get_headers(), timeout=20)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json()['data']}
            else:
                logger.error(f"❌ Error confirmando Payment Intent {payment_intent_id}: {response.text}")
                return {'success': False, 'error': response.text}
        except Exception as e:
            logger.error(f"❌ Excepción confirmando Payment Intent: {e}")
            return {'success': False, 'error': str(e)}

    def crear_client_component_key(self):
        try:
            url = f"{self.BASE_URL}/identity/component_client_keys"
            payload = {"data": {}}
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)
            
            if response.status_code == 201:
                data = response.json().get('data', {})

                # Compatibilidad con posibles variantes de respuesta Duffel
                client_key = None
                if isinstance(data, dict):
                    client_key = (
                        data.get('client_key')
                        or data.get('component_client_key')
                        or data.get('key')
                        or data.get('token')
                        or data.get('jwt')
                        or data.get('clientToken')
                    )
                elif isinstance(data, str):
                    client_key = data

                if not client_key:
                    logger.error(f"❌ Duffel component key vacío. Respuesta data={data}")
                    return {'success': False, 'error': 'Duffel no devolvió client_key'}

                return {'success': True, 'client_key': client_key}
            else:
                return {'success': False, 'error': response.text}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==========================================
    # HELPERs
    # ==========================================
    def _parse_duration(self, iso_duration):
        """Convierte PT2H30M a '2h 30m'"""
        if not iso_duration: return ""
        try:
            s = iso_duration.replace("P", "").replace("T", "")
            d, h, m = 0, 0, 0
            if 'D' in s: 
                parts = s.split('D')
                d = int(parts[0])
                s = parts[1] if len(parts) > 1 else ""
            if 'H' in s: 
                parts = s.split('H')
                h = int(parts[0])
                s = parts[1] if len(parts) > 1 else ""
            if 'M' in s: 
                m = int(s.replace('M', ''))
            
            res = []
            if d: res.append(f"{d}d")
            if h: res.append(f"{h}h")
            if m: res.append(f"{m}m")
            return " ".join(res)
        except (ValueError, IndexError, Exception):
            return iso_duration
    def actualizar_datos_pasajero(self, passenger_id, identity_data):
        """
        Actualiza los datos de identidad (DNI/Pasaporte) de un pasajero en Duffel.
        """
        try:
            url = f"{self.BASE_URL}/air/passengers/{passenger_id}"
            payload = { "data": identity_data }
            response = requests.patch(url, headers=self._get_headers(), json=payload, timeout=15)
            if response.status_code == 200:
                return {'success': True}
            else:
                return {'success': False, 'error': response.json().get('errors', [{}])[0].get('message')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    def get_order_details(self, order_id):
        """Obtiene detalles de una orden existente."""
        return self._duffel_get(
            f"{self.BASE_URL}/air/orders/{order_id}",
            label="Order Details"
        )

    def get_order_available_services(self, order_id):
        """Obtiene servicios disponibles (maletas) para una orden ya pagada."""
        return self._duffel_get(
            f"{self.BASE_URL}/air/orders/{order_id}/available_services",
            default=[], label="Order Available Services"
        )

    def crear_service_order(self, order_id, service_id, amount, currency):
        """Añade un servicio extra a una orden existente. Requiere pago."""
        try:
            url = f"{self.BASE_URL}/air/service_orders"
            payload = {
                "data": {
                    "order_id": order_id,
                    "services": [{"id": service_id, "quantity": 1}],
                    "payment": {
                        "amount": str(amount),
                        "currency": currency
                    }
                }
            }
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=15)
            if response.status_code == 201:
                return {'success': True, 'data': response.json()['data']}
            else:
                logger.error(f"Error creating service order: {response.text}")
                return {'success': False, 'error': response.json().get('errors', [{}])[0].get('message')}
        except Exception as e:
            logger.error(f"Excepción en crear_service_order: {e}")
            return {'success': False, 'error': str(e)}

    def get_order_seat_maps(self, order_id):
        """Obtiene mapas de asientos para una orden existente."""
        return self._duffel_get(
            f"{self.BASE_URL}/air/seat_maps",
            params={'order_id': order_id},
            default=[], label="Order Seat Maps"
        )
    def buscar_vuelos_multi(self, slices, adultos=1, ninos=0, bebes=0, clase='economy'):
        """
        Realiza una búsqueda MULTI-CITY en Duffel.
        slices: [{'origin': 'MAD', 'destination': 'LON', 'departure_date': '2024-10-10'}, ...]
        """
        if not self.duffel_token:
            return []

        payload = {
            "data": {
                "slices": slices,
                "passengers": self._build_passengers(adultos, ninos, bebes),
                "cabin_class": self.CLASE_MAP.get(clase, 'economy')
            }
        }

        try:
            url = f"{self.BASE_URL}/air/offer_requests?return_offers=true&supplier_timeout=20000"
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=25)
            
            if response.status_code == 201:
                data = response.json().get('data', {})
                offers = data.get('offers', [])
                # Procesamos indicando que es multi-city
                return self._procesar_ofertas(offers, "MULTI", "CITY")
            else:
                logger.error(f"❌ Error Multi-City Search: {response.text}")
                return []
        except Exception as e:
            logger.error(f"❌ Excepción en buscar_vuelos_multi: {e}")
            return []
