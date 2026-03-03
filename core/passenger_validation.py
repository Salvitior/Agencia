"""
Validación de datos de pasajeros: documentos, edades, menores, pasaportes expirados.
"""

from datetime import date, datetime, timedelta
import re
import logging

logger = logging.getLogger(__name__)


class ValidacionError:
    """Representa un error de validación"""
    def __init__(self, campo, mensaje, tipo='error'):
        self.campo = campo
        self.mensaje = mensaje
        self.tipo = tipo  # 'error', 'warning'

    def to_dict(self):
        return {
            'campo': self.campo,
            'mensaje': self.mensaje,
            'tipo': self.tipo,
        }


class ValidadorPasajeros:
    """
    Valida datos de pasajeros antes de crear una reserva.
    
    Reglas implementadas:
    - Formato de DNI/NIE/Pasaporte
    - Pasaporte no expirado (mínimo 6 meses de vigencia para viajes internacionales)
    - Menores con documentación adecuada
    - Fecha de nacimiento coherente con tipo de pasajero
    - Nombre y apellidos no vacíos
    - Email válido para el contacto principal
    - Teléfono con formato válido
    """

    # Patrones de documentos españoles
    PATRON_DNI = re.compile(r'^[0-9]{8}[A-Z]$')
    PATRON_NIE = re.compile(r'^[XYZ][0-9]{7}[A-Z]$')
    PATRON_PASAPORTE_ES = re.compile(r'^[A-Z]{2,3}[0-9]{6}$')
    PATRON_PASAPORTE_GENERICO = re.compile(r'^[A-Z0-9]{5,20}$')
    PATRON_EMAIL = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PATRON_TELEFONO = re.compile(r'^\+?[0-9\s\-()]{7,20}$')

    # Letras de control para DNI
    LETRAS_DNI = 'TRWAGMYFPDXBNJZSQVHLCKE'

    # Edades máximas y mínimas por tipo
    LIMITES_EDAD = {
        'adulto': {'min': 12, 'max': 120},
        'niño': {'min': 2, 'max': 11},  # child (2-11)
        'nino': {'min': 2, 'max': 11},
        'bebe': {'min': 0, 'max': 1},   # infant (0-1)
        'infant_without_seat': {'min': 0, 'max': 1},
        'child': {'min': 2, 'max': 11},
        'adult': {'min': 12, 'max': 120},
    }

    @classmethod
    def validar_reserva_completa(cls, pasajeros, fecha_vuelo, es_internacional=False):
        """
        Valida todos los pasajeros de una reserva.
        
        Args:
            pasajeros: Lista de dicts con datos de pasajeros
            fecha_vuelo: Date del primer vuelo
            es_internacional: Si el vuelo es internacional (requiere pasaporte)
            
        Returns:
            dict: {valido: bool, errores: [...], warnings: [...]}
        """
        errores = []
        warnings = []

        if not pasajeros or len(pasajeros) == 0:
            errores.append(ValidacionError('pasajeros', 'Debe haber al menos un pasajero').to_dict())
            return {'valido': False, 'errores': errores, 'warnings': warnings}

        # Verificar que hay al menos un adulto
        tiene_adulto = False
        menores_sin_adulto = []

        for idx, pax in enumerate(pasajeros):
            pax_errores, pax_warnings = cls.validar_pasajero(pax, idx, fecha_vuelo, es_internacional)
            errores.extend(pax_errores)
            warnings.extend(pax_warnings)

            tipo = pax.get('type', pax.get('tipo_pasajero', 'adult')).lower()
            if tipo in ('adulto', 'adult'):
                tiene_adulto = True
            elif tipo in ('bebe', 'infant_without_seat', 'niño', 'nino', 'child'):
                menores_sin_adulto.append(idx)

        if not tiene_adulto and menores_sin_adulto:
            errores.append(ValidacionError(
                'pasajeros',
                'Los menores de edad necesitan viajar con al menos un adulto'
            ).to_dict())

        # Verificar ratio bebés/adultos (máximo 1 bebé por adulto)
        num_adultos = sum(1 for p in pasajeros
                         if p.get('type', p.get('tipo_pasajero', 'adult')).lower() in ('adulto', 'adult'))
        num_bebes = sum(1 for p in pasajeros
                        if p.get('type', p.get('tipo_pasajero', '')).lower() in ('bebe', 'infant_without_seat'))
        
        if num_bebes > num_adultos:
            errores.append(ValidacionError(
                'pasajeros',
                f'No puede haber más bebés ({num_bebes}) que adultos ({num_adultos}). Máximo 1 bebé por adulto.'
            ).to_dict())

        return {
            'valido': len(errores) == 0,
            'errores': errores,
            'warnings': warnings,
        }

    @classmethod
    def validar_pasajero(cls, pax, indice, fecha_vuelo, es_internacional=False):
        """Valida un pasajero individual"""
        errores = []
        warnings = []
        prefix = f'pasajero_{indice}'

        # --- Nombre y apellidos ---
        nombre = (pax.get('given_name') or pax.get('nombre', '')).strip()
        apellidos = (pax.get('family_name') or pax.get('apellidos', '')).strip()

        if not nombre:
            errores.append(ValidacionError(f'{prefix}.nombre', 'El nombre es obligatorio').to_dict())
        elif len(nombre) < 2:
            errores.append(ValidacionError(f'{prefix}.nombre', 'El nombre debe tener al menos 2 caracteres').to_dict())

        if not apellidos:
            errores.append(ValidacionError(f'{prefix}.apellidos', 'Los apellidos son obligatorios').to_dict())
        elif len(apellidos) < 2:
            errores.append(ValidacionError(f'{prefix}.apellidos', 'Los apellidos deben tener al menos 2 caracteres').to_dict())

        # --- Fecha de nacimiento ---
        fecha_nac = pax.get('born_on') or pax.get('fecha_nacimiento')
        tipo = (pax.get('type') or pax.get('tipo_pasajero', 'adult')).lower()

        if not fecha_nac:
            errores.append(ValidacionError(f'{prefix}.fecha_nacimiento', 'La fecha de nacimiento es obligatoria').to_dict())
        else:
            try:
                if isinstance(fecha_nac, str):
                    fecha_nac_date = datetime.strptime(fecha_nac, '%Y-%m-%d').date()
                elif isinstance(fecha_nac, date):
                    fecha_nac_date = fecha_nac
                else:
                    raise ValueError("Formato inválido")

                # Verificar que no es una fecha futura
                if fecha_nac_date > date.today():
                    errores.append(ValidacionError(
                        f'{prefix}.fecha_nacimiento',
                        'La fecha de nacimiento no puede ser futura'
                    ).to_dict())
                else:
                    # Calcular edad en la fecha del vuelo
                    edad = cls._calcular_edad(fecha_nac_date, fecha_vuelo)

                    # Verificar coherencia con tipo de pasajero
                    limites = cls.LIMITES_EDAD.get(tipo)
                    if limites:
                        if edad < limites['min'] or edad > limites['max']:
                            errores.append(ValidacionError(
                                f'{prefix}.tipo_pasajero',
                                f'La edad ({edad} años) no corresponde al tipo "{tipo}" '
                                f'(debe tener entre {limites["min"]} y {limites["max"]} años)'
                            ).to_dict())

                    # Warning para menores que viajan
                    if edad < 2:
                        warnings.append(ValidacionError(
                            f'{prefix}.edad',
                            f'Pasajero menor de 2 años. Viajará como bebé en brazos.',
                            'warning'
                        ).to_dict())
                    elif edad < 14:
                        warnings.append(ValidacionError(
                            f'{prefix}.edad',
                            f'Menor de 14 años. Puede requerir autorización de viaje para menores.',
                            'warning'
                        ).to_dict())

            except (ValueError, TypeError):
                errores.append(ValidacionError(
                    f'{prefix}.fecha_nacimiento',
                    'Formato de fecha inválido. Use YYYY-MM-DD'
                ).to_dict())

        # --- Documento de identidad ---
        tipo_doc = (pax.get('identity_document_type') or pax.get('tipo_documento', '')).upper()
        num_doc = (pax.get('identity_document_number') or pax.get('documento', '')).strip().upper()
        
        if es_internacional:
            # Para vuelos internacionales se necesita pasaporte
            if tipo_doc and tipo_doc not in ('PASSPORT', 'PASAPORTE'):
                warnings.append(ValidacionError(
                    f'{prefix}.documento',
                    'Para vuelos internacionales se recomienda pasaporte en vigor',
                    'warning'
                ).to_dict())

        if num_doc:
            doc_valido, doc_msg = cls.validar_documento(tipo_doc, num_doc)
            if not doc_valido:
                errores.append(ValidacionError(f'{prefix}.documento', doc_msg).to_dict())
        else:
            # Menores de 14 podrían no tener DNI en España, pero necesitan algo
            if fecha_nac:
                try:
                    if isinstance(fecha_nac, str):
                        fn = datetime.strptime(fecha_nac, '%Y-%m-%d').date()
                    else:
                        fn = fecha_nac
                    edad = cls._calcular_edad(fn, date.today())
                    if edad >= 14:
                        errores.append(ValidacionError(
                            f'{prefix}.documento',
                            'El documento de identidad es obligatorio para mayores de 14 años'
                        ).to_dict())
                    elif es_internacional:
                        errores.append(ValidacionError(
                            f'{prefix}.documento',
                            'Para vuelos internacionales, todos los pasajeros necesitan documento de viaje'
                        ).to_dict())
                except (ValueError, TypeError):
                    pass

        # --- Caducidad del documento ---
        fecha_cad = pax.get('identity_document_expiry') or pax.get('fecha_caducidad_documento')
        if fecha_cad:
            try:
                if isinstance(fecha_cad, str):
                    fecha_cad_date = datetime.strptime(fecha_cad, '%Y-%m-%d').date()
                else:
                    fecha_cad_date = fecha_cad

                if fecha_cad_date < date.today():
                    errores.append(ValidacionError(
                        f'{prefix}.documento_caducidad',
                        'El documento está caducado. Debe renovarlo antes de viajar.'
                    ).to_dict())
                elif es_internacional and fecha_cad_date < fecha_vuelo + timedelta(days=180):
                    warnings.append(ValidacionError(
                        f'{prefix}.documento_caducidad',
                        'El pasaporte debe tener al menos 6 meses de vigencia para viajes internacionales. '
                        f'Caduca el {fecha_cad_date.isoformat()}.',
                        'warning'
                    ).to_dict())
                elif fecha_cad_date < fecha_vuelo:
                    errores.append(ValidacionError(
                        f'{prefix}.documento_caducidad',
                        f'El documento caduca ({fecha_cad_date.isoformat()}) antes de la fecha de vuelo ({fecha_vuelo.isoformat()})'
                    ).to_dict())
            except (ValueError, TypeError):
                warnings.append(ValidacionError(
                    f'{prefix}.documento_caducidad',
                    'No se pudo verificar la fecha de caducidad del documento',
                    'warning'
                ).to_dict())
        elif es_internacional:
            warnings.append(ValidacionError(
                f'{prefix}.documento_caducidad',
                'Se recomienda indicar la fecha de caducidad del pasaporte para viajes internacionales',
                'warning'
            ).to_dict())

        # --- Nacionalidad ---
        nacionalidad = pax.get('nationality') or pax.get('nacionalidad', '')
        if not nacionalidad:
            warnings.append(ValidacionError(
                f'{prefix}.nacionalidad',
                'La nacionalidad es recomendable para completar la reserva',
                'warning'
            ).to_dict())

        # --- Género (requerido por muchas aerolíneas) ---
        genero = pax.get('gender') or pax.get('genero', '')
        if not genero:
            warnings.append(ValidacionError(
                f'{prefix}.genero',
                'El género es requerido por la mayoría de aerolíneas',
                'warning'
            ).to_dict())

        return errores, warnings

    @classmethod
    def validar_documento(cls, tipo_doc, numero):
        """
        Valida formato de documento de identidad.
        
        Returns:
            tuple: (es_valido, mensaje_error)
        """
        numero = numero.strip().upper().replace(' ', '').replace('-', '')

        if tipo_doc in ('DNI', 'NATIONAL_IDENTITY_CARD'):
            return cls._validar_dni(numero)
        elif tipo_doc in ('NIE',):
            return cls._validar_nie(numero)
        elif tipo_doc in ('PASSPORT', 'PASAPORTE'):
            return cls._validar_pasaporte(numero)
        else:
            # Validación genérica
            if len(numero) < 5:
                return False, 'El número de documento es demasiado corto'
            if len(numero) > 20:
                return False, 'El número de documento es demasiado largo'
            return True, ''

    @classmethod
    def _validar_dni(cls, numero):
        """Valida DNI español con letra de control"""
        if not cls.PATRON_DNI.match(numero):
            return False, 'Formato de DNI inválido. Debe ser 8 dígitos + letra (ej: 12345678Z)'

        # Verificar letra de control
        num = int(numero[:8])
        letra_esperada = cls.LETRAS_DNI[num % 23]
        if numero[8] != letra_esperada:
            return False, f'La letra del DNI no es correcta. Se esperaba "{letra_esperada}"'

        return True, ''

    @classmethod
    def _validar_nie(cls, numero):
        """Valida NIE español"""
        if not cls.PATRON_NIE.match(numero):
            return False, 'Formato de NIE inválido. Debe ser X/Y/Z + 7 dígitos + letra (ej: X1234567A)'

        # Convertir primera letra a número para calcular
        primera = {'X': '0', 'Y': '1', 'Z': '2'}[numero[0]]
        num = int(primera + numero[1:8])
        letra_esperada = cls.LETRAS_DNI[num % 23]
        if numero[8] != letra_esperada:
            return False, f'La letra del NIE no es correcta. Se esperaba "{letra_esperada}"'

        return True, ''

    @classmethod
    def _validar_pasaporte(cls, numero):
        """Valida formato básico de pasaporte"""
        if len(numero) < 5:
            return False, 'El número de pasaporte es demasiado corto'
        if len(numero) > 20:
            return False, 'El número de pasaporte es demasiado largo'
        if not cls.PATRON_PASAPORTE_GENERICO.match(numero):
            return False, 'El pasaporte solo puede contener letras y números'
        return True, ''

    @classmethod
    def validar_contacto(cls, email, telefono=None):
        """Valida datos de contacto del titular"""
        errores = []

        if not email:
            errores.append(ValidacionError('email', 'El email es obligatorio').to_dict())
        elif not cls.PATRON_EMAIL.match(email):
            errores.append(ValidacionError('email', 'El formato del email no es válido').to_dict())

        if telefono:
            telefono_limpio = telefono.strip()
            if not cls.PATRON_TELEFONO.match(telefono_limpio):
                errores.append(ValidacionError('telefono', 'El formato del teléfono no es válido').to_dict())

        return errores

    @staticmethod
    def _calcular_edad(fecha_nacimiento, fecha_referencia):
        """Calcula la edad en años a una fecha de referencia"""
        if isinstance(fecha_referencia, datetime):
            fecha_referencia = fecha_referencia.date()
        edad = fecha_referencia.year - fecha_nacimiento.year
        if (fecha_referencia.month, fecha_referencia.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
            edad -= 1
        return edad
