import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'Oxi'
copyright = '2026, Domingo E. Savoretti'
author = 'Domingo E. Savoretti'

try:
    from oxi.__about__ import __version__
    release = __version__
except ImportError:
    release = '1.4.11'

extensions = ['myst_parser', 'sphinx.ext.autodoc', 'sphinx_autodoc_typehints']
html_theme = 'furo'
exclude_patterns = ['_build', '.venv']