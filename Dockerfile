# 심사·체험용 공개 데모 이미지.
#
# Inventor는 리눅스에서 돌지 않으므로 이 이미지는 .dxf / .dwg 만 분석한다.
# check.py 가 확장자로 추출기를 고르고, dwg.py 는 ezdxf(순수 파이썬)로 도면을
# 읽으므로 Inventor 경로를 건드리지 않고 그대로 동작한다. 채점 규칙 23개와
# 투상도 AI 판정은 완전히 동일하게 적용된다.
#
# .ipt / .idw / .iam 까지 분석하려면 Inventor가 설치된 Windows PC에서
# setup.ps1 + run.ps1 로 실행해야 한다. README 참고.
FROM python:3.13-slim

# dwg2dxf: LibreDWG(GPL-3.0). 저장소에 넣지 않고 여기서 설치한다 (NOTICE.md).
# find_libredwg() 가 PATH에서 찾아 쓴다.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libredwg-tools \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY static/ ./static/
COPY samples/ ./samples/

# 컨테이너 밖에서 포트를 정해준다 (Railway/Render/Fly 전부 $PORT 를 넣어준다).
ENV CADCHECK_PORT=8000
EXPOSE 8000

# main.py 는 127.0.0.1 에 바인딩한다 -- 로컬 서버로 쓸 때 의도한 동작이고,
# 컨테이너 안에서는 외부에서 닿지 않으므로 여기서만 0.0.0.0 으로 띄운다.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
