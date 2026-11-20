#!/usr/bin/env bash
set -euo pipefail
umask 022
here=$(cd -- "$(dirname -- "$0")" && pwd)
repo=$(cd -- "$here/../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
ctx="$work/context"
mkdir -p "$ctx"/{runtime/backends,licenses,models,experiments}

fetch() {
    curl --fail --location --silent --show-error --retry 4 --retry-all-errors \
        --connect-timeout 20 --output "$2" "$1"
}

# SHA-256, name in the official amd64 release, installed name (the ELF SONAME where needed).
cat > "$work/runtime.lock" <<'LOCK'
dbfeea380cdc1de9bbfe32399befbcd8381a3c5ac83e573d79d0fa41bdc40037 llama-server llama-server
ad64929e139fd7054ec649d02633fea41e72c6c7ec04d621d0dbe3f8efc16ec2 libllama-server-impl.so libllama-server-impl.so
88cda65aa5f78dd621b0c468659a436d73722e0094772977679f6f81d2d52729 libllama-common.so.0.0.1 libllama-common.so.0
1b7e94d1c4661671d82cd4a8a40d1734d93b333e1e337e262f9a1ac223fecd5b libllama.so.0.0.1 libllama.so.0
3c8ccb5bd3826df3558499db744911195ae6a437f2d4194da228d811008b0ea4 libmtmd.so.0.0.1 libmtmd.so.0
40e1f9070eee43ad95a8f3151b691368ac64db9f826fc5796d5ba84836a1305f libggml.so.0.15.3 libggml.so.0
3b5e61bbb1e0c0d2b0ca001b7014d6f572367b312f24defb43f0869694ff3249 libggml-base.so.0.15.3 libggml-base.so.0
46286721d8ff20a6f9efcdea0a58a0ab443b0ed8df54f5004965990975282659 libggml-cpu-haswell.so backends/libggml-cpu-haswell.so
LOCK

if [[ -n ${BABEL_OLLAMA_LIB:-} ]]; then
    lib=$BABEL_OLLAMA_LIB
else
    archive="$work/ollama-linux-amd64.tar.zst"
    fetch "https://github.com/ollama/ollama/releases/download/v0.32.1/ollama-linux-amd64.tar.zst" "$archive"
    printf '%s  %s\n' 83b1f22841eb7f6c4900c6797f960ebaa09466874442ea5b8ae3da6980d3914c "$archive" | sha256sum --check --strict
    mapfile -t members < <(awk '{print "lib/ollama/" $2}' "$work/runtime.lock")
    tar --zstd -xf "$archive" -C "$work" -- "${members[@]}"
    lib="$work/lib/ollama"
fi

while read -r hash src dest; do
    install -m 0644 "$lib/$src" "$ctx/runtime/$dest"
    printf '%s  runtime/%s\n' "$hash" "$dest" >> "$ctx/SHA256SUMS"
done < "$work/runtime.lock"
chmod 0755 "$ctx/runtime/llama-server"

model=3d0b790534fe4b79525fc3692950408dca41171676ed7e21db57af5c65ef6ab6
registry=https://registry.ollama.ai/v2/library/qwen3/blobs
gguf="$ctx/models/qwen3-1.7b.gguf"
if [[ -n ${BABEL_QWEN_GGUF:-} ]]; then
    cp --reflink=auto -- "$BABEL_QWEN_GGUF" "$gguf"
else
    fetch "$registry/sha256:$model" "$gguf"
fi
chmod 0644 "$gguf"
printf '%s  models/qwen3-1.7b.gguf\n' "$model" >> "$ctx/SHA256SUMS"

cat > "$work/edition.lock" <<'LOCK'
737d7c1fc25fc5e67bfac4df68ee05517a13f7afa05ddaa07796124e648d4bd8  experiments/generative_coupling.py
ea720e6448144eaec8778a17ccc485290e2287289faef716679ce46a8f3467f4  experiments/ollama_continuation_v3.py
6fc319021feea8bc3993414121cc1e7a5817e2af1876759bd76ef9bef0d8dc72  experiments/ollama_generative_address.py
39793e7229807c33eaf7dc02323fcbc0ed20cb5a09a0beeb581559600ccda020  experiments/qwen_reference.py
2b193a3c8d7139c575d49785c7a7a76ae79a53d506c88a51677b8df687618ca6  models/top256_alphabet/alphabet_top256.json
LOCK
while read -r hash path; do
    install -D -m 0644 "$repo/$path" "$ctx/$path"
done < "$work/edition.lock"
cat "$work/edition.lock" >> "$ctx/SHA256SUMS"

raw=https://raw.githubusercontent.com
fetch "$raw/ollama/ollama/30c390384e20333b67cadab60da5bcb669407f01/LICENSE" "$ctx/licenses/Ollama"
fetch "$raw/ggml-org/llama.cpp/cb295bf59663cd3577389315636772f4060bd1f5/LICENSE" "$ctx/licenses/llama.cpp"
fetch "$registry/sha256:d18a5cc71b84bc4af394a31116bd3932b42241de70c77d2b76d69a314ec8aa12" "$ctx/licenses/Qwen3"
cat >> "$ctx/SHA256SUMS" <<'LOCK'
5934ed2ce0d15154bcdb9c85203210abac0da4314af34081e36df4599f90b226  licenses/Ollama
94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d  licenses/llama.cpp
d18a5cc71b84bc4af394a31116bd3932b42241de70c77d2b76d69a314ec8aa12  licenses/Qwen3
b803a85bd3f0cc66a67fc234c568d720cd3e669468b6d8e82370e53f3c09c3dc  serve.sh
LOCK
install -m 0644 "$here/Dockerfile" "$here/serve.sh" "$ctx/"
cd "$ctx"
sha256sum --check --strict SHA256SUMS
find . -exec touch -h -d @0 {} +
docker buildx build --builder default --platform linux/amd64 --load --provenance=false \
    --build-arg SOURCE_DATE_EPOCH=0 --tag babel-qwen-reference:v1 .
