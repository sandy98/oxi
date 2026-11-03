#!/bin/bash
# static/cgi-bin/forker.sh
sleep 30 &
echo "HTTP/1.1 200 OK"
echo "Content-Type: text/plain"
echo ""
echo "Done with the forking..."

