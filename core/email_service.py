from flask_mail import Mail, Message
import os
from datetime import datetime
import base64

class EmailService:
    def __init__(self, app=None):
        self.mail = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
        app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
        app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
        app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
        app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))
        
        self.mail = Mail(app)
        self.admin_email = os.getenv('ADMIN_EMAIL', os.getenv('MAIL_USERNAME'))
    
    def generar_token_confirmacion(self, id_solicitud):
        # Generamos un token simple
        return base64.urlsafe_b64encode(f"{id_solicitud}:{datetime.utcnow().timestamp()}".encode()).decode()

    def decodificar_token(self, token):
        try:
            decoded = base64.urlsafe_b64decode(token).decode()
            id_solicitud, _ = decoded.split(':')
            return int(id_solicitud)
        except:
            return None

    def enviar_solicitud_proveedor(self, solicitud, tour):
        """
        Envía email al proveedor B2B para confirmar disponibilidad.
        Incluye un enlace mágico para confirmar la reserva.
        """
        # Simulamos envío al admin/test si no hay email proveedor real
        provider_email = os.getenv('ADMIN_EMAIL') 
        
        token = self.generar_token_confirmacion(solicitud.id)
        confirm_link = f"{os.getenv('APP_URL')}/confirmar-reserva/{token}"
        
        subject = f"🔔 Nueva Solicitud de Reserva: {tour.titulo} (ID: {solicitud.id})"
        
        html_body = f"""
        <html>
        <body style="font-family: sans-serif; background-color: #f3f4f6; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 8px;">
            <h2 style="color: #1e293b;">Solicitud de Bloqueo de Plazas</h2>
            <p>Hola, necesitamos bloquear plazas para la siguiente reserva:</p>
            <ul>
                <li><strong>Tour:</strong> {tour.titulo}</li>
                <li><strong>Proveedor Ref:</strong> {tour.proveedor}</li>
                <li><strong>Cliente:</strong> {solicitud.nombre_cliente} {solicitud.apellidos_cliente}</li>
                <li><strong>Pax:</strong> {solicitud.num_personas}</li>
                <li><strong>Fecha:</strong> {solicitud.fecha_preferida.strftime('%d/%m/%Y') if solicitud.fecha_preferida else 'A confirmar'}</li>
            </ul>
            <p style="background:#f3f4f6; padding:15px; border-left:4px solid #bfa15f;">
                {solicitud.mensaje or "Sin observaciones."}
            </p>
            <br>
            <p>Por favor, confirma disponibilidad haciendo clic abajo:</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{confirm_link}" style="background:#10b981; color:white; padding:15px 30px; text-decoration:none; border-radius:5px; font-weight: bold;">
                    ✅ CONFIRMAR DISPONIBILIDAD
                </a>
            </div>
            <p style="font-size: 0.9em; color: #64748b;">Si no hay plazas, por favor responde a este correo con alternativas.</p>
        </div>
        </body>
        </html>
        """
        return self._send_raw(provider_email, subject, html_body)

    def enviar_confirmacion_cliente_final(self, solicitud, tour):
        """Envía confirmación final al cliente tras la confirmación del proveedor"""
        subject = f"✅ Reserva Confirmada: {tour.titulo}"
        
        html_body = f"""
        <html>
        <body style="font-family: sans-serif; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px; border-top: 6px solid #bfa15f;">
            <h1 style="color: #1e293b; margin-top:0;">¡Tu viaje está confirmado!</h1>
            <p>Hola {solicitud.nombre_cliente},</p>
            <p>Tenemos buenas noticias. El proveedor ha confirmado las plazas para <strong>{tour.titulo}</strong>.</p>
            
            <div style="background: #ecfdf5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #047857; margin-top:0;">Próximos Pasos (Pago)</h3>
                <p style="margin-bottom: 0;">Para finalizar la reserva, por favor realiza el pago del depósito. Un agente te contactará en breve con los detalles finales.</p>
            </div>
            
            <p>Puedes contactarnos al Whatsapp prioritario si tienes dudas.</p>
            
            <div style="margin-top:20px; text-align:center;">
                <a href="{os.getenv('APP_URL')}/contacto" style="background:#0f172a; color:white; padding:15px 30px; text-decoration:none; border-radius:30px; font-weight:bold;">
                    CONTACTAR AGENCIA
                </a>
            </div>
        </div>
        </body>
        </html>
        """
        return self._send_raw(solicitud.email_cliente, subject, html_body)

    def _send_raw(self, to, subject, html):
        try:
            msg = Message(subject=subject, recipients=[to], html=html)
            self.mail.send(msg)
            print(f"✅ Email enviado a {to}")
            return True
        except Exception as e:
            print(f"❌ Error enviando email: {e}")
            return False

    # Mantener métodos legacy por compatibilidad (opcional, o redirigirlos)
    def enviar_solicitud_tour(self, solicitud_data, tour_data):
        provider_email = os.getenv('ADMIN_EMAIL', getattr(self, 'admin_email', None))
        if not provider_email:
            return False

        nombre_tour = tour_data.get('titulo') or tour_data.get('nombre') or 'Tour sin título'
        subject = f"🔔 Nueva solicitud de tour: {nombre_tour}"
        html_body = f"""
        <html>
        <body style="font-family: sans-serif; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 24px; border-radius: 10px;">
            <h2 style="margin-top: 0; color: #1e293b;">Nueva solicitud de tour</h2>
            <ul>
                <li><strong>Tour:</strong> {nombre_tour}</li>
                <li><strong>Cliente:</strong> {solicitud_data.get('nombre', '')}</li>
                <li><strong>Email:</strong> {solicitud_data.get('email', '')}</li>
                <li><strong>Teléfono:</strong> {solicitud_data.get('telefono', '')}</li>
                <li><strong>Personas:</strong> {solicitud_data.get('num_personas', 1)}</li>
            </ul>
            <p><strong>Mensaje:</strong></p>
            <p style="background: #f3f4f6; padding: 12px; border-radius: 8px;">
                {solicitud_data.get('mensaje', 'Sin mensaje')}
            </p>
        </div>
        </body>
        </html>
        """
        return self._send_raw(provider_email, subject, html_body)

    def enviar_notificacion_pedido(self, pedido_data):
        admin_email = os.getenv('ADMIN_EMAIL', getattr(self, 'admin_email', None))
        if not admin_email:
            return False

        subject = f"🧾 Nuevo pedido registrado: {pedido_data.get('codigo_reserva', 'SIN-CODIGO')}"
        html_body = f"""
        <html>
        <body style="font-family: sans-serif; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 24px; border-radius: 10px;">
            <h2 style="margin-top: 0; color: #1e293b;">Notificación de pedido</h2>
            <ul>
                <li><strong>Código:</strong> {pedido_data.get('codigo_reserva', '')}</li>
                <li><strong>Cliente:</strong> {pedido_data.get('nombre_cliente', '')}</li>
                <li><strong>Email:</strong> {pedido_data.get('email_cliente', '')}</li>
                <li><strong>Importe:</strong> {pedido_data.get('precio_total', '')} {pedido_data.get('moneda', 'EUR')}</li>
                <li><strong>Estado:</strong> {pedido_data.get('estado', '')}</li>
            </ul>
        </div>
        </body>
        </html>
        """
        return self._send_raw(admin_email, subject, html_body)

    def enviar_confirmacion_cliente(self, email, nombre, tour_titulo):
        subject = f"✅ Solicitud recibida: {tour_titulo}"
        html_body = f"""
        <html>
        <body style="font-family: sans-serif; background-color: #f8fafc; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 24px; border-radius: 10px;">
            <h2 style="margin-top: 0; color: #1e293b;">Hemos recibido tu solicitud</h2>
            <p>Hola {nombre},</p>
            <p>Tu solicitud para el tour <strong>{tour_titulo}</strong> se ha enviado correctamente.</p>
            <p>En breve nos pondremos en contacto contigo con la disponibilidad y los siguientes pasos.</p>
        </div>
        </body>
        </html>
        """
        return self._send_raw(email, subject, html_body)

email_service = EmailService()
