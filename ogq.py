"""결과 화면에 OGQ 마켓 캐릭터 스티커를 싣는다.

대회 사무국이 준 OGQ 마켓 API 로 OGQ 공식계정의 무료 스티커 '박하의 힐링타임'을 받는다.
파일은 저장소에 넣지 않는다. 대회 참여 목적으로만 쓰고 배포·복제하지 않는다는 조건이라,
서버가 실행 중에 받아 자기 디스크에만 둔다. 방문자 브라우저는 OGQ 서버가 아니라 우리 서버에서
받으므로 방문자 접속 정보가 OGQ 로 가지 않는다.

키는 환경변수 OGQ_API_KEY 에서만 읽는다. 키가 없거나 OGQ 가 안 되면 스티커 없이 화면이 돈다.
"""
import os
import threading
import time

import requests

BASE = "https://4th-ai-ogq.competition.ogq.me"
PACK = "5747936e27e7c"          # 박하의 힐링타임 · OGQ
STICKERS = {                    # 화면 상황 -> 팩 안의 낱장 imageId
    "pass": "5ca40081d1977",    # 엄지척 — 합격선 통과
    "short": "5ca40081d1988",   # 아령 운동 — 합격선 미달
    "fail": "5ca40081d198a",    # 눈물 — 오작(실격)
    "fixed": "5ca40081d197c",   # 짝짝 — 재검사에서 고쳐진 항목이 있음
    "wait": "5ca40081d1980",    # 뜨개질하며 시계 보기 — 검사 중
    "error": "5ca40081d1987",   # 시무룩 — 검사 실패
}
CACHE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                     "cad-checker", "ogq")
RETRY_SEC = 5 * 60              # 받기에 실패하면 이만큼은 다시 부르지 않는다 (API 한도 분당 60회)
_lock = threading.Lock()
_failed_at = [0.0]


def available():
    return bool(os.environ.get("OGQ_API_KEY"))


def _path(image_id):
    return os.path.join(CACHE, f"{PACK}-{image_id}.png")


def _read(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _fetch_pack():
    """상세 조회 한 번으로 받은 미리보기 주소에서 쓰는 낱장만 받아 둔다. 주소는 조립하지 않는다."""
    r = requests.get(f"{BASE}/v1/assets/{PACK}", timeout=10,
                     headers={"X-OGQ-API-KEY": os.environ["OGQ_API_KEY"]})
    r.raise_for_status()
    os.makedirs(CACHE, exist_ok=True)
    wanted = set(STICKERS.values())
    for image in r.json().get("images") or []:
        if image.get("imageId") not in wanted:
            continue
        data = requests.get(image["imageUrl"], timeout=15).content
        if not data.startswith(b"\x89PNG"):
            raise ValueError(f"PNG 가 아닌 응답 ({image['imageId']})")
        tmp = _path(image["imageId"]) + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, _path(image["imageId"]))


def sticker(name):
    """PNG bytes, or None when the sticker cannot be served."""
    image_id = STICKERS.get(name)
    if not image_id or not available():
        return None
    data = _read(_path(image_id))
    if data is not None:
        return data
    with _lock:                 # 첫 화면에서 스티커 요청이 몰려도 API 는 한 번만 부른다
        data = _read(_path(image_id))
        if data is not None or time.time() - _failed_at[0] < RETRY_SEC:
            return data
        try:
            _fetch_pack()
        except (requests.RequestException, ValueError, KeyError, OSError) as e:
            _failed_at[0] = time.time()
            print(f"[ogq] 스티커를 못 받음: {type(e).__name__}: {str(e)[:200]}", flush=True)
            return None
    return _read(_path(image_id))
