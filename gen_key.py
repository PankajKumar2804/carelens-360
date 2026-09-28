import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# Generate private key
key = rsa.generate_private_key(backend=default_backend(), public_exponent=65537, key_size=2048)
private_key = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
public_key = key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# Save to .snowflake directory
base_dir = r"C:\Users\panka\.snowflake"
priv_path = os.path.join(base_dir, "rsa_key.p8")
with open(priv_path, "wb") as f:
    f.write(private_key)

# Format the public key for the SQL command (strip headers and newlines)
pub_lines = public_key.decode('utf-8').split('\n')
pub_base64 = "".join(pub_lines[1:-2]) # Strip BEGIN/END and empty lines

print(f"\n--- SUCCESS: KEYPAIR GENERATED ---\n")
print(f"Private Key saved to: {priv_path}")
print(f"\nSQL COMMAND TO RUN IN SNOWFLAKE UI:\n")
print(f"ALTER USER PANKAJKR SET RSA_PUBLIC_KEY='{pub_base64}';")
