import os
import ssl

from skyvern.config import settings

if settings.TIKTOKEN_ALLOW_INSECURE_SSL:
    # Opt-in escape hatch for environments without proper CA certificates: disable TLS
    # verification before tiktoken downloads its BPE file. Off by default — enabling this
    # weakens TLS for the whole process, so only use it as a last resort.
    os.environ["CURL_CA_BUNDLE"] = ""
    os.environ["REQUESTS_CA_BUNDLE"] = ""
    ssl._create_default_https_context = ssl._create_unverified_context

import tiktoken  # noqa: E402  (imported after the optional SSL setup above)

_ENCODING = tiktoken.encoding_for_model("gpt-4o")


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def encode_tokens(text: str) -> list[int]:
    return _ENCODING.encode(text)


def decode_tokens(tokens: list[int]) -> str:
    return _ENCODING.decode(tokens)
