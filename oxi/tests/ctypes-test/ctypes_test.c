/*
 * =====================================================================================
 *
 *       Filename:  ctypes_test.c
 *
 *    Description:  
 *
 *        Version:  1.0
 *        Created:  30/10/26 13:54:40
 *       Revision:  none
 *       Compiler:  gcc
 *
 *         Author:  Domingo E. Savoretti 
 *   Organization:  
 *
 * =====================================================================================
 */

#include <Python.h>

#include <stdio.h>
#include <stdlib.h>

// __attribute__((visibility("default")))
// __attribute__((used))
void greet() {
    printf("%s\n%s\n", "Hello, Welcome to embedded Python!", "This is a greeting from C!!");
}

void pygreet() {
    
    PyGILState_STATE gstate = PyGILState_Ensure();

    PyRun_SimpleString(
        "import ctypes\n"
        "print('\033[36m[Python]\033[0m This is a greeting from inside embedded Python!!')\n"
        "cgreet = ctypes.CDLL(None).greet\n"
        "cgreet()\n"
    );

    PyGILState_Release(gstate);
}

int main(int argc, char* argv[]) {
    // greet();
    Py_Initialize();
    pygreet();
    Py_FinalizeEx();
}


