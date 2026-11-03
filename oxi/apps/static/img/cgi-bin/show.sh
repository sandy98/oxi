#!/bin/bash

cd static/img
echo '<!DOCTYPE html>'
echo '<html>'
echo '<head>'
echo '<style>'
echo ' body {'
echo '   font-family: Arial, Helvetica, sans-serif;'
echo '}'
echo 'a {'
echo '  font-family: monospace;'
echo '  color: steelblue; '
echo '  text-decoration: none;
echo '}'
echo 'a::hover {'
echo '  text-decoration: underline;
echo '}'
echo 'div {'
echo '  margin-bottom: 0.3rem;'
echo '}'
echo '</style>'
echo '</head>'
echo '<body>'
echo '<h2>Images Directory</h2>'
for file in `ls`
    do echo "<div><a href=\"/img/$file\">$file</a></div>"
done
echo '</body>'
echo '</html>'

