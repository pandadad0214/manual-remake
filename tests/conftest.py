import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if not os.path.exists(os.path.join(ROOT, "tests", "fixtures", "sample_manual.pdf")):
    from tests.make_fixtures import build

    build()
