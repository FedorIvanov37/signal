from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from datetime import datetime, timedelta


key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

subject = issuer = x509.Name(
    [
        x509.NameAttribute(NameOID.COMMON_NAME, "CY"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Limassol"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Limassol"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Fedor Ivanov"),
        # x509.NameAttribute(NameOID.COMMON_NAME, "192.168.0.3"),

    ]
)

cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.utcnow()
).not_valid_after(
    datetime.utcnow() + timedelta(days=365)
).add_extension(
    x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
).sign(key, hashes.SHA256(), default_backend())

with open("private_key.pem", "wb") as private_key_file:
    private_key_file.write(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
    )

with open("certificate.pem", "wb") as ssl_cert_file:
    ssl_cert_file.write(cert.public_bytes(serialization.Encoding.PEM))





