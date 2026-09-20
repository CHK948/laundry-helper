@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo    浣熊先生洗衣助手 - 一键启动
echo ============================================
echo.

REM ---- 1. 查找 Python ----
REM 注意: Microsoft Store 的 python.exe 是假的执行别名，必须实际运行验证
set "PYTHON="
py -3 --version >nul 2>nul && set "PYTHON=py -3"
if not defined PYTHON (
    python --version >nul 2>nul && set "PYTHON=python"
)
REM 兜底: 直接去常见安装目录找（应对 PATH 未刷新、商店别名占用 python 的情况）
if not defined PYTHON (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%~fD\python.exe" set PYTHON="%%~fD\python.exe"
    )
)
if not defined PYTHON (
    for /d %%D in ("%ProgramFiles%\Python3*") do (
        if exist "%%~fD\python.exe" set PYTHON="%%~fD\python.exe"
    )
)
if not defined PYTHON (
    echo [错误] 未检测到可用的 Python，请先安装 Python 3.10+。
    echo 安装时请勾选 "Add python.exe to PATH"。
    echo 如果已安装但仍报错，请在 设置 ^> 应用 ^> 高级应用设置 ^> 应用执行别名
    echo 中关闭 python.exe / python3.exe 的微软商店别名。
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [1/5] 使用 Python:
%PYTHON% --version

REM ---- 2. 配置文件 ----
if not exist "config.json" (
    if exist "config.example.json" (
        copy /y "config.example.json" "config.json" >nul
        echo [2/5] 已从 config.example.json 生成 config.json
    ) else (
        echo [2/5] 警告: 未找到 config.example.json，跳过
    )
) else (
    echo [2/5] 已存在 config.json，跳过
)

REM ---- 3. 虚拟环境 ----
if not exist ".venv\Scripts\activate.bat" (
    echo [3/5] 首次运行，正在创建虚拟环境 .venv ...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
) else (
    echo [3/5] 虚拟环境已存在，跳过
)
call ".venv\Scripts\activate.bat"

REM ---- 4. 安装依赖 ----
if not exist ".venv\.deps_installed" (
    echo [4/5] 正在安装依赖（首次较慢，请耐心等待）...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络后重试。
        pause
        exit /b 1
    )
    echo done> ".venv\.deps_installed"
) else (
    echo [4/5] 依赖已安装，跳过
)

REM ---- 5. 启动服务 ----
echo [5/5] 启动服务，浏览器将自动打开 http://127.0.0.1:8090
start "" /b cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8090"
echo.
echo 提示: 保持本窗口开启，按 Ctrl+C 可停止服务。
echo.
python app.py

echo.
echo 服务已停止。
pause
