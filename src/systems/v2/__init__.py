"""
V2 Trading Systems - Improved with Automatic Stop-Loss/Take-Profit
"""

from src.systems.v2.event_driven import ImprovedEventDrivenSystem
from src.systems.v2.hybrid import ImprovedHybridSystem

__all__ = [
    'ImprovedEventDrivenSystem',
    'ImprovedHybridSystem',
]