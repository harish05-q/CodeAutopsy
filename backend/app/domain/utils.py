import time
import secrets

ENCODING = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

def encode_time(millis: int, length: int = 10) -> str:
    chars = []
    for _ in range(length):
        millis, remainder = divmod(millis, 32)
        chars.append(ENCODING[remainder])
    return "".join(reversed(chars))

def encode_random(length: int = 16) -> str:
    return "".join(secrets.choice(ENCODING) for _ in range(length))

def generate_ulid() -> str:
    """Generate a standard 26-character Base32 ULID string."""
    millis = int(time.time() * 1000)
    return encode_time(millis) + encode_random()
