"""Address service and client for the separately pinned Qwen3.5 4B edition."""
import argparse
import os

import qwen_reference as reference

EDITION = "babel-qwen35-ref-v1"
MODEL_SHA256 = "a9d0a3e1d8c91732a3812becd31f8d4a8ff57414903f226306069f0437e2ac50"
ADDRESS_ENDPOINT = "http://127.0.0.1:18872"


class Qwen35Client(reference.ReferenceClient):
    def __init__(self, endpoint=None):
        address = endpoint or os.getenv("BABEL_QWEN35_ENDPOINT", ADDRESS_ENDPOINT)
        self.request = reference.transport(address, 3600)

    def _call(self, path, payload=None):
        result = self.request(path, payload)
        if result.get("edition") != EDITION:
            raise reference.ReferenceUnavailable("Ответ относится к другому изданию библиотеки.")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--endpoint", default=reference.MODEL_ENDPOINT)
    args = parser.parse_args()
    # This process owns one isolated model. The original edition remains unchanged.
    reference.EDITION = EDITION
    reference.text.GGUF_SHA256 = MODEL_SHA256
    reference.serve(args.host, args.port, args.endpoint)
