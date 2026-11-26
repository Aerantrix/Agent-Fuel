import sys
from pathlib import Path

# The project is run from its root (python -m evaluation.analyse); make the
# tests see control/ and sandbox/ the same way.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
