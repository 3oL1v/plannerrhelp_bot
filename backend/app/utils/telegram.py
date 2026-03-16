from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_value = data.pop("hash", None)
    if not hash_value:
        return None

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, hash_value):
        return None

    user_blob = data.get("user")
    if not user_blob:
        return None
    return json.loads(user_blob)
