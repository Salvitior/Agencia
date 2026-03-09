"""
Modelos de base de datos para el sistema de agencia de viajes
"""

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, Date, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from flask_login import UserMixin

Base = declarative_base()


class Usuario(Base, UserMixin):
    """Usuarios del sistema (admin/agentes)"""
    __tablename__ = 'usuarios'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    rol = Column(String(20), default='agente')  # 'admin' o 'agente'
    activo = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    pedidos = relationship('Pedido', back_populates='usuario', cascade='all, delete-orphan')
    
    @property
    def is_active(self):
        """Flask-Login: usuario está activo"""
        return self.activo
    
    def __repr__(self):
        return f"<Usuario {self.username} ({self.rol})>"


class Tour(Base):
    """Tours/Paquetes de viaje"""
    __tablename__ = 'tours'
    
    # Campos principales
    id = Column(Integer, primary_key=True, autoincrement=True)
    titulo = Column(String(300), nullable=False)
    descripcion = Column(Text)
    destino = Column(String(150), index=True)
    origen = Column(String(150))
    
    # Precios y duración
    precio_desde = Column(Float, index=True)
    precio_hasta = Column(Float)
    duracion_dias = Column(Integer)
    
    # Medios
    imagen_url = Column(String(500))
    mapa_url = Column(String(500))
    
    # Proveedor
    proveedor = Column(String(100), index=True)
    url_proveedor = Column(String(500))
    
    # Categorización
    categoria = Column(String(50))
    continente = Column(String(50), index=True)
    pais = Column(String(100), index=True)
    ciudad_salida = Column(String(100))
    tipo_viaje = Column(String(50))  # Playa, Cultural, Aventura, Circuito, Crucero
    nivel_confort = Column(String(20))  # Económico, Medio, Premium, Lujo
    
    # Temporada (meses como strings: "enero", "marzo", etc.)
    temporada_inicio = Column(String(20))
    temporada_fin = Column(String(20))
    
    # Detalles
    incluye = Column(Text)
    no_incluye = Column(Text)
    itinerario = Column(Text)
    
    # Métricas
    num_visitas = Column(Integer, default=0)
    num_solicitudes = Column(Integer, default=0)
    
    # SEO y búsqueda
    slug = Column(String(300), unique=True, index=True)
    keywords = Column(Text)
    destacado = Column(Boolean, default=False, index=True)
    
    # Ofertas (visible en /ofertas, descuento y fecha fin)
    es_oferta = Column(Boolean, default=False, index=True)
    descuento_pct = Column(Float, nullable=True)  # ej. 15 = 15%
    texto_oferta = Column(String(120), nullable=True)  # ej. "Últimas plazas", "-40%"
    fecha_fin_oferta = Column(Date, nullable=True)
    
    # ✅ NUEVO: Full-text search vector para búsqueda rápida
    from sqlalchemy.dialects.postgresql import TSVECTOR
    search_vector = Column(TSVECTOR)
    
    # Control
    activo = Column(Boolean, default=True, index=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ✅ OPTIMIZADO: Índices compuestos para queries frecuentes
    __table_args__ = (
        # Índices existentes
        Index('idx_continente_precio', 'continente', 'precio_desde'),
        Index('idx_destino_activo', 'destino', 'activo'),
        Index('idx_proveedor_categoria', 'proveedor', 'categoria'),
        Index('idx_destacado_activo', 'destacado', 'activo'),
        Index('idx_tipo_viaje', 'tipo_viaje', 'activo'),
        
        # ✅ NUEVOS: Índices compuestos para rendimiento
        Index('idx_activo_categoria', 'activo', 'categoria'),
        Index('idx_activo_precio', 'activo', 'precio_desde'),
        Index('idx_activo_destacado_popularidad', 'activo', 'destacado', 'num_solicitudes'),
        Index('idx_activo_continente', 'activo', 'continente'),
        
        # ✅ CRÍTICO: Índice GIN para full-text search
        Index('idx_search_vector', 'search_vector', postgresql_using='gin'),
    )
    
    # Relaciones
    salidas = relationship('SalidaTour', back_populates='tour', cascade='all, delete-orphan')
    solicitudes = relationship('SolicitudTour', back_populates='tour', cascade='all, delete-orphan')
    
    def to_dict(self, include_salidas=False):
        """Serializa el tour a diccionario"""
        data = {
            'id': self.id,
            'titulo': self.titulo,
            'descripcion': self.descripcion,
            'destino': self.destino,
            'origen': self.origen,
            'precio_desde': self.precio_desde,
            'precio_hasta': self.precio_hasta,
            'duracion_dias': self.duracion_dias,
            'imagen_url': self.imagen_url,
            'mapa_url': self.mapa_url,
            'proveedor': self.proveedor,
            'url_proveedor': self.url_proveedor,
            'categoria': self.categoria,
            'continente': self.continente,
            'pais': self.pais,
            'ciudad_salida': self.ciudad_salida,
            'tipo_viaje': self.tipo_viaje,
            'nivel_confort': self.nivel_confort,
            'temporada_inicio': self.temporada_inicio,
            'temporada_fin': self.temporada_fin,
            'incluye': self.incluye,
            'no_incluye': self.no_incluye,
            'itinerario': self.itinerario,
            'num_visitas': self.num_visitas,
            'num_solicitudes': self.num_solicitudes,
            'slug': self.slug,
            'keywords': self.keywords,
            'destacado': self.destacado,
            'activo': self.activo,
            'es_oferta': getattr(self, 'es_oferta', False),
            'descuento_pct': getattr(self, 'descuento_pct', None),
            'texto_oferta': getattr(self, 'texto_oferta', None),
            'fecha_fin_oferta': self.fecha_fin_oferta.isoformat() if getattr(self, 'fecha_fin_oferta', None) else None,
        }
        if include_salidas and self.salidas:
            data['salidas'] = [salida.to_dict() for salida in self.salidas]
        return data
    
    def __repr__(self):
        return f"<Tour {self.id}: {self.titulo[:50]}>"


class SalidaTour(Base):
    """Fechas de salida específicas para tours con inventario"""
    __tablename__ = 'salidas_tour'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tour_id = Column(Integer, ForeignKey('tours.id', ondelete='CASCADE'), nullable=False, index=True)
    
    fecha_salida = Column(Date, nullable=False, index=True)
    plazas_totales = Column(Integer, default=0)
    plazas_vendidas = Column(Integer, default=0)
    precio_especial = Column(Float)  # Precio específico para esta salida
    
    estado = Column(String(20), default='abierta')  # abierta, confirmada, completa, cancelada
    fecha_confirmacion_proveedor = Column(DateTime)
    notas = Column(Text)
    
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    tour = relationship('Tour', back_populates='salidas')
    
    @property
    def plazas_disponibles(self):
        """Calcula plazas disponibles en tiempo real"""
        return max(0, self.plazas_totales - self.plazas_vendidas)
    
    def to_dict(self):
        return {
            'id': self.id,
            'tour_id': self.tour_id,
            'fecha_salida': self.fecha_salida.isoformat() if self.fecha_salida else None,
            'plazas_totales': self.plazas_totales,
            'plazas_vendidas': self.plazas_vendidas,
            'plazas_disponibles': self.plazas_disponibles,
            'precio_especial': self.precio_especial,
            'estado': self.estado,
            'notas': self.notas
        }
    
    def __repr__(self):
        return f"<Salida {self.id}: Tour {self.tour_id} - {self.fecha_salida}>"


class Pedido(Base):
    """Pedidos/Reservas de clientes"""
    __tablename__ = 'pedidos'
    
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), index=True)
    tour_id = Column(Integer, ForeignKey('tours.id'), index=True)
    
    num_personas = Column(Integer, nullable=False)
    precio_total = Column(Float, nullable=False)
    estado = Column(String(50), default='pendiente', index=True)
    
    fecha_pedido = Column(DateTime, default=datetime.utcnow, index=True)
    stripe_session_id = Column(String(255), unique=True)
    
    # Relaciones
    usuario = relationship('Usuario', back_populates='pedidos')
    
    def to_dict(self):
        """Serializa el pedido a diccionario"""
        return {
            'id': self.id,
            'usuario_id': self.usuario_id,
            'tour_id': self.tour_id,
            'num_personas': self.num_personas,
            'precio_total': self.precio_total,
            'estado': self.estado,
            'fecha_pedido': self.fecha_pedido.isoformat() if self.fecha_pedido else None,
            'stripe_session_id': self.stripe_session_id,
        }

    def __repr__(self):
        return f"<Pedido {self.id}: €{self.precio_total} - {self.estado}>"


