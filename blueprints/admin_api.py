"""
Blueprint de Administración mejorado:
- Dashboard con ventas día/semana/mes y reservas pendientes
- Gestión de reservas: buscar, filtrar, cambiar estado
- Gestión de clientes: historial, contactar
- Gestión de reembolsos parciales/totales
- Facturación automática
- Analytics: top rutas, conversión, revenue por proveedor
- Audit log de acciones
- Gestión de usuarios/agentes (permisos, roles)
"""

from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from datetime import datetime, timedelta, date
from sqlalchemy import func, desc, and_, or_
import json
import logging

logger = logging.getLogger(__name__)

admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/admin/api/v2')


def registrar_auditoria(session, usuario_id, accion, entidad_tipo=None, entidad_id=None,
                         datos_antes=None, datos_despues=None):
    """Registra una acción en el audit log"""
    try:
        from database.models_clientes import AuditLog
        log = AuditLog(
            usuario_id=usuario_id,
            accion=accion,
            entidad_tipo=entidad_tipo,
            entidad_id=str(entidad_id) if entidad_id else None,
            datos_antes=json.dumps(datos_antes) if datos_antes else None,
            datos_despues=json.dumps(datos_despues) if datos_despues else None,
            ip_address=request.remote_addr if request else None,
            user_agent=request.user_agent.string[:500] if request and request.user_agent else None,
        )
        session.add(log)
        session.commit()
    except Exception as e:
        logger.warning(f"Error registrando auditoría: {e}")


