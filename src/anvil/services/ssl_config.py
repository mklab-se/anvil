"""SSL configuration utilities for corporate networks."""

import os
import ssl
import warnings
from functools import lru_cache


@lru_cache(maxsize=1)
def get_ssl_verify() -> bool | str:
    """Get SSL verification setting.

    Checks environment variables in order:
    1. ANVIL_SSL_VERIFY - set to 'false' or '0' to disable verification
    2. SSL_CERT_FILE - path to CA bundle file
    3. REQUESTS_CA_BUNDLE - alternative path to CA bundle

    Returns:
        True for default verification, False to disable, or path to CA bundle.
    """
    # Check if SSL verification is explicitly disabled
    ssl_verify = os.environ.get("ANVIL_SSL_VERIFY", "").lower()
    if ssl_verify in ("false", "0", "no", "off"):
        warnings.warn(
            "SSL verification is disabled via ANVIL_SSL_VERIFY. "
            "This is insecure and should only be used for testing.",
            stacklevel=2,
        )
        return False

    # Check for custom CA bundle
    ca_bundle = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if ca_bundle and os.path.exists(ca_bundle):
        return ca_bundle

    return True


def get_ssl_context() -> ssl.SSLContext | bool:
    """Get SSL context for use with libraries that need it.

    Returns:
        SSLContext with CA bundle loaded, or False to disable verification.
    """
    verify = get_ssl_verify()

    if verify is False:
        return False

    if isinstance(verify, str):
        # Custom CA bundle path
        context = ssl.create_default_context()
        context.load_verify_locations(verify)
        return context

    return True  # Use default


def format_ssl_error_message(error: Exception) -> str:
    """Format a helpful error message for SSL errors.

    Args:
        error: The SSL-related exception.

    Returns:
        User-friendly error message with troubleshooting steps.
    """
    error_str = str(error).lower()

    # Detect SSL certificate errors
    ssl_keywords = [
        "ssl",
        "certificate",
        "cert",
        "verify",
        "handshake",
        "tlsv1",
        "sslv3",
        "unable to get local issuer",
        "certificate verify failed",
        "self signed certificate",
    ]

    is_ssl_error = any(keyword in error_str for keyword in ssl_keywords)

    if not is_ssl_error:
        return str(error)

    return f"""SSL Certificate Error: {error}

This often happens on corporate networks that use a custom CA bundle.

To fix this, try one of the following:

1. Set your corporate CA bundle:
   export SSL_CERT_FILE=/path/to/corporate-ca-bundle.crt
   export REQUESTS_CA_BUNDLE=/path/to/corporate-ca-bundle.crt

2. On macOS, export the system certificates:
   security export -t certs -f pemseq -k /Library/Keychains/System.keychain -o ~/corp-ca.pem
   export SSL_CERT_FILE=~/corp-ca.pem

3. Temporarily disable SSL verification (NOT recommended for production):
   export ANVIL_SSL_VERIFY=false

For more help, contact your IT department for the corporate CA certificate."""
