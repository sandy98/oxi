#! -*- coding: utf_8 -*-

import enum, random, os, re, json, inspect, asyncio
from io import StringIO
import xml.etree.ElementTree as ET
from xml.dom import minidom
from html.parser import HTMLParser

from . import __version__ as oxi_version
from .utils import SmartDict, aopen, dual_mode
from .server import OxiProtocol

oxi_version
       
#############################################################################################################################

class Carets(enum.Enum):
    CARET_UP = "&#9650;"
    CARET_DOWN = "&#9660;"

MenuColors = {
    'MAINBACKNORMAL':  "#676767",
    'MAINBACKSELECTED':  "steelblue",
    'MAINFORENORMAL':  "#ffffff",
    'MAINFORESELECTED':  "#020582",
    'ITEMBACKNORMAL':  "#f9f9f9",
    'ITEMBACKSELECTED':  "#dddddd",
    'ITEMFORENORMAL':  "#000000",
    'ITEMFORESELECTED':  "#020281",
}


class Menu:
    """
    Handles menu display stuff
    """

    mainBack = MenuColors.get("MAINBACKNORMAL")
    mainBackSelected = MenuColors.get("MAINBACKSELECTED")
    itemBack = MenuColors.get("ITEMBACKNORMAL")
    itemBackSelected = MenuColors.get("ITEMBACKSELECTED")

    style = """
    .navbar {{
        overflow: hidden;
        background-color: {0};
    }}

    .navheader {{
        color: #e4e4e4; 
        font-size: 150%; 
        font-weight: bold;
        float: left;
        display: flex;
        flex-direction: row;
        align-items: center;
        padding: 10px;
    }}

    .navbar a {{
        float: left;
        font-size: 16px;
        color: white;
        text-align: center;
        padding: 14px 16px;
        text-decoration: none;
    }}

    .dropdown {{
        float: left;
        overflow: hidden;
    }}

    .dropdown .dropbtn {{
        font-size: 16px;
        border: none;
        outline: none;
        color: white;
        padding: 14px 16px;
        background-color: inherit;
        font-family: inherit;
        margin: 0;
    }}

    .navbar a:hover, .dropdown:hover .dropbtn {{
        background-color: {1};
    }}

    .dropdown-content {{
        display: none;
        position: absolute;
        background-color: {2};
        min-width: 160px;
        box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
        z-index: 1;
    }}

    .dropdown-content a {{
        float: none;
        color: black;
        padding: 12px 16px;
        text-decoration: none;
        display: block;
        text-align: left;
    }}

    .dropdown-content a:hover {{
        background-color: {3};
    }}

    .dropdown:hover .dropdown-content {{
        display: block;
    }}
    """

    @classmethod
    def getStyle(cls, mB = mainBack, mBS= mainBackSelected, iB= itemBack, iBS= itemBackSelected):
        return cls.style.format(mB, mBS, iB, iBS)


class MenuItem(Menu):
    def __init__(self, label: str, href: str):
        self.label = label
        self.href = href

    def __repr__(self):
        return '<a href="{0}">{1}</a>'.format(self.href, self.label)

class MenuSep(MenuItem):
    def __init__(self):
        super().__init__('', '')

    def __repr__(self):
        return '<hr>'


class DropdownMenu(Menu):
    def __init__(self, label="Dropdown", items: list[MenuItem] = None):
        self.label = label
        self.items: list[MenuItem] = items or []

    def addItem(self, item: MenuItem):
        if not isinstance(item, (MenuItem, DropdownMenu)):
            return False
        else:
            self.items.append(item)
            return True

    def __repr__(self):
        parts = []
        prefix = f"""
        <div class="dropdown">
            <button class="dropbtn">{self.label}
            <!--<i class="fa fa-caret-down"></i>-->
            <i style="font-size: 75%;">&nbsp;&#9660;</i>
            </button>
            <div class="dropdown-content">
        """
        parts.append(prefix)
        for i in self.items:
            parts.append(str(i))
        suffix = """
            </div>
        </div>
        """
        parts.append(suffix)
        return "".join(parts)


