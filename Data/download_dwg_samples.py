"""Pull DWG test samples from Kaggle into this Data/ folder.

Requires: pip install kagglehub
Requires Kaggle API credentials configured (~/.kaggle/kaggle.json) — see
https://github.com/Kagglehub/kagglehub#authenticate
"""

import shutil
from pathlib import Path

import kagglehub

path = kagglehub.dataset_download("manisha717/dataset-for-dwg")
print("Path to dataset files:", path)

dest = Path(__file__).parent
for f in Path(path).rglob("*"):
    if f.is_file():
        shutil.copy2(f, dest / f.name)
        print("Copied:", f.name)
