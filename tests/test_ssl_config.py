"""Tests for SSL configuration and diagnostics utilities."""

from unittest.mock import MagicMock, patch

import pytest

from anvil.services.ssl_config import (
    CertificateInfo,
    SSLDiagnostics,
    _analyze_certificate_file,
    diagnose_ssl_issues,
    export_macos_certificates,
    format_ssl_error_message,
    get_ssl_verify,
)

# Sample PEM certificate for testing (self-signed, not real)
SAMPLE_PEM_CERT = """-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKHBfpegPjMCMA0GCSqGSIb3DQEBCwUAMBExDzANBgNVBAMMBnRl
c3RjYTAeFw0yNDAxMDEwMDAwMDBaFw0yNTAxMDEwMDAwMDBaMBExDzANBgNVBAMM
BnRlc3RjYTBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQC5284rts+FhLpUCQFXJT6F
xI0GD9qNBaH2C8MHk0VDR5NQdGKIgDEHWQdXKRMsNLUbKw6nXkPUX8H0HBV5f8hX
AgMBAAGjUzBRMB0GA1UdDgQWBBTGZpPOl6GRaKCEU87AxuMAOQJiijAfBgNVHSME
GDAWgBTGZpPOl6GRaKCEU87AxuMAOQJiijAPBgNVHRMBAf8EBTADAQH/MA0GCSqG
SIb3DQEBCwUAA0EAuG0PsHzCgeFbzWXiehHLCpsZ97PbMPvzJTNNi5zzNvNVLjSP
DZpk9ztMNm3kE3H0IWKhK9HqYmR8Y0TlBCH3Pg==
-----END CERTIFICATE-----
"""


class TestGetSSLVerify:
    """Tests for get_ssl_verify function."""

    def setup_method(self):
        """Clear the cache before each test."""
        get_ssl_verify.cache_clear()

    def teardown_method(self):
        """Clean up environment after each test."""
        get_ssl_verify.cache_clear()

    def test_returns_true_by_default(self, monkeypatch):
        """Test that default returns True for standard SSL verification."""
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

        result = get_ssl_verify()
        assert result is True

    def test_returns_false_when_disabled(self, monkeypatch):
        """Test that SSL verification can be disabled."""
        monkeypatch.setenv("ANVIL_SSL_VERIFY", "false")
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

        with pytest.warns(UserWarning, match="SSL verification is disabled"):
            result = get_ssl_verify()
        assert result is False

    def test_returns_false_for_various_disable_values(self, monkeypatch):
        """Test various ways to disable SSL verification."""
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

        for value in ["false", "0", "no", "off", "FALSE", "NO"]:
            get_ssl_verify.cache_clear()
            monkeypatch.setenv("ANVIL_SSL_VERIFY", value)
            with pytest.warns(UserWarning):
                result = get_ssl_verify()
            assert result is False, f"Expected False for ANVIL_SSL_VERIFY={value}"

    def test_returns_ca_bundle_path_when_set(self, monkeypatch, tmp_path):
        """Test that SSL_CERT_FILE path is returned when file exists."""
        ca_file = tmp_path / "ca-bundle.crt"
        ca_file.write_text(SAMPLE_PEM_CERT)

        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)
        monkeypatch.setenv("SSL_CERT_FILE", str(ca_file))
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

        result = get_ssl_verify()
        assert result == str(ca_file)

    def test_returns_requests_ca_bundle_when_set(self, monkeypatch, tmp_path):
        """Test that REQUESTS_CA_BUNDLE is used as fallback."""
        ca_file = tmp_path / "ca-bundle.crt"
        ca_file.write_text(SAMPLE_PEM_CERT)

        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(ca_file))

        result = get_ssl_verify()
        assert result == str(ca_file)

    def test_ignores_nonexistent_ca_bundle(self, monkeypatch):
        """Test that nonexistent CA bundle paths are ignored."""
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)
        monkeypatch.setenv("SSL_CERT_FILE", "/nonexistent/path/ca-bundle.crt")
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

        result = get_ssl_verify()
        assert result is True  # Falls back to default