class MenuBar:

    def __init__(self, items: list[Menu] = None, mB=Menu.mainBack, mBS=Menu.mainBackSelected, iB=Menu.itemBack, iBS=Menu.itemBackSelected):
        self.items = items or []
        self.mB = mB
        self.mBS = mBS
        self.iB = iB
        self.iBS = iBS

    def setBackground(self, color):
        self.mB = color
        
    def addItem(self, item: MenuItem):
        if not isinstance(item, (MenuItem, DropdownMenu)):
            return False
        else:
            self.items.append(item)
            return True

    def __repr__(self):
        parts = []
        for i in self.items:
            parts.append(str(i))
        joined = "".join(parts)
        return f'<style>{Menu.getStyle(self.mB, self.mBS, self.iB, self.iBS)}</style><div class="navbar">{joined}</div>'


class NavBar(MenuBar):

    def __init__(self, head: str = None, items: list[Menu] = None):
        super().__init__(items)
        self.head = head or ''

    def __repr__(self):
        parentrepr = super().__repr__()
        replace = f'<div class="navbar"><div class="navheader">&nbsp;{self.head}&nbsp;&nbsp;&nbsp;</div>'
        return parentrepr.replace('<div class="navbar">', replace)
    

class Head:
    def __init__(self, title: str, links: list[str] = None, styles: list[str] = None, scripts: list[str] = None):
        self.title = title
        self.links = links or []
        self.styles = styles or []
        self.scripts = scripts or []

    @property
    def links_list(self) -> str:
        return('\n'.join(self.links))

    @property
    def styles_list(self) -> str:
        return('\n'.join(self.styles))

    @property
    def scripts_list(self) -> str:
        return('\n'.join(self.scripts))

    def add_item(self, item_type: str = 'script', content: str = ''):
        if item_type == 'link':
            target_list = self.links
        elif item_type == 'style':
            target_list = self.styles
        elif item_type == 'script':
            target_list = self.scripts
        else:
            return False
        target_list.append(f"{content}")
        return True
    
    def __repr__(self):
        return """
        <head>
            <meta charset="utf-8">
            <title>{0}</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0, shrink-to-fit=no">
            <!--LINKS-->\n{1}
            <!--STYLES-->\n{2}
            <!--SCRIPTS-->\n{3}
        </head>
        """.format(self.title, self.links_list, self.styles_list, self.scripts_list )


class Body:
    def __init__(self, navbar: NavBar = None, font_family: str = "sans-serif"):
        self.navbar = navbar
        self.font_family = font_family

    def __repr__(self):
        retval =  '<body style="font-family: ' + self.font_family + ';">'
        retval += '<div id="main">'
        retval += str(self.navbar) if self.navbar else ''
        retval += ' <div id="contents">'
        retval += '  {{ contents }}'
        retval += '</div>'
        retval += '</div>'
        retval += '</body>'
        
        return retval


class HTMLApp:
    def __init__(self, head: Head, body: Body, lang: str = 'en'):
        self.lang = lang
        self.head = head
        self.body = body

    def __repr__(self):
        return f"""
        <!DOCTYPE html>
        <html lang={self.lang}>
        {repr(self.head)}
        {repr(self.body)}
        </html>
        """


#############################################################################################################################

######################################################################################

# Templates related code