class SolicitudTour(Base):
    """Solicitudes de información sobre tours"""
    __tablename__ = 'solicitudes_tour'
    
    id = Column(Integer, primary_key=True)
    tour_id = Column(Integer, ForeignKey('tours.id', ondelete='SET NULL'), index=True)
    
    nombre = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False)
    telefono = Column(String(50))
    num_personas = Column(Integer)
    mensaje = Column(Text)
    
    fecha_solicitud = Column(DateTime, default=datetime.utcnow, index=True)
    estado = Column(String(50), default='nueva', index=True)  # nueva, contactado, cerrado
    
    # Relaciones
    tour = relationship('Tour', back_populates='solicitudes')
    
    def to_dict(self, incluir_sensibles=False):
        """Serializa la solicitud a diccionario"""
        data = {
            'id': self.id,
            'tour_id': self.tour_id,
            'nombre': self.nombre,
            'num_personas': self.num_personas,
            'mensaje': self.mensaje,
            'fecha_solicitud': self.fecha_solicitud.isoformat() if self.fecha_solicitud else None,
            'estado': self.estado,
        }
        if incluir_sensibles:
            data['email'] = self.email
            data['telefono'] = self.telefono
        return data
    
    def __repr__(self):
        return f"<Solicitud {self.id}: {self.nombre} - Tour {self.tour_id}>"


