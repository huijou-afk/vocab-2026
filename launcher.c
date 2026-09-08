#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <mach-o/dyld.h>
#include <libgen.h>

int main(int argc, char *argv[]) {
    char exec_path[4096];
    uint32_t size = sizeof(exec_path);
    if (_NSGetExecutablePath(exec_path, &size) != 0) {
        return 1;
    }
    
    // exec_path: .../VocabGenerator.app/Contents/MacOS/VocabGenerator
    char *dir1 = dirname(exec_path);   // .../Contents/MacOS
    char *dir2 = dirname(dir1);        // .../Contents
    char *app_dir = dirname(dir2);     // .../VocabGenerator.app
    char *proj_dir = dirname(app_dir); // .../Vocab
    
    char project_path[4096];
    strncpy(project_path, proj_dir, sizeof(project_path) - 1);
    project_path[sizeof(project_path) - 1] = '\0';
    
    // Pass the project directory to python via environment variable
    setenv("VOCAB_PROJECT_DIR", project_path, 1);
    
    // Python binary path in ~/.gemini_vocab_env
    char python_path[4096];
    const char *home = getenv("HOME");
    if (!home) home = "/tmp";
    snprintf(python_path, sizeof(python_path), "%s/.gemini_vocab_env/bin/python3", home);
    
    // App script path: first check inside App Resources, fallback to project_path/app.py
    char script_path[4096];
    snprintf(script_path, sizeof(script_path), "%s/Contents/Resources/app.py", app_dir);
    if (access(script_path, R_OK) != 0) {
        snprintf(script_path, sizeof(script_path), "%s/app.py", project_path);
    }
    
    // Change working directory to project directory so slides/ and files are created there
    chdir(project_path);
    
    char *args[] = {python_path, script_path, NULL};
    execv(python_path, args);
    
    perror("execv failed");
    return 1;
}
