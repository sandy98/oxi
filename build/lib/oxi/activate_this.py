# -*- coding: utf-8 -*-

# This script is used to manually activate a virtual environment by modifying
# the system path and environment variables to point to the virtual environment.

import os, sys
from pathlib import Path

oxi_env = False

try:
    print("Activating virtualenv...")

    # Path to the virtual environment
    oxi_path = Path(os.path.abspath(__file__)).parent.parent

    # Update sys.path to include oxi path
    sys.path.insert(0, str(oxi_path))

    oxi_env = True
    print(f"Virtual environment activated for Oxi: {str(oxi_path)}.")
except Exception as e:
    print("Virtual environment activation failed. Error: {0}".format(str(e)))