class TestAnalyzeCertificateFile:
    """Tests for certificate file analysis."""

    def test_detects_nonexistent_file(self):
        """Test handling of nonexistent file."""
        info = _analyze_certificate_file("/nonexistent/path/cert.pem")
        assert info.exists is False
        assert "does not exist" in info.error

    def test_detects_valid_pem(self, tmp_path):
        """Test detection of valid PEM certificate."""
        cert_file = tmp_path / "cert.pem"
        cert_file.write_text(SAMPLE_PEM_CERT)

        info = _analyze_certificate_file(str(cert_file))
        assert info.exists is True
        assert info.readable is True
        assert info.is_valid_pem is True
        assert info.cert_count == 1
        assert info.error is None

    def test_detects_multiple_certs(self, tmp_path):
        """Test detection of multiple certificates in bundle."""
        cert_file = tmp_path / "bundle.pem"
        cert_file.write_text(SAMPLE_PEM_CERT + "\n" + SAMPLE_PEM_CERT)

        info = _analyze_certificate_file(str(cert_file))
        assert info.cert_count == 2

    def test_detects_invalid_pem(self, tmp_path):
        """Test detection of invalid PEM format."""
        cert_file = tmp_path / "invalid.pem"
        cert_file.write_text("This is not a certificate")

        info = _analyze_certificate_file(str(cert_file))
        assert info.exists is True
        assert info.readable is True
        assert info.is_valid_pem is False
        assert "does not contain any PEM certificates" in info.error

    def test_detects_malformed_pem(self, tmp_path):
        """Test detection of malformed PEM (mismatched markers)."""
        cert_file = tmp_path / "malformed.pem"
        cert_file.write_text("-----BEGIN CERTIFICATE-----\ndata\n")

        info = _analyze_certificate_file(str(cert_file))
        assert info.is_valid_pem is False
        assert "Malformed PEM" in info.error


class TestDiagnoseSSLIssues:
    """Tests for SSL diagnostics function."""

    def test_returns_diagnostics_object(self, monkeypatch):
        """Test that diagnostics returns proper object."""
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)

        diag = diagnose_ssl_issues()
        assert isinstance(diag, SSLDiagnostics)
        assert diag.test_host == "management.azure.com"
        assert isinstance(diag.issues, list)
        assert isinstance(diag.recommendations, list)

    def test_detects_missing_ca_bundle(self, monkeypatch):
        """Test detection of missing CA bundle configuration."""
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)

        diag = diagnose_ssl_issues()
        assert any("No custom CA bundle" in issue for issue in diag.issues)

    def test_detects_nonexistent_ca_file(self, monkeypatch):
        """Test detection of configured but nonexistent CA file."""
        monkeypatch.setenv("SSL_CERT_FILE", "/nonexistent/ca-bundle.pem")
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)

        diag = diagnose_ssl_issues()
        assert diag.cert_file_info is not None
        assert diag.cert_file_info.exists is False
        assert any("does not exist" in issue for issue in diag.issues)

    def test_analyzes_valid_ca_file(self, monkeypatch, tmp_path):
        """Test analysis of valid CA file."""
        ca_file = tmp_path / "ca-bundle.pem"
        ca_file.write_text(SAMPLE_PEM_CERT)

        monkeypatch.setenv("SSL_CERT_FILE", str(ca_file))
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)

        diag = diagnose_ssl_issues()
        assert diag.cert_file_info is not None
        assert diag.cert_file_info.is_valid_pem is True

    def test_detects_system_info(self, monkeypatch):
        """Test that system info is populated."""
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)

        diag = diagnose_ssl_issues()
        assert diag.system in ("Darwin", "Linux", "Windows")

    @patch("anvil.services.ssl_config.shutil.which")
    def test_handles_missing_openssl(self, mock_which, monkeypatch):
        """Test handling when openssl is not available."""
        mock_which.return_value = None
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)

        diag = diagnose_ssl_issues()
        assert diag.openssl_available is False


