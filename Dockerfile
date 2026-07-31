FROM python:3.13-slim

ARG LIBREDWG_VERSION=0.14

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      build-essential autoconf automake libtool pkg-config curl ca-certificates \
      fonts-dejavu-core fonts-nanum; \
    curl -fsSL -o /tmp/libredwg.tar.gz \
      "https://github.com/LibreDWG/libredwg/releases/download/${LIBREDWG_VERSION}/libredwg-${LIBREDWG_VERSION}.tar.gz"; \
    mkdir -p /tmp/libredwg; \
    tar -xzf /tmp/libredwg.tar.gz -C /tmp/libredwg --strip-components=1; \
    cd /tmp/libredwg; \
    ./configure --prefix=/usr/local --disable-shared --disable-python; \
    make -j"$(nproc)"; \
    make install; \
    command -v dwg2dxf; \
    dwg2dxf --version; \
    rm -rf /tmp/libredwg /tmp/libredwg.tar.gz; \
    apt-get purge -y --auto-remove \
      build-essential autoconf automake libtool pkg-config curl; \
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

# A successful image must convert, parse, and render a real DWG, not merely
# contain a binary named dwg2dxf.
RUN python -c "import os, tempfile; import dwg; src='samples/sample_075em07z.dwg'; out=os.path.join(tempfile.mkdtemp(), 'sample.dxf'); assert dwg.dwg_via_libredwg(src, out), 'LibreDWG could not convert the bundled DWG sample'; svg, _, _ = dwg.render_svg(out); assert len(svg) > 1000, 'DWG preview SVG is empty'; print('DWG conversion and preview smoke test passed')"

EXPOSE 7860

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
