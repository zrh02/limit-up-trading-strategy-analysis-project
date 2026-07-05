from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent

SOURCE_DATA = ROOT_DIR / "data" / "processed" / "model_dataset.csv"
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "output"

ATTRIBUTE_DATA = DATA_DIR / "limit_up_attribute_dataset.csv"

