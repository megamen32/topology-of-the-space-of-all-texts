"""Look up a five-symbol context in the original or the packaged Markov tables."""
from __future__ import annotations

from functools import lru_cache
import mmap
from pathlib import Path
from struct import Struct
from zipfile import ZipFile


STATE = Struct("<Q")
ROW = Struct("<256H")
ZIP_FORMAT = "zip-deflate-blocks-v1"


def model_file(directory: Path, name: str) -> Path:
    path = Path(name)
    if not path.is_absolute():
        return directory / path
    # Some historical manifests contain the training host's absolute paths.
    local = directory / path.name
    return local if local.is_file() else path


class Markov5Rows:
    def __init__(self, directory: Path, metadata: dict):
        index_path = model_file(directory, metadata["index_file"])
        rows_path = model_file(directory, metadata["rows_file"])
        self.index = index_path.read_bytes()
        self.state_count = int(metadata["observed_states"])
        if len(self.index) != self.state_count * STATE.size:
            raise ValueError("Markov-5 index length differs from the declared state count")
        self.size = len(self.index) + rows_path.stat().st_size

        row_format = metadata.get("rows_format", "dense-u16le")
        self.archive = None
        if row_format == ZIP_FORMAT:
            self.block_rows = int(metadata["rows_per_block"])
            if self.block_rows < 1:
                raise ValueError("a Markov-5 block must contain at least one row")
            self.archive = ZipFile(rows_path)
            self.read_block = lru_cache(maxsize=32)(self.archive.read)
        elif row_format == "dense-u16le":
            if rows_path.stat().st_size != self.state_count * ROW.size:
                raise ValueError("Markov-5 cost table length differs from the index")
            with rows_path.open("rb") as source:
                self.dense = mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ)
        else:
            raise ValueError(f"unknown Markov-5 row format {row_format!r}")

    def get(self, state: int, fallback):
        low, high = 0, self.state_count
        while low < high:
            middle = (low + high) // 2
            candidate = STATE.unpack_from(self.index, middle * STATE.size)[0]
            if candidate < state:
                low = middle + 1
            else:
                high = middle
        if low == self.state_count or STATE.unpack_from(self.index, low * STATE.size)[0] != state:
            return fallback
        if self.archive is None:
            return ROW.unpack_from(self.dense, low * ROW.size)
        block, row = divmod(low, self.block_rows)
        return ROW.unpack_from(self.read_block(f"{block:05d}.bin"), row * ROW.size)
