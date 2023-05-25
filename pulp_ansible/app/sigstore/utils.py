"""
Utils for interacting with Sigstore-specific components.
"""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import UnsupportedAlgorithm


def validate_and_format_pem_public_key(value) -> str:
    """Validate the public key and return a formatted version."""
    try:
        public_key = serialization.load_pem_public_key(value.encode(), backend=default_backend())
        pem_data = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        return pem_data.strip()

    except (ValueError, TypeError, UnsupportedAlgorithm):
        raise Exception("Invalid PEM public key format.")
