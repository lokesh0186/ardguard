"""Public fact-provider interfaces."""

from ardguard.providers.base import FactProvider
from ardguard.providers.static import StaticFactProvider

__all__ = ["FactProvider", "StaticFactProvider"]