# ==========================================
# MODELOS PARA SISTEMA DE VENTAS (WEBHOOK)
# ==========================================

class Cliente(Base):
    """Clientes de la agencia"""
    __tablename__ = 'clientes'
    
    id_cliente = Column(Integer, primary_key=True, autoincrement=True)
    nombre_razon_social = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    telefono = Column(String(50))
    direccion = Column(Text)
    dni_cif = Column(String(20))
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    expedientes = relationship('Expediente', back_populates='cliente')
    
    def __repr__(self):
        return f"<Cliente {self.id_cliente}: {self.nombre_razon_social}>"


class Expediente(Base):
    """Expedientes de viaje (post-venta)"""
    __tablename__ = 'expedientes'
    
    id_expediente = Column(Integer, primary_key=True, autoincrement=True)
    codigo_expediente = Column(String(50), unique=True, nullable=False, index=True)
    id_cliente_titular = Column(Integer, ForeignKey('clientes.id_cliente', ondelete='CASCADE'), nullable=False)
    id_viaje = Column(Integer, ForeignKey('tours.id', ondelete='SET NULL'))
    
    estado = Column(String(20), default='PENDIENTE', index=True)  # PENDIENTE, CONFIRMADO, PAGADO, COMPLETADO, CANCELADO
    total_venta = Column(Float, nullable=False)
    fecha_salida = Column(Date)
    fecha_regreso = Column(Date)
    
    notas = Column(Text)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, index=True)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    cliente = relationship('Cliente', back_populates='expedientes')
    viaje = relationship('Tour')
    pasajeros = relationship('Pasajero', back_populates='expediente', cascade='all, delete-orphan')
    facturas = relationship('Factura', back_populates='expediente', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Expediente {self.codigo_expediente} - €{self.total_venta}>"


class Pasajero(Base):
    """Pasajeros de un expediente"""
    __tablename__ = 'pasajeros'
    
    id_pasajero = Column(Integer, primary_key=True, autoincrement=True)
    id_expediente = Column(Integer, ForeignKey('expedientes.id_expediente', ondelete='CASCADE'), nullable=False, index=True)
    
    nombre_completo = Column(String(255), nullable=False)
    dni_pasaporte_encriptado = Column(String(500))  # AES-256 encrypted
    dni_blind_index = Column(String(64), index=True)  # SHA-256 hash para búsquedas
    fecha_nacimiento = Column(Date)
    nacionalidad = Column(String(50))
    tipo_pasajero = Column(String(20), default='adulto')  # adulto, niño, bebe
    
    # Relaciones
    expediente = relationship('Expediente', back_populates='pasajeros')
    
    def __repr__(self):
        return f"<Pasajero {self.id_pasajero}: {self.nombre_completo}>"


class Factura(Base):
    """Facturas emitidas"""
    __tablename__ = 'facturas'
    
    id_factura = Column(Integer, primary_key=True, autoincrement=True)
    id_expediente = Column(Integer, ForeignKey('expedientes.id_expediente', ondelete='CASCADE'), nullable=False, index=True)
    
    numero_factura = Column(String(50), unique=True, nullable=False, index=True)
    email_cliente = Column(String(255), nullable=False)
    monto = Column(Float, nullable=False)
    
    # Stripe
    stripe_id = Column(String(255), unique=True, index=True)
    stripe_payment_intent = Column(String(255))
    
    # Archivos
    url_archivo_pdf = Column(String(500))
    
    # Control
    pagada = Column(Boolean, default=False)
    fecha_emision = Column(DateTime, default=datetime.utcnow, index=True)
    fecha_vencimiento = Column(Date)
    fecha_pago = Column(DateTime)
    
    # Relaciones
    expediente = relationship('Expediente', back_populates='facturas')
    
    def __repr__(self):
        return f"<Factura {self.numero_factura} - €{self.monto}>"

class ReservaVuelo(Base):
    """Reservas de vuelos (Duffel + Amadeus + Stripe)"""
    __tablename__ = 'reservas_vuelo'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo_reserva = Column(String(50), unique=True, nullable=False, index=True)
    
    # Provider (DUFFEL o AMADEUS)
    provider = Column(String(20), default='DUFFEL', index=True)
    
    # Duffel IDs
    offer_id_duffel = Column(String(255), index=True)  # ID de la oferta seleccionada
    order_id_duffel = Column(String(255), index=True)  # ID del order creado
    
    # ✅ NUEVO: Amadeus IDs
    amadeus_order_id = Column(String(255), index=True)  # ID de la orden Amadeus
    amadeus_pnr = Column(String(50), index=True)  # queuingOfficeId (el PNR real)
    
    # Datos del vuelo (JSON)
    datos_vuelo = Column(Text)  # JSON: origen, destino, fecha, aerolinea, etc.
    pasajeros = Column(Text)  # JSON array con datos de cada pasajero
    
    # ✅ NUEVO: Oferta completa de Amadeus (para auditoría)
    amadeus_full_offer = Column(Text)  # JSON con estructura completa de la oferta validada
    
    # Precios
    precio_vuelos = Column(Float, nullable=False)
    precio_extras = Column(Float, default=0.0)  # Equipaje, seguro, etc.
    precio_total = Column(Float, nullable=False)
    
    # ✅ NUEVO: Información de validación de precio
    amadeus_full_pricing = Column(Text)  # JSON con respuesta de validación de precio
    fecha_validacion_precio = Column(DateTime)  # Cuándo se validó el precio
    
    # ✅ NUEVO: Política de ticketing
    lastTicketingDate = Column(String(20))  # Fecha límite para emitir: "2024-12-25"
    ticketingAgreement = Column(Text)  # JSON: {"option": "CONFIRM|DELAY|GUARANTEE", "delay": "6D"}
    
    # Stripe
    stripe_payment_intent_id = Column(String(255), index=True)
    stripe_session_id = Column(String(255))
    
    # Duffel Payments (separado de Stripe)
    duffel_payment_intent_id = Column(String(255), index=True)
    
    # Estado
    estado = Column(String(50), default='PENDIENTE', index=True)
    # PENDIENTE -> PAGADO -> CONFIRMADO -> EMITIDO -> ERROR
    
    # Contacto
    nombre_cliente = Column(String(255))  # Nombre completo del titular
    email_cliente = Column(String(255), nullable=False, index=True)
    telefono_cliente = Column(String(50))
    
    # Datos de vuelo extraídos (queryable)
    booking_reference = Column(String(100), index=True)  # Ref de booking (antes en notas)
    numero_vuelo = Column(String(50), index=True)  # Nº vuelo principal (ej: IB3216)
    fecha_vuelo_ida = Column(Date, index=True)  # Para queries de check-in 24h
    moneda = Column(String(3), default='EUR')  # ISO 4217
    
    # Check-in
    checkin_recordatorio_enviado = Column(Boolean, default=False)
    
    # Metadatos
    es_viaje_redondo = Column(Boolean, default=False)
    notas = Column(Text)
    error_mensaje = Column(Text)  # Si hay error en booking
    
    # Información de emisión
    ticket_numbers = Column(Text)  # JSON array: ["0011234567890", ...]
    amenities_added = Column(Text)  # JSON: [{"type": "SEAT", "value": "12A"}, ...]
    
    # Fechas
    fecha_creacion = Column(DateTime, default=datetime.utcnow, index=True)
    fecha_pago = Column(DateTime)
    fecha_confirmacion = Column(DateTime)
    fecha_orden_creada = Column(DateTime)
    fecha_emision = Column(DateTime)

    def to_dict(self):
        """Serializa la reserva a diccionario"""
        import json as _json
        datos = {}
        try:
            datos = _json.loads(self.datos_vuelo) if self.datos_vuelo else {}
        except (ValueError, TypeError):
            pass
        return {
            'id': self.id,
            'codigo_reserva': self.codigo_reserva,
            'provider': self.provider,
            'estado': self.estado,
            'nombre_cliente': self.nombre_cliente,
            'email_cliente': self.email_cliente,
            'telefono_cliente': self.telefono_cliente,
            'precio_vuelos': self.precio_vuelos,
            'precio_extras': self.precio_extras,
            'precio_total': self.precio_total,
            'moneda': self.moneda or 'EUR',
            'booking_reference': self.booking_reference,
            'numero_vuelo': self.numero_vuelo,
            'fecha_vuelo_ida': str(self.fecha_vuelo_ida) if self.fecha_vuelo_ida else None,
            'es_viaje_redondo': self.es_viaje_redondo,
            'datos_vuelo': datos,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            'fecha_pago': self.fecha_pago.isoformat() if self.fecha_pago else None,
            'fecha_confirmacion': self.fecha_confirmacion.isoformat() if self.fecha_confirmacion else None,
            'fecha_emision': self.fecha_emision.isoformat() if self.fecha_emision else None,
        }

    def __repr__(self):
        return f"<ReservaVuelo {self.codigo_reserva} - {self.estado} ({self.provider})>"


class DuffelSearch(Base):
    """Busquedas de vuelos Duffel para analitica"""
    __tablename__ = 'duffel_searches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    origen = Column(String(10), index=True)
    destino = Column(String(10), index=True)
    fecha = Column(String(20))
    adultos = Column(Integer, default=1)
    ninos = Column(Integer, default=0)
    bebes = Column(Integer, default=0)
    clase = Column(String(30))
    results_count = Column(Integer)
    user_ip = Column(String(64))
    fecha_creacion = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<DuffelSearch {self.origen}->{self.destino} {self.fecha}>"


class ConfigWeb(Base):
    """Configuración editable de la web (textos, contacto, etc.) para el panel admin."""
    __tablename__ = 'config_web'

    id = Column(Integer, primary_key=True, autoincrement=True)
    clave = Column(String(80), unique=True, nullable=False, index=True)
    valor = Column(Text, nullable=True)
    descripcion = Column(String(255), nullable=True)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ConfigWeb {self.clave}>"
