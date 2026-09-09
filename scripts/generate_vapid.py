import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def main():
    v = Vapid()
    v.generate_keys()

    priv_raw = v.private_key.private_numbers().private_value.to_bytes(32, "big")
    pub_raw = v.public_key.public_bytes(
        encoding=serialization.Encoding.X962, format=serialization.PublicFormat.UncompressedPoint
    )

    print("Quyidagi qatorlarni .env fayliga qo'shing:\n")
    print(f"VAPID_PUBLIC_KEY={_b64url(pub_raw)}")
    print(f"VAPID_PRIVATE_KEY={_b64url(priv_raw)}")
    print("VAPID_SUBJECT=mailto:admin@example.com")


if __name__ == "__main__":
    main()