def init_admin_api_blueprint():
    """Inicializa el blueprint de admin API v2"""

    # ================================
    # DASHBOARD KPIs
    # ================================

    @admin_api_bp.route('/dashboard/kpis')
    @login_required
    def dashboard_kpis():
        """KPIs principales del dashboard"""
        from database import ReservaVuelo, get_db_session, Factura

        session = get_db_session()
        try:
            hoy = date.today()
            inicio_semana = hoy - timedelta(days=hoy.weekday())
            inicio_mes = hoy.replace(day=1)
            inicio_mes_anterior = (inicio_mes - timedelta(days=1)).replace(day=1)

            # Ventas del día
            ventas_hoy = session.query(
                func.count(ReservaVuelo.id),
                func.coalesce(func.sum(ReservaVuelo.precio_total), 0)
            ).filter(
                func.date(ReservaVuelo.fecha_pago) == hoy,
                ReservaVuelo.estado.in_(['PAGADO', 'CONFIRMADO', 'EMITIDO'])
            ).first()

            # Ventas de la semana
            ventas_semana = session.query(
                func.count(ReservaVuelo.id),
                func.coalesce(func.sum(ReservaVuelo.precio_total), 0)
            ).filter(
                func.date(ReservaVuelo.fecha_pago) >= inicio_semana,
                ReservaVuelo.estado.in_(['PAGADO', 'CONFIRMADO', 'EMITIDO'])
            ).first()

            # Ventas del mes
            ventas_mes = session.query(
                func.count(ReservaVuelo.id),
                func.coalesce(func.sum(ReservaVuelo.precio_total), 0)
            ).filter(
                func.date(ReservaVuelo.fecha_pago) >= inicio_mes,
                ReservaVuelo.estado.in_(['PAGADO', 'CONFIRMADO', 'EMITIDO'])
            ).first()

            # Ventas mes anterior (para comparación)
            ventas_mes_anterior = session.query(
                func.coalesce(func.sum(ReservaVuelo.precio_total), 0)
            ).filter(
                func.date(ReservaVuelo.fecha_pago) >= inicio_mes_anterior,
                func.date(ReservaVuelo.fecha_pago) < inicio_mes,
                ReservaVuelo.estado.in_(['PAGADO', 'CONFIRMADO', 'EMITIDO'])
            ).scalar()

            # Reservas pendientes
            pendientes = session.query(func.count(ReservaVuelo.id)).filter(
                ReservaVuelo.estado == 'PENDIENTE'
            ).scalar()

            # Reservas hoy (creadas)
            creadas_hoy = session.query(func.count(ReservaVuelo.id)).filter(
                func.date(ReservaVuelo.fecha_creacion) == hoy
            ).scalar()

            # Tasa de conversión del mes
            busquedas_mes = 0
            reservas_mes = ventas_mes[0] if ventas_mes else 0
            try:
                from database import DuffelSearch
                busquedas_mes = session.query(func.count(DuffelSearch.id)).filter(
                    func.date(DuffelSearch.fecha_creacion) >= inicio_mes
                ).scalar() or 0
            except Exception:
                pass

            tasa_conversion = (reservas_mes / busquedas_mes * 100) if busquedas_mes > 0 else 0

            # Revenue por proveedor este mes
            revenue_proveedor = session.query(
                ReservaVuelo.provider,
                func.count(ReservaVuelo.id),
                func.coalesce(func.sum(ReservaVuelo.precio_total), 0)
            ).filter(
                func.date(ReservaVuelo.fecha_pago) >= inicio_mes,
                ReservaVuelo.estado.in_(['PAGADO', 'CONFIRMADO', 'EMITIDO'])
            ).group_by(ReservaVuelo.provider).all()

            session.close()

            revenue_mes_actual = float(ventas_mes[1]) if ventas_mes else 0
            variacion = 0
            if ventas_mes_anterior and float(ventas_mes_anterior) > 0:
                variacion = ((revenue_mes_actual - float(ventas_mes_anterior)) / float(ventas_mes_anterior)) * 100

            return jsonify({
                'ventas_hoy': {
                    'count': ventas_hoy[0] if ventas_hoy else 0,
                    'total': float(ventas_hoy[1]) if ventas_hoy else 0,
                },
                'ventas_semana': {
                    'count': ventas_semana[0] if ventas_semana else 0,
                    'total': float(ventas_semana[1]) if ventas_semana else 0,
                },
                'ventas_mes': {
                    'count': ventas_mes[0] if ventas_mes else 0,
                    'total': revenue_mes_actual,
                    'variacion_pct': round(variacion, 1),
                },
                'pendientes': pendientes or 0,
                'creadas_hoy': creadas_hoy or 0,
                'tasa_conversion': round(tasa_conversion, 2),
                'busquedas_mes': busquedas_mes,
                'revenue_proveedor': [
                    {'proveedor': r[0], 'reservas': r[1], 'total': float(r[2])}
                    for r in revenue_proveedor
                ],
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @admin_api_bp.route('/dashboard/ventas-diarias')
    @login_required
    def ventas_diarias():
        """Ventas diarias de los últimos 30 días para gráfico"""
        from database import ReservaVuelo, get_db_session

        session = get_db_session()
        try:
            dias = int(request.args.get('dias', 30))
            fecha_inicio = date.today() - timedelta(days=dias)

            ventas = session.query(
                func.date(ReservaVuelo.fecha_pago),
                func.count(ReservaVuelo.id),
                func.coalesce(func.sum(ReservaVuelo.precio_total), 0)
            ).filter(
                func.date(ReservaVuelo.fecha_pago) >= fecha_inicio,
                ReservaVuelo.estado.in_(['PAGADO', 'CONFIRMADO', 'EMITIDO'])
            ).group_by(func.date(ReservaVuelo.fecha_pago)).order_by(
                func.date(ReservaVuelo.fecha_pago)
            ).all()

            session.close()

            return jsonify({
                'datos': [
                    {'fecha': str(v[0]), 'reservas': v[1], 'total': float(v[2])}
                    for v in ventas
                ]
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    # ================================
    # GESTIÓN DE RESERVAS
    # ================================

    @admin_api_bp.route('/reservas')
    @login_required
    def listar_reservas():
        """Lista reservas con filtros avanzados y paginación"""
        from database import ReservaVuelo, get_db_session

        session = get_db_session()
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 25))
            estado = request.args.get('estado')
            provider = request.args.get('provider')
            busqueda = request.args.get('q', '').strip()
            fecha_desde = request.args.get('fecha_desde')
            fecha_hasta = request.args.get('fecha_hasta')
            ordenar = request.args.get('ordenar', 'fecha_desc')

            query = session.query(ReservaVuelo)

            # Filtros
            if estado:
                query = query.filter(ReservaVuelo.estado == estado)
            if provider:
                query = query.filter(ReservaVuelo.provider == provider)
            if busqueda:
                query = query.filter(or_(
                    ReservaVuelo.codigo_reserva.ilike(f'%{busqueda}%'),
                    ReservaVuelo.email_cliente.ilike(f'%{busqueda}%'),
                    ReservaVuelo.nombre_cliente.ilike(f'%{busqueda}%'),
                    ReservaVuelo.booking_reference.ilike(f'%{busqueda}%'),
                ))
            if fecha_desde:
                query = query.filter(func.date(ReservaVuelo.fecha_creacion) >= fecha_desde)
            if fecha_hasta:
                query = query.filter(func.date(ReservaVuelo.fecha_creacion) <= fecha_hasta)

            # Ordenar
            if ordenar == 'fecha_desc':
                query = query.order_by(ReservaVuelo.fecha_creacion.desc())
            elif ordenar == 'fecha_asc':
                query = query.order_by(ReservaVuelo.fecha_creacion.asc())
            elif ordenar == 'precio_desc':
                query = query.order_by(ReservaVuelo.precio_total.desc())
            elif ordenar == 'precio_asc':
                query = query.order_by(ReservaVuelo.precio_total.asc())

            total = query.count()
            reservas = query.offset((page - 1) * per_page).limit(per_page).all()

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
                    'nombre_cliente': r.nombre_cliente,
                    'email_cliente': r.email_cliente,
                    'origen': datos_vuelo.get('origen', ''),
                    'destino': datos_vuelo.get('destino', ''),
                    'precio_total': r.precio_total,
                    'moneda': r.moneda or 'EUR',
                    'booking_reference': r.booking_reference,
                    'fecha_creacion': r.fecha_creacion.isoformat() if r.fecha_creacion else None,
                    'fecha_pago': r.fecha_pago.isoformat() if r.fecha_pago else None,
                })

            session.close()

            return jsonify({
                'reservas': resultado,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page,
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @admin_api_bp.route('/reservas/<codigo>/estado', methods=['PUT'])
    @login_required
    def cambiar_estado_reserva(codigo):
        """Cambiar estado de una reserva"""
        from database import ReservaVuelo, get_db_session

        data = request.json or {}
        nuevo_estado = data.get('estado')
        
        estados_validos = ['PENDIENTE', 'PAGADO', 'CONFIRMADO', 'EMITIDO', 'CANCELADO', 'REEMBOLSADO', 'ERROR']
        if nuevo_estado not in estados_validos:
            return jsonify({'error': f'Estado inválido. Válidos: {estados_validos}'}), 400

        session = get_db_session()
        try:
            reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo).first()
            if not reserva:
                session.close()
                return jsonify({'error': 'Reserva no encontrada'}), 404

            estado_anterior = reserva.estado
            reserva.estado = nuevo_estado
            
            if nuevo_estado == 'CONFIRMADO' and not reserva.fecha_confirmacion:
                reserva.fecha_confirmacion = datetime.utcnow()
            if nuevo_estado == 'EMITIDO' and not reserva.fecha_emision:
                reserva.fecha_emision = datetime.utcnow()

            # Audit log
            registrar_auditoria(
                session, current_user.id, 'cambiar_estado_reserva',
                'reserva', codigo,
                {'estado': estado_anterior},
                {'estado': nuevo_estado},
            )

            session.commit()
            session.close()

            return jsonify({'success': True, 'estado_anterior': estado_anterior, 'estado_nuevo': nuevo_estado})
        except Exception as e:
            session.rollback()
            session.close()
            return jsonify({'error': str(e)}), 500

    # ================================
    # GESTIÓN DE CLIENTES
    # ================================

    @admin_api_bp.route('/clientes')
    @login_required
    def listar_clientes():
        """Lista clientes registrados"""
        from database import get_db_session
        from database.models_clientes import ClienteUsuario

        session = get_db_session()
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 25))
            busqueda = request.args.get('q', '').strip()

            query = session.query(ClienteUsuario).filter_by(activo=True)
            
            if busqueda:
                query = query.filter(or_(
                    ClienteUsuario.email.ilike(f'%{busqueda}%'),
                    ClienteUsuario.nombre.ilike(f'%{busqueda}%'),
                    ClienteUsuario.apellidos.ilike(f'%{busqueda}%'),
                ))

            total = query.count()
            clientes = query.order_by(ClienteUsuario.fecha_registro.desc()
                                     ).offset((page - 1) * per_page).limit(per_page).all()

            session.close()

            return jsonify({
                'clientes': [c.to_dict() for c in clientes],
                'total': total,
                'page': page,
                'per_page': per_page,
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @admin_api_bp.route('/clientes/<int:cliente_id>/historial')
    @login_required
    def historial_cliente(cliente_id):
        """Ver historial completo de un cliente"""
        from database import ReservaVuelo, get_db_session
        from database.models_clientes import ClienteUsuario, ReservaCliente

        session = get_db_session()
        try:
            cliente = session.query(ClienteUsuario).filter_by(id=cliente_id).first()
            if not cliente:
                session.close()
                return jsonify({'error': 'Cliente no encontrado'}), 404

            # Reservas
            reservas = session.query(ReservaVuelo).filter_by(
                email_cliente=cliente.email
            ).order_by(ReservaVuelo.fecha_creacion.desc()).all()

            # Stats
            total_gastado = sum(r.precio_total or 0 for r in reservas if r.estado in ('PAGADO', 'CONFIRMADO', 'EMITIDO'))
            total_reservas = len(reservas)

            session.close()

            return jsonify({
                'cliente': cliente.to_dict(incluir_sensibles=True),
                'stats': {
                    'total_reservas': total_reservas,
                    'total_gastado': total_gastado,
                    'primera_reserva': reservas[-1].fecha_creacion.isoformat() if reservas else None,
                    'ultima_reserva': reservas[0].fecha_creacion.isoformat() if reservas else None,
                },
                'reservas': [{
                    'codigo': r.codigo_reserva,
                    'estado': r.estado,
                    'precio': r.precio_total,
                    'fecha': r.fecha_creacion.isoformat() if r.fecha_creacion else None,
                } for r in reservas[:20]],
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    # ================================
    # GESTIÓN DE REEMBOLSOS
    # ================================

    @admin_api_bp.route('/reembolsos')
    @login_required
    def listar_reembolsos():
        """Lista solicitudes de reembolso"""
        from database import get_db_session
        from database.models_clientes import SolicitudReembolso

        session = get_db_session()
        try:
            estado = request.args.get('estado')
            query = session.query(SolicitudReembolso)
            if estado:
                query = query.filter_by(estado=estado)
            
            reembolsos = query.order_by(SolicitudReembolso.fecha_solicitud.desc()).all()
            session.close()

            return jsonify({
                'reembolsos': [r.to_dict() for r in reembolsos],
                'total': len(reembolsos),
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @admin_api_bp.route('/reembolsos/<int:reembolso_id>', methods=['PUT'])
    @login_required
    def gestionar_reembolso(reembolso_id):
        """Aprobar/rechazar/procesar un reembolso"""
        from database import get_db_session, ReservaVuelo
        from database.models_clientes import SolicitudReembolso
        import stripe

        data = request.json or {}
        nuevo_estado = data.get('estado')
        monto_aprobado = data.get('monto_aprobado')
        notas = data.get('notas', '')

        session = get_db_session()
        try:
            reembolso = session.query(SolicitudReembolso).filter_by(id=reembolso_id).first()
            if not reembolso:
                session.close()
                return jsonify({'error': 'Reembolso no encontrado'}), 404

            estado_anterior = reembolso.estado
            reembolso.estado = nuevo_estado
            reembolso.notas_agente = notas
            reembolso.agente_id = current_user.id
            reembolso.fecha_resolucion = datetime.utcnow()

            if monto_aprobado is not None:
                reembolso.monto_aprobado = float(monto_aprobado)

            # Si se aprueba, intentar procesar con Stripe
            if nuevo_estado == 'procesado' and reembolso.monto_aprobado:
                reserva = session.query(ReservaVuelo).filter_by(
                    codigo_reserva=reembolso.codigo_reserva
                ).first()

                if reserva and reserva.stripe_payment_intent_id:
                    try:
                        import os
                        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
                        refund = stripe.Refund.create(
                            payment_intent=reserva.stripe_payment_intent_id,
                            amount=int(reembolso.monto_aprobado * 100),
                        )
                        reembolso.stripe_refund_id = refund.id
                        reserva.estado = 'REEMBOLSADO'
                        logger.info(f"💰 Reembolso Stripe procesado: {refund.id}")
                    except Exception as e:
                        logger.error(f"Error procesando reembolso Stripe: {e}")
                        reembolso.notas_agente += f"\nError Stripe: {str(e)}"

            # Audit log
            registrar_auditoria(
                session, current_user.id, 'gestionar_reembolso',
                'reembolso', reembolso_id,
                {'estado': estado_anterior},
                {'estado': nuevo_estado, 'monto_aprobado': reembolso.monto_aprobado},
            )

            session.commit()
            session.close()

            return jsonify({'success': True, 'reembolso': reembolso.to_dict()})
        except Exception as e:
            session.rollback()
            session.close()
            return jsonify({'error': str(e)}), 500

    # ================================
    # FACTURACIÓN AUTOMÁTICA
    # ================================

    @admin_api_bp.route('/facturar/<codigo>', methods=['POST'])
    @login_required
    def facturar_reserva(codigo):
        """Genera factura automática para una reserva"""
        from database import ReservaVuelo, get_db_session
        from core.document_generator import FacturaSequencer

        session = get_db_session()
        try:
            reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo).first()
            if not reserva:
                session.close()
                return jsonify({'error': 'Reserva no encontrada'}), 404

            # Datos fiscales del cliente (del request o del cliente registrado)
            cliente_datos = request.json or {}
            
            resultado = FacturaSequencer.crear_factura_desde_reserva(reserva, cliente_datos)
            
            registrar_auditoria(
                session, current_user.id, 'generar_factura',
                'reserva', codigo,
                datos_despues={'numero_factura': resultado.get('numero_factura')},
            )

            session.close()
            return jsonify(resultado)
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    # ================================
    # ANALYTICS AVANZADOS
    # ================================

    @admin_api_bp.route('/analytics/top-rutas')
    @login_required
    def top_rutas():
        """Top rutas más buscadas y con más reservas"""
        from database import DuffelSearch, ReservaVuelo, get_db_session

        session = get_db_session()
        try:
            dias = int(request.args.get('dias', 30))
            fecha_inicio = date.today() - timedelta(days=dias)
            limit = int(request.args.get('limit', 20))

            # Top rutas buscadas
            top_buscadas = session.query(
                DuffelSearch.origen,
                DuffelSearch.destino,
                func.count(DuffelSearch.id).label('busquedas'),
            ).filter(
                func.date(DuffelSearch.fecha_creacion) >= fecha_inicio
            ).group_by(
                DuffelSearch.origen, DuffelSearch.destino
            ).order_by(desc('busquedas')).limit(limit).all()

            # Top rutas reservadas
            reservas = session.query(ReservaVuelo).filter(
                func.date(ReservaVuelo.fecha_creacion) >= fecha_inicio,
                ReservaVuelo.estado.in_(['PAGADO', 'CONFIRMADO', 'EMITIDO']),
            ).all()

            rutas_reservadas = {}
            for r in reservas:
                try:
                    dv = json.loads(r.datos_vuelo) if r.datos_vuelo else {}
                    ruta = f"{dv.get('origen', '???')}-{dv.get('destino', '???')}"
                    if ruta not in rutas_reservadas:
                        rutas_reservadas[ruta] = {'reservas': 0, 'revenue': 0}
                    rutas_reservadas[ruta]['reservas'] += 1
                    rutas_reservadas[ruta]['revenue'] += float(r.precio_total or 0)
                except (json.JSONDecodeError, TypeError):
                    pass

            top_reservadas = sorted(rutas_reservadas.items(), key=lambda x: x[1]['revenue'], reverse=True)[:limit]

            session.close()

            return jsonify({
                'top_buscadas': [
                    {'origen': r[0], 'destino': r[1], 'busquedas': r[2]}
                    for r in top_buscadas
                ],
                'top_reservadas': [
                    {'ruta': r[0], 'reservas': r[1]['reservas'], 'revenue': r[1]['revenue']}
                    for r in top_reservadas
                ],
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @admin_api_bp.route('/analytics/conversion')
    @login_required
    def analytics_conversion():
        """Métricas de conversión por ruta y proveedor"""
        from database import DuffelSearch, ReservaVuelo, get_db_session

        session = get_db_session()
        try:
            dias = int(request.args.get('dias', 30))
            fecha_inicio = date.today() - timedelta(days=dias)

            # Búsquedas totales
            total_busquedas = session.query(func.count(DuffelSearch.id)).filter(
                func.date(DuffelSearch.fecha_creacion) >= fecha_inicio
            ).scalar() or 0

            # Reservas totales (creadas)
            total_reservas_creadas = session.query(func.count(ReservaVuelo.id)).filter(
                func.date(ReservaVuelo.fecha_creacion) >= fecha_inicio
            ).scalar() or 0

            # Reservas pagadas
            total_pagadas = session.query(func.count(ReservaVuelo.id)).filter(
                func.date(ReservaVuelo.fecha_creacion) >= fecha_inicio,
                ReservaVuelo.estado.in_(['PAGADO', 'CONFIRMADO', 'EMITIDO'])
            ).scalar() or 0

            # Conversión por proveedor
            por_proveedor = session.query(
                ReservaVuelo.provider,
                func.count(ReservaVuelo.id).label('total'),
                func.sum(
                    func.cast(
                        ReservaVuelo.estado.in_(['PAGADO', 'CONFIRMADO', 'EMITIDO']),
                        type_=func.INTEGER if hasattr(func, 'INTEGER') else None
                    )
                ).label('pagadas'),
                func.coalesce(func.sum(ReservaVuelo.precio_total), 0).label('revenue'),
            ).filter(
                func.date(ReservaVuelo.fecha_creacion) >= fecha_inicio
            ).group_by(ReservaVuelo.provider).all()

            session.close()

            return jsonify({
                'periodo_dias': dias,
                'total_busquedas': total_busquedas,
                'total_reservas_creadas': total_reservas_creadas,
                'total_pagadas': total_pagadas,
                'tasa_busqueda_reserva': round((total_reservas_creadas / total_busquedas * 100), 2) if total_busquedas > 0 else 0,
                'tasa_reserva_pago': round((total_pagadas / total_reservas_creadas * 100), 2) if total_reservas_creadas > 0 else 0,
                'por_proveedor': [{
                    'proveedor': p[0],
                    'total_reservas': p[1],
                    'revenue': float(p[3]) if p[3] else 0,
                } for p in por_proveedor],
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @admin_api_bp.route('/analytics/tracking-busquedas')
    @login_required
    def tracking_busquedas():
        """Tracking detallado de búsquedas"""
        try:
            from database import get_db_session
            from database.models_clientes import TrackingBusqueda

            session = get_db_session()
            dias = int(request.args.get('dias', 7))
            fecha_inicio = date.today() - timedelta(days=dias)

            # Rutas más buscadas con tasa de conversión
            rutas = session.query(
                TrackingBusqueda.origen,
                TrackingBusqueda.destino,
                func.count(TrackingBusqueda.id).label('busquedas'),
                func.sum(func.cast(TrackingBusqueda.selecciono_vuelo, Integer)).label('seleccionaron'),
                func.sum(func.cast(TrackingBusqueda.completo_pago, Integer)).label('completaron'),
                func.avg(TrackingBusqueda.precio_min).label('precio_medio_min'),
            ).filter(
                func.date(TrackingBusqueda.fecha) >= fecha_inicio
            ).group_by(
                TrackingBusqueda.origen, TrackingBusqueda.destino
            ).order_by(desc('busquedas')).limit(30).all()

            session.close()

            return jsonify({
                'rutas': [{
                    'origen': r[0], 'destino': r[1],
                    'busquedas': r[2],
                    'seleccionaron': int(r[3] or 0),
                    'completaron': int(r[4] or 0),
                    'conversion': round((int(r[4] or 0) / r[2] * 100), 1) if r[2] > 0 else 0,
                    'precio_medio_min': round(float(r[5] or 0), 2),
                } for r in rutas],
            })
        except Exception as e:
            return jsonify({'error': str(e), 'rutas': []}), 200

    # ================================
    # GESTIÓN DE USUARIOS/AGENTES
    # ================================

    @admin_api_bp.route('/usuarios')
    @login_required
    def listar_usuarios():
        """Lista usuarios del panel admin"""
        from database import Usuario, get_db_session

        if current_user.rol != 'admin':
            return jsonify({'error': 'Solo los administradores pueden gestionar usuarios'}), 403

        session = get_db_session()
        try:
            usuarios = session.query(Usuario).all()
            session.close()
            return jsonify({
                'usuarios': [{
                    'id': u.id,
                    'username': u.username,
                    'email': u.email,
                    'rol': u.rol,
                    'activo': u.activo,
                    'fecha_creacion': u.fecha_creacion.isoformat() if u.fecha_creacion else None,
                } for u in usuarios]
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    @admin_api_bp.route('/usuarios', methods=['POST'])
    @login_required
    def crear_usuario():
        """Crear nuevo agente/admin"""
        from database import Usuario, get_db_session

        if current_user.rol != 'admin':
            return jsonify({'error': 'Solo admin puede crear usuarios'}), 403

        data = request.json or {}

        session = get_db_session()
        try:
            existente = session.query(Usuario).filter_by(username=data.get('username')).first()
            if existente:
                session.close()
                return jsonify({'error': 'Username ya existe'}), 400

            nuevo = Usuario(
                username=data['username'],
                password_hash=generate_password_hash(data['password']),
                email=data['email'],
                rol=data.get('rol', 'agente'),
                activo=True,
            )
            session.add(nuevo)

            registrar_auditoria(
                session, current_user.id, 'crear_usuario',
                'usuario', data['username'],
                datos_despues={'username': data['username'], 'rol': data.get('rol', 'agente')},
            )

            session.commit()
            session.close()
            return jsonify({'success': True}), 201
        except Exception as e:
            session.rollback()
            session.close()
            return jsonify({'error': str(e)}), 500

    @admin_api_bp.route('/usuarios/<int:user_id>', methods=['PUT', 'DELETE'])
    @login_required
    def gestionar_usuario(user_id):
        """Editar/desactivar usuario"""
        from database import Usuario, get_db_session

        if current_user.rol != 'admin':
            return jsonify({'error': 'Solo admin'}), 403

        session = get_db_session()
        try:
            usuario = session.query(Usuario).filter_by(id=user_id).first()
            if not usuario:
                session.close()
                return jsonify({'error': 'Usuario no encontrado'}), 404

            if request.method == 'DELETE':
                usuario.activo = False
                registrar_auditoria(session, current_user.id, 'desactivar_usuario', 'usuario', user_id)
                session.commit()
                session.close()
                return jsonify({'success': True})

            data = request.json or {}
            if 'rol' in data:
                usuario.rol = data['rol']
            if 'email' in data:
                usuario.email = data['email']
            if 'activo' in data:
                usuario.activo = data['activo']
            if 'password' in data and data['password']:
                usuario.password_hash = generate_password_hash(data['password'])

            registrar_auditoria(session, current_user.id, 'editar_usuario', 'usuario', user_id)
            session.commit()
            session.close()
            return jsonify({'success': True})
        except Exception as e:
            session.rollback()
            session.close()
            return jsonify({'error': str(e)}), 500

    # ================================
    # AUDIT LOG
    # ================================

    @admin_api_bp.route('/audit-log')
    @login_required
    def ver_audit_log():
        """Ver log de auditoría"""
        from database import get_db_session
        from database.models_clientes import AuditLog

        if current_user.rol != 'admin':
            return jsonify({'error': 'Solo admin'}), 403

        session = get_db_session()
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))

            logs = session.query(AuditLog).order_by(
                AuditLog.fecha.desc()
            ).offset((page - 1) * per_page).limit(per_page).all()

            session.close()

            return jsonify({
                'logs': [{
                    'id': l.id,
                    'usuario_id': l.usuario_id,
                    'accion': l.accion,
                    'entidad_tipo': l.entidad_tipo,
                    'entidad_id': l.entidad_id,
                    'ip': l.ip_address,
                    'fecha': l.fecha.isoformat() if l.fecha else None,
                } for l in logs]
            })
        except Exception as e:
            session.close()
            return jsonify({'error': str(e)}), 500

    # Import needed
    from werkzeug.security import generate_password_hash
    from sqlalchemy import Integer

    return admin_api_bp
