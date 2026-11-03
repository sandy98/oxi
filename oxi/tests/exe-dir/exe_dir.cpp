/*
 * =====================================================================================
 *
 *       Filename:  exe_dir.cpp
 *
 *    Description:  
 *
 *        Version:  1.0
 *        Created:  03/11/26 00:12:40
 *       Revision:  none
 *       Compiler:  gcc
 *
 *         Author:  YOUR NAME (), 
 *   Organization:  
 *
 * =====================================================================================
 */

#include <iostream>
#include <filesystem>

#if defined(_WIN32)
#include <windows.h>
#elif defined(__linux__)
#include <unistd.h>
#include <limits.h>
/// Lykewise for macOS, you would use _NSGetExecutablePath
#endif

std::filesystem::path get_executable_directory() {
#if defined(_WIN32)
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(NULL, path, MAX_PATH);
    return std::filesystem::path(path).parent_path();

#elif defined(__linux__)
    char path[PATH_MAX];
    ssize_t count = readlink("/proc/self/exe", path, PATH_MAX);
    if (count != -1) {
        path[count] = '\0';
        return std::filesystem::path(path).parent_path();
    }
#endif

    return ""; // Fallback
}

int main() {
    std::filesystem::path exe_dir = get_executable_directory();
    std::cout << "Executable directory: " << exe_dir << std::endl;
    try {
        // Fetch the current working directory
        std::filesystem::path cwd = std::filesystem::current_path();

        // Print it directly (or use cwd.string() / cwd.u8string())
        std::cout << "Current Working Directory: " << cwd << std::endl;
        
    } catch (const std::filesystem::filesystem_error& e) {
        std::cerr << "Error fetching CWD: " << e.what() << std::endl;
    }

    return 0;
}


