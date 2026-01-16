import ssl
import os

# Disable SSL verification for tiktoken BPE file download
# This is needed in Docker environments without proper CA certificates
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""

# Create unverified SSL context
ssl._create_default_https_context = ssl._create_unverified_context

import tiktoken


def count_tokens(text: str) -> int:
    return len(tiktoken.encoding_for_model("gpt-4o").encode(text))
