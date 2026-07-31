FROM python:3.13-slim

ARG LIBREDWG_VERSION=0.14

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      build-essential curl ca-certificates \
      fonts-dejavu-core fonts-nanum; \
    ( set -eux; \
      curl -fsSL -o /tmp/libredwg.tar.gz \
        "https://github.com/LibreDWG/libredwg/releases/download/${LIBREDWG_VERSION}/libredwg-${LIBREDWG_VERSION}.tar.gz"; \
      mkdir -p /tmp/libredwg; \
      tar -xzf /tmp/libredwg.tar.gz -C /tmp/libredwg --strip-components=1; \
      cd /tmp/libredwg; \
      ./configure --prefix=/usr/local --disable-shared --disable-python; \
      make -j"$(nproc)"; \
      make install; \
      dwg2dxf --version; \
    ) || echo "WARNING: LibreDWG build failed. This server will read DXF only."; \
    rm -rf /tmp/libredwg /tmp/libredwg.tar.gz; \
    apt-get purge -y --auto-remove build-essential curl; \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 app
USER app
ENV HOME=/home/app \
    PATH=/home/app/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /home/app/src

COPY --chown=app requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=app *.py ./
COPY --chown=app static/ ./static/
COPY --chown=app samples/ ./samples/

EXPOSE 7860

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