class CodeBuilder:
    """Build source code conveniently."""

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = indent

    def add_line(self, line):
        """Add a line of source to the code.
        Indentation and newline will be added for you, don't provide them.
        """
        self.code.extend([" " * self.indent_level, line, "\n"])

    INDENT_STEP = 4      # PEP8 says so!

    def indent(self):
        """Increase the current indent for following lines."""
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        """Decrease the current indent for following lines."""
        self.indent_level -= self.INDENT_STEP

    def add_section(self):
        """Add a section, a sub-CodeBuilder."""
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    def __str__(self):
        return "".join(str(c) for c in self.code)

    def get_globals(self):
        """Execute the code, and return a dict of globals it defines."""
        # A check that the caller really finished all the blocks they started.
        assert self.indent_level == 0
        # Get the Python source as a single string.
        python_source = str(self)
        # Execute the source, defining globals, and return them.
        global_namespace = {}
        exec(python_source, global_namespace)
        return global_namespace


class TemplateSyntaxError(BaseException):
    pass


class TemplateLight:

    test_tpl = """
        <h2> Hello, I am {{ user  }}. </h2>
        <p>These are my favourite teams, in no particular order.<p>
        <p>
          <ul>
            {% for team in teams %}
              <li> {{ team }} </li>
            {% endfor %}
          </ul>
        </p>
        """

    def __init__(self, text, **contexts):
        """Construct a TemplateLight with the given `text`.
        `contexts` are key-value pairs to use for future renderings.
        These are good for filters and global values.
        """
        self._template_text = text
        self.context = {}
        # for context in contexts:
        # self.context.update(context)
        self.context.update(contexts)
        self.all_vars = set()
        self.loop_vars = set()

        code = CodeBuilder()
        code.add_line("def render_function(context, do_dots):")
        code.indent()
        vars_code = code.add_section()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")

        buffered = []

        def flush_output():
            """Force `buffered` to the code builder."""
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) > 1:
                code.add_line("extend_result([%s])" % ", ".join(buffered))
            del buffered[:]

        ops_stack = []
        text = text.replace(",", " , ")
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)

        for token in tokens:
            if token.startswith('{#'):
                # Comment: ignore it and move on.
                continue
            elif token.startswith('{{'):
                # An expression to evaluate.
                expr = self._expr_code(token[2:-2].strip())
                buffered.append("to_str({0})".format(expr))
            elif token.startswith('{%'):
                # Action tag: split into words and parse further.
                flush_output()
                words = token[2:-2].strip().split()
                if words[0] == 'if':
                    # An if statement: evaluate the expression to determine if.
                    # if len(words) != 2:
                    #    self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if {0}:".format(
                        self._expr_code(' '.join(words[1:]))))
                    code.indent()
                elif words[0] == 'elif':
                    # An elif statement: evaluate the expression to determine else.
                    #print("Uso de 'else' en el template detectado.")
                    # if len(words) != 2:
                    #    self._syntax_error("Don't understand elif", token)
                    if not ops_stack:
                        self._syntax_error(
                            "'elif' without previous 'if'", token)
                    start_what = ops_stack.pop()
                    if (start_what != "if"):
                        self._syntax_error(
                            "'elif' without previous 'if'", token)
                    ops_stack.append('if')
                    code.dedent()
                    code.add_line("elif {0}:".format(
                        self._expr_code(' '.join(words[1:]))))
                    code.indent()
                elif words[0] == 'else':
                    # An else statement: evaluate the expression to determine else.
                    #print("Uso de 'else' en el template detectado.")
                    if len(words) != 1:
                        self._syntax_error("Don't understand else", token)
                    if not ops_stack:
                        self._syntax_error(
                            "'Else' without previous 'if'", token)
                    start_what = ops_stack.pop()
                    if (start_what != "if"):
                        self._syntax_error(
                            "'Else' without previous 'if'", token)
                    ops_stack.append('else')
                    code.dedent()
                    code.add_line("else:")
                    code.indent()
                elif words[0] == 'for':
                    # A loop: iterate over expression result.
                    if words[-2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    loopvars = list(filter(lambda x: x != ',', words[1:-2]))
                    for loopvar in loopvars:
                        self._variable(loopvar, self.loop_vars)
                    deco_loopvars = list(map(lambda v: f"c_{v}", loopvars))
                    line_to_add = "for {0} in {1}:".format(
                        " , ".join(deco_loopvars), self._expr_code(words[-1]))
                    code.add_line(line_to_add)
                    code.indent()
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack.
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if (start_what != end_what) and (start_what != "else" or end_what != "if"):
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                else:
                    self._syntax_error("Don't understand tag", words[0])
            else:
                # Literal content.  If it isn't empty, output it.
                if token:
                    buffered.append(repr(token))

        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])

        flush_output()

        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))

        code.add_line("return ''.join(result)")
        code.dedent()

        self._code = code
        self._render_function = code.get_globals()['render_function']

    @staticmethod
    def _is_string(name):
        pattrn = r"""^(\"|\')(.*?)\1$"""
        return re.match(pattrn, name)

    @staticmethod
    def _is_reserved(name):
        if name == "true":
            name = "True"
        if name == "false":
            name = "False"
