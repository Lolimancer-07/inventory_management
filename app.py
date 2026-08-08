import sys
import os

# Add inventory_app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'inventory_app'))

from app import app  # noqa: F401
