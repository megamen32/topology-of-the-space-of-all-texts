#!/usr/bin/env python3
"""Smoke tests for the fixed-length Babel-1 API contract."""
from __future__ import annotations

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
    for text in ("", "hello", "привет, библиотека"):
        ranked = post(client, "/api/rank", {"mode": "babel_1_shell", "text": text})
        assert ranked["mode"] == "babel_1_shell"
        assert ranked["edition"] == "Babel-1"
        assert ranked["length"] == 4096
        assert len(ranked["page"]) == 4096
        opened = post(client, "/api/unrank", {"mode": "babel_1_shell", "rank": ranked["rank"]})
        assert opened["page"] == ranked["page"]

    ranker = backend_app.babel_1_ranker()
    for rank in (0, 1, ranker.space_size - 1):
        opened = post(client, "/api/unrank", {"mode": "babel_1_shell", "rank": str(rank)})
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
