# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Enhanced credential classification and type detection system.

This module provides intelligent credential analysis and classification
based on content patterns, structure, and metadata.
"""

import base64
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SSHKeyType(Enum):
    """SSH key types with their identifiers."""
    RSA = "ssh-rsa"
    DSA = "ssh-dss"
    ECDSA = "ecdsa-sha2"
    ED25519 = "ssh-ed25519"
    UNKNOWN = "unknown"


class CertificateType(Enum):
    """Certificate types and formats."""
    PEM_X509 = "pem_x509"
    DER_X509 = "der_x509"
    PKCS12 = "pkcs12"
    PEM_PRIVATE_KEY = "pem_private_key"
    OPENSSH_PRIVATE_KEY = "openssh_private_key"
    UNKNOWN = "unknown"


class CredentialStrength(Enum):
    """Credential strength assessment."""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"
    UNKNOWN = "unknown"


@dataclass
class CredentialClassification:
    """Detailed classification of a credential."""
    detected_type: str
    subtype: Optional[str] = None
    strength: CredentialStrength = CredentialStrength.UNKNOWN
    key_size: Optional[int] = None
    algorithm: Optional[str] = None
    format: Optional[str] = None
    has_passphrase: bool = False
    expires: Optional[str] = None
    issuer: Optional[str] = None
    subject: Optional[str] = None
    fingerprint: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    security_warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class CredentialClassifier:
    """Intelligent credential classification system."""

    # SSH key patterns
    SSH_KEY_PATTERNS = {
        SSHKeyType.RSA: [
            r"-----BEGIN RSA PRIVATE KEY-----",
            r"-----BEGIN OPENSSH PRIVATE KEY-----.*ssh-rsa",
            r"^ssh-rsa\s+",
        ],
        SSHKeyType.DSA: [
            r"-----BEGIN DSA PRIVATE KEY-----",
            r"^ssh-dss\s+",
        ],
        SSHKeyType.ECDSA: [
            r"-----BEGIN EC PRIVATE KEY-----",
            r"^ecdsa-sha2-",
        ],
        SSHKeyType.ED25519: [
            r"-----BEGIN OPENSSH PRIVATE KEY-----.*ssh-ed25519",
            r"^ssh-ed25519\s+",
        ],
    }

    # Certificate patterns
    CERT_PATTERNS = {
        CertificateType.PEM_X509: [
            r"-----BEGIN CERTIFICATE-----",
            r"-----BEGIN X509 CERTIFICATE-----",
        ],
        CertificateType.PEM_PRIVATE_KEY: [
            r"-----BEGIN PRIVATE KEY-----",
            r"-----BEGIN ENCRYPTED PRIVATE KEY-----",
        ],
        CertificateType.OPENSSH_PRIVATE_KEY: [
            r"-----BEGIN OPENSSH PRIVATE KEY-----",
        ],
        CertificateType.PKCS12: [
            r"-----BEGIN PKCS12-----",
        ],
    }

    # Key size patterns for RSA
    RSA_KEY_SIZE_PATTERNS = {
        1024: r"RSA.*1024.*bit",
        2048: r"RSA.*2048.*bit",
        3072: r"RSA.*3072.*bit",
        4096: r"RSA.*4096.*bit",
    }

    def classify_credential(self, credential_data: Dict[str, Any]) -> CredentialClassification:
        """Classify a credential based on its content and metadata."""
        classification = CredentialClassification(detected_type="unknown")

        # Extract the credential content for analysis
        content = self._extract_credential_content(credential_data)
        if not content:
            return classification

        # Classify based on content type
        if self._is_ssh_key(content):
            return self._classify_ssh_key(content, credential_data)
        elif self._is_certificate(content):
            return self._classify_certificate(content, credential_data)
        elif self._is_api_token(content):
            return self._classify_api_token(content, credential_data)
        elif self._is_password(content):
            return self._classify_password(content, credential_data)
        else:
            return self._classify_generic_secret(content, credential_data)

    def _extract_credential_content(self, credential_data: Dict[str, Any]) -> Optional[str]:
        """Extract the main credential content for analysis."""
        # Try different field names that might contain the credential
        content_fields = ['private_key', 'secret', 'password', 'token', 'certificate', 'key']

        for field in content_fields:
            if field in credential_data and credential_data[field]:
                return str(credential_data[field])

        return None

    def _is_ssh_key(self, content: str) -> bool:
        """Check if content is an SSH key."""
        ssh_indicators = [
            "-----BEGIN RSA PRIVATE KEY-----",
            "-----BEGIN DSA PRIVATE KEY-----",
            "-----BEGIN EC PRIVATE KEY-----",
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            "ssh-rsa",
            "ssh-dss",
            "ecdsa-sha2",
            "ssh-ed25519",
        ]
        return any(indicator in content for indicator in ssh_indicators)

    def _is_certificate(self, content: str) -> bool:
        """Check if content is a certificate."""
        cert_indicators = [
            "-----BEGIN CERTIFICATE-----",
            "-----BEGIN X509 CERTIFICATE-----",
            "-----BEGIN PRIVATE KEY-----",
            "-----BEGIN ENCRYPTED PRIVATE KEY-----",
            "-----BEGIN PKCS12-----",
        ]
        return any(indicator in content for indicator in cert_indicators)

    def _is_api_token(self, content: str) -> bool:
        """Check if content appears to be an API token."""
        # GitHub personal access tokens
        if re.match(r'^ghp_[a-zA-Z0-9]{36}$', content):
            return True
        # GitHub fine-grained tokens
        if re.match(r'^github_pat_[a-zA-Z0-9_]+$', content):
            return True
        # GitLab tokens
        if re.match(r'^glpat-[a-zA-Z0-9_-]{20}$', content):
            return True
        # Generic long alphanumeric strings that might be tokens
        if len(content) > 20 and re.match(r'^[a-zA-Z0-9_-]+$', content):
            return True

        return False

    def _is_password(self, content: str) -> bool:
        """Check if content appears to be a password."""
        # If it's not clearly another type and is reasonably short, might be a password
        return len(content) < 100 and not self._is_api_token(content)

    def _classify_ssh_key(self, content: str, credential_data: Dict[str, Any]) -> CredentialClassification:
        """Classify SSH key details."""
        classification = CredentialClassification(detected_type="ssh_private_key")

        # Determine SSH key type
        for key_type, patterns in self.SSH_KEY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.MULTILINE | re.DOTALL):
                    classification.subtype = key_type.value
                    break
            if classification.subtype:
                break

        # Check for passphrase protection
        if "ENCRYPTED" in content or "Proc-Type: 4,ENCRYPTED" in content:
            classification.has_passphrase = True
            classification.security_warnings.append("SSH key is passphrase protected")
        else:
            classification.security_warnings.append("SSH key is not passphrase protected")

        # Estimate key size for RSA keys
        if classification.subtype == SSHKeyType.RSA.value:
            classification.key_size = self._estimate_rsa_key_size(content)
            if classification.key_size:
                if classification.key_size < 2048:
                    classification.strength = CredentialStrength.WEAK
                    classification.security_warnings.append(f"RSA key size {classification.key_size} is considered weak")
                elif classification.key_size == 2048:
                    classification.strength = CredentialStrength.MODERATE
                elif classification.key_size >= 4096:
                    classification.strength = CredentialStrength.STRONG
                else:
                    classification.strength = CredentialStrength.MODERATE

        # Generate fingerprint if possible
        classification.fingerprint = self._generate_ssh_fingerprint(content)

        classification.algorithm = classification.subtype
        classification.format = "openssh" if "OPENSSH" in content else "pem"

        return classification

    def _classify_certificate(self, content: str, credential_data: Dict[str, Any]) -> CredentialClassification:
        """Classify certificate details."""
        classification = CredentialClassification(detected_type="certificate")

        # Determine certificate type
        for cert_type, patterns in self.CERT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    classification.subtype = cert_type.value
                    break
            if classification.subtype:
                break

        classification.format = "pem" if "-----BEGIN" in content else "der"

        # Try to extract certificate information
        if "-----BEGIN CERTIFICATE-----" in content:
            cert_info = self._parse_x509_certificate(content)
            classification.issuer = cert_info.get('issuer')
            classification.subject = cert_info.get('subject')
            classification.expires = cert_info.get('expires')

            # Check expiration
            if cert_info.get('is_expired'):
                classification.validation_errors.append("Certificate is expired")
            elif cert_info.get('expires_soon'):
                classification.security_warnings.append("Certificate expires within 30 days")

        return classification

    def _classify_api_token(self, content: str, credential_data: Dict[str, Any]) -> CredentialClassification:
        """Classify API token details."""
        classification = CredentialClassification(detected_type="api_token")

        # Identify token type
        if content.startswith('ghp_'):
            classification.subtype = "github_personal_access_token"
            classification.strength = CredentialStrength.STRONG
        elif content.startswith('github_pat_'):
            classification.subtype = "github_fine_grained_token"
            classification.strength = CredentialStrength.STRONG
        elif content.startswith('glpat-'):
            classification.subtype = "gitlab_personal_access_token"
            classification.strength = CredentialStrength.STRONG
        else:
            classification.subtype = "generic_token"
            classification.strength = self._assess_token_strength(content)

        classification.metadata['token_length'] = len(content)

        return classification

    def _classify_password(self, content: str, credential_data: Dict[str, Any]) -> CredentialClassification:
        """Classify password strength."""
        classification = CredentialClassification(detected_type="password")
        classification.strength = self._assess_password_strength(content)
        classification.metadata['password_length'] = len(content)

        # Password strength warnings
        if classification.strength == CredentialStrength.WEAK:
            classification.security_warnings.append("Password is weak")
        elif classification.strength == CredentialStrength.MODERATE:
            classification.security_warnings.append("Password strength is moderate")

        return classification

    def _classify_generic_secret(self, content: str, credential_data: Dict[str, Any]) -> CredentialClassification:
        """Classify generic secret content."""
        classification = CredentialClassification(detected_type="secret_text")
        classification.metadata['content_length'] = len(content)
        classification.metadata['content_type'] = 'binary' if self._is_binary_content(content) else 'text'

        return classification

    def _estimate_rsa_key_size(self, content: str) -> Optional[int]:
        """Estimate RSA key size from content."""
        # Try to extract key size from OpenSSH format comments
        for size, pattern in self.RSA_KEY_SIZE_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                return size

        # Estimate from key length (rough approximation)
        key_lines = [line for line in content.split('\n')
                    if line and not line.startswith('-----')]
        if key_lines:
            total_key_length = sum(len(line) for line in key_lines)
            # Rough estimation based on base64 encoded key length
            if total_key_length < 800:
                return 1024
            elif total_key_length < 1600:
                return 2048
            elif total_key_length < 2400:
                return 3072
            else:
                return 4096

        return None

    def _generate_ssh_fingerprint(self, content: str) -> Optional[str]:
        """Generate SSH key fingerprint."""
        # This is a simplified version - real implementation would use cryptographic libraries
        try:
            import hashlib
            # Extract just the key portion (without headers/footers)
            key_lines = [line.strip() for line in content.split('\n')
                        if line.strip() and not line.startswith('-----') and not line.startswith('Comment:')]
            if key_lines:
                key_data = ''.join(key_lines)
                hash_obj = hashlib.md5(key_data.encode())
                fingerprint = hash_obj.hexdigest()
                # Format as typical SSH fingerprint
                return ':'.join(fingerprint[i:i+2] for i in range(0, len(fingerprint), 2))
        except Exception as e:
            logger.debug(f"Could not generate SSH fingerprint: {e}")

        return None

    def _parse_x509_certificate(self, content: str) -> Dict[str, Any]:
        """Parse X.509 certificate information."""
        # This is a placeholder - real implementation would use cryptographic libraries
        # like cryptography or OpenSSL
        cert_info = {}

        try:
            # Extract basic information that might be visible in PEM format
            if "Subject:" in content:
                subject_match = re.search(r'Subject:(.+)', content)
                if subject_match:
                    cert_info['subject'] = subject_match.group(1).strip()

            if "Issuer:" in content:
                issuer_match = re.search(r'Issuer:(.+)', content)
                if issuer_match:
                    cert_info['issuer'] = issuer_match.group(1).strip()

        except Exception as e:
            logger.debug(f"Could not parse certificate: {e}")

        return cert_info

    def _assess_password_strength(self, password: str) -> CredentialStrength:
        """Assess password strength."""
        score = 0

        # Length
        if len(password) >= 12:
            score += 2
        elif len(password) >= 8:
            score += 1

        # Character variety
        if re.search(r'[a-z]', password):
            score += 1
        if re.search(r'[A-Z]', password):
            score += 1
        if re.search(r'[0-9]', password):
            score += 1
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1

        # Common patterns (negative scoring)
        if re.search(r'(123|abc|password|admin)', password, re.IGNORECASE):
            score -= 2

        if score >= 5:
            return CredentialStrength.STRONG
        elif score >= 3:
            return CredentialStrength.MODERATE
        else:
            return CredentialStrength.WEAK

    def _assess_token_strength(self, token: str) -> CredentialStrength:
        """Assess API token strength."""
        if len(token) >= 40:
            return CredentialStrength.STRONG
        elif len(token) >= 20:
            return CredentialStrength.MODERATE
        else:
            return CredentialStrength.WEAK

    def _is_binary_content(self, content: str) -> bool:
        """Check if content appears to be binary."""
        try:
            content.encode('utf-8')
            # Check for non-printable characters
            return any(ord(char) < 32 or ord(char) > 126 for char in content if char not in '\n\r\t')
        except UnicodeEncodeError:
            return True


def classify_credential(credential_data: Dict[str, Any]) -> CredentialClassification:
    """Convenience function to classify a credential."""
    classifier = CredentialClassifier()
    return classifier.classify_credential(credential_data)
