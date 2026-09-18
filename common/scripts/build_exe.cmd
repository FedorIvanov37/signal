@echo off
rem Build signal.exe using the manifest beside build_exe.py.
rem Output: common/bin/signal.exe; replaced only after a successful build.
rem Implementation: common/core/toolkit/build_binary/build_exe.py
rem Requires Python 3.12 in LOCALAPPDATA/Programs/Python/Python312,
rem the application dependencies, and PyInstaller in that Python environment.
rem Usage from the project root: common\scripts\build_exe.cmd
rem Can also be launched by its full path from any working directory.
rem Intermediate files use system Temp and are removed when the build exits.
rem Prepares default config/theme in Temp; existing Signal settings are untouched.
rem Local appearance and splitter layout files are excluded from bundled assets.
rem This builds only the binary; it does not collect a release or runtime data.
rem It does not run the EXE or move it to the project root.

"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%~dp0..\core\toolkit\build_binary\build_exe.py"
exit /b %errorlevel%
