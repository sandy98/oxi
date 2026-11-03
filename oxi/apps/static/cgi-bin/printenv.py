#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys

def separator():
    #sys.stdout.write(f"<p>{'-' * 80}</p>\n")
    sys.stdout.write('<hr style="color: red;">\n')

sys.stdout.write("HTTP/1.1 200 OK\r\n")
sys.stdout.write("Content-Type: text/html; charset=utf-8\r\n\r\n")

ret = """
<style>
    body {
        font-family: Arial, Helvetica, sans-serif;
    }
</style>
""" 

sys.stdout.write(ret)

separator()
for k, v in os.environ.items():
    if k.upper() == "USER":
        sys.stdout.write(f'<p style="padding: 0.1em;">{k} = {v}</p>\n') 
        separator()
    sys.stdout.write(f'<p style="padding: 0;">{k} = {v}</p>')
#sys.stdout.write(f'<p style="padding: 0.5em;">{repr(form)}</p>\n')
separator()

sys.stdout.flush()
