@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM compile.bat ---- 一键编译 LaTeX 教材项目
REM
REM 双击或命令行运行即可编译当前目录的 main.tex。
REM 产物只进 build/，项目根目录零残留。
REM
REM 用法：
REM   双击本文件                     → 用默认引擎编译
REM   compile.bat                    → 同上
REM   compile.bat lualatex           → 用 lualatex 编译
REM   compile.bat xelatex 5          → 用 xelatex 编译，最多 5 遍
REM
REM 前提：当前目录含 main.tex + preamble.tex + chapters/ + images/。
REM 编译产物全部输出到 build/ 子目录。
REM ============================================================
setlocal enabledelayedexpansion

REM --- 配置区（按实际环境修改）---
REM skill 仓库路径（compile_tex.py 所在目录）
set "SKILL_DIR=D:\Documents\02_Programming\pdf-textbook-to-tex-textbook"
REM 默认编译引擎（xelatex 或 lualatex）
set "DEFAULT_ENGINE=xelatex"
REM --- 配置区结束 ---

REM 解析命令行参数
set "ENGINE=%DEFAULT_ENGINE%"
set "MAX_PASSES=3"
if not "%~1"=="" set "ENGINE=%~1"
if not "%~2"=="" set "MAX_PASSES=%~2"

REM 确认 main.tex 存在
if not exist "main.tex" (
    echo [FAIL] 当前目录找不到 main.tex
    echo        请将本文件放到含 main.tex 的项目根目录后运行
    pause
    exit /b 1
)

set "COMPILE_PY=%SKILL_DIR%\scripts\compile_tex.py"

if exist "%COMPILE_PY%" (
    echo === 使用 compile_tex.py（完整模式：自动补跑收敛 + 摘要）===
    python "%COMPILE_PY%" . --engine %ENGINE% --passes %MAX_PASSES%
) else (
    echo === 未找到 compile_tex.py，回退到直接编译模式 ===
    echo     路径: %COMPILE_PY%
    echo.
    if not exist build mkdir build

    for /l %%i in (1,1,%MAX_PASSES%) do (
        echo --- 第 %%i/%MAX_PASSES% 遍（%ENGINE%）---
        %ENGINE% -interaction=nonstopmode -output-directory=build main.tex
        if errorlevel 1 (
            echo [FAIL] 编译失败，返回码 !errorlevel!
            pause
            exit /b !errorlevel!
        )
        REM 清理根目录残留（Windows 下 -output-directory 未完全隔离）
        for %%e in (aux log out toc pdf synctex synctex.gz fls fdb_latexmk xdv blg bbl) do (
            if exist "main.%%e" del /q "main.%%e" 2>nul
        )
    )

    echo.
    echo === 编译完成，产物位于 build/ ===
    if exist "build\main.pdf" (
        echo PDF: build\main.pdf
    ) else (
        echo [WARN] build\main.pdf 不存在，请检查编译错误
    )
)

echo.
pause