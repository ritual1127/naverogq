# P11 · 다른 CAD 가 쓴 DXF 하나에서 통째로 터졌다

| | |
|---|---|
| 상태 | ✅ **해결** (2026-08-27) |
| 처음 본 날 | 2026-08-27 |
| 무엇에 영향을 주나 | 실제 도면 분석 전부 — 업로드·측정·렌더 ([P04](P04-표본도면.md)) |
| 맡은 사람 | 박지완 |
| 목록 | [문제점 전체](README.md) |

## 증상

실제 시험 도면을 인터넷에서 구할 수 있는지 찾다가, 남이 만든 DXF 를 하나 넣어 봤다.
[LibreCAD 이슈 #2109](https://github.com/LibreCAD/LibreCAD/issues/2109) 에 붙어 있는
`gdt-test-qcad-pro-trial.zip` 안의 `gdt-R15.dxf` — **QCAD Professional 이 쓴 파일**이다.

```
ValueError: could not convert string to float: '0.0l'
```

분석이 시작도 못 하고 죽었다. 파일 어딘가에 실수 값이 `0.0l` 로 적혀 있다.
숫자 `0` 이 아니라 알파벳 `l` 이 붙어 있다.

**우리가 만든 도면에서는 한 번도 안 났다.** 합성 18장은 `bench.py` 가 `ezdxf` 로
직접 쓴 것이라 언제나 규격에 맞다. 파일을 만드는 쪽과 읽는 쪽이 같은 라이브러리다.

## 원인

`ezdxf.readfile()` 은 조금이라도 규격에 어긋나면 예외를 던진다. 같은 파일을
`ezdxf.recover.readfile()` 로 열면 **오류 3건을 잡고 1건을 고쳐서 정상으로 연다.**
AutoCAD 계열도 이런 파일을 그냥 연다. 즉 파일이 못 쓸 정도로 망가진 게 아니라
**우리가 너무 엄격한 문으로 읽고 있었다.**

`dwg.py` 안에 `ezdxf.readfile()` 을 직접 부르는 자리가 **네 군데**였다 —
`dxf_has_content` · `recover_orphaned_paper_views` · `facts_from_dxf` · `render_svg`.
앞의 두 개는 예외를 삼키고 `False` 를 돌려주기 때문에 더 나빴다. **터지지도 않고
"내용이 없는 도면"으로 조용히 취급한다.**

## 조치

네 자리가 다 지나가는 문 하나를 `dwg.readfile()` 로 만들고, 거기서만 복구 읽기로
넘어가게 했다. 호출부마다 `try` 를 붙이지 않았다 — 네 군데에 같은 코드를 넣으면
다음에 다섯 번째 자리가 생길 때 또 빠진다.

```python
def readfile(path):
    try:
        return ezdxf.readfile(path)
    except Exception:
        doc, auditor = recover.readfile(path)
        print(f"[dwg] 손상된 DXF 를 복구해서 열었습니다 "
              f"(오류 {len(auditor.errors)} · 고침 {len(auditor.fixes)}): ...")
        return doc
```

복구해서 열었을 때는 **로그에 남긴다.** 조용히 고치면 나중에 이상한 결과가 나왔을 때
파일이 원래 깨져 있었다는 걸 알 방법이 없다.

## 확인

- `gdt-R15.dxf` — 전에는 `ValueError`. 지금은 `[dwg] 손상된 DXF 를 복구해서 열었습니다
  (오류 3 · 고침 1)` 을 찍고 **지적 7건**(fail 1 · error 3 · warn 3)까지 정상으로 나온다.
- 합성 도면 18장 — `python bench.py` **18/18 · 검출률 100.0% · 정확도 100.0%** 그대로.
- `python -m pytest test_rules.py -q` — **18개 통과** (17개에서 하나 늘었다).
- 새 시험 `test_malformed_dxf_recovers` — 정상 DXF 를 만들어 실수 값 하나를 `120.0l` 로
  망가뜨린 뒤, `ezdxf.readfile` 은 반드시 터지고 `dwg.readfile` 은 열리고
  `dwg.dxf_has_content` 가 **빈 도면으로 오해하지 않는지**까지 본다.

## 왜 이게 중요한가

[P04](P04-표본도면.md) 가 말하는 "우리가 만든 도면으로만 쟀다" 의 실제 값이 이것이다.
실기 도면은 AutoCAD · Inventor · ZWCAD 가 쓴다. **남이 쓴 파일 한 장을 처음 넣어 본
그 자리에서 터졌다.** 인터뷰로 실제 도면을 받기 시작하면 이 부류가 계속 나온다.

## 기록

- 2026-08-27 — 인터넷에서 실기 연습 도면을 구할 수 있는지 찾다가, 처음 넣어 본 남의 DXF 에서 발견하고 같은 날 고쳤다.
