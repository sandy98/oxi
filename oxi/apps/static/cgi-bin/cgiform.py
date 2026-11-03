#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, cgi, cgitb
from mimetypes import types_map
types_map['.md'] = "text/markdown"
# from tempfile import TemporaryFile
# from io import BytesIO
cgitb.enable()

def encode_image(image_data, image_type='image/jpeg'):
    import base64
    img_template = "data:{0};base64,{1}"
    img_string = base64.b64encode(image_data).decode("utf-8")
    return img_template.format(image_type, img_string)


# form = cgi.FieldStorage()

def separator():
    #sys.stdout.write(f"<p>{'-' * 80}</p>\n")
    sys.stdout.write('<hr style="color: red;">\n')

sys.stdout.write("HTTP/1.1 200 OK\r\n")
sys.stdout.write("Content-Type: text/html; charset=utf-8\r\n\r\n")

form = cgi.FieldStorage()
# form = cgi.parse_multipart(sys.stdin, os.environ)
# cgi.print_form(form)

# separator()
# sys.stdout.write(f"<p>Stdin received: /{entry}/</p>\n")
# separator()
# for k, v in os.environ.items():
#     if k.upper() == "USER":
#         sys.stdout.write(f'<p style="padding: 0.5em;">{k} = {v}</p>\n') 
#         separator()
#     sys.stdout.write(f'<p style="padding: 0.5rem;">{k} = {v}</p>')
# #sys.stdout.write(f'<p style="padding: 0.5em;">{repr(form)}</p>\n')
# separator()
# sys.stdout.write(f'<p style="padding: 0.5em;"><strong>Username:</strong> {form.getvalue("username")}</p>\n')
# sys.stdout.write(f'<p style="padding: 0.5em;"><strong>Password:</strong> {form.getvalue("passwd")}</p>\n')
# separator()

ret = """
<style>
    body {
        font-family: Arial, Helvetica, sans-serif;
    }
</style>
""" 

# ret += f"<hr><p style='color: green;'>{repr(form)}</p><hr>"
try:
    content_type = os.environ['CONTENT_TYPE']
    ret += f"<h2><strong style='color: steelblue;'>Content-Type:&nbsp;</strong>{content_type}</h2><hr>"
except:
    pass
for key in form:
    # # # ret += f"<p>{repr(form[key])}</p>"
    field_item = form[key]
    try:
        if field_item.filename:
            filename = field_item.filename
            ret += f"<h3><strong style='color: steelblue;'>File:&nbsp;</strong>{filename}</h3>"
            mimetype = types_map.get(os.path.splitext(filename)[1])
            if mimetype and mimetype.startswith("image"):
                encoded_img = encode_image(form.getvalue(key))
                ret += f'<p><img src="{encoded_img}" /></p>'
            elif mimetype and mimetype.startswith("text"):
                ret += f"<p><textarea style='width: 90%; height: 15rem; font-size: 1.4rem;'>{form.getvalue(key).decode('latin-1')}</textarea></p>"
            else:
                ret += f"<h3><strong style='color: steelblue;'>{key}</strong> = {form.getvalue(key)}</h3>"
        else:
            try:
                ret += f"<h3><strong style='color: steelblue;'>{key}</strong> = {form.getvalue(key)}</h3>"
            except Exception as exc:
                excname = exc.__class__.__name__
                ret += f"<h3 style='color: red;'>Error while retrieving key/value pair {excname}: {exc}</h3>"
    
    
    except Exception as exc:
        excname = exc.__class__.__name__
        ret += f"<h3 style='color: red;'>Error while retrieving file entry {excname}: {exc}</h3>"
    ret +="<hr>"
ret += "<br><p style='text-align: center;'><button style='font-size: 1.5rem;' onclick='history.back();'>Back</button></p>"


sys.stdout.write(ret)
sys.stdout.flush()
