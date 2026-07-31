FROM python:3.13-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libredwg-tools \
 && rm -rf /var/lib/apt/lists/*

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