class TestFormatSSLErrorMessage:
    """Tests for SSL error message formatting."""

    def test_returns_original_for_non_ssl_error(self):
        """Test that non-SSL errors are returned as-is."""
        error = Exception("Connection refused")
        result = format_ssl_error_message(error)
        assert result == "Connection refused"

    def test_detects_ssl_keywords(self):
        """Test detection of various SSL-related error keywords."""
        ssl_errors = [
            "SSL: CERTIFICATE_VERIFY_FAILED",
            "certificate verify failed",
            "unable to get local issuer certificate",
            "self signed certificate in certificate chain",
            "SSL handshake failed",
        ]

        for error_msg in ssl_errors:
            error = Exception(error_msg)
            result = format_ssl_error_message(error)
            assert "SSL DIAGNOSTICS" in result, f"Should detect SSL error: {error_msg}"

    def test_includes_environment_variables(self, monkeypatch):
        """Test that error message includes env var status."""
        monkeypatch.setenv("SSL_CERT_FILE", "/test/path.pem")
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)

        error = Exception("SSL certificate verify failed")
        result = format_ssl_error_message(error)

        assert "SSL_CERT_FILE:" in result
        assert "/test/path.pem" in result

    def test_includes_recommendations(self, monkeypatch):
        """Test that error message includes recommendations."""
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)

        error = Exception("SSL certificate verify failed")
        result = format_ssl_error_message(error)

        assert "RECOMMENDATIONS" in result

    def test_includes_last_resort_option(self, monkeypatch):
        """Test that error message includes ANVIL_SSL_VERIFY option."""
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("ANVIL_SSL_VERIFY", raising=False)

        error = Exception("SSL certificate verify failed")
        result = format_ssl_error_message(error)

        assert "ANVIL_SSL_VERIFY=false" in result


class TestExportMacOSCertificates:
    """Tests for macOS certificate export function."""

    @patch("anvil.services.ssl_config.platform.system")
    def test_fails_on_non_macos(self, mock_system):
        """Test that function fails on non-macOS systems."""
        mock_system.return_value = "Linux"
        success, message = export_macos_certificates()
        assert success is False
        assert "only available on macOS" in message

    @patch("anvil.services.ssl_config.platform.system")
    @patch("anvil.services.ssl_config.shutil.which")
    def test_fails_without_security_command(self, mock_which, mock_system):
        """Test that function fails without security command."""
        mock_system.return_value = "Darwin"
        mock_which.return_value = None
        success, message = export_macos_certificates()
        assert success is False
        assert "security command not found" in message

    @patch("anvil.services.ssl_config.platform.system")
    @patch("anvil.services.ssl_config.shutil.which")
    @patch("anvil.services.ssl_config.subprocess.run")
    def test_exports_certificates_successfully(self, mock_run, mock_which, mock_system, tmp_path):
        """Test successful certificate export."""
        mock_system.return_value = "Darwin"
        mock_which.return_value = "/usr/bin/security"

        output_path = tmp_path / "exported.pem"

        # Mock successful export - write actual content to the file
        def run_side_effect(cmd, **kwargs):
            if "-o" in cmd:
                # Write certificate content to the output file
                output_path.write_text(SAMPLE_PEM_CERT)
            result = MagicMock()
            result.returncode = 0
            result.stdout = SAMPLE_PEM_CERT
            result.stderr = ""
            return result

        mock_run.side_effect = run_side_effect

        success, message = export_macos_certificates(str(output_path))
        assert success is True
        assert "Exported" in message
        assert str(output_path) in message


class TestCertificateInfoDataclass:
    """Tests for CertificateInfo dataclass."""

    def test_default_values(self):
        """Test default values for CertificateInfo."""
        info = CertificateInfo(path="/test/path")
        assert info.path == "/test/path"
        assert info.exists is False
        assert info.readable is False
        assert info.is_valid_pem is False
        assert info.cert_count == 0
        assert info.error is None
        assert info.subjects == []


class TestSSLDiagnosticsDataclass:
    """Tests for SSLDiagnostics dataclass."""

    def test_default_values(self):
        """Test default values for SSLDiagnostics."""
        diag = SSLDiagnostics()
        assert diag.ssl_cert_file is None
        assert diag.requests_ca_bundle is None
        assert diag.anvil_ssl_verify is None
        assert diag.test_host == "management.azure.com"
        assert diag.connection_successful is False
        assert diag.openssl_available is False
        assert diag.issues == []
        assert diag.recommendations == []
        assert diag.can_auto_fix is False
