"""
Modelos para el área de clientes (registro, login, historial, pasajeros frecuentes)
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, Date,
    ForeignKey, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime
from flask_login import UserMixin
from .models import Base
import enum


class EstadoReembolso(enum.Enum):
    SOLICITADO = "solicitado"
    EN_REVISION = "en_revision"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    PROCESADO = "procesado"
    PARCIAL = "parcial"


class ClienteUsuario(Base, UserMixin):
    """
    Usuarios del área de clientes (público).
    Separado de Usuario (admin/agentes) para mantener roles claros.
    """
    __tablename__ = 'clientes_usuarios'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(100), nullable=False)
    apellidos = Column(String(150), nullable=False)
    telefono = Column(String(50))
    
    # Datos fiscales opcionales
    dni_cif = Column(String(20))
    direccion_fiscal = Column(Text)
    codigo_postal = Column(String(10))
    ciudad = Column(String(100))
    pais = Column(String(100), default='España')

    # Preferencias
    idioma = Column(String(5), default='es')
    moneda_preferida = Column(String(3), default='EUR')
    acepta_newsletter = Column(Boolean, default=False)

    # GDPR
    consentimiento_cookies = Column(Boolean, default=False)
    fecha_consentimiento = Column(DateTime)
    solicitud_eliminacion = Column(Boolean, default=False)
    fecha_solicitud_eliminacion = Column(DateTime)

    # Control
    email_verificado = Column(Boolean, default=False)
    token_verificacion = Column(String(255))
    token_reset_password = Column(String(255))
    token_reset_expira = Column(DateTime)
    activo = Column(Boolean, default=True)
    ultimo_login = Column(DateTime)
    fecha_registro = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    pasajeros_frecuentes = relationship(
        'PasajeroFrecuente', back_populates='cliente',
        cascade='all, delete-orphan'
    )
    reservas = relationship(
        'ReservaCliente', back_populates='cliente',
        cascade='all, delete-orphan'
    )
    reembolsos = relationship(
        'SolicitudReembolso', back_populates='cliente',
        cascade='all, delete-orphan'
    )

    __table_args__ = (
        Index('idx_cliente_email_activo', 'email', 'activo'),
    )

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"

    def to_dict(self, incluir_sensibles=False):
        data = {
            'id': self.id,
            'nombre': self.nombre,
            'apellidos': self.apellidos,
            'email': self.email,
            'telefono': self.telefono,
            'idioma': self.idioma,
            'moneda_preferida': self.moneda_preferida,
            'fecha_registro': self.fecha_registro.isoformat() if self.fecha_registro else None,
        }
        if incluir_sensibles:
            data['dni_cif'] = self.dni_cif
            data['direccion_fiscal'] = self.direccion_fiscal
            data['codigo_postal'] = self.codigo_postal
            data['ciudad'] = self.ciudad
            data['pais'] = self.pais
        return data

    def __repr__(self):
        return f"<ClienteUsuario {self.id}: {self.email}>"


class PasajeroFrecuente(Base):
    """
    Datos de pasajeros guardados para reutilizar en futuras reservas.
    DNI/pasaporte cifrado con AES-256.
    """
    __tablename__ = 'pasajeros_frecuentes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey('clientes_usuarios.id', ondelete='CASCADE'), nullable=False, index=True)

    # Datos personales
    nombre = Column(String(100), nullable=False)
    apellidos = Column(String(150), nullable=False)
    fecha_nacimiento = Column(Date, nullable=False)
    nacionalidad = Column(String(100), default='España')
    genero = Column(String(10))  # M, F

    # Documentos (cifrados AES-256)
    tipo_documento = Column(String(20), nullable=False)  # DNI, PASAPORTE, NIE
    documento_cifrado = Column(String(500))
    documento_blind_index = Column(String(64), index=True)
    pais_expedicion = Column(String(100))
    fecha_expedicion = Column(Date)
    fecha_caducidad = Column(Date)

    # Tipo
    tipo_pasajero = Column(String(20), default='adulto')  # adulto, niño, bebe

    # Control
    es_titular = Column(Boolean, default=False)  # Si es el propio cliente
    alias = Column(String(50))  # "Mi pareja", "Hijo pequeño", etc.
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    cliente = relationship('ClienteUsuario', back_populates='pasajeros_frecuentes')

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellidos': self.apellidos,
            'fecha_nacimiento': self.fecha_nacimiento.isoformat() if self.fecha_nacimiento else None,
            'nacionalidad': self.nacionalidad,
            'genero': self.genero,
            'tipo_documento': self.tipo_documento,
            'pais_expedicion': self.pais_expedicion,
            'fecha_caducidad': self.fecha_caducidad.isoformat() if self.fecha_caducidad else None,
            'tipo_pasajero': self.tipo_pasajero,
            'es_titular': self.es_titular,
            'alias': self.alias,
        }

    def __repr__(self):
        return f"<PasajeroFrecuente {self.id}: {self.nombre} {self.apellidos}>"


class ReservaCliente(Base):
    """
    Vincula reservas de vuelo con clientes registrados.
    Permite historial y gestión desde el área de cliente.
    """
    __tablename__ = 'reservas_clientes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey('clientes_usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    reserva_vuelo_id = Column(Integer, ForeignKey('reservas_vuelo.id', ondelete='SET NULL'), index=True)
    codigo_reserva = Column(String(50), nullable=False, index=True)

    # Tipo de reserva
    tipo = Column(String(20), default='vuelo')  # vuelo, tour, paquete

    # Estado visible para el cliente
    estado_cliente = Column(String(50), default='confirmada')
    # confirmada, en_curso, completada, cancelada, reembolsada

    # Extras añadidos post-compra
    extras_post_compra = Column(Text)  # JSON: [{tipo, descripcion, precio, fecha}]

    # Modificaciones
    historial_cambios = Column(Text)  # JSON: [{fecha, tipo, descripcion, coste}]
    nombre_correccion = Column(Text)  # JSON: {original, nuevo, coste, estado}

    # Control
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    cliente = relationship('ClienteUsuario', back_populates='reservas')

    __table_args__ = (
        Index('idx_reserva_cliente_tipo', 'cliente_id', 'tipo'),
        Index('idx_reserva_cliente_estado', 'cliente_id', 'estado_cliente'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'reserva_vuelo_id': self.reserva_vuelo_id,
            'codigo_reserva': self.codigo_reserva,
            'tipo': self.tipo,
            'estado_cliente': self.estado_cliente,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
        }

    def __repr__(self):
        return f"<ReservaCliente {self.codigo_reserva} (cliente {self.cliente_id})>"


class SolicitudReembolso(Base):
    """Solicitudes de reembolso total o parcial"""
    __tablename__ = 'solicitudes_reembolso'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey('clientes_usuarios.id', ondelete='CASCADE'), nullable=False, index=True)
    codigo_reserva = Column(String(50), nullable=False, index=True)

    # Tipo
    tipo_reembolso = Column(String(20), default='total')  # total, parcial
    monto_solicitado = Column(Float)
    monto_aprobado = Column(Float)
    motivo = Column(Text, nullable=False)

    # Estado
    estado = Column(String(20), default='solicitado', index=True)
    # solicitado, en_revision, aprobado, rechazado, procesado

    # Gestión interna
    notas_agente = Column(Text)
    agente_id = Column(Integer, ForeignKey('usuarios.id'))
    
    # Stripe refund
    stripe_refund_id = Column(String(255))
    
    # Fechas
    fecha_solicitud = Column(DateTime, default=datetime.utcnow, index=True)
    fecha_resolucion = Column(DateTime)

    # Relaciones
    cliente = relationship('ClienteUsuario', back_populates='reembolsos')

    def to_dict(self):
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'codigo_reserva': self.codigo_reserva,
            'tipo_reembolso': self.tipo_reembolso,
            'monto_solicitado': self.monto_solicitado,
            'monto_aprobado': self.monto_aprobado,
            'motivo': self.motivo,
            'estado': self.estado,
            'fecha_solicitud': self.fecha_solicitud.isoformat() if self.fecha_solicitud else None,
            'fecha_resolucion': self.fecha_resolucion.isoformat() if self.fecha_resolucion else None,
        }

    def __repr__(self):
        return f"<Reembolso {self.id}: {self.codigo_reserva} - {self.estado}>"


class NotificacionCliente(Base):
    """Notificaciones enviadas a clientes (cambios vuelo, retrasos, etc.)"""
    __tablename__ = 'notificaciones_clientes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey('clientes_usuarios.id', ondelete='CASCADE'), index=True)
    codigo_reserva = Column(String(50), index=True)

    # Tipo de notificación
    tipo = Column(String(30), nullable=False, index=True)
    # cambio_vuelo, retraso, cancelacion, puerta, checkin_24h, recordatorio, confirmacion

    # Contenido
    titulo = Column(String(255), nullable=False)
    mensaje = Column(Text, nullable=False)
    datos_extra = Column(Text)  # JSON con datos específicos

    # Canales
    enviado_email = Column(Boolean, default=False)
    enviado_sms = Column(Boolean, default=False)
    enviado_push = Column(Boolean, default=False)

    # Estado
    leida = Column(Boolean, default=False)
    fecha_envio = Column(DateTime, default=datetime.utcnow, index=True)
    fecha_lectura = Column(DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'tipo': self.tipo,
            'titulo': self.titulo,
            'mensaje': self.mensaje,
            'leida': self.leida,
            'enviado_email': self.enviado_email,
            'fecha_envio': self.fecha_envio.isoformat() if self.fecha_envio else None,
        }

    def __repr__(self):
        return f"<Notificacion {self.id}: {self.tipo} - {self.titulo[:30]}>"


class AuditLog(Base):
    """Log de auditoría para acciones administrativas"""
    __tablename__ = 'audit_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), index=True)
    accion = Column(String(100), nullable=False, index=True)
    entidad_tipo = Column(String(50))  # reserva, tour, cliente, factura
    entidad_id = Column(String(50))
    datos_antes = Column(Text)  # JSON
    datos_despues = Column(Text)  # JSON
    ip_address = Column(String(64))
    user_agent = Column(String(500))
    fecha = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_audit_entidad', 'entidad_tipo', 'entidad_id'),
        Index('idx_audit_fecha_accion', 'fecha', 'accion'),
    )

    def __repr__(self):
        return f"<AuditLog {self.id}: {self.accion} on {self.entidad_tipo}:{self.entidad_id}>"


class ConsentimientoCookies(Base):
    """Registro GDPR de consentimiento de cookies"""
    __tablename__ = 'consentimientos_cookies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey('clientes_usuarios.id', ondelete='SET NULL'), index=True)
    ip_address = Column(String(64))
    user_agent = Column(String(500))

    # Categorías aceptadas
    cookies_necesarias = Column(Boolean, default=True)
    cookies_analiticas = Column(Boolean, default=False)
    cookies_marketing = Column(Boolean, default=False)
    cookies_funcionales = Column(Boolean, default=False)

    fecha_consentimiento = Column(DateTime, default=datetime.utcnow)
    fecha_revocacion = Column(DateTime)
    activo = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Consentimiento {self.id}: {self.ip_address}>"


class TrackingBusqueda(Base):
    """Tracking de búsquedas para analytics (rutas más buscadas, conversión)"""
    __tablename__ = 'tracking_busquedas'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), index=True)
    cliente_id = Column(Integer, ForeignKey('clientes_usuarios.id', ondelete='SET NULL'), index=True)

    # Datos de búsqueda
    tipo = Column(String(20), default='vuelo')  # vuelo, tour, paquete
    origen = Column(String(10), index=True)
    destino = Column(String(10), index=True)
    fecha_ida = Column(Date)
    fecha_vuelta = Column(Date)
    adultos = Column(Integer, default=1)
    ninos = Column(Integer, default=0)
    bebes = Column(Integer, default=0)
    clase = Column(String(30))

    # Resultados
    num_resultados = Column(Integer, default=0)
    precio_min = Column(Float)
    precio_max = Column(Float)

    # Conversión
    selecciono_vuelo = Column(Boolean, default=False)
    inicio_reserva = Column(Boolean, default=False)
    completo_pago = Column(Boolean, default=False)
    codigo_reserva = Column(String(50))

    # Filtros aplicados
    filtros_aplicados = Column(Text)  # JSON: {escalas, aerolineas, horarios, etc.}

    # Meta
    ip_address = Column(String(64))
    user_agent = Column(String(500))
    referrer = Column(String(500))
    fecha = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_tracking_ruta', 'origen', 'destino'),
        Index('idx_tracking_conversion', 'selecciono_vuelo', 'inicio_reserva', 'completo_pago'),
        Index('idx_tracking_fecha_tipo', 'fecha', 'tipo'),
    )

    def __repr__(self):
        return f"<Tracking {self.id}: {self.origen}->{self.destino}>"
