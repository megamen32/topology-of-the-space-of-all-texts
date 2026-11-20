FROM docker.io/library/python:3.12.16-slim-bookworm@sha256:0f086103b026048cc50cb5da25ec435c023c5241a83fc44daea593377abc61c4

LABEL org.opencontainers.image.title="Babel Qwen3.5 reference v1" \
      org.opencontainers.image.base.digest="sha256:0f086103b026048cc50cb5da25ec435c023c5241a83fc44daea593377abc61c4" \
      babel.llama.release="ollama 0.32.1 / llama.cpp b9888 (cb295bf59663cd3577389315636772f4060bd1f5)" \
      babel.gguf.sha256="a9d0a3e1d8c91732a3812becd31f8d4a8ff57414903f226306069f0437e2ac50"

WORKDIR /opt/babel
ENV GGML_BACKEND_PATH=/opt/babel/runtime/backends/libggml-cpu-haswell.so \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY models/qwen35-4b.gguf ./models/qwen35-4b.gguf
COPY runtime/ ./runtime/
COPY licenses/ ./licenses/
COPY experiments/ ./experiments/
COPY models/top256_alphabet/ ./models/top256_alphabet/
COPY SHA256SUMS serve.sh ./
USER 65534:65534
EXPOSE 8080 8081
ENTRYPOINT ["/bin/bash", "/opt/babel/serve.sh"]
CMD ["/opt/babel/runtime/llama-server", \
     "--host", "0.0.0.0", "--port", "8080", "--model", "/opt/babel/models/qwen35-4b.gguf", \
     "--alias", "babel-qwen35-ref-v1", "--ctx-size", "6144", "--parallel", "1", \
     "--threads", "4", "--threads-batch", "4", "--threads-http", "2", "--batch-size", "128", "--ubatch-size", "128", \
     "--n-gpu-layers", "0", "--flash-attn", "off", "--fit", "off", \
     "--cache-ram", "0", "--no-cache-prompt", "--cache-reuse", "0", "--no-cache-idle-slots", \
     "--no-kv-unified", "--ctx-checkpoints", "0", "--no-slots", "--no-webui", "--offline"]
