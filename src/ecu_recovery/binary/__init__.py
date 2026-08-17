"""Firmware intake contracts.

The public imports live here while the original module paths remain available
for backward compatibility.
"""

from ..intake import IntakeError, profile_binary
from ..models import BinaryProfile, RepeatedRegion

__all__ = ["BinaryProfile", "IntakeError", "RepeatedRegion", "profile_binary"]
