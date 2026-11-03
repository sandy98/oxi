#!/usr/bin/env python3
import os
print("Content-Type: text/plain")
print()
print(f"SCRIPT_NAME: {os.environ.get('SCRIPT_NAME', 'MISSING')}")
print(f"PATH_INFO:   {os.environ.get('PATH_INFO', 'MISSING')}")
print(f"DOCUMENT_ROOT: {os.environ.get('DOCUMENT_ROOT', 'MISSING')}")
print(f"QUERY_STRING: {os.environ.get('QUERY_STRING', 'MISSING')}")