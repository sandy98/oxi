# 🚀 DETECCIÓN NATIVA DE VERSIÓN
PYTHON_VERSION := $(shell python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

PYTHON_CONFIG := python$(PYTHON_VERSION)-config

CFLAGS := $(shell $(PYTHON_CONFIG) --cflags)
LFLAGS := $(shell $(PYTHON_CONFIG) --ldflags --embed)

all: ctypes_test

ctypes_test: ctypes_test.c
	gcc -std=c17 ctypes_test.c $(CFLAGS) -rdynamic -o ctypes_test $(LFLAGS)

clean:
	$(RM) ctypes_test.c

.PHONY: all clean

