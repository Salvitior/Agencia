"""
Blueprint del Área de Cliente:
- Registro / Login
- Historial de reservas y viajes
- Datos guardados (pasajeros frecuentes, documentos)
- Ver/cancelar/modificar reserva
- Descargar e-ticket y factura
- Solicitar reembolso
- Añadir extras post-compra
- Corrección de nombre
- Notificaciones
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session as flask_session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import json
import secrets
import logging
import os

logger = logging.getLogger(__name__)

clientes_bp = Blueprint('clientes', __name__, url_prefix='/cliente')


def cliente_login_required(f):
    """Decorador para proteger rutas del área de cliente"""
    @wraps(f)
    def decorated(*args, **kwargs):
        cliente_id = flask_session.get('cliente_id')
        if not cliente_id:
            if request.is_json:
                return jsonify({'error': 'Autenticación requerida', 'redirect': '/cliente/login'}), 401
            return redirect(url_for('clientes.login'))
        return f(*args, **kwargs)
    return decorated


def get_cliente_actual():
    """Obtiene el cliente actual de la sesión"""
    from database import get_db_session
    from database.models_clientes import ClienteUsuario
    
    cliente_id = flask_session.get('cliente_id')
    if not cliente_id:
        return None
    
    session = get_db_session()
    try:
        cliente = session.query(ClienteUsuario).filter_by(id=cliente_id, activo=True).first()
        return cliente
    finally:
        session.close()


def init_clientes_blueprint(email_manager=None, booking_service=None):
    """Inicializa el blueprint con dependencias"""

    # =========================
    # REGISTRO Y AUTENTICACIÓN
    # =========================

    @clientes_bp.route('/registro', methods=['GET', 'POST'])
    def registro():
        if request.method == 'GET':
            return render_template('cliente_registro.html')

        data = request.json or request.form
        email = (data.get('email') or '').strip().lower()
        password = data.get('password', '')
        nombre = (data.get('nombre') or '').strip()
        apellidos = (data.get('apellidos') or '').strip()
        telefono = (data.get('telefono') or '').strip()
        acepta_terminos = data.get('acepta_terminos', False)

        # Validaciones
        errores = []
        if not email or '@' not in email:
            errores.append('Email inválido')
        if len(password) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres')
        if not nombre:
            errores.append('El nombre es obligatorio')
        if not apellidos:
            errores.append('Los apellidos son obligatorios')
        if not acepta_terminos:
            errores.append('Debes aceptar los términos y condiciones')

        if errores:
            return jsonify({'success': False, 'errores': errores}), 400

        from database import get_db_session
        from database.models_clientes import ClienteUsuario

        session = get_db_session()
        try:
            # Verificar email único
            existente = session.query(ClienteUsuario).filter_by(email=email).first()
            if existente:
                session.close()
                return jsonify({'success': False, 'errores': ['Ya existe una cuenta con ese email']}), 400

            # Crear usuario
            token_verificacion = secrets.token_urlsafe(32)
            nuevo_cliente = ClienteUsuario(
                email=email,
                password_hash=generate_password_hash(password),
                nombre=nombre,
                apellidos=apellidos,
                telefono=telefono,
                token_verificacion=token_verificacion,
                consentimiento_cookies=True,
                fecha_consentimiento=datetime.utcnow(),
            )
            session.add(nuevo_cliente)
            session.commit()
            cliente_id = nuevo_cliente.id
            session.close()

            # Enviar email de verificación
            if email_manager:
                try:
                    app_url = os.getenv('APP_URL', 'http://localhost:5000')
                    link = f"{app_url}/cliente/verificar/{token_verificacion}"
                    email_manager.send_email(
                        email,
                        '✉️ Verifica tu cuenta - Viatges Carcaixent',
                        f"""
                        <html><body style="font-family: Arial; color: #333;">
                            <h1 style="color: #6366f1;">¡Bienvenido/a, {nombre}!</h1>
                            <p>Gracias por registrarte en Viatges Carcaixent.</p>
                            <p>Para activar tu cuenta, haz clic en el siguiente enlace:</p>
                            <a href="{link}" style="display: inline-block; background: #6366f1; color: white; 
                               padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                                Verificar mi cuenta
                            </a>
                            <p style="color: #666; margin-top: 20px;">Si no has creado esta cuenta, ignora este email.</p>
                        </body></html>
                        """
                    )
                except Exception as e:
                    logger.error(f"Error enviando email de verificación: {e}")

            logger.info(f"✅ Nuevo cliente registrado: {email} (ID: {cliente_id})")
            return jsonify({
                'success': True,
                'mensaje': 'Cuenta creada correctamente. Revisa tu email para verificar la cuenta.',
            })
        except Exception as e:
            session.rollback()
            session.close()
            logger.error(f"Error en registro: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @clientes_bp.route('/verificar/<token>')
    def verificar_email(token):
        from database import get_db_session
        from database.models_clientes import ClienteUsuario

        session = get_db_session()
        try:
            cliente = session.query(ClienteUsuario).filter_by(token_verificacion=token).first()
            if not cliente:
                return render_template('cliente_mensaje.html',
                                      titulo='Error', mensaje='Enlace de verificación inválido o expirado.')

            cliente.email_verificado = True
            cliente.token_verificacion = None
            session.commit()
            session.close()

            return render_template('cliente_mensaje.html',
                                  titulo='¡Cuenta verificada!',
                                  mensaje='Tu cuenta ha sido verificada correctamente. Ya puedes iniciar sesión.')
        except Exception as e:
            session.close()
            return render_template('cliente_mensaje.html', titulo='Error', mensaje=str(e))

    @clientes_bp.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return render_template('cliente_login.html')

        data = request.json or request.form
        email = (data.get('email') or '').strip().lower()
        password = data.get('password', '')

        from database import get_db_session
        from database.models_clientes import ClienteUsuario

        session = get_db_session()
        try:
            cliente = session.query(ClienteUsuario).filter_by(email=email, activo=True).first()

            if not cliente or not check_password_hash(cliente.password_hash, password):
                session.close()
                return jsonify({'success': False, 'error': 'Email o contraseña incorrectos'}), 401

            if not cliente.email_verificado:
                session.close()
                return jsonify({'success': False, 'error': 'Debes verificar tu email antes de iniciar sesión'}), 403

            # Guardar sesión
            flask_session['cliente_id'] = cliente.id
            flask_session['cliente_email'] = cliente.email
            flask_session['cliente_nombre'] = cliente.nombre_completo

            cliente.ultimo_login = datetime.utcnow()
            session.commit()
            session.close()

            logger.info(f"✅ Login cliente: {email}")
            return jsonify({
                'success': True,
                'redirect': url_for('clientes.dashboard'),
                'cliente': {
                    'nombre': cliente.nombre_completo,
                    'email': cliente.email,
                }
            })
        except Exception as e:
            session.close()
            return jsonify({'success': False, 'error': str(e)}), 500

    @clientes_bp.route('/logout')
    def logout():
        flask_session.pop('cliente_id', None)
        flask_session.pop('cliente_email', None)
        flask_session.pop('cliente_nombre', None)
        return redirect('/')

    @clientes_bp.route('/recuperar-password', methods=['GET', 'POST'])
    def recuperar_password():
        if request.method == 'GET':
            return render_template('cliente_recuperar_password.html')

        data = request.json or request.form
        email = (data.get('email') or '').strip().lower()

        from database import get_db_session
        from database.models_clientes import ClienteUsuario

        session = get_db_session()
        try:
            cliente = session.query(ClienteUsuario).filter_by(email=email, activo=True).first()
            if cliente:
                token = secrets.token_urlsafe(32)
                cliente.token_reset_password = token
                cliente.token_reset_expira = datetime.utcnow() + timedelta(hours=1)
                session.commit()

                if email_manager:
                    app_url = os.getenv('APP_URL', 'http://localhost:5000')
                    link = f"{app_url}/cliente/reset-password/{token}"
                    email_manager.send_email(
                        email,
                        '🔐 Restablecer contraseña - Viatges Carcaixent',
                        f"""<html><body style="font-family: Arial;">
                            <h2>Restablece tu contraseña</h2>
                            <p>Haz clic en el enlace para crear una nueva contraseña (válido 1 hora):</p>
                            <a href="{link}" style="background: #6366f1; color: white; padding: 10px 20px; 
                               text-decoration: none; border-radius: 6px;">Restablecer contraseña</a>
                        </body></html>"""
                    )

            session.close()
            # Siempre responder igual (seguridad)
            return jsonify({'success': True, 'mensaje': 'Si el email existe, recibirás instrucciones para restablecer tu contraseña.'})
        except Exception as e:
            session.close()
            return jsonify({'success': False, 'error': str(e)}), 500

    @clientes_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        from database import get_db_session
        from database.models_clientes import ClienteUsuario

        if request.method == 'GET':
            return render_template('cliente_reset_password.html', token=token)

        data = request.json or request.form
        new_password = data.get('password', '')

        if len(new_password) < 8:
            return jsonify({'success': False, 'error': 'La contraseña debe tener al menos 8 caracteres'}), 400

        session = get_db_session()
        try:
            cliente = session.query(ClienteUsuario).filter_by(token_reset_password=token).first()
            if not cliente:
                session.close()
                return jsonify({'success': False, 'error': 'Token inválido'}), 400

            if cliente.token_reset_expira and cliente.token_reset_expira < datetime.utcnow():
                session.close()
                return jsonify({'success': False, 'error': 'El enlace ha expirado. Solicita uno nuevo.'}), 400

            cliente.password_hash = generate_password_hash(new_password)
            cliente.token_reset_password = None
            cliente.token_reset_expira = None
            session.commit()
            session.close()

            return jsonify({'success': True, 'mensaje': 'Contraseña actualizada correctamente.'})
        except Exception as e:
            session.close()
            return jsonify({'success': False, 'error': str(e)}), 500

    # =========================
    # DASHBOARD y PERFIL
    # =========================

    @clientes_bp.route('/dashboard')
    @cliente_login_required
    def dashboard():
        from database import get_db_session
        from database.models_clientes import ClienteUsuario

        session = get_db_session()
        try:
            cliente = session.query(ClienteUsuario).filter_by(id=flask_session['cliente_id']).first()
            cliente_data = cliente.to_dict() if cliente else {
                'nombre': flask_session.get('cliente_nombre', ''),
                'email': flask_session.get('cliente_email', ''),
                'apellidos': '',
                'telefono': '',
            }
            session.close()
        except Exception:
            cliente_data = {
                'nombre': flask_session.get('cliente_nombre', ''),
                'email': flask_session.get('cliente_email', ''),
                'apellidos': '',
                'telefono': '',
            }
        return render_template('cliente_dashboard.html', cliente=cliente_data)

    @clientes_bp.route('/api/perfil', methods=['GET', 'PUT'])
    @cliente_login_required
    def perfil():
        from database import get_db_session
        from database.models_clientes import ClienteUsuario

        session = get_db_session()
        try:
            cliente = session.query(ClienteUsuario).filter_by(id=flask_session['cliente_id']).first()
            if not cliente:
                session.close()
                return jsonify({'error': 'Cliente no encontrado'}), 404

            if request.method == 'GET':
                data = cliente.to_dict(incluir_sensibles=True)
                session.close()
                return jsonify(data)

            # PUT: actualizar perfil
            data = request.json
            campos_actualizables = ['nombre', 'apellidos', 'telefono', 'dni_cif', 
                                    'direccion_fiscal', 'codigo_postal', 'ciudad', 'pais',
                                    'idioma', 'moneda_preferida', 'acepta_newsletter']
            for campo in campos_actualizables:
                if campo in data:
                    setattr(cliente, campo, data[campo])

            session.commit()
            session.close()
            return jsonify({'success': True, 'mensaje': 'Perfil actualizado'})
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    # =========================
    # HISTORIAL DE RESERVAS
    # =========================

    @clientes_bp.route('/api/reservas')
    @cliente_login_required
    def listar_reservas():
        """Lista todas las reservas del cliente"""
        from database import ReservaVuelo, get_db_session
        from database.models_clientes import ReservaCliente

        session = get_db_session()
        try:
            cliente_id = flask_session['cliente_id']
            
            # Buscar por vinculación directa
            vinculos = session.query(ReservaCliente).filter_by(cliente_id=cliente_id).all()
            reservas_ids = [v.reserva_vuelo_id for v in vinculos if v.reserva_vuelo_id]
            
            # También buscar por email
            from database.models_clientes import ClienteUsuario
            cliente = session.query(ClienteUsuario).filter_by(id=cliente_id).first()
            if cliente:
                reservas_email = session.query(ReservaVuelo).filter_by(
                    email_cliente=cliente.email
                ).all()
                reservas_ids.extend([r.id for r in reservas_email])
            
            reservas_ids = list(set(reservas_ids))
            reservas = session.query(ReservaVuelo).filter(
                ReservaVuelo.id.in_(reservas_ids)
            ).order_by(ReservaVuelo.fecha_creacion.desc()).all()

            resultado = []
            for r in reservas:
                datos_vuelo = {}
                try:
                    datos_vuelo = json.loads(r.datos_vuelo) if r.datos_vuelo else {}
                except (json.JSONDecodeError, TypeError):
                    pass

                resultado.append({
                    'id': r.id,
                    'codigo_reserva': r.codigo_reserva,
                    'estado': r.estado,
                    'provider': r.provider,
                    'origen': datos_vuelo.get('origen', ''),
                    'destino': datos_vuelo.get('destino', ''),
                    'fecha_ida': datos_vuelo.get('fecha_ida', ''),
                    'aerolinea': datos_vuelo.get('aerolinea', ''),
                    'precio_total': r.precio_total,
                    'moneda': r.moneda or 'EUR',
                    'es_ida_vuelta': r.es_viaje_redondo,
                    'booking_reference': r.booking_reference,
                    'fecha_creacion': r.fecha_creacion.isoformat() if r.fecha_creacion else None,
                })

            session.close()
            return jsonify({'reservas': resultado, 'total': len(resultado)})
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @clientes_bp.route('/api/reservas/<codigo>')
    @cliente_login_required
    def detalle_reserva(codigo):
        """Detalle completo de una reserva"""
        from database import ReservaVuelo, get_db_session

        session = get_db_session()
        try:
            reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo).first()
            if not reserva:
                session.close()
                return jsonify({'error': 'Reserva no encontrada'}), 404

            # Verificar que pertenece al cliente
            from database.models_clientes import ClienteUsuario
            cliente = session.query(ClienteUsuario).filter_by(id=flask_session['cliente_id']).first()
            if not cliente or reserva.email_cliente != cliente.email:
                session.close()
                return jsonify({'error': 'No autorizado'}), 403

            datos_vuelo = json.loads(reserva.datos_vuelo) if reserva.datos_vuelo else {}
            pasajeros = json.loads(reserva.pasajeros) if reserva.pasajeros else []
            notas = json.loads(reserva.notas) if reserva.notas else {}

            resultado = {
                'codigo_reserva': reserva.codigo_reserva,
                'estado': reserva.estado,
                'provider': reserva.provider,
                'booking_reference': reserva.booking_reference,
                'datos_vuelo': datos_vuelo,
                'pasajeros': [{
                    'nombre': f"{p.get('given_name', '')} {p.get('family_name', '')}",
                    'tipo': p.get('type', 'adult'),
                } for p in pasajeros],
                'precio_vuelos': reserva.precio_vuelos,
                'precio_extras': reserva.precio_extras,
                'precio_total': reserva.precio_total,
                'moneda': reserva.moneda or 'EUR',
                'es_ida_vuelta': reserva.es_viaje_redondo,
                'extras': notas.get('extras', []),
                'extras_post_compra': notas.get('extras_post_compra', []),
                'cambios_nombre': notas.get('cambios_nombre', []),
                'reembolso': notas.get('reembolso_solicitado'),
                'fecha_creacion': reserva.fecha_creacion.isoformat() if reserva.fecha_creacion else None,
                'fecha_pago': reserva.fecha_pago.isoformat() if reserva.fecha_pago else None,
                'permite_cancelar': reserva.estado in ('PENDIENTE', 'PAGADO', 'CONFIRMADO'),
                'permite_modificar': reserva.estado in ('CONFIRMADO', 'EMITIDO'),
                'tiene_eticket': reserva.estado in ('CONFIRMADO', 'EMITIDO'),
                'tiene_factura': reserva.estado in ('PAGADO', 'CONFIRMADO', 'EMITIDO'),
            }

            session.close()
            return jsonify(resultado)
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    # =========================
    # GESTIÓN DE RESERVAS
    # =========================

    @clientes_bp.route('/api/reservas/<codigo>/cancelar', methods=['POST'])
    @cliente_login_required
    def cancelar_reserva(codigo):
        """Solicitar cancelación de reserva"""
        data = request.json or {}
        motivo = data.get('motivo', 'Solicitud del cliente')

        if booking_service:
            resultado = booking_service.solicitar_reembolso(
                codigo, motivo,
                cliente_id=flask_session['cliente_id'],
                tipo='total',
            )
            return jsonify(resultado)
        return jsonify({'error': 'Servicio no disponible'}), 503

    @clientes_bp.route('/api/reservas/<codigo>/cambio-nombre', methods=['POST'])
    @cliente_login_required
    def cambio_nombre(codigo):
        """Solicitar cambio/corrección de nombre"""
        data = request.json or {}
        pasajero_indice = data.get('pasajero_indice', 0)
        nuevo_nombre = data.get('nombre', '').strip()
        nuevos_apellidos = data.get('apellidos', '').strip()

        if not nuevo_nombre or not nuevos_apellidos:
            return jsonify({'error': 'Nombre y apellidos son obligatorios'}), 400

        if booking_service:
            resultado = booking_service.solicitar_cambio_nombre(
                codigo, pasajero_indice, nuevo_nombre, nuevos_apellidos
            )
            return jsonify(resultado)
        return jsonify({'error': 'Servicio no disponible'}), 503

    @clientes_bp.route('/api/reservas/<codigo>/extras', methods=['POST'])
    @cliente_login_required
    def añadir_extra(codigo):
        """Añadir extra post-compra"""
        data = request.json or {}

        if booking_service:
            resultado = booking_service.añadir_extra_post_compra(codigo, data)
            return jsonify(resultado)
        return jsonify({'error': 'Servicio no disponible'}), 503

    @clientes_bp.route('/api/reservas/<codigo>/reembolso', methods=['POST'])
    @cliente_login_required
    def solicitar_reembolso(codigo):
        """Solicitar reembolso"""
        data = request.json or {}
        motivo = data.get('motivo', '')
        tipo = data.get('tipo', 'total')

        if not motivo:
            return jsonify({'error': 'Debe indicar el motivo del reembolso'}), 400

        if booking_service:
            resultado = booking_service.solicitar_reembolso(
                codigo, motivo,
                cliente_id=flask_session['cliente_id'],
                tipo=tipo,
            )
            return jsonify(resultado)
        return jsonify({'error': 'Servicio no disponible'}), 503

    # =========================
    # DESCARGAS (E-TICKET, FACTURA)
    # =========================

    @clientes_bp.route('/api/reservas/<codigo>/eticket')
    @cliente_login_required
    def descargar_eticket(codigo):
        """Descargar billete electrónico PDF"""
        from database import ReservaVuelo, get_db_session
        from core.document_generator import generar_eticket_pdf

        session = get_db_session()
        try:
            reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo).first()
            if not reserva:
                session.close()
                return jsonify({'error': 'Reserva no encontrada'}), 404

            if reserva.estado not in ('CONFIRMADO', 'EMITIDO'):
                session.close()
                return jsonify({'error': 'El billete aún no está disponible'}), 400

            # Preparar datos
            datos_vuelo = json.loads(reserva.datos_vuelo) if reserva.datos_vuelo else {}
            pasajeros = json.loads(reserva.pasajeros) if reserva.pasajeros else []
            notas = json.loads(reserva.notas) if reserva.notas else {}
            tickets = json.loads(reserva.ticket_numbers) if reserva.ticket_numbers else []

            reserva_data = {
                'codigo_reserva': reserva.codigo_reserva,
                'booking_reference': reserva.booking_reference or 'N/A',
                'datos_vuelo': datos_vuelo,
                'pasajeros': pasajeros,
                'ticket_numbers': tickets,
                'precio_total': reserva.precio_total,
                'moneda': reserva.moneda or 'EUR',
                'extras': notas.get('extras_desglose', []),
            }
            session.close()

            ruta_pdf = generar_eticket_pdf(reserva_data)
            return send_file(ruta_pdf, as_attachment=True, download_name=f"eticket_{codigo}.pdf")
        except Exception as e:
            session.close()
            logger.error(f"Error generando e-ticket: {e}")
            return jsonify({'error': str(e)}), 500

    @clientes_bp.route('/api/reservas/<codigo>/factura')
    @cliente_login_required
    def descargar_factura_cliente(codigo):
        """Descargar factura PDF"""
        from database import ReservaVuelo, Factura, get_db_session
        from core.document_generator import FacturaSequencer

        session = get_db_session()
        try:
            reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo).first()
            if not reserva:
                session.close()
                return jsonify({'error': 'Reserva no encontrada'}), 404

            # Buscar factura existente
            factura = session.query(Factura).filter_by(
                email_cliente=reserva.email_cliente
            ).order_by(Factura.fecha_emision.desc()).first()

            if factura and factura.url_archivo_pdf and os.path.exists(factura.url_archivo_pdf):
                ruta_pdf = factura.url_archivo_pdf
            else:
                # Generar factura automáticamente
                from database.models_clientes import ClienteUsuario
                cliente = session.query(ClienteUsuario).filter_by(
                    id=flask_session['cliente_id']
                ).first()

                cliente_datos = None
                if cliente:
                    cliente_datos = {
                        'nombre': cliente.nombre_completo,
                        'cif': cliente.dni_cif or '',
                        'direccion': cliente.direccion_fiscal or '',
                        'email': cliente.email,
                    }

                resultado = FacturaSequencer.crear_factura_desde_reserva(reserva, cliente_datos)
                ruta_pdf = resultado.get('ruta_pdf')

            session.close()

            if ruta_pdf and os.path.exists(ruta_pdf):
                return send_file(ruta_pdf, as_attachment=True, download_name=f"factura_{codigo}.pdf")
            return jsonify({'error': 'No se pudo generar la factura'}), 500
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    # =========================
    # PASAJEROS FRECUENTES
    # =========================

    @clientes_bp.route('/api/pasajeros-frecuentes', methods=['GET', 'POST'])
    @cliente_login_required
    def pasajeros_frecuentes():
        from database import get_db_session
        from database.models_clientes import PasajeroFrecuente
        from core.security import cifrar, generar_hash_dni

        session = get_db_session()
        try:
            cliente_id = flask_session['cliente_id']

            if request.method == 'GET':
                pasajeros = session.query(PasajeroFrecuente).filter_by(
                    cliente_id=cliente_id
                ).all()
                session.close()
                return jsonify({
                    'pasajeros': [p.to_dict() for p in pasajeros]
                })

            # POST: crear nuevo pasajero frecuente
            data = request.json
            
            # Cifrar documento
            documento = data.get('documento', '')
            doc_cifrado = cifrar(documento) if documento else None
            doc_hash = generar_hash_dni(documento) if documento else None

            from datetime import date as date_type
            fecha_nac = None
            if data.get('fecha_nacimiento'):
                try:
                    fecha_nac = datetime.strptime(data['fecha_nacimiento'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            fecha_cad = None
            if data.get('fecha_caducidad'):
                try:
                    fecha_cad = datetime.strptime(data['fecha_caducidad'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            nuevo = PasajeroFrecuente(
                cliente_id=cliente_id,
                nombre=data.get('nombre', ''),
                apellidos=data.get('apellidos', ''),
                fecha_nacimiento=fecha_nac,
                nacionalidad=data.get('nacionalidad', 'España'),
                genero=data.get('genero', ''),
                tipo_documento=data.get('tipo_documento', 'DNI'),
                documento_cifrado=doc_cifrado,
                documento_blind_index=doc_hash,
                pais_expedicion=data.get('pais_expedicion', 'España'),
                fecha_caducidad=fecha_cad,
                tipo_pasajero=data.get('tipo_pasajero', 'adulto'),
                es_titular=data.get('es_titular', False),
                alias=data.get('alias', ''),
            )
            session.add(nuevo)
            session.commit()
            resultado = nuevo.to_dict()
            resultado['id'] = nuevo.id
            session.close()

            return jsonify({'success': True, 'pasajero': resultado}), 201
        except Exception as e:
            session.rollback()
            session.close()
            return jsonify({'error': str(e)}), 500

    @clientes_bp.route('/api/pasajeros-frecuentes/<int:pax_id>', methods=['PUT', 'DELETE'])
    @cliente_login_required
    def gestionar_pasajero_frecuente(pax_id):
        from database import get_db_session
        from database.models_clientes import PasajeroFrecuente

        session = get_db_session()
        try:
            pax = session.query(PasajeroFrecuente).filter_by(
                id=pax_id, cliente_id=flask_session['cliente_id']
            ).first()
            
            if not pax:
                session.close()
                return jsonify({'error': 'Pasajero no encontrado'}), 404

            if request.method == 'DELETE':
                session.delete(pax)
                session.commit()
                session.close()
                return jsonify({'success': True})

            # PUT: actualizar
            data = request.json
            for campo in ['nombre', 'apellidos', 'nacionalidad', 'genero',
                          'tipo_documento', 'pais_expedicion', 'tipo_pasajero', 'alias']:
                if campo in data:
                    setattr(pax, campo, data[campo])

            if 'fecha_nacimiento' in data:
                try:
                    pax.fecha_nacimiento = datetime.strptime(data['fecha_nacimiento'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            if 'fecha_caducidad' in data:
                try:
                    pax.fecha_caducidad = datetime.strptime(data['fecha_caducidad'], '%Y-%m-%d').date()
                except ValueError:
                    pass

            if 'documento' in data and data['documento']:
                from core.security import cifrar, generar_hash_dni
                pax.documento_cifrado = cifrar(data['documento'])
                pax.documento_blind_index = generar_hash_dni(data['documento'])

            session.commit()
            resultado = pax.to_dict()
            session.close()
            return jsonify({'success': True, 'pasajero': resultado})
        except Exception as e:
            session.rollback()
            session.close()
            return jsonify({'error': str(e)}), 500

    # =========================
    # NOTIFICACIONES
    # =========================

    @clientes_bp.route('/api/notificaciones')
    @cliente_login_required
    def listar_notificaciones():
        from database import get_db_session
        from database.models_clientes import NotificacionCliente

        session = get_db_session()
        try:
            notificaciones = session.query(NotificacionCliente).filter_by(
                cliente_id=flask_session['cliente_id']
            ).order_by(NotificacionCliente.fecha_envio.desc()).limit(50).all()

            resultado = [n.to_dict() for n in notificaciones]
            no_leidas = sum(1 for n in notificaciones if not n.leida)
            session.close()

            return jsonify({
                'notificaciones': resultado,
                'no_leidas': no_leidas,
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @clientes_bp.route('/api/notificaciones/<int:notif_id>/leer', methods=['POST'])
    @cliente_login_required
    def marcar_leida(notif_id):
        from database import get_db_session
        from database.models_clientes import NotificacionCliente

        session = get_db_session()
        try:
            notif = session.query(NotificacionCliente).filter_by(
                id=notif_id, cliente_id=flask_session['cliente_id']
            ).first()
            if notif:
                notif.leida = True
                notif.fecha_lectura = datetime.utcnow()
                session.commit()
            session.close()
            return jsonify({'success': True})
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    # =========================
    # GDPR: DERECHO AL OLVIDO
    # =========================

    @clientes_bp.route('/api/solicitar-eliminacion', methods=['POST'])
    @cliente_login_required
    def solicitar_eliminacion():
        """GDPR: Solicitar eliminación de cuenta y datos"""
        from database import get_db_session
        from database.models_clientes import ClienteUsuario

        session = get_db_session()
        try:
            cliente = session.query(ClienteUsuario).filter_by(
                id=flask_session['cliente_id']
            ).first()
            if cliente:
                cliente.solicitud_eliminacion = True
                cliente.fecha_solicitud_eliminacion = datetime.utcnow()
                session.commit()

            session.close()
            return jsonify({
                'success': True,
                'mensaje': 'Solicitud de eliminación registrada. Se procesará en un máximo de 30 días según el RGPD.'
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @clientes_bp.route('/api/descargar-datos')
    @cliente_login_required
    def descargar_datos():
        """GDPR: Exportar todos los datos del cliente"""
        from database import get_db_session
        from database.models_clientes import ClienteUsuario, PasajeroFrecuente, ReservaCliente, NotificacionCliente

        session = get_db_session()
        try:
            cliente = session.query(ClienteUsuario).filter_by(
                id=flask_session['cliente_id']
            ).first()
            if not cliente:
                session.close()
                return jsonify({'error': 'No encontrado'}), 404

            pasajeros = session.query(PasajeroFrecuente).filter_by(cliente_id=cliente.id).all()
            reservas = session.query(ReservaCliente).filter_by(cliente_id=cliente.id).all()
            notificaciones = session.query(NotificacionCliente).filter_by(cliente_id=cliente.id).all()

            datos_exportados = {
                'cuenta': cliente.to_dict(incluir_sensibles=True),
                'pasajeros_frecuentes': [p.to_dict() for p in pasajeros],
                'reservas': [r.to_dict() for r in reservas],
                'notificaciones': [n.to_dict() for n in notificaciones],
                'fecha_exportacion': datetime.utcnow().isoformat(),
            }

            session.close()
            return jsonify(datos_exportados)
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    return clientes_bp