#        if name == "null" or name == "nil":
#            name = "None"
        return name in ["|", "if", "else", "and", "or", "not", "in", "is", "True", "False", "None"]

    @staticmethod
    def _is_variable(name):
        if TemplateLight._is_reserved(name) or TemplateLight._is_string(name):
            return False
        pattrn = r"(?P<varname>[_a-zA-Z][_a-zA-Z0-9]*)(?P<subscript>\[(?P<subvar>.+)\])?$"
        return re.match(pattrn, name)

    def _variable(self, name, vars_set):
        """Track that `name` is used as a variable.
        Adds the name to `vars_set`, a set of variable names.
        Raises an syntax error if `name` is not a valid name.
        """
        m = self._is_variable(name)
        if not m:
            self._syntax_error("Not a valid name", name)
        d = m.groupdict()
        vars_set.add(d.get("varname"))
        #subvar = d.get("subvar")
        # if subvar and self._is_variable(subvar):
        #    vars_set.add(self._expr_code(subvar))

    def _expr_code(self, expr):
        """Generate a Python expression for `expr`."""
        nonisobar = r"[^\s]\|[^\s]"
        if re.findall(nonisobar, expr):
            pipes = expr.split("|")
            code = self._expr_code(pipes[0])
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = "c_%s(%s)" % (func, code)
        elif "." in expr:
            dots = expr.split(".")
            code = self._expr_code(dots[0])
            args = ", ".join(repr(d) for d in dots[1:])
            code = "do_dots(%s, %s)" % (code, args)
        else:
            subexprs = expr.split()
            code = ""
            for subexpr in subexprs:
                m = self._is_variable(subexpr)
                if m:
                    self._variable(subexpr, self.all_vars)
                    d = m.groupdict()
                    varname = f"c_{d.get('varname')}"
                    subscript = d.get('subscript', '')
                    if subscript:
                        subvar = d.get('subvar')
                        if subvar and self._is_variable(subvar):
                            subscript = subscript.replace(
                                subvar, f"c_{subvar}")
                    code += "{0}{1} ".format(varname,
                                             subscript if subscript else "")
                else:
                    code += f"{subexpr} "
        return code

    def _syntax_error(self, msg, thing):
        """Raise a syntax error using `msg`, and showing `thing`."""
        raise TemplateSyntaxError("%s: %r" % (msg, thing))

    def _do_dots(self, value, *dots):
        """Evaluate dotted expressions at runtime."""
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                if isinstance(value, (list, tuple)):
                    if isinstance(dot, str) and dot.isnumeric():
                        dot = int(dot)
                value = value[dot]
            if callable(value):
                value = value()
        return value

    def render(self, **context):
        """Render this template by applying it to `context`.
        `context` is a dictionary of values to use in this rendering.
        """
        # Make the complete context we'll use.
        render_context = dict(self.context)
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)
    
    template_filters = {}

TemplateLight.template_filters['title'] = str.title
TemplateLight.template_filters['capitalize'] = str.capitalize
TemplateLight.template_filters['upper'] = str.upper
TemplateLight.template_filters['lower'] = str.lower 
TemplateLight.template_filters['toJson'] = lambda x: json.dumps(x, ensure_ascii=False)

def get_template_dir():
    templates_root = OxiProtocol.config.get(
        'template-dir', 'templates')
    return os.path.join(os.getcwd(), templates_root)

def get_template_fullpath(template_file):
    return os.path.join(get_template_dir(), template_file)

def _load_template_sync(template_filename):
    path = get_template_fullpath(template_filename)
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()

def load_template(template_filename):
    path = get_template_fullpath(template_filename)
    with open(path, "r", encoding="utf-8") as fp:
        return fp.read()

async def load_template_async(template_filename):
    return await asyncio.to_thread(load_template, template_filename)
    
def preprocess_template(tpl_str=TemplateLight.test_tpl):
    ftpl = StringIO(tpl_str)
    lines = ftpl.readlines()
    ftpl.close()
    for index, line in enumerate(lines):
        stripline = line.strip()
        # m = re.match(r"^\{\#include\s+(?P<inc_file>.+?)\s+\#\}$", stripline)
        if stripline.startswith('{#include') and stripline.endswith("#}"):
            # m = re.match(r"^(.+?)\s+(.+?)\s+(\#\})$", stripline)
            m = re.split(r"\s+", stripline)
            if m:
                # inc_file = m.groupdict().get("inc_file")
                # inc_file = m.groups()[1]
                inc_file = m[1]
                if not inc_file:
                    raise TemplateSyntaxError(
                        "Include directiva must refer to a file")
                fullpath = get_template_fullpath(
                    inc_file.replace("\"", "").replace("'", ""))
                if os.path.exists(fullpath) and os.path.isfile(fullpath):
                    fp = open(fullpath)
                    new_tpl_str = fp.read()
                    fp.close()
                    replace_line = preprocess_template(
                        new_tpl_str)
                    lines[index] = replace_line
            else:
                raise TemplateSyntaxError(
                    "Included file {0} in line {1} does not exist.".format(inc_file, index))
    return "".join(lines)

def compile_template(tpl_str=TemplateLight.test_tpl):
    if not tpl_str:
        return None
    words = tpl_str.split()
    if len(words) == 1:
        fullpath = get_template_fullpath(tpl_str)
        if os.path.exists(fullpath) and os.path.isfile(fullpath):
            # fp = open(fullpath)
            # tpl_str = fp.read()
            # fp.close()
            tpl_str = load_template(tpl_str)

    return TemplateLight(preprocess_template(tpl_str),
                            **TemplateLight.template_filters)

def render_template(tpl_str=TemplateLight.test_tpl, **kw):
    if tpl_str.__class__.__name__ == "TemplateLight":
        return tpl_str.render(**kw)
    elif tpl_str.__class__.__name__ == "str":
        compiled = compile_template(preprocess_template(tpl_str))
        if compiled:
            return compiled.render(**kw)
        else:
            return None
    else:
        return None

    # End of template related stuff

# End of templates related code

#############################################################################################################################

#############################################################################################################################

# Special templates

swiss_army_knife_template = """
{{% if full %}}
    <{{{{parentElement}}}} class="{{{{parentClass}}}}" {{% if size %}} size="{{{{ size }}}}" {{% endif%}}>
{{% endif %}}
{header}
{{% for record in records %}}
    {{% if childElement == 'option' %}}
        <{{{{childElement}}}} {{% if record['{idColumn}'] == {selected} %}} selected {{% endif %}} value="{{{{ record['{idColumn}'] }}}}" data-id="{{{{ record['{idColumn}'] }}}}" data-json='{{{{ record|toJson }}}}'>
            {{{{ record['{nameColumn}'] }}}}
        </{{{{childElement}}}}>
    {{% elif childElement == 'li' %}}
        <{{{{childElement}}}} data-id="{{{{ record['{idColumn}'] }}}}" data-json='{{{{ record|toJson }}}}'>
            <span {{% if record['{idColumn}'] == {selected} %}} class="selected" {{% endif %}}>{{{{ record['{nameColumn}'] }}}}</span>
        </{{{{childElement}}}}>
    {{% elif childElement == 'tr' %}}
        <{{{{childElement}}}} data-id="{{{{ record['{idColumn}'] }}}}" data-json='{{{{ record|toJson }}}}' {{% if record['{idColumn}'] == {selected} %}} class="selected" {{% endif %}}>
            {{%for key in keyz %}}
                <{{{{grandchildElement}}}}> 
                    {{{{ record[key] }}}}
                </{{{{grandchildElement}}}}>
            {{%endfor%}}
        </{{{{childElement}}}}>
    {{% elif childElement == 'p' %}}
        <{{{{childElement}}}} data-id="{{{{ record['{idColumn}'] }}}}" data-json='{{{{ record|toJson }}}}' {{% if record['{idColumn}'] == {selected} %}} class="selected" {{% endif %}}>
            {{%for key in keyz %}}
                <{{{{grandchildElement}}}}> 
                    {{{{ record[key] }}}}
                </{{{{grandchildElement}}}}>
            {{%endfor%}}
        </{{{{childElement}}}}>
    {{% else %}}
        <p data-id="{{{{ record['{idColumn}'] }}}}" data-json='{{{{ record|toJson }}}}'>{{{{record['{nameColumn}']}}}}</p>
    {{% endif %}}
{{% endfor %}}
{footer}

{{% if full %}}
    </{{{{parentElement}}}}>
{{% endif %}}

"""

def swiss_army_knife(records, **kwargs):
    options = SmartDict({
        'parentElement': 'select',
        'childElement': 'option',
        'grandchildElement': 'span',
        'header': '',
        'footer': '',
        'selected': 0,
        'idColumn': 'id',
        'nameColumn': 'name',
        'titleColumn': 'description',
        'full': True,
        'parentClass': '',
        'emptyMsg': 'No records found.',
        'selected': 0,
        'size': None
    })
    options.update(kwargs)
    if not len(records):
        return f"""
        <p class='{options.parentClass}'>{options.emptyMsg}</p>
        """
    options.keyz = records[0].keys()
    options.headers = [key.title() for key in options.keyz]
    
    if options.parentElement.lower() == 'table':
        options.childElement = 'tr'
        options.grandchildElement = 'td'
        options.parentClass = options.parentClass or 'zebra'
        options.header = f"""
        <thead>
        <tr>
        {'<th>' + '</th><th>'.join(options.headers) + '</th>'}
        </tr>
        </thead>
        <tbody>
        """
        options.footer = '</tbody>'
    elif options.parentElement.lower() == 'div':
        options.childElement = 'p'
        options.grandchildElement = 'span'
        options.parentClass = options.parentClass or 'panel'
    elif options.parentElement.lower() == 'ul':
        options.childElement = 'li'
        options.grandchildElement = 'a'
        options.parentClass = options.parentClass or 'big'
    elif options.parentElement.lower() == 'select':
        options.childElement = 'option'
        options.grandchildElement = 'span'
        options.parentClass = options.parentClass or 'big'

    if options.nameColumn not in options.keyz:
        listkeyz = list(options.keyz)
        if len(listkeyz) > 1:
            options.nameColumn = list(options.keyz)[1] 
        else:
            options.nameColumn = list(options.keyz)[0]

    formatted_template = swiss_army_knife_template.format(**options)
    rendered = render_template(formatted_template, records=records, **options)
    try: 
        prepared_rendered = rendered.strip('\n ').encode('utf-8').decode('utf-8')
        if not options.get('full'):
            return prepared_rendered
        prettyhtml = minidom.parseString(prepared_rendered).toprettyxml(indent="  ")
        return prettyhtml
    except Exception as e:
        print(f"Error parsing template: {e}")
        return rendered
    
