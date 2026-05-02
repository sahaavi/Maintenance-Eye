"""
EAM provider selection and singleton lifecycle.

Concrete adapters stay in their own modules; this module owns runtime
selection between Firestore and JSON-backed EAM implementations.
"""

import logging

import google.auth
from config import settings
from google.auth.exceptions import DefaultCredentialsError
from services.eam_interface import EAMService
from services.firestore_eam import FirestoreEAM
from services.json_eam import JsonEAM

logger = logging.getLogger("maintenance-eye.eam-provider")

_eam_service: EAMService | None = None


def _has_firestore_runtime() -> bool:
    """
    Detect whether Firestore can be used in this runtime.
    - Emulator host always enables Firestore.
    - Otherwise require valid ADC credentials.
    """
    if settings.FIRESTORE_EMULATOR_HOST:
        return True
    try:
        google.auth.default()
        return True
    except DefaultCredentialsError:
        return False
    except Exception as exc:
        logger.debug(f"Failed checking ADC credentials: {exc}")
        return False


def get_eam_service() -> EAMService:
    """Get or create the active EAM service singleton.

    Tries Firestore first; falls back to the JSON-backed adapter when
    Firestore is unavailable or fails during initialization.
    """
    global _eam_service
    if _eam_service is not None:
        return _eam_service

    if _has_firestore_runtime():
        try:
            _eam_service = FirestoreEAM()
            return _eam_service
        except Exception as exc:
            logger.warning(f"Firestore init failed, falling back to JSON: {exc}")

    logger.info("Using JSON-backed EAM service (seed_data.json)")
    _eam_service = JsonEAM()
    return _eam_service
