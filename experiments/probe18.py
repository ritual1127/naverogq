import os
import olefile

FILES = [
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\1본체.ipt",
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\3축.idw",
    r"C:\Users\smile\OneDrive\Desktop\캐드 파일\편심구동장치(조립)_(배포)\조립품1.iam",
]

for path in FILES:
    print("\n" + "=" * 70)
    print(os.path.basename(path), os.path.getsize(path), "bytes")
    print("=" * 70)
    if not olefile.isOleFile(path):
        print("  NOT an OLE compound file")
        continue
    ole = olefile.OleFileIO(path)
    streams = ole.listdir()
    print(f"  streams: {len(streams)}")
    for s in streams[:18]:
        try:
            size = ole.get_size("/".join(s))
        except Exception:
            size = "?"
        print(f"     {'/'.join(s)}  ({size} bytes)")
    if len(streams) > 18:
        print(f"     ... and {len(streams) - 18} more")

    print("\n  -- standard OLE property sets --")
    for meta_stream in ("\x05SummaryInformation", "\x05DocumentSummaryInformation"):
        if ole.exists(meta_stream):
            print(f"     {meta_stream!r}: present")
    try:
        meta = ole.get_metadata()
        for attr in ("title", "subject", "author", "keywords", "comments",
                     "last_saved_by", "revision_number", "company", "category"):
            v = getattr(meta, attr, None)
            if v:
                print(f"     {attr} = {v!r}")
    except Exception as e:
        print("     get_metadata failed:", type(e).__name__, e)

    print("\n  -- searching every stream for readable iProperty text --")
    hits = 0
    for s in streams:
        name = "/".join(s)
        if not name.startswith("\x05"):
            continue
        try:
            data = ole.openstream(name).read()
        except Exception:
            continue
        print(f"     property stream {name!r}: {len(data)} bytes")
        hits += 1
    print(f"     property streams found: {hits}")
    ole.close()

print("\n\nCONCLUSION: geometry lives in proprietary streams; only what prints "
      "above is reachable without Inventor.")

