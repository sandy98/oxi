# -*- coding: utf-8 -*-

import asyncio
from contextvars import ContextVar

try:
    from utils import SmartDict
except:
    from tina.utils import SmartDict

current_session = ContextVar("current_session", default=SmartDict(session_id=None, 
session_data=SmartDict(user=None)))



