"""
Identity Module - OpenClaw-style identity management
"""

from .loader import IdentityLoader, get_identity_loader, inject_identity

__all__ = ['IdentityLoader', 'get_identity_loader', 'inject_identity']
