import sys

from app import main as _main

sys.modules[__name__] = _main
