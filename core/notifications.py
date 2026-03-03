"""
Servicio de Notificaciones:
- Recordatorio check-in 24h antes
- Cambios de vuelo (retrasos, cancelaciones, cambio de puerta)
- Confirmaciones de reserva
- Enlace directo al check-in de la aerolínea
"""

import json
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Gestiona el envío de notificaciones a clientes por múltiples canales:
    - Email (principal)
    - SMS (futuro)
    - Push notifications (futuro)
    """

    def __init__(self, email_manager=None):
        self.email_manager = email_manager
        self.app_url = os.getenv('APP_URL', 'https://viatgescarcaixent.com')

    def _guardar_notificacion(self, cliente_id, codigo_reserva, tipo, titulo, mensaje, datos_extra=None, canal_email=False):
        """Guarda la notificación en la base de datos"""
        try:
            from database import get_db_session
            from database.models_clientes import NotificacionCliente

            session = get_db_session()
            notif = NotificacionCliente(
                cliente_id=cliente_id,
                codigo_reserva=codigo_reserva,
                tipo=tipo,
                titulo=titulo,
                mensaje=mensaje,
                datos_extra=json.dumps(datos_extra) if datos_extra else None,
                enviado_email=canal_email,
                fecha_envio=datetime.utcnow(),
            )
            session.add(notif)
            session.commit()
            notif_id = notif.id
            session.close()
            return notif_id
        except Exception as e:
            logger.warning(f"No se pudo guardar notificación en DB: {e}")
            return None

    def _buscar_cliente_id(self, email):
        """Busca el ID de cliente por email"""
        try:
            from database import get_db_session
            from database.models_clientes import ClienteUsuario
            session = get_db_session()
            cliente = session.query(ClienteUsuario).filter_by(email=email, activo=True).first()
            cliente_id = cliente.id if cliente else None
            session.close()
            return cliente_id
        except Exception:
            return None

    # ================================
    # RECORDATORIO CHECK-IN 24H
    # ================================

    def enviar_recordatorio_checkin(self, reserva):
        """
        Envía recordatorio de check-in 24h antes del vuelo.
        Incluye enlace directo al check-in de la aerolínea.
        """
        try:
            datos_vuelo = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else (reserva.datos_vuelo or {})
            
            origen = datos_vuelo.get('origen', 'N/A')
            destino = datos_vuelo.get('destino', 'N/A')
            aerolinea = datos_vuelo.get('aerolinea', '')
            iata_code = datos_vuelo.get('aerolinea_iata', '')
            
            # Enlace de check-in
            checkin_link = self._obtener_enlace_checkin(iata_code, reserva.booking_reference)
            
            checkin_html = ""
            if checkin_link:
                checkin_html = f"""
                <div style="text-align: center; margin: 25px 0;">
                    <a href="{checkin_link}" target="_blank"
                       style="display: inline-block; background: #10b981; color: white; 
                              padding: 15px 40px; text-decoration: none; border-radius: 8px; 
                              font-weight: bold; font-size: 16px;">
                        ✈️ Hacer Check-in Online
                    </a>
                    <p style="color: #64748b; font-size: 12px; margin-top: 10px;">
                        Se abrirá la web de {aerolinea or 'la aerolínea'}
                    </p>
                </div>
                """

            manage_link = f"{self.app_url}/api/manage-booking"
            
            subject = f"⏰ ¡Check-in abierto! {origen} → {destino} - Mañana"
            html = f"""
            <html>
                <body style="font-family: 'Segoe UI', Arial; color: #1e293b; background: #f8fafc; padding: 20px;">
                    <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 25px; text-align: center; color: white;">
                            <h1 style="margin: 0;">⏰ Check-in Disponible</h1>
                            <p style="margin: 8px 0 0; font-size: 18px;">{origen} → {destino}</p>
                        </div>
                        <div style="padding: 25px;">
                            <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 4px;">
                                <p style="margin: 0; color: #92400e; font-weight: bold;">
                                    Tu vuelo sale mañana. ¡Haz el check-in ahora!
                                </p>
                            </div>
                            
                            <div style="margin: 20px 0; padding: 15px; background: #f8fafc; border-radius: 8px;">
                                <p><strong>Reserva:</strong> {reserva.codigo_reserva}</p>
                                <p><strong>Localizador:</strong> {reserva.booking_reference or 'N/A'}</p>
                                <p><strong>Vuelo:</strong> {reserva.numero_vuelo or 'Ver detalles'}</p>
                            </div>

                            {checkin_html}
                            
                            <div style="background: #f0f9ff; padding: 15px; border-radius: 8px; margin-top: 20px;">
                                <p style="margin: 0; color: #0369a1; font-weight: bold;">📋 Recuerda:</p>
                                <ul style="color: #0369a1; margin: 8px 0 0; padding-left: 18px;">
                                    <li>Lleva tu DNI/pasaporte en vigor</li>
                                    <li>Llega al aeropuerto con 2-3h de antelación</li>
                                    <li>Revisa las restricciones de equipaje</li>
                                </ul>
                            </div>
                            
                            <div style="text-align: center; margin-top: 20px;">
                                <a href="{manage_link}" style="color: #6366f1; font-weight: bold;">
                                    Gestionar reserva
                                </a>
                            </div>
                        </div>
                        <div style="background: #f1f5f9; padding: 15px; text-align: center; color: #94a3b8; font-size: 12px;">
                            Viatges Carcaixent - Recordatorio automático
                        </div>
                    </div>
                </body>
            </html>
            """

            # Enviar email
            enviado = False
            if self.email_manager:
                enviado = self.email_manager.send_email(reserva.email_cliente, subject, html)

            # Guardar notificación
            cliente_id = self._buscar_cliente_id(reserva.email_cliente)
            self._guardar_notificacion(
                cliente_id=cliente_id,
                codigo_reserva=reserva.codigo_reserva,
                tipo='checkin_24h',
                titulo=f'Check-in abierto: {origen} → {destino}',
                mensaje=f'Tu vuelo sale mañana. Haz el check-in ahora.',
                datos_extra={'checkin_link': checkin_link, 'vuelo': reserva.numero_vuelo},
                canal_email=enviado,
            )

            return enviado

        except Exception as e:
            logger.error(f"Error enviando recordatorio check-in: {e}")
            return False

    # ================================
    # CAMBIOS DE VUELO
    # ================================

    def notificar_cambio_vuelo(self, reserva, tipo_cambio, detalles):
        """
        Notifica al cliente sobre cambios en su vuelo.
        
        tipo_cambio: 'retraso', 'cancelacion', 'cambio_puerta', 'cambio_horario', 'cambio_terminal'
        detalles: dict con información específica del cambio
        """
        try:
            datos_vuelo = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else {}
            origen = datos_vuelo.get('origen', 'N/A')
            destino = datos_vuelo.get('destino', 'N/A')

            # Configurar colores y mensajes según el tipo
            configs = {
                'retraso': {
                    'color_bg': '#fef3c7', 'color_header': '#f59e0b',
                    'icono': '⚠️', 'titulo': 'Retraso en tu vuelo',
                    'urgencia': 'media',
                },
                'cancelacion': {
                    'color_bg': '#fee2e2', 'color_header': '#ef4444',
                    'icono': '🚫', 'titulo': 'Vuelo cancelado',
                    'urgencia': 'alta',
                },
                'cambio_puerta': {
                    'color_bg': '#dbeafe', 'color_header': '#3b82f6',
                    'icono': '🚪', 'titulo': 'Cambio de puerta de embarque',
                    'urgencia': 'baja',
                },
                'cambio_horario': {
                    'color_bg': '#fef3c7', 'color_header': '#f59e0b',
                    'icono': '🕐', 'titulo': 'Cambio de horario',
                    'urgencia': 'media',
                },
                'cambio_terminal': {
                    'color_bg': '#dbeafe', 'color_header': '#3b82f6',
                    'icono': '🏢', 'titulo': 'Cambio de terminal',
                    'urgencia': 'media',
                },
            }

            config = configs.get(tipo_cambio, configs['cambio_horario'])

            # Construir detalles HTML
            detalles_html = ""
            for key, value in detalles.items():
                label = key.replace('_', ' ').capitalize()
                detalles_html += f"<p><strong>{label}:</strong> {value}</p>"

            subject = f"{config['icono']} {config['titulo']} - {origen}→{destino}"
            html = f"""
            <html>
                <body style="font-family: Arial; color: #1e293b; background: #f8fafc; padding: 20px;">
                    <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px; overflow: hidden;">
                        <div style="background: {config['color_header']}; padding: 25px; text-align: center; color: white;">
                            <h1 style="margin: 0;">{config['icono']} {config['titulo']}</h1>
                            <p style="margin: 8px 0 0;">{origen} → {destino}</p>
                        </div>
                        <div style="padding: 25px;">
                            <div style="background: {config['color_bg']}; padding: 15px; border-radius: 8px;">
                                {detalles_html}
                            </div>
                            <div style="margin-top: 20px; padding: 15px; background: #f8fafc; border-radius: 8px;">
                                <p><strong>Reserva:</strong> {reserva.codigo_reserva}</p>
                                <p><strong>Localizador:</strong> {reserva.booking_reference or 'N/A'}</p>
                            </div>
                            <p style="margin-top: 20px; color: #64748b;">
                                Si necesitas asistencia, contacta con nosotros.
                            </p>
                        </div>
                    </div>
                </body>
            </html>
            """

            enviado = False
            if self.email_manager:
                enviado = self.email_manager.send_email(reserva.email_cliente, subject, html)

            cliente_id = self._buscar_cliente_id(reserva.email_cliente)
            self._guardar_notificacion(
                cliente_id=cliente_id,
                codigo_reserva=reserva.codigo_reserva,
                tipo=f'cambio_vuelo_{tipo_cambio}',
                titulo=config['titulo'],
                mensaje=json.dumps(detalles),
                datos_extra=detalles,
                canal_email=enviado,
            )

            return enviado
        except Exception as e:
            logger.error(f"Error notificando cambio de vuelo: {e}")
            return False

    # ================================
    # CONFIRMACIÓN DE RESERVA
    # ================================

    def notificar_confirmacion_reserva(self, reserva, booking_reference):
        """Envía confirmación de reserva con localizador y resumen"""
        try:
            datos_vuelo = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else {}
            pasajeros = json.loads(reserva.pasajeros) if isinstance(reserva.pasajeros, str) else []

            origen = datos_vuelo.get('origen', 'N/A')
            destino = datos_vuelo.get('destino', 'N/A')

            pax_list = ""
            for p in pasajeros:
                nombre = f"{p.get('given_name', '')} {p.get('family_name', '')}"
                pax_list += f"<li>{nombre}</li>"

            manage_link = f"{self.app_url}/cliente/dashboard"
            eticket_link = f"{self.app_url}/cliente/api/reservas/{reserva.codigo_reserva}/eticket"

            subject = f"✅ Reserva Confirmada - {booking_reference} - {origen}→{destino}"
            html = f"""
            <html>
                <body style="font-family: 'Segoe UI', Arial; color: #1e293b; background: #f8fafc; padding: 20px;">
                    <div style="max-width: 650px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; text-align: center; color: white;">
                            <h1 style="margin: 0;">✅ ¡Reserva Confirmada!</h1>
                        </div>
                        <div style="padding: 30px;">
                            <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 20px; border-radius: 4px; margin-bottom: 25px;">
                                <p style="margin: 0; color: #047857; font-weight: bold;">Tu localizador:</p>
                                <p style="margin: 5px 0 0; font-size: 24px; color: #065f46; letter-spacing: 2px; font-weight: bold;">{booking_reference}</p>
                            </div>

                            <h3 style="color: #334155; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px;">📋 Resumen</h3>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr><td style="padding: 6px 0; color: #64748b;"><strong>Reserva:</strong></td><td>{reserva.codigo_reserva}</td></tr>
                                <tr><td style="padding: 6px 0; color: #64748b;"><strong>Ruta:</strong></td><td>{origen} → {destino}</td></tr>
                                <tr><td style="padding: 6px 0; color: #64748b;"><strong>Fecha:</strong></td><td>{datos_vuelo.get('fecha_ida', 'N/A')}</td></tr>
                                <tr><td style="padding: 6px 0; color: #64748b;"><strong>Tipo:</strong></td><td>{'Ida y vuelta' if reserva.es_viaje_redondo else 'Solo ida'}</td></tr>
                                <tr><td style="padding: 6px 0; color: #64748b;"><strong>Total:</strong></td><td><strong>{reserva.precio_total} {reserva.moneda or 'EUR'}</strong></td></tr>
                            </table>

                            <h3 style="color: #334155; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-top: 20px;">👥 Pasajeros</h3>
                            <ul>{pax_list}</ul>

                            <div style="text-align: center; margin-top: 30px;">
                                <a href="{eticket_link}" style="display: inline-block; background: #6366f1; color: white; 
                                   padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 5px;">
                                    📄 Descargar E-Ticket
                                </a>
                                <a href="{manage_link}" style="display: inline-block; background: #10b981; color: white; 
                                   padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 5px;">
                                    👤 Mi Área de Cliente
                                </a>
                            </div>
                        </div>
                        <div style="background: #f1f5f9; padding: 20px; text-align: center; color: #94a3b8; font-size: 12px;">
                            <p style="margin: 0;">Viatges Carcaixent | Confirmación #{reserva.id}</p>
                            <p style="margin: 5px 0 0;">Este email es tu confirmación de compra. Guárdalo.</p>
                        </div>
                    </div>
                </body>
            </html>
            """

            enviado = False
            if self.email_manager:
                enviado = self.email_manager.send_email(reserva.email_cliente, subject, html)

            cliente_id = self._buscar_cliente_id(reserva.email_cliente)
            self._guardar_notificacion(
                cliente_id=cliente_id,
                codigo_reserva=reserva.codigo_reserva,
                tipo='confirmacion',
                titulo=f'Reserva confirmada: {origen} → {destino}',
                mensaje=f'Localizador: {booking_reference}',
                datos_extra={'booking_reference': booking_reference},
                canal_email=enviado,
            )

            return enviado
        except Exception as e:
            logger.error(f"Error enviando confirmación: {e}")
            return False

    # ================================
    # MONITOREO DE STATUS DE VUELO
    # ================================

    def verificar_cambios_vuelo(self, amadeus_adapter=None):
        """
        Verifica cambios en vuelos próximos y notifica a los clientes.
        Se ejecuta periódicamente como tarea programada.
        """
        from database import ReservaVuelo, get_db_session
        from datetime import date

        session = get_db_session()
        try:
            hoy = date.today()
            manana = hoy + timedelta(days=1)
            pasado = hoy + timedelta(days=2)

            # Buscar reservas con vuelos en las próximas 48h
            reservas = session.query(ReservaVuelo).filter(
                ReservaVuelo.estado.in_(['CONFIRMADO', 'EMITIDO']),
                ReservaVuelo.fecha_vuelo_ida.between(hoy, pasado),
            ).all()

            cambios_detectados = 0
            for reserva in reservas:
                try:
                    # Verificar estado del vuelo con Amadeus
                    if amadeus_adapter and reserva.numero_vuelo:
                        status = amadeus_adapter.get_flight_status(
                            reserva.numero_vuelo,
                            reserva.fecha_vuelo_ida.isoformat() if reserva.fecha_vuelo_ida else None,
                        )
                        
                        if status:
                            # Detectar retraso
                            if status.get('delay_minutes', 0) > 15:
                                self.notificar_cambio_vuelo(reserva, 'retraso', {
                                    'retraso_minutos': status['delay_minutes'],
                                    'nueva_hora_salida': status.get('new_departure_time', 'Pendiente'),
                                    'motivo': status.get('reason', 'No especificado'),
                                })
                                cambios_detectados += 1

                            # Detectar cancelación
                            if status.get('status') == 'CANCELLED':
                                self.notificar_cambio_vuelo(reserva, 'cancelacion', {
                                    'motivo': status.get('reason', 'Vuelo cancelado por la aerolínea'),
                                    'opciones': 'Contacta con nosotros para alternativas o reembolso.',
                                })
                                cambios_detectados += 1

                            # Detectar cambio de puerta
                            if status.get('gate') and status.get('gate_changed'):
                                self.notificar_cambio_vuelo(reserva, 'cambio_puerta', {
                                    'nueva_puerta': status['gate'],
                                    'terminal': status.get('terminal', 'N/A'),
                                })
                                cambios_detectados += 1
                                
                except Exception as e:
                    logger.warning(f"Error verificando vuelo {reserva.codigo_reserva}: {e}")

            session.close()
            logger.info(f"🔍 Verificación de vuelos: {len(reservas)} revisados, {cambios_detectados} cambios detectados")
            return cambios_detectados

        except Exception as e:
            session.close()
            logger.error(f"Error en verificación de vuelos: {e}")
            return 0

    # ================================
    # UTILIDADES
    # ================================

    def _obtener_enlace_checkin(self, iata_code, booking_ref=''):
        """
        Retorna el enlace directo al check-in online de la aerolínea.
        """
        checkin_links = {
            'IB': 'https://www.iberia.com/es/check-in/',
            'VY': 'https://www.vueling.com/es/servicios-vueling/check-in-online',
            'FR': 'https://www.ryanair.com/es/es/check-in',
            'U2': 'https://www.easyjet.com/es/check-in',
            'UX': 'https://www.aireuropa.com/es/vuelos/check-in-online',
            'LH': 'https://www.lufthansa.com/es/es/check-in',
            'AF': 'https://wwws.airfrance.es/check-in',
            'BA': 'https://www.britishairways.com/travel/olcilandingpageauthaliases/public/es_es',
            'KL': 'https://www.klm.es/check-in',
            'TK': 'https://www.turkishairlines.com/es-es/any-content/check-in/',
            'EK': 'https://www.emirates.com/es/english/manage-booking/online-check-in/',
            'QR': 'https://www.qatarairways.com/en/check-in.html',
            'W6': 'https://wizzair.com/es-es/check-in',
            'NK': 'https://www.spirit.com/check-in',
            'TP': 'https://www.flytap.com/es-es/check-in',
            'AZ': 'https://www.ita-airways.com/es_es/check-in.html',
            'SK': 'https://www.flysas.com/es/check-in/',
            'OS': 'https://www.austrian.com/es/es/check-in',
            'LX': 'https://www.swiss.com/es/es/check-in',
        }

        link = checkin_links.get(iata_code, '')
        if not link:
            # Generar enlace genérico
            link = f"https://www.google.com/search?q={iata_code}+airline+online+check+in"
        
        return link
