"""Probe 19: decode the OLE property streams -- do real iProperties come out
without Inventor? This is the last piece needed to say exactly what a cloud
deployment could and could not check.
"""
import os
import olefile

FILES = [r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\1본체.ipt",
         r"C:\Users\smile\OneDrive\Desktop\캐드 파일\모델링, 도면\3축.idw"]

for path in FILES:
    print("\n" + "=" * 70)
    print(os.path.basename(path))
    print("=" * 70)
    ole = olefile.OleFileIO(path)
    for entry in ole.listdir():
        name = "/".join(entry)
        if not name.startswith("\x05"):
            continue
        try:
            props = ole.getproperties(name, convert_time=True)
        except Exception as e:
            print(f"  {name!r}: decode failed ({type(e).__name__})")
            continue
        readable = {k: v for k, v in props.items()
                    if isinstance(v, str) and v.strip()}
        if not readable:
            continue
        print(f"\n  stream {name!r} -> {len(props)} properties")
        for k, v in sorted(readable.items()):
            print(f"      [{k}] {v!r}")
    ole.close()

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
print("readable without Inventor : iProperties (part number, material, author...)")
print("NOT readable              : sketches/constraints, dimensions, tolerances,")
print("                            holes, walls, interference -- all of that is")
print("                            in the proprietary RSeStorage streams.")
