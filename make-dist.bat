@echo off
echo Building Wiper distribution...

REM Clean up any existing distribution folders
if exist wiper.dist (
    echo Cleaning existing distribution folder wiper.dist...
    del wiper.dist\* /Q
)

REM Build the standalone executable with Nuitka and gcc/mingw
echo Building executable with Nuitka...
call nuitka --windows-icon-from-ico=appicon.ico --windows-console-mode=disable --standalone --enable-plugin=tk-inter --windows-uac-admin wiper.py
echo Building executable with gcc...
call C:\Users\user\AppData\Local\Nuitka\Nuitka\Cache\downloads\gcc\x86_64\14.2.0posix-19.1.1-12.0.0-msvcrt-r2\mingw64\bin\gcc.exe -o wiper.dist\zd-win.exe zd-win.c

REM Copy configuration and resource files
echo Copying configuration and resource files...
robocopy ./ ./wiper.dist appicon.png LICENSE README.md *.json

echo Distribution build complete!
echo Files are available in the wiper.dist directory.