# End of special templates


#############################################################################################################################

class FormElement:

    options = {
        'C': 'Text',
        'N': 'Number',
        'D': 'Date',
        'L': 'Logical',
        'O': 'Options'
    }

    def __init__(self, description: str, elemtype:str="C", options:str="",
                 elemname:str="subitem", elemvalue:str="", elemid:int=0,  
                 p_class:str="renglon", label_class:str="large steelblue",
                 input_class:str="small"):
        self.description = description
        self.elemtype = "C"
        if elemtype in self.options.keys():
            self.elemtype = elemtype
        else:
            raise ValueError("Element type must be one of 'C, N, D, L, O'")
        self.options = options
        self.name = elemname
        self.id = elemid
        self.value = elemvalue
        self.p_class = p_class
        self.label_class = label_class
        self.input_class = input_class

    
    def __repr__(self):
        instance_name = f"{self.name}-{self.id}"
        if self.elemtype == 'C':
            return f'''<input value="{self.value or ''}" style="font-size: 1.3em;" type="text" id="{instance_name}" name="{instance_name}" class="{self.input_class}"/>'''
        elif self.elemtype == 'N':
            return f'''<input value="{self.value or ''}" style="font-size: 1.3em; text-align: right;" type="number" id="{instance_name}" name="{instance_name}" style="text-align: right;" />'''
        elif self.elemtype == 'D':
            return f'''<input value="{self.value or ''}" style="font-size: 1.3em;" type="date" id="{instance_name}" name="{instance_name}" />'''
        elif self.elemtype == 'L':
            return f'''
              <span style="display: inline-flex; flex-direction: row; align-items: center;">
              <strong style="font-size: 1em;"> 
                <label class="green" for="{self.description}-si">Sí</label>&nbsp;<input {'checked ' if str(self.value) == "1" else ' '}  id="{instance_name}-1" name="{instance_name}" style="transform: scale(2); margin: 5px;" type="radio" name="{self.description}" id="{self.description}-si" value="1">
                <label class="red" for="{self.description}-no">No</label>&nbsp;<input {'checked ' if str(self.value) == "0" else ' '} id="{instance_name}-0" name="{instance_name}" style="transform: scale(2); margin: 5px;" type="radio" name="{self.description}" id="{self.description}-no" value="0">
              </strong>
              </span>
            '''
        else:
            if not self.options:
                return f'<select class="{self.input_class}" style="font-size: 1.3em;" name="{self.description}">\n\t<option selected disabled value="">Debe proveer una opción.</option>\n</select>'
            else:
                options = re.split(r"\s*,\s*", self.options)
                optionstring = "\n".join([f'''\t<option {' selected ' if o == self.value else ' '} value="{o}">{o.title()}</option>''' for o in options])
                return f'''<select class="{self.input_class}"  id="{instance_name}" name="{instance_name}" style="font-size: 1.2em; padding: 5px; padding-left: 10px; padding-right: 10px;">\n{optionstring}\n</select>'''

    def __str__(self):
        response = f'''
        <p class="{self.p_class}">
          <label class="{self.label_class}">{self.description}</label>
          {repr(self)}
        </p>
        '''
        return response

#############################################################################################################################

