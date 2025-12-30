"""SSL configuration and diagnostics utilities for corporate networks."""

import os
import platform
import shutil
import ssl
import subprocess
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


@dataclass
class CertificateInfo:
    """Information about a certificate file."""

    path: str
    exists: bool = False
    readable: bool = False
    is_valid_pem: bool = False
    cert_count: int = 0
    error: str | None = None
    subjects: list[str] = field(default_factory=list)


@dataclass
class SSLDiagnostics:
    """Results of SSL diagnostics."""

    # Environment variable status
    ssl_cert_file: str | None = None
    requests_ca_bundle: str | None = None
    anvil_ssl_verify: str | None = None

    # Certificate file analysis
    cert_file_info: CertificateInfo | None = None

    # Connection test results
    test_host: str = "management.azure.com"
    connection_successful: bool = False
    connection_error: str | None = None
    openssl_available: bool = False
    openssl_output: str | None = None

    # System info
    system: str = ""
    has_security_command: bool = False  # macOS security command

    # Recommendations
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    can_auto_fix: bool = False
    auto_fix_command: str | None = None


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


def _analyze_certificate_file(path: str) -> CertificateInfo:
    """Analyze a certificate file for validity.

    Args:
        path: Path to the certificate file.

    Returns:
        CertificateInfo with analysis results.
    """
    info = CertificateInfo(path=path)

    # Check if file exists
    if not os.path.exists(path):
        info.error = f"File does not exist: {path}"
        return info
    info.exists = True

    # Check if readable
    try:
        with open(path, "rb") as f:
            content = f.read()
        info.readable = True
    except PermissionError:
        info.error = f"Permission denied reading: {path}"
        return info
    except Exception as e:
        info.error = f"Cannot read file: {e}"
        return info

    # Check if it's valid PEM format
    try:
        content_str = content.decode("utf-8", errors="replace")

        # Count certificates in the bundle
        cert_count = content_str.count("-----BEGIN CERTIFICATE-----")
        end_count = content_str.count("-----END CERTIFICATE-----")

        if cert_count == 0:
            info.error = "File does not contain any PEM certificates"
            return info

        if cert_count != end_count:
            info.error = f"Malformed PEM: {cert_count} BEGIN markers but {end_count} END markers"
            return info

        info.is_valid_pem = True
        info.cert_count = cert_count

        # Try to extract subject names using openssl if available
        if shutil.which("openssl"):
            try:
                result = subprocess.run(
                    ["openssl", "crl2pkcs7", "-nocrl", "-certfile", path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    # Parse subjects from the certificates
                    result2 = subprocess.run(
                        [
                            "openssl",
                            "pkcs7",
                            "-print_certs",
                            "-noout",
                            "-text",
                        ],
                        input=result.stdout,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result2.returncode == 0:
                        for line in result2.stdout.split("\n"):
                            if "Subject:" in line:
                                subject = line.split("Subject:")[-1].strip()
                                # Extract CN if present
                                if "CN = " in subject:
                                    cn = subject.split("CN = ")[-1].split(",")[0]
                                    info.subjects.append(cn)
                                elif "CN=" in subject:
                                    cn = subject.split("CN=")[-1].split(",")[0]
                                    info.subjects.append(cn)
            except Exception:
                pass  # Subject extraction is optional

    except Exception as e:
        info.error = f"Error parsing certificate: {e}"
        return info

    return info


def _test_ssl_connection(
    host: str, port: int = 443, ca_file: str | None = None
) -> tuple[bool, str]:
    """Test SSL connection to a host using openssl.

    Args:
        host: Hostname to connect to.
        port: Port number (default 443).
        ca_file: Optional CA file to use.

    Returns:
        Tuple of (success, output/error message).
    """
    if not shutil.which("openssl"):
        return False, "openssl command not available"

    cmd = ["openssl", "s_client", "-connect", f"{host}:{port}", "-verify", "5"]
    if ca_file:
        cmd.extend(["-CAfile", ca_file])

    try:
        # Send empty input to close connection after handshake
        result = subprocess.run(
            cmd,
            input="",
            capture_output=True,
            text=True,
            timeout=15,
        )

        output = result.stdout + result.stderr

        # Check for success indicators
        if "Verify return code: 0 (ok)" in output:
            return True, output

        # Extract the verification error
        for line in output.split("\n"):
            if "verify error:" in line.lower():
                return False, line.strip()
            if "Verify return code:" in line:
                return False, line.strip()

        if result.returncode != 0:
            return False, output[-500:] if len(output) > 500 else output

        return False, "Unknown SSL error"

    except subprocess.TimeoutExpired:
        return False, "Connection timed out"
    except Exception as e:
        return False, str(e)


def _get_certificate_chain(host: str, port: int = 443) -> list[str]:
    """Get the certificate chain from a host.

    Args:
        host: Hostname to connect to.
        port: Port number.

    Returns:
        List of certificate subjects in the chain.
    """
    if not shutil.which("openssl"):
        return []

    try:
        result = subprocess.run(
            ["openssl", "s_client", "-connect", f"{host}:{port}", "-showcerts"],
            input="",
            capture_output=True,
            text=True,
            timeout=15,
        )

        subjects = []
        for line in result.stdout.split("\n"):
            if line.strip().startswith("s:"):
                # Server certificate subject
                subject = line.split("s:")[-1].strip()
                subjects.append(f"Server: {subject}")
            elif line.strip().startswith("i:"):
                # Issuer
                issuer = line.split("i:")[-1].strip()
                subjects.append(f"Issuer: {issuer}")

        return subjects[:10]  # Limit to first 10 entries

    except Exception:
        return []


def diagnose_ssl_issues(test_host: str = "management.azure.com") -> SSLDiagnostics:
    """Run comprehensive SSL diagnostics.

    This function checks:
    1. Environment variables (SSL_CERT_FILE, REQUESTS_CA_BUNDLE, ANVIL_SSL_VERIFY)
    2. Certificate file validity
    3. SSL connection to Azure management endpoint
    4. System capabilities (openssl, macOS security command)

    Args:
        test_host: Host to test SSL connection against.

    Returns:
        SSLDiagnostics with detailed results and recommendations.
    """
    diag = SSLDiagnostics(test_host=test_host)

    # System info
    diag.system = platform.system()
    diag.openssl_available = shutil.which("openssl") is not None
    diag.has_security_command = shutil.which("security") is not None and diag.system == "Darwin"

    # Check environment variables
    diag.ssl_cert_file = os.environ.get("SSL_CERT_FILE")
    diag.requests_ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE")
    diag.anvil_ssl_verify = os.environ.get("ANVIL_SSL_VERIFY")

    # Determine which CA file is in use
    ca_file = diag.ssl_cert_file or diag.requests_ca_bundle

    # Analyze certificate file if specified
    if ca_file:
        diag.cert_file_info = _analyze_certificate_file(ca_file)

        if not diag.cert_file_info.exists:
            diag.issues.append(f"Certificate file does not exist: {ca_file}")
            diag.recommendations.append(f"Create or update the certificate file at: {ca_file}")
        elif not diag.cert_file_info.readable:
            diag.issues.append(f"Cannot read certificate file: {ca_file}")
            diag.recommendations.append(f"Check permissions on: {ca_file}")
        elif not diag.cert_file_info.is_valid_pem:
            diag.issues.append(f"Invalid certificate format: {diag.cert_file_info.error}")
            diag.recommendations.append("Ensure the file contains valid PEM-formatted certificates")
        elif diag.cert_file_info.cert_count == 0:
            diag.issues.append("Certificate bundle is empty")
    else:
        diag.issues.append("No custom CA bundle configured (SSL_CERT_FILE or REQUESTS_CA_BUNDLE)")

    # Test SSL connection
    if diag.openssl_available:
        # First test with the configured CA file
        success, output = _test_ssl_connection(test_host, ca_file=ca_file)
        diag.connection_successful = success
        diag.openssl_output = output

        if not success:
            diag.connection_error = output

            # Analyze the specific error
            output_lower = output.lower()

            if "unable to get local issuer certificate" in output_lower:
                diag.issues.append("Missing intermediate or root CA certificate in chain")
                # Get the certificate chain to show what's missing
                chain = _get_certificate_chain(test_host)
                if chain:
                    diag.recommendations.append(
                        f"The server's certificate chain requires these CAs: {', '.join(chain[:4])}"
                    )

            elif "self signed certificate in certificate chain" in output_lower:
                diag.issues.append(
                    "Self-signed certificate in chain (common with corporate proxies)"
                )
                diag.recommendations.append(
                    "Your corporate proxy likely uses a self-signed CA. "
                    "Export it from your system keychain."
                )

            elif "certificate has expired" in output_lower:
                diag.issues.append("A certificate in the chain has expired")
                diag.recommendations.append(
                    "Contact your IT department - a certificate needs renewal"
                )

            elif "unable to verify the first certificate" in output_lower:
                diag.issues.append("Cannot verify the server's certificate")
                if ca_file:
                    diag.recommendations.append(
                        f"The CA bundle at {ca_file} may not contain the required root CA"
                    )

            # Test without custom CA to see if system defaults work
            if ca_file:
                success_default, _ = _test_ssl_connection(test_host, ca_file=None)
                if success_default:
                    diag.issues.append(
                        "Connection works with system CAs but fails with your custom CA bundle"
                    )
                    diag.recommendations.append(
                        "Your custom CA bundle may be incomplete. Try combining it with system CAs."
                    )
    else:
        diag.issues.append("openssl command not available - cannot perform detailed diagnostics")
        diag.recommendations.append("Install openssl for better SSL troubleshooting")

    # Platform-specific recommendations
    if diag.system == "Darwin" and diag.has_security_command:
        # macOS - offer to export system keychain
        export_path = Path.home() / "anvil-ca-bundle.pem"
        diag.auto_fix_command = (
            f"security export -t certs -f pemseq -k /Library/Keychains/System.keychain "
            f"-o {export_path} && "
            f"security export -t certs -f pemseq -k ~/Library/Keychains/login.keychain-db "
            f">> {export_path} 2>/dev/null; "
            f'echo "\\nExported to {export_path}. Run:\\n'
            f'export SSL_CERT_FILE={export_path}"'
        )
        diag.can_auto_fix = True
        if not diag.connection_successful:
            diag.recommendations.append(
                f"On macOS, export your system certificates:\n"
                f"   security export -t certs -f pemseq -k /Library/Keychains/System.keychain -o {export_path}\n"
                f"   export SSL_CERT_FILE={export_path}"
            )

    elif diag.system == "Linux":
        # Linux - check common CA bundle locations
        linux_ca_paths = [
            "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu
            "/etc/pki/tls/certs/ca-bundle.crt",  # RHEL/CentOS
            "/etc/ssl/ca-bundle.pem",  # OpenSUSE
            "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # Fedora
        ]
        for path in linux_ca_paths:
            if os.path.exists(path):
                if not ca_file:
                    diag.recommendations.append(
                        f"Try using your system CA bundle:\n   export SSL_CERT_FILE={path}"
                    )
                break

    # Add general recommendations if nothing specific found
    if not diag.recommendations:
        if diag.anvil_ssl_verify and diag.anvil_ssl_verify.lower() in ("false", "0", "no", "off"):
            diag.recommendations.append(
                "SSL verification is currently disabled. "
                "This works but is insecure for production use."
            )
        else:
            diag.recommendations.append(
                "Contact your IT department for the corporate CA certificate bundle"
            )

    return diag


def format_ssl_error_message(error: Exception) -> str:
    """Format a helpful error message for SSL errors with diagnostics.

    Args:
        error: The SSL-related exception.

    Returns:
        User-friendly error message with diagnostics and troubleshooting steps.
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

    # Run diagnostics
    diag = diagnose_ssl_issues()

    # Build detailed error message
    lines = [
        f"SSL Certificate Error: {error}",
        "",
        "=" * 60,
        "SSL DIAGNOSTICS",
        "=" * 60,
        "",
    ]

    # Environment variables
    lines.append("Environment Variables:")
    lines.append(f"  SSL_CERT_FILE:      {diag.ssl_cert_file or '(not set)'}")
    lines.append(f"  REQUESTS_CA_BUNDLE: {diag.requests_ca_bundle or '(not set)'}")
    lines.append(f"  ANVIL_SSL_VERIFY:   {diag.anvil_ssl_verify or '(not set)'}")
    lines.append("")

    # Certificate file analysis
    if diag.cert_file_info:
        lines.append("Certificate File Analysis:")
        lines.append(f"  Path: {diag.cert_file_info.path}")
        lines.append(f"  Exists: {'Yes' if diag.cert_file_info.exists else 'No'}")
        if diag.cert_file_info.exists:
            lines.append(f"  Readable: {'Yes' if diag.cert_file_info.readable else 'No'}")
            if diag.cert_file_info.readable:
                lines.append(f"  Valid PEM: {'Yes' if diag.cert_file_info.is_valid_pem else 'No'}")
                if diag.cert_file_info.is_valid_pem:
                    lines.append(f"  Certificate count: {diag.cert_file_info.cert_count}")
                    if diag.cert_file_info.subjects:
                        lines.append(
                            f"  Contains CAs: {', '.join(diag.cert_file_info.subjects[:5])}"
                        )
        if diag.cert_file_info.error:
            lines.append(f"  Error: {diag.cert_file_info.error}")
        lines.append("")

    # Connection test
    lines.append(f"Connection Test ({diag.test_host}):")
    lines.append(f"  OpenSSL available: {'Yes' if diag.openssl_available else 'No'}")
    if diag.openssl_available:
        lines.append(f"  Connection: {'SUCCESS' if diag.connection_successful else 'FAILED'}")
        if diag.connection_error:
            lines.append(f"  Error: {diag.connection_error}")
    lines.append("")

    # Issues found
    if diag.issues:
        lines.append("Issues Found:")
        for issue in diag.issues:
            lines.append(f"  - {issue}")
        lines.append("")

    # Recommendations
    lines.append("=" * 60)
    lines.append("RECOMMENDATIONS")
    lines.append("=" * 60)
    lines.append("")

    if diag.recommendations:
        for i, rec in enumerate(diag.recommendations, 1):
            lines.append(f"{i}. {rec}")
            lines.append("")

    # Quick fix option
    if diag.can_auto_fix and diag.system == "Darwin":
        lines.append("Quick Fix for macOS:")
        lines.append("  Run this command to export system certificates:")
        lines.append("")
        export_path = Path.home() / "anvil-ca-bundle.pem"
        lines.append(
            f"  security export -t certs -f pemseq "
            f"-k /Library/Keychains/System.keychain -o {export_path}"
        )
        lines.append(f"  export SSL_CERT_FILE={export_path}")
        lines.append("")

    # Last resort
    lines.append("Last Resort (NOT recommended for production):")
    lines.append("  export ANVIL_SSL_VERIFY=false")
    lines.append("")

    return "\n".join(lines)


def export_macos_certificates(output_path: str | None = None) -> tuple[bool, str]:
    """Export macOS system certificates to a PEM file.

    Args:
        output_path: Path to write certificates. Defaults to ~/anvil-ca-bundle.pem

    Returns:
        Tuple of (success, message/path).
    """
    if platform.system() != "Darwin":
        return False, "This function is only available on macOS"

    if not shutil.which("security"):
        return False, "macOS security command not found"

    if output_path is None:
        output_path = str(Path.home() / "anvil-ca-bundle.pem")

    try:
        # Export system keychain
        result = subprocess.run(
            [
                "security",
                "export",
                "-t",
                "certs",
                "-f",
                "pemseq",
                "-k",
                "/Library/Keychains/System.keychain",
                "-o",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return False, f"Failed to export system keychain: {result.stderr}"

        # Try to append login keychain (may fail if locked)
        login_keychain = Path.home() / "Library/Keychains/login.keychain-db"
        if login_keychain.exists():
            try:
                result2 = subprocess.run(
                    [
                        "security",
                        "export",
                        "-t",
                        "certs",
                        "-f",
                        "pemseq",
                        "-k",
                        str(login_keychain),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result2.returncode == 0 and result2.stdout:
                    with open(output_path, "a") as f:
                        f.write(result2.stdout)
            except Exception:
                pass  # Login keychain is optional

        # Verify the export
        info = _analyze_certificate_file(output_path)
        if not info.is_valid_pem or info.cert_count == 0:
            return False, "Export produced invalid certificate file"

        return True, (
            f"Exported {info.cert_count} certificates to {output_path}\n\n"
            f"To use this CA bundle, run:\n"
            f"  export SSL_CERT_FILE={output_path}\n\n"
            f"Add this to your ~/.zshrc or ~/.bashrc to make it permanent."
        )

    except subprocess.TimeoutExpired:
        return False, "Certificate export timed out"
    except Exception as e:
        return False, f"Failed to export certificates: {e}"
