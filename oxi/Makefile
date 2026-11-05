# 🚀 DETECCIÓN NATIVA DE VERSIÓN
PYTHON_VERSION := $(shell python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

PYTHON_CONFIG := python$(PYTHON_VERSION)-config

CFLAGS := $(shell $(PYTHON_CONFIG) --cflags)
LFLAGS := $(shell $(PYTHON_CONFIG) --ldflags --embed)

all: server

server: src/server.cpp src/server.hpp src/request.hpp
	@echo "Compiling src/server.cpp with C++23 and Python $(PYTHON_VERSION) embedding..."
	$(CXX) -std=c++23 src/server.cpp $(CFLAGS) -o server $(LFLAGS)

clean:
	$(RM) server
	# Restore the stub so the package is in its original state
	cp server.stub server
	chmod +x server

.PHONY: all clean