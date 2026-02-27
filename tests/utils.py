
import os
import sys

def setup_project_root():
    """
    Adds the project root directory to sys.path so that modules like 'cortex', 'agent_fabric', etc.
    can be imported.
    """
    # Assuming this file is in <project_root>/tests/utils.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, '..'))

    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Also add the tests directory itself to sys.path to allow 'from tests.utils import ...'
    # when running scripts from within tests/
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
