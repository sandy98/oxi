# -*- coding: utf-8 -*-

from contextvars import ContextVar

from utils import SmartDict

current_session = ContextVar("current_session", default=SmartDict(user=None))
