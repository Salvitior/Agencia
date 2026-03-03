import os
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

class EmailManager:
    """Manages sending automated emails to customers."""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_pass = os.getenv('SMTP_PASS')
        self.sender_email = os.getenv('SENDER_EMAIL', self.smtp_user)
        self.smtp_timeout = int(os.getenv('SMTP_TIMEOUT', '20'))
        self.smtp_use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() == 'true'

    @staticmethod
    def _looks_like_email(value):
        return isinstance(value, str) and '@' in value and '.' in value.split('@')[-1]

    def send_email(self, to_email, subject, body_html):
        if not self._looks_like_email(to_email):
            logger.warning(f"⚠️ Invalid recipient email: {to_email}")
            return False

        if not self.smtp_user or not self.smtp_pass:
            logger.warning("⚠️ SMTP credentials not found. Email not sent.")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(body_html, 'html'))

            if self.smtp_use_ssl or self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=self.smtp_timeout) as server:
                    server.login(self.smtp_user, self.smtp_pass)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.smtp_timeout) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.smtp_user, self.smtp_pass)
                    server.send_message(msg)
            
            logger.info(f"📧 Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return False

    def send_order_confirmation(self, to_email, booking_ref, amount, currency):
        subject = f"Confirmación de Reserva - {booking_ref}"
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h1 style="color: #6366f1;">¡Gracias por tu reserva!</h1>
                <p>Tu vuelo ha sido confirmado con éxito.</p>
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px;">
                    <p><strong>Localizador:</strong> {booking_ref}</p>
                    <p><strong>Importe Total:</strong> {amount} {currency}</p>
                </div>
                <p>Puedes realizar el check-in desde nuestra web 24h antes de tu vuelo.</p>
                <p>Buen viaje,<br>El equipo de Viatges Carcaixent</p>
            </body>
        </html>
        """
        return self.send_email(to_email, subject, html)

    def send_flight_tickets(self, reserva, order_data):
        """Envía billetes electrónicos tras confirmación de vuelo"""
        booking_ref = order_data.get('booking_reference', 'N/A')
        pasajeros = order_data.get('passengers', [])
        slices = order_data.get('slices', [])
        
        # Construir info de vuelo
        flights_info = ""
        for idx, slice_data in enumerate(slices, 1):
            segments = slice_data.get('segments', [])
            if segments:
                origin = segments[0].get('origin', {}).get('iata_code', 'N/A')
                destination = segments[-1].get('destination', {}).get('iata_code', 'N/A')
                departure = segments[0].get('departing_at', 'N/A')
                flights_info += f"""
                <div style="margin: 15px 0; padding: 15px; background: #f1f5f9; border-radius: 8px;">
                    <h3 style="margin-top: 0; color: #475569;">Vuelo {idx}: {origin} → {destination}</h3>
                    <p><strong>Salida:</strong> {departure}</p>
                    <p><strong>Segmentos:</strong> {len(segments)}</p>
                </div>
                """
        
        passengers_info = ""
        for pax in pasajeros:
            name = f"{pax.get('given_name', '')} {pax.get('family_name', '')}"
            passengers_info += f"<li>{name}</li>"
        
        subject = f"🎫 Tus Billetes Electrónicos - {booking_ref}"
        html = f"""
        <html>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px;">
                <div style="max-width: 650px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <div style="background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); padding: 30px; text-align: center; color: white;">
                        <h1 style="margin: 0; font-size: 28px;">✈️ Billetes Confirmados</h1>
                        <p style="margin: 10px 0 0; opacity: 0.9;">Código de Reserva: <strong>{reserva.codigo_reserva}</strong></p>
                    </div>
                    
                    <div style="padding: 30px;">
                        <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 20px; margin-bottom: 25px; border-radius: 4px;">
                            <p style="margin: 0; color: #047857; font-weight: bold;">✅ Tu reserva ha sido confirmada con la aerolínea</p>
                            <p style="margin: 10px 0 0; color: #065f46;">Localizador: <strong style="font-size: 18px; letter-spacing: 1px;">{booking_ref}</strong></p>
                        </div>
                        
                        <h2 style="color: #334155; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">👥 Pasajeros</h2>
                        <ul style="color: #475569;">
                            {passengers_info}
                        </ul>
                        
                        <h2 style="color: #334155; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; margin-top: 30px;">✈️ Detalles de tu Vuelo</h2>
                        {flights_info}
                        
                        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin-top: 25px; border-radius: 4px;">
                            <p style="margin: 0; color: #92400e;"><strong>📋 Importante:</strong></p>
                            <ul style="color: #92400e; margin: 10px 0 0; padding-left: 20px;">
                                <li>Llega al aeropuerto con 2-3 horas de antelación</li>
                                <li>Realiza el check-in online 24h antes del vuelo</li>
                                <li>Lleva documento de identidad válido</li>
                                <li>Revisa las restricciones de equipaje</li>
                            </ul>
                        </div>
                        
                        <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                            <p style="color: #64748b; margin-bottom: 15px;">¿Necesitas ayuda?</p>
                            <a href="{os.getenv('APP_URL', 'https://tuagencia.com')}/contacto" 
                               style="display: inline-block; background: #6366f1; color: white; padding: 12px 30px; 
                                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                                Contactar Soporte
                            </a>
                        </div>
                    </div>
                    
                    <div style="background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 13px;">
                        <p style="margin: 0;">Viatges Carcaixent | Confirmación de vuelo #{reserva.id}</p>
                        <p style="margin: 5px 0 0;">Este es un email automático, por favor no respondas directamente.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        logger.info(f"📧 Enviando billetes electrónicos a {reserva.email_cliente} para reserva {reserva.codigo_reserva}")
        return self.send_email(reserva.email_cliente, subject, html)

    def enviar_confirmacion_amadeus(self, reserva, pnr, tickets):
        """
        Envía confirmación y eTickets Amadeus tras emisión automática post-pago.
        
        reserva: ReservaVuelo object
        pnr: PNR code from Amadeus
        tickets: List of ticket objects with ticketNumber
        """
        email_to = reserva.correo_contacto or reserva.email_cliente or 'no-email@agencia.local'
        
        try:
            # Extraer números de ticket
            ticket_numbers = []
            if isinstance(tickets, list):
                for t in tickets:
                    if isinstance(t, dict):
                        ticket_numbers.append(t.get('ticketNumber', 'N/A'))
                    else:
                        ticket_numbers.append(str(t))
            
            tickets_str = ", ".join(ticket_numbers) if ticket_numbers else "Procesando..."
            
            # Extraer datos del vuelo
            try:
                datos_vuelo = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else (reserva.datos_vuelo or {})
            except:
                datos_vuelo = {}
            
            origin = datos_vuelo.get('origen', 'N/A')
            destination = datos_vuelo.get('destino', 'N/A')
            flight_info = f"{origin} → {destination}" if origin and destination else "Ver detalles en tu cuenta"
            
            subject = f"🎫 Emisión Confirmada - PNR {pnr}"
            html = f"""
            <html>
                <body style="font-family: 'Segoe UI', Arial, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px;">
                    <div style="max-width: 650px; margin: auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; text-align: center; color: white;">
                            <h1 style="margin: 0; font-size: 28px;">✅ Emisión Completada</h1>
                            <p style="margin: 10px 0 0; opacity: 0.9;">Tu vuelo ha sido emitido automáticamente</p>
                        </div>
                        
                        <div style="padding: 30px;">
                            <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 20px; margin-bottom: 25px; border-radius: 4px;">
                                <p style="margin: 0; color: #047857; font-weight: bold;">✈️ Vuelo Emitido</p>
                                <p style="margin: 10px 0 0; color: #065f46; font-size: 16px;"><strong>{flight_info}</strong></p>
                            </div>
                            
                            <div style="background: #f0f9ff; border: 2px solid #0284c7; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                                <h3 style="margin-top: 0; color: #0c4a6e;">📍 Detalles de Reserva</h3>
                                <table style="width: 100%; border-collapse: collapse;">
                                    <tr>
                                        <td style="padding: 8px 0; color: #475569;"><strong>Código de Reserva:</strong></td>
                                        <td style="padding: 8px 0; color: #1e40af; font-weight: bold;">{reserva.codigo_reserva}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0; color: #475569;"><strong>PNR:</strong></td>
                                        <td style="padding: 8px 0; color: #1e40af; font-size: 18px; letter-spacing: 1px; font-weight: bold;">{pnr}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0; color: #475569;"><strong>Números de Ticket:</strong></td>
                                        <td style="padding: 8px 0; color: #1e40af; font-weight: bold;">{tickets_str}</td>
                                    </tr>
                                    <tr>
                                        <td style="padding: 8px 0; color: #475569;"><strong>Proveedor:</strong></td>
                                        <td style="padding: 8px 0; color: #1e40af; font-weight: bold;">Amadeus</td>
                                    </tr>
                                </table>
                            </div>
                            
                            <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                                <p style="margin: 0; color: #92400e;"><strong>📋 Próximos Pasos:</strong></p>
                                <ul style="color: #92400e; margin: 10px 0 0; padding-left: 20px;">
                                    <li>Guarda tu PNR para check-in online o en mostrador</li>
                                    <li>Llega al aeropuerto con 2-3 horas de antelación</li>
                                    <li>Ten listos tus documentos (pasaporte/DNI)</li>
                                    <li>Verifica las restricciones de equipaje</li>
                                </ul>
                            </div>
                            
                            <div style="background: #e0e7ff; border-left: 4px solid #6366f1; padding: 15px; border-radius: 4px;">
                                <p style="margin: 0; color: #3730a3;"><strong>💳 Estado del Pago:</strong></p>
                                <p style="margin: 10px 0 0; color: #3730a3;">Tu pago ha sido procesado exitosamente. El vuelo ha sido emitido automáticamente.</p>
                            </div>
                            
                            <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                                <p style="color: #64748b; margin-bottom: 15px;">¿Necesitas ayuda?</p>
                                <a href="{os.getenv('APP_URL', 'https://tuagencia.com')}/contacto" 
                                   style="display: inline-block; background: #6366f1; color: white; padding: 12px 30px; 
                                          text-decoration: none; border-radius: 6px; font-weight: bold;">
                                    Contactar Soporte
                                </a>
                            </div>
                        </div>
                        
                        <div style="background: #f1f5f9; padding: 20px; text-align: center; color: #64748b; font-size: 13px;">
                            <p style="margin: 0;">Viatges Carcaixent | Confirmación de emisión #{reserva.id}</p>
                            <p style="margin: 5px 0 0;">Este es un email automático, por favor no respondas directamente.</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
            logger.info(f"📧 Enviando confirmación Amadeus a {email_to} (PNR: {pnr})")
            return self.send_email(email_to, subject, html)
            
        except Exception as e:
            logger.error(f"❌ Error enviando email de confirmación Amadeus: {e}")
            return False

