"""
Blueprints package

Actualmente solo se mantiene tours.py para compatibilidad y evolución
modular futura. Las rutas de vuelos/pagos viven en app.py.
"""

from .tours import init_tours_blueprint

__all__ = ['init_tours_blueprint']