def test1():
    import asyncio
    from server import run_dev_server
    from app import OxiApp

    head = Head("Tina Demo App")
    head.add_item('script', '<script>console.clear(); console.info("Tina Demo App loaded.");</script>')
    menubar = NavBar("TinA Demo App", [MenuItem("Home", "/"),
                       DropdownMenu("Text", [MenuItem("A", "/a"), MenuItem("B", "/b")]),
                       DropdownMenu("Numbers", [MenuItem("One", "/one"), MenuItem("Two", "/two")]),
                       DropdownMenu("Menu Colors", [MenuItem("Normal", "/colors"), MenuItem("Reversed", "/colors?reverse")]),
                       MenuItem("About", "/about")
                       ])
    # menubar.mB = '#008f00'
    menubar.mB = '#808080'
    htmlApp = HTMLApp(head=head, body=Body(menubar))

    app = OxiApp()

    @app.get('/')
    async def home():
        return render_template(str(htmlApp), contents="<p></p><p></p><h2 style='color: steelblue; shadow: 3px;'>Home</h2>")

    @app.get('/a')
    async def a():
        return render_template(str(htmlApp), contents="<p></p><p></p><h2 style='color: red;'>A</h2>")

    @app.get('/b')
    async def b():
        return render_template(str(htmlApp), contents="<p></p><p></p><h2 style='color: green;'>B</h2>")

    @app.get('/one')
    async def one():
        return render_template(str(htmlApp), contents="<p></p><p></p><h2 style='color: magenta;'>One</h2>")

    @app.get('/two')
    async def two():
        return render_template(str(htmlApp), contents="<p></p><p></p><h2 style='color: silver;'>Two</h2>")

    @app.get('/colors')
    async def colors():

        def reversestr(s):
            l = list(s)
            l.reverse()
            return ''.join(l)


        template_filters_bak = TemplateLight.template_filters.copy()

        TemplateLight.template_filters['title'] = str.title
        TemplateLight.template_filters['capitalize'] = str.capitalize
        TemplateLight.template_filters['upper'] = str.upper
        TemplateLight.template_filters['lower'] = str.lower
        TemplateLight.template_filters['reverse'] = reversestr
        TemplateLight.template_filters['toJson'] = lambda x: json.dumps(x, ensure_ascii=False)

        retval = f"<p></p><p></p><h1 style='color: {random.choice(['red', 'green', 'blue'])}; text-align: center;'>Colors</h1>"
        retval += "<p>&nbsp;</p><p>&nbsp;</p>"
        retval += '<div>'

        reversefilter = True if b'reverse' in app.scope.get('query_string') else False

        template = '''
        {% for k, v in items %}
            <div 
              style="display:flex; 
                flex-direction: row; 
                justify-content: space-around; 
                align-items: center; 
                font-size: 200%; 
                margin-bottom: 15px;"
            >
                <span style="width: 10em; max-width: 10em; min-width: 10em; font-weight: bodld;">
                {% if rf %}
                    {{ k|upper|reverse }}
                {% else %}
                    {{ k|upper }}
                {% endif %}
                </span>
                <span 
                  style="width: 1.5em, min-width: 1.5em, max-width: 1.5em; height: 1.5em; min-height: 1.5em; 
                  max-height: 1.5em; border: solid 1px; background: {{ v }};"
                >
                    &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
                </span>
            </div>
        {% endfor %}
        '''

        retval += render_template(template, items=MenuColors.items(), rf=reversefilter)            
        retval += '</div>'
        rendered = render_template(str(htmlApp), contents=retval)
        TemplateLight.template_filters = template_filters_bak.copy()
        return rendered
    
    @app.get('/about')
    async def about():
        html="<p></p><p></p><h2 style='color: steelblue;'>Every app needs an 'about' page. This is it.</h2>"
        return render_template(str(htmlApp), contents=html)


    print("\nServer HTML content at port 8410.")
    asyncio.run(run_dev_server(app, '', 8410))

def test2():
    import sys, subprocess
    tpl = """
Hi, I am {{ user }}!
"""
    # pre = preprocess_template(tpl)
    subprocess.run(("clear",))
    usr = sys.argv[1] if len(sys.argv) > 1 else "Fico"
    src = sys.argv[2] if len(sys.argv) > 2 else "/nowhere/never"
    rendered = render_template(tpl, user= usr, source=src)
    print(rendered)

if __name__ == '__main__':
    try:
        test1()
    except KeyboardInterrupt:
        print("\nServer is going down.\nBye, bye...")
    except Exception as exc:
        print(f"\nUnexpected error: {exc}\nQuitting...")
