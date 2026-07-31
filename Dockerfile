FROM python:3.13-slim AS libredwg

ARG LIBREDWG_VERSION=0.14

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/libredwg.tar.gz \
      "https://github.com/LibreDWG/libredwg/releases/download/${LIBREDWG_VERSION}/libredwg-${LIBREDWG_VERSION}.tar.gz" \
 && mkdir -p /tmp/src \
 && tar -xzf /tmp/libredwg.tar.gz -C /tmp/src --strip-components=1 \
 && cd /tmp/src \
 && ./configure --prefix=/opt/libredwg --disable-shared --enable-static \
      --disable-python --disable-bindings --disable-docs \
 && make -j"$(nproc)" \
 && make install-strip || make install


FROM python:3.13-slim

COPY --from=libredwg /opt/libredwg/bin/dwg2dxf /usr/local/bin/dwg2dxf

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
