from pathlib import Path
import json
ROOT=Path(json.loads((Path(__file__).parent/'project.json').read_text())['data_root']).resolve()
def owned(path):
    path=Path(path).resolve()
    if not path.is_relative_to(ROOT):raise ValueError('This destination belongs to another project. Use an Iron Widow shot or layer link.')
    return path
