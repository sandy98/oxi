#!/usr/bin/env python3
import sys

# Emit a 404 with custom headers
print("Status: 404 Not Found")
print("Content-Type: application/json")
print("X-Custom-Header: Hello-From-CGI")
print()
print('{"error": "Resource missing", "code": 404}')