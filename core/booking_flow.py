"""
Servicio de Booking Flow: gestión completa del flujo de reserva.
Seleccionar vuelo → elegir extras → datos pasajeros → pago → confirmación

Extras disponibles: equipaje, asientos, seguro de viaje, fast-track
"""

import json
import secrets
import logging
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger(__name__)


# ==============================
# CATÁLOGO DE EXTRAS
# ==============================

EXTRAS_CATALOGO = {
    'seguro_viaje': {
        'id': 'seguro_viaje',
        'nombre': 'Seguro de Viaje',
        'descripcion': 'Cobertura médica, cancelación, equipaje perdido y repatriación',
        'coberturas': [
            'Gastos médicos hasta 100.000€',
            'Cancelación de viaje hasta importe completo',
            'Equipaje perdido/dañado hasta 1.500€',
            'Repatriación sanitaria',
            'Responsabilidad civil hasta 60.000€',
            'Retraso de vuelo (+6h): 150€',
        ],
        'precios': {
            'basico': {'nombre': 'Básico', 'precio': 19.90, 'por_persona': True},
            'premium': {'nombre': 'Premium', 'precio': 39.90, 'por_persona': True},
            'total': {'nombre': 'Total', 'precio': 59.90, 'por_persona': True},
        },
        'icono': '🛡️',
        'obligatorio': False,
    },
    'fast_track': {
        'id': 'fast_track',
        'nombre': 'Fast Track Seguridad',
        'descripcion': 'Acceso prioritario al control de seguridad del aeropuerto',
        'precios': {
            'unico': {'nombre': 'Fast Track', 'precio': 7.50, 'por_persona': True},
        },
        'icono': '⚡',
        'obligatorio': False,
        'disponibilidad': 'Sujeto a disponibilidad del aeropuerto',
    },
    'equipaje_facturado': {
        'id': 'equipaje_facturado',
        'nombre': 'Equipaje Facturado',
        'descripcion': 'Añade maleta facturada a tu vuelo',
        'opciones': [
            {'id': 'maleta_15kg', 'nombre': '1 maleta 15kg', 'precio': 25.00},
            {'id': 'maleta_23kg', 'nombre': '1 maleta 23kg', 'precio': 35.00},
            {'id': 'maleta_32kg', 'nombre': '1 maleta 32kg', 'precio': 55.00},
            {'id': 'maleta_extra_23kg', 'nombre': '2ª maleta 23kg', 'precio': 50.00},
        ],
        'icono': '🧳',
        'obligatorio': False,
        'nota': 'Los precios pueden variar según la aerolínea. Se aplicará el precio real al confirmar.',
    },
    'seleccion_asiento': {
        'id': 'seleccion_asiento',
        'nombre': 'Selección de Asiento',
        'descripcion': 'Elige tu asiento preferido en el avión',
        'precios': {
            'estandar': {'nombre': 'Asiento estándar', 'precio': 5.00, 'por_persona': True},
            'ventana_pasillo': {'nombre': 'Ventana o pasillo', 'precio': 8.00, 'por_persona': True},
            'extra_legroom': {'nombre': 'Más espacio para piernas', 'precio': 18.00, 'por_persona': True},
            'primera_fila': {'nombre': 'Primera fila', 'precio': 25.00, 'por_persona': True},
        },
        'icono': '💺',
        'obligatorio': False,
    },
    'embarque_prioritario': {
        'id': 'embarque_prioritario',
        'nombre': 'Embarque Prioritario',
        'descripcion': 'Embarca primero y asegura espacio para tu equipaje de mano',
        'precios': {
            'unico': {'nombre': 'Priority Boarding', 'precio': 6.00, 'por_persona': True},
        },
        'icono': '🎫',
        'obligatorio': False,
    },
    'traslado_aeropuerto': {
        'id': 'traslado_aeropuerto',
        'nombre': 'Traslado Aeropuerto',
        'descripcion': 'Transfer desde/hacia el aeropuerto',
        'precios': {
            'ida': {'nombre': 'Solo ida', 'precio': 25.00, 'por_persona': False},
            'ida_vuelta': {'nombre': 'Ida y vuelta', 'precio': 45.00, 'por_persona': False},
        },
        'icono': '🚕',
        'obligatorio': False,
    },
}


class BookingFlowService:
    """
    Gestiona el flujo completo de reserva:
    1. Seleccionar vuelo
    2. Elegir extras (equipaje, asientos, seguro, fast-track)
    3. Datos de pasajeros (con validación)
    4. Pago (tarjeta)
    5. Confirmación (email + localizador)
    """

    def __init__(self, motor_busqueda=None, email_manager=None):
        self.motor_busqueda = motor_busqueda
        self.email_manager = email_manager

    def obtener_extras_disponibles(self, offer_id=None, provider='DUFFEL'):
        """
        Retorna los extras disponibles para un vuelo.
        Si se proporciona offer_id, intenta obtener los reales de la aerolínea.
        """
        extras = {}

        # Extras de catálogo propio (siempre disponibles)
        for key, extra in EXTRAS_CATALOGO.items():
            extras[key] = extra.copy()

        # Si hay offer_id, intentar obtener equipaje/asientos reales
        if offer_id and self.motor_busqueda:
            try:
                detalles = self.motor_busqueda.get_offer_details(offer_id)
                if detalles:
                    # Extraer servicios de equipaje reales
                    servicios = detalles.get('available_services', [])
                    if servicios:
                        opciones_equipaje = []
                        for srv in servicios:
                            if srv.get('type') == 'baggage':
                                opciones_equipaje.append({
                                    'id': srv.get('id'),
                                    'nombre': srv.get('metadata', {}).get('type', 'Equipaje'),
                                    'precio': float(srv.get('total_amount', 0)),
                                    'peso': srv.get('metadata', {}).get('maximum_weight_kg'),
                                    'service_id': srv.get('id'),
                                })
                        if opciones_equipaje:
                            extras['equipaje_facturado']['opciones'] = opciones_equipaje
                            extras['equipaje_facturado']['nota'] = 'Precios reales de la aerolínea'
            except Exception as e:
                logger.warning(f"No se pudieron obtener extras reales del vuelo: {e}")

        return extras

    def calcular_precio_extras(self, extras_seleccionados, num_pasajeros=1):
        """
        Calcula el precio total de los extras seleccionados.
        
        Args:
            extras_seleccionados: Lista de dicts [{id, opcion, cantidad}]
            num_pasajeros: Número de pasajeros
            
        Returns:
            dict: {total, desglose: [{nombre, precio_unitario, cantidad, subtotal}]}
        """
        total = Decimal('0')
        desglose = []

        for extra in extras_seleccionados:
            extra_id = extra.get('id')
            opcion = extra.get('opcion', 'unico')
            cantidad = extra.get('cantidad', 1)

            catalogo_item = EXTRAS_CATALOGO.get(extra_id)
            if not catalogo_item:
                continue

            # Buscar precio
            precio_unitario = Decimal('0')
            nombre = catalogo_item['nombre']

            if 'precios' in catalogo_item:
                precio_info = catalogo_item['precios'].get(opcion, {})
                precio_unitario = Decimal(str(precio_info.get('precio', 0)))
                nombre = f"{catalogo_item['nombre']} - {precio_info.get('nombre', opcion)}"

                # Si es por persona, multiplicar
                if precio_info.get('por_persona', False):
                    cantidad = cantidad * num_pasajeros

            elif 'opciones' in catalogo_item:
                for opt in catalogo_item['opciones']:
                    if opt['id'] == opcion:
                        precio_unitario = Decimal(str(opt.get('precio', 0)))
                        nombre = f"{catalogo_item['nombre']} - {opt.get('nombre', opcion)}"
                        break

            subtotal = precio_unitario * cantidad
            total += subtotal

            desglose.append({
                'extra_id': extra_id,
                'nombre': nombre,
                'precio_unitario': float(precio_unitario),
                'cantidad': cantidad,
                'subtotal': float(subtotal),
            })

        return {
            'total': float(total),
            'desglose': desglose,
        }

    def crear_prereserva(self, datos):
        """
        Crea una pre-reserva con todos los datos del flujo.
        
        Args:
            datos: {
                offer_id, provider, datos_vuelo, pasajeros, extras,
                email_cliente, telefono_cliente, es_ida_vuelta
            }
            
        Returns:
            dict: {success, codigo_reserva, reserva_id, precio_desglose}
        """
        from database import ReservaVuelo, get_db_session
        from core.passenger_validation import ValidadorPasajeros

        try:
            # 1. Validar datos de contacto
            errores_contacto = ValidadorPasajeros.validar_contacto(
                datos.get('email_cliente'),
                datos.get('telefono_cliente')
            )
            if errores_contacto:
                return {'success': False, 'errores': errores_contacto}

            # 2. Validar pasajeros
            pasajeros = datos.get('pasajeros', [])
            datos_vuelo = datos.get('datos_vuelo', {})
            
            fecha_vuelo_str = datos_vuelo.get('fecha_ida') or datos_vuelo.get('fecha', '')
            try:
                fecha_vuelo = datetime.strptime(fecha_vuelo_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                fecha_vuelo = date.today()

            es_internacional = datos_vuelo.get('es_internacional', False)
            validacion = ValidadorPasajeros.validar_reserva_completa(
                pasajeros, fecha_vuelo, es_internacional
            )

            if not validacion['valido']:
                return {
                    'success': False,
                    'errores': validacion['errores'],
                    'warnings': validacion['warnings'],
                }

            # 3. Calcular precio total
            precio_vuelos = Decimal(str(datos.get('precio_vuelos', 0)))
            extras_seleccionados = datos.get('extras', [])
            precio_extras = self.calcular_precio_extras(extras_seleccionados, len(pasajeros))
            
            precio_total = precio_vuelos + Decimal(str(precio_extras['total']))

            # 4. Generar código de reserva
            codigo_reserva = f"VGT-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

            # 5. Crear reserva en DB
            session = get_db_session()
            try:
                provider = datos.get('provider', 'DUFFEL')
                
                nueva_reserva = ReservaVuelo(
                    codigo_reserva=codigo_reserva,
                    provider=provider,
                    offer_id_duffel=datos.get('offer_id') if provider == 'DUFFEL' else None,
                    amadeus_order_id=datos.get('amadeus_order_id') if provider == 'AMADEUS' else None,
                    pasajeros=json.dumps(pasajeros),
                    datos_vuelo=json.dumps(datos_vuelo),
                    precio_vuelos=float(precio_vuelos),
                    precio_extras=float(precio_extras['total']),
                    precio_total=float(precio_total),
                    email_cliente=datos.get('email_cliente'),
                    telefono_cliente=datos.get('telefono_cliente'),
                    nombre_cliente=f"{pasajeros[0].get('given_name', '')} {pasajeros[0].get('family_name', '')}".strip(),
                    es_viaje_redondo=datos.get('es_ida_vuelta', False),
                    estado='PENDIENTE',
                    notas=json.dumps({
                        'extras': extras_seleccionados,
                        'extras_desglose': precio_extras['desglose'],
                        'warnings': validacion.get('warnings', []),
                    }),
                )

                session.add(nueva_reserva)
                session.commit()
                reserva_id = nueva_reserva.id
                session.close()

                logger.info(f"✅ Pre-reserva creada: {codigo_reserva} (€{precio_total})")

                return {
                    'success': True,
                    'codigo_reserva': codigo_reserva,
                    'reserva_id': reserva_id,
                    'precio_desglose': {
                        'vuelos': float(precio_vuelos),
                        'extras': float(precio_extras['total']),
                        'extras_detalle': precio_extras['desglose'],
                        'total': float(precio_total),
                    },
                    'warnings': validacion.get('warnings', []),
                }

            except Exception as e:
                session.rollback()
                session.close()
                raise e

        except Exception as e:
            logger.error(f"❌ Error creando pre-reserva: {e}")
            return {'success': False, 'error': str(e)}

    def confirmar_reserva(self, codigo_reserva, payment_data):
        """
        Confirma una reserva tras el pago exitoso.
        - Crea order en Duffel/Amadeus
        - Actualiza estado
        - Envía email de confirmación
        - Vincula con cliente si está registrado
        """
        from database import ReservaVuelo, get_db_session

        session = get_db_session()
        try:
            reserva = session.query(ReservaVuelo).filter_by(
                codigo_reserva=codigo_reserva
            ).first()

            if not reserva:
                return {'success': False, 'error': 'Reserva no encontrada'}

            # Actualizar datos de pago
            reserva.estado = 'PAGADO'
            reserva.fecha_pago = datetime.utcnow()
            
            if payment_data.get('stripe_payment_intent_id'):
                reserva.stripe_payment_intent_id = payment_data['stripe_payment_intent_id']
            if payment_data.get('duffel_payment_intent_id'):
                reserva.duffel_payment_intent_id = payment_data['duffel_payment_intent_id']

            session.commit()

            # Crear order en proveedor
            resultado_order = None
            if reserva.provider == 'DUFFEL' and self.motor_busqueda:
                pasajeros_data = json.loads(reserva.pasajeros)
                resultado_order = self.motor_busqueda.crear_order_duffel(
                    offer_id=reserva.offer_id_duffel,
                    pasajeros_data=pasajeros_data
                )

                if resultado_order and resultado_order.get('success'):
                    reserva.order_id_duffel = resultado_order['order_id']
                    reserva.booking_reference = resultado_order.get('booking_reference')
                    reserva.estado = 'CONFIRMADO'
                    reserva.fecha_confirmacion = datetime.utcnow()
                    session.commit()

                    # Enviar email
                    if self.email_manager:
                        try:
                            self.email_manager.send_flight_tickets(reserva, resultado_order.get('order_data', {}))
                        except Exception as e:
                            logger.error(f"Error enviando email de confirmación: {e}")

                else:
                    reserva.estado = 'ERROR'
                    reserva.error_mensaje = resultado_order.get('error', 'Error desconocido')
                    session.commit()

            # Vincular con cliente registrado si existe
            self._vincular_con_cliente(reserva, session)

            session.close()

            return {
                'success': True,
                'codigo_reserva': reserva.codigo_reserva,
                'booking_reference': reserva.booking_reference,
                'estado': reserva.estado,
            }

        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error confirmando reserva: {e}")
            return {'success': False, 'error': str(e)}

    def _vincular_con_cliente(self, reserva, session):
        """Vincula la reserva con un ClienteUsuario si existe"""
        try:
            from database.models_clientes import ClienteUsuario, ReservaCliente
            
            cliente = session.query(ClienteUsuario).filter_by(
                email=reserva.email_cliente, activo=True
            ).first()

            if cliente:
                vinculo = ReservaCliente(
                    cliente_id=cliente.id,
                    reserva_vuelo_id=reserva.id,
                    codigo_reserva=reserva.codigo_reserva,
                    tipo='vuelo',
                    estado_cliente='confirmada',
                )
                session.add(vinculo)
                session.commit()
                logger.info(f"Reserva {reserva.codigo_reserva} vinculada con cliente {cliente.id}")
        except Exception as e:
            logger.debug(f"No se pudo vincular con cliente: {e}")

    def añadir_extra_post_compra(self, codigo_reserva, extra_data):
        """
        Permite añadir extras después de la compra:
        - Equipaje adicional
        - Selección de asiento
        - Seguro de viaje
        - Fast-track
        """
        from database import ReservaVuelo, get_db_session

        session = get_db_session()
        try:
            reserva = session.query(ReservaVuelo).filter_by(
                codigo_reserva=codigo_reserva
            ).first()

            if not reserva:
                return {'success': False, 'error': 'Reserva no encontrada'}

            if reserva.estado not in ('CONFIRMADO', 'EMITIDO'):
                return {'success': False, 'error': 'Solo se pueden añadir extras a reservas confirmadas'}

            # Calcular precio del extra
            extras = [extra_data]
            pasajeros = json.loads(reserva.pasajeros) if reserva.pasajeros else []
            precio = self.calcular_precio_extras(extras, len(pasajeros))

            # Para equipaje/asientos reales, usar API del proveedor
            if reserva.provider == 'DUFFEL' and self.motor_busqueda:
                service_id = extra_data.get('service_id')
                if service_id and reserva.order_id_duffel:
                    try:
                        resultado = self.motor_busqueda.book_extra_service(
                            reserva.order_id_duffel, service_id
                        )
                        if resultado.get('success'):
                            precio['total'] = float(resultado.get('total_amount', precio['total']))
                    except Exception as e:
                        logger.warning(f"Error al añadir extra via proveedor: {e}")

            # Registrar el extra
            notas = json.loads(reserva.notas) if reserva.notas else {}
            extras_post = notas.get('extras_post_compra', [])
            extras_post.append({
                'tipo': extra_data.get('id'),
                'opcion': extra_data.get('opcion'),
                'precio': precio['total'],
                'fecha': datetime.utcnow().isoformat(),
            })
            notas['extras_post_compra'] = extras_post
            reserva.notas = json.dumps(notas)

            # Actualizar precio
            reserva.precio_extras = (reserva.precio_extras or 0) + precio['total']
            reserva.precio_total = (reserva.precio_vuelos or 0) + (reserva.precio_extras or 0)

            session.commit()
            session.close()

            return {
                'success': True,
                'precio_extra': precio['total'],
                'nuevo_total': float(reserva.precio_total),
            }

        except Exception as e:
            session.rollback()
            session.close()
            return {'success': False, 'error': str(e)}

    def solicitar_cambio_nombre(self, codigo_reserva, pasajero_indice, nuevo_nombre, nuevos_apellidos):
        """
        Solicita corrección de nombre en una reserva.
        Normalmente las aerolíneas permiten correcciones menores.
        """
        from database import ReservaVuelo, get_db_session

        session = get_db_session()
        try:
            reserva = session.query(ReservaVuelo).filter_by(
                codigo_reserva=codigo_reserva
            ).first()

            if not reserva:
                return {'success': False, 'error': 'Reserva no encontrada'}

            pasajeros = json.loads(reserva.pasajeros) if reserva.pasajeros else []
            if pasajero_indice >= len(pasajeros):
                return {'success': False, 'error': 'Pasajero no encontrado'}

            pax = pasajeros[pasajero_indice]
            nombre_original = f"{pax.get('given_name', '')} {pax.get('family_name', '')}"
            nombre_nuevo = f"{nuevo_nombre} {nuevos_apellidos}"

            # Registrar la solicitud
            notas = json.loads(reserva.notas) if reserva.notas else {}
            cambios = notas.get('cambios_nombre', [])
            cambios.append({
                'pasajero': pasajero_indice,
                'original': nombre_original,
                'nuevo': nombre_nuevo,
                'estado': 'pendiente',
                'fecha': datetime.utcnow().isoformat(),
                'coste_estimado': 30.00,  # Coste típico de corrección
            })
            notas['cambios_nombre'] = cambios
            reserva.notas = json.dumps(notas)

            session.commit()
            session.close()

            return {
                'success': True,
                'mensaje': 'Solicitud de cambio de nombre registrada. Un agente la procesará en breve.',
                'coste_estimado': 30.00,
            }

        except Exception as e:
            session.rollback()
            session.close()
            return {'success': False, 'error': str(e)}

    def solicitar_reembolso(self, codigo_reserva, motivo, cliente_id=None, tipo='total'):
        """
        Crea una solicitud de reembolso total o parcial.
        """
        from database import ReservaVuelo, get_db_session

        session = get_db_session()
        try:
            reserva = session.query(ReservaVuelo).filter_by(
                codigo_reserva=codigo_reserva
            ).first()

            if not reserva:
                return {'success': False, 'error': 'Reserva no encontrada'}

            if reserva.estado in ('CANCELADO', 'REEMBOLSADO'):
                return {'success': False, 'error': 'La reserva ya está cancelada o reembolsada'}

            # Crear solicitud de reembolso
            try:
                from database.models_clientes import SolicitudReembolso
                
                reembolso = SolicitudReembolso(
                    cliente_id=cliente_id,
                    codigo_reserva=codigo_reserva,
                    tipo_reembolso=tipo,
                    monto_solicitado=float(reserva.precio_total),
                    motivo=motivo,
                    estado='solicitado',
                )
                session.add(reembolso)
                session.commit()
                reembolso_id = reembolso.id
            except Exception:
                # Si no existe la tabla, registrar en notas
                notas = json.loads(reserva.notas) if reserva.notas else {}
                notas['reembolso_solicitado'] = {
                    'tipo': tipo,
                    'motivo': motivo,
                    'monto': float(reserva.precio_total),
                    'fecha': datetime.utcnow().isoformat(),
                    'estado': 'solicitado',
                }
                reserva.notas = json.dumps(notas)
                session.commit()
                reembolso_id = None

            session.close()

            return {
                'success': True,
                'reembolso_id': reembolso_id,
                'mensaje': 'Solicitud de reembolso registrada. Recibirás una respuesta en 24-48 horas.',
            }

        except Exception as e:
            session.rollback()
            session.close()
            return {'success': False, 'error': str(e)}
