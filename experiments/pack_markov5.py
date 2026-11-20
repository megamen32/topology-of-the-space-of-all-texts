"""Package dense historical Markov-5 tables for random access from a Git clone."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

if __package__:
    from .markov5_storage import model_file, ROW, STATE, ZIP_FORMAT
else:
    from markov5_storage import model_file, ROW, STATE, ZIP_FORMAT


def pack(manifest: Path, destination: Path) -> None:
    source = json.loads(manifest.read_text(encoding="utf-8"))
    if source.get("rows_format", "dense-u16le") != "dense-u16le" or source["context_symbols"] != 5:
        raise ValueError("expected a dense five-symbol Markov model")
    index = model_file(manifest.parent, source["index_file"])
    rows = model_file(manifest.parent, source["rows_file"])
    count = source["observed_states"]
    if index.stat().st_size != count * STATE.size or rows.stat().st_size != count * ROW.size:
        raise ValueError("dense table dimensions do not match the manifest")
    if destination.exists():
        raise FileExistsError(f"choose a new output directory: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as temporary:
        build = Path(temporary) / "model"
        build.mkdir()
        shutil.copyfile(manifest, build / "markov5_meta.original.json")
        index_copy = build / "markov5_index_u64.bin"
        shutil.copyfile(index, index_copy)
        archive = build / "markov5_rows.zip"
        rows_per_block = 256
        row_hash = sha256()
        with rows.open("rb") as table, ZipFile(archive, "w") as output:
            for block in range((count + rows_per_block - 1) // rows_per_block):
                data = table.read(rows_per_block * ROW.size)
                row_hash.update(data)
                # ZipInfo supplies a fixed timestamp for reproducible archives.
                member = ZipInfo(f"{block:05d}.bin")
                output.writestr(member, data, compress_type=ZIP_DEFLATED, compresslevel=6)

        result = {key: value for key, value in source.items()
                  if key not in ("created_at", "index_file", "rows_file")}
        result.update(
            index_file=index_copy.name, rows_file=archive.name, rows_format=ZIP_FORMAT,
            rows_per_block=rows_per_block, index_sha256=sha256(index_copy.read_bytes()).hexdigest(),
            dense_rows_sha256=row_hash.hexdigest(),
        )
        (build / "markov5_meta.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        build.rename(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="the original markov5_meta.json")
    parser.add_argument("destination", type=Path, help="new directory for the Git-sized model")
    arguments = parser.parse_args()
    pack(arguments.manifest, arguments.destination)
