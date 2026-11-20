#!/usr/bin/env python3
"""Smoke tests for the fixed-length Babel-1 API contract."""
from __future__ import annotations

from hashlib import sha256
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import backend_app


def post(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def main() -> None:
    client = backend_app.app.test_client()
    catalogue = post(client, "/api/unrank", {"mode": "hierarchical_catalogue_v1", "rank": "0"})
    assert catalogue["edition"] == "Ранний читаемый каталог"
    assert catalogue["page_kind"] == "structured_catalogue"
    assert catalogue["structured_pages"] >= 20
    assert "михаил лермонтов" in catalogue["page"]
    assert post(client, "/api/rank", {
        "mode": "hierarchical_catalogue_v1", "text": catalogue["page"],
    })["rank"] == "0"

    fallback = post(client, "/api/unrank", {
        "mode": "hierarchical_catalogue_v1", "rank": str(catalogue["structured_pages"]),
    })
    assert fallback["page_kind"] == "raw_fallback"
    assert post(client, "/api/rank", {
        "mode": "hierarchical_catalogue_v1", "text": fallback["page"],
    })["rank"] == fallback["rank"]

    for text in ("", "hello", "привет, библиотека"):
        ranked = post(client, "/api/rank", {"mode": "babel_1_shell", "text": text})
        assert ranked["mode"] == "babel_1_shell"
        assert ranked["edition"] == "Babel-1"
        assert ranked["length"] == 4096
        assert len(ranked["page"]) == 4096
        opened = post(client, "/api/unrank", {"mode": "babel_1_shell", "rank": ranked["rank"]})
        assert opened["page"] == ranked["page"]

    ranker = backend_app.babel_1_ranker()
    # UTF-8 hashes from the original dense-table edition on the production host.
    # A different language model could still pass every round-trip assertion.
    published_pages = {
        0: "61aecfcd4b6bffdda645c66e91e363ef446ddb718a41b44e1d91cb574eae7c82",
        1: "ffa7e538d37cf7f4f063fda21f2aa021ad44ad5ad1cc75feadff9508f74ffef1",
        2: "9486ce6805e3a8aae037c11b7101ea8fe44fcf7007b837abb0c74dfbdef82b2d",
        15: "625e296321be9b72769060d49d13f17e8a6aad9acd2277e2a9a360715847787f",
        16: "cde290e0e3a983be53fcca0802cb26776bd12decb649800049fe6e12d7bd96fe",
        255: "ec1913c5af3176147939b5b3878e7b8efdc921fb0be32de2171fa0debcba6d98",
        256: "aa0c228d55f4599d70647b988701a10177bb55c4cf173f2d94c916e4ff6d8bfe",
        ranker.space_size // 2: "e5d1e35ba9b19a21017db9876c8018db6901d8386dee28e148dc01a405179ded",
        ranker.space_size - 1: "af669a6092f79d829535d1e015ad12b0ecaab659f759fe6be11545abc4ae12fe",
    }
    for rank, expected_hash in published_pages.items():
        opened = post(client, "/api/unrank", {"mode": "babel_1_shell", "rank": str(rank)})
        assert sha256(opened["page"].encode("utf-8")).hexdigest() == expected_hash, rank
        ranked = post(client, "/api/rank", {"mode": "babel_1_shell", "text": opened["page"]})
        assert ranked["rank"] == str(rank)

    route = post(client, "/api/babel-1-route", {"index": 0})
    assert route["route"] == "russian_public_domain_v1"
    assert route["author"] == "Александр Пушкин"
    assert route["source_text"].startswith("Мороз и солнце")
    assert len(route["page"]) == 4096
    assert post(client, "/api/rank", {"mode": "babel_1_shell", "text": route["page"]})["rank"] == route["rank"]

    print("Babel-1 API smoke tests passed")


if __name__ == "__main__":
    main()
