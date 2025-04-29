#-*- coding: utf-8 -*-
import re, asyncio
from functools import wraps


######################################################################################

def safe_filename(name):
    name = name.replace(' ', '_')
    return re.sub(r'[^a-zA-Z0-9._-]', '', name)

######################################################################################

def dual_mode(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                async def async_wrapper():
                    return await asyncio.to_thread(func, *args, **kwargs)
                return async_wrapper()
        except RuntimeError:
            pass
        return func(*args, **kwargs)
    
    return wrapper

######################################################################################

async def aopen(filename:str, mode:str='r'):
    coro = asyncio.to_thread(open, filename, mode)
    return await coro

######################################################################################

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

class SmartDict(dict):
    """SmartDict class with attributes equating dict keys"""

    def __init__(self, d: dict = None, **kw):
        super().__init__(d or {}, **kw)

    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        raise AttributeError(f"'SmartDict' object has no attribute '{attr}'")

    def __setattr__(self, attr, value):
        if hasattr(dict, attr):
            raise AttributeError(f"Cannot set attribute '{attr}': reserved name")
        self[attr] = value

    def __delattr__(self, attr):
        if attr in self:
            del self[attr]
        else:
            raise AttributeError(f"'SmartDict' object has no attribute '{attr}'")

    def copy(self):
        return SmartDict(super().copy())

