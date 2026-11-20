#!/usr/bin/env python3
"""Verify every published cost row against the historical production table."""
from hashlib import sha256
import json
from pathlib import Path
from struct import pack
from zipfile import ZipFile


MODELS = Path(__file__).resolve().parents[1] / "models"
DIRECTORY = MODELS / "top256_markov5"


def main() -> None:
    original = DIRECTORY / "markov5_meta.original.json"
    assert sha256(original.read_bytes()).hexdigest() == "d2c4c2ccbc2add02fe3d687f041944cf14ab5e80a3eba12d693a26d24e5214d0"
    alphabet = (MODELS / "top256_alphabet/alphabet_top256.json").read_bytes()
    assert sha256(alphabet).hexdigest() == "2b193a3c8d7139c575d49785c7a7a76ae79a53d506c88a51677b8df687618ca6"
    old = json.loads(original.read_bytes())
    meta = json.loads((DIRECTORY / "markov5_meta.json").read_bytes())
    for key in ("type", "symbols", "context_symbols", "observed_states", "alphabet", "fallback_costs"):
        assert meta[key] == old[key], key
    assert meta["alphabet"] == json.loads(alphabet)["alphabet"]
    assert sha256(pack("<256H", *meta["fallback_costs"])).hexdigest() == "ef98140a06554751124fa6c27b45443e8851acb28554eae2400caf723b916cad"
    index = (DIRECTORY / meta["index_file"]).read_bytes()
    assert sha256(index).hexdigest() == "764c4a58e15000b54ef9945ab667337c38a587c7c7106383d2b31636b49c67a3"
    assert len(index) == 8 * meta["observed_states"] == 8 * 2_664_834

    digest = sha256()
    with ZipFile(DIRECTORY / meta["rows_file"]) as archive:
        for start in range(0, meta["observed_states"], meta["rows_per_block"]):
            data = archive.read(f"{start // meta['rows_per_block']:05d}.bin")
            assert len(data) == 512 * min(meta["rows_per_block"], meta["observed_states"] - start)
            digest.update(data)
    assert digest.hexdigest() == meta["dense_rows_sha256"] == "2268971985cd4b2b56ab41cdb7f2d8beb4a417d8d397be532ffec801eceb4567"
    print("Markov-5: original alphabet, metadata, index and all 2,664,834 rows verified")


if __name__ == "__main__":
    main()
