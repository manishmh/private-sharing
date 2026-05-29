"""Short, nanoid-style base62 token generation (6 chars, NOT UUIDs)."""
import secrets

_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
TOKEN_LENGTH = 6


def generate_token(length: int = TOKEN_LENGTH) -> str:
    """Cryptographically-random base62 token, e.g. 'Ab3xK9'."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def is_valid_token(value: str) -> bool:
    return (
        len(value) == TOKEN_LENGTH
        and all(c in _ALPHABET for c in value)
    )
