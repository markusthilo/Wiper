@echo off
echo Building Wiper distribution...

REM Clean up any existing distribution folders
if exist wiper.dist (
    echo Cleaning existing distribution folder wiper.dist...
    del wiper.dist\* /Q
)

REM Build the standalone executable with Nuitka and gcc/mingw
REM echo Building executable with Nuitka...
REM call nuitka --windows-icon-from-ico=appicon.ico --windows-console-mode=disable --standalone --enable-plugin=tk-inter --windows-uac-admin wiper.py
echo Building executable with gcc...
REM This is the path to gcc installed by Nuitka
call C:\Users\THI\AppData\Local\Nuitka\Nuitka\Cache\downloads\gcc\x86_64\14.2.0posix-19.1.1-12.0.0-msvcrt-r2\mingw64\bin\gcc.exe -o zd-win.exe zd-win.c

REM Copy configuration and resource files
REM echo Copying configuration and resource files...
REM robocopy ./ ./wiper.dist appicon.png LICENSE README.md *.json

echo Distribution build complete!
echo Files are available in the wiper.dist directory.