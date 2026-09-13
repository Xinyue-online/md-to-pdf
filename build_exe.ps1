# build_exe.ps1 — 用 PyInstaller 把 md-to-pdf 图形界面打包为「无黑框」单文件 exe
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File build_exe.ps1
# 产物：
#   dist\md-to-pdf.exe（单文件、--windowed 无控制台黑框；双击即打开拖放式转换窗口）
#
# 说明：
#   - 入口用 md_to_pdf_gui.py（GUI），核心转换 md_to_pdf.py 因被 import 而自动打入；
#   - 用 --collect-data tkinterdnd2 打包 tkdnd（Tk 拖拽扩展）的二进制与 Tcl 脚本；
#   - 运行时目标机器仍需 xelatex（见 install_tex.ps1）。GUI 内 tkdnd 加载失败会
#     自动退回「选择文件」，因此窗口总能打开。
#
# 若还要「命令行版」exe（会带黑框，供脚本调用）：把入口换成 md_to_pdf.py，
# 并把 --windowed 换成 --console、--name 改为 md-to-pdf-cli 即可（独立命名，互不覆盖）。
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# 1. 安装 PyInstaller（如已装则跳过）
python -m pip show pyinstaller 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "==> 安装 PyInstaller ..."
    python -m pip install pyinstaller
}

# 2. 打包（GUI 入口、无控制台、收集 tkdnd 拖拽数据）——产物名沿用 md-to-pdf.exe（无后缀）
# 注意 1：md-to-pdf.spec 由 PyInstaller 按下面的命令行**自动重写**（含 --add-data 的
#         datas），所以不要手改 spec —— 改了会在下次打包时被覆盖。
# 注意 2：本脚本含中文，必须存成「UTF-8 with BOM」。无 BOM 时 Windows PowerShell 5.1
#         按 ANSI 解码，中文乱码、字符串终止符被吃掉，脚本直接解析失败。
# 注意 3：dist\md-to-pdf.exe 正在运行（GUI 开着）时无法覆盖，PyInstaller 会报
#         PermissionError；先关掉窗口再打包。下面显式检查退出码，避免"没打成功却打印完成"。
Write-Host "==> PyInstaller 打包 md-to-pdf.exe（无黑框）..."
# --add-data 把默认排版模板 templates\default.tex 一并收进 exe（解包到 sys._MEIPASS），
# 否则打包版找不到默认模板、启动即报「排版模板不存在」。换模板无需重打包：
# exe 支持 --template 指向外部 .tex。
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name md-to-pdf `
    --collect-data tkinterdnd2 `
    --add-data "templates;templates" `
    md_to_pdf_gui.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Error "PyInstaller 打包失败（exit $LASTEXITCODE）。若提示 PermissionError: dist\md-to-pdf.exe，请先关闭正在运行的 md-to-pdf 窗口再重试。"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "==> 完成：dist\md-to-pdf.exe（双击即打开转换窗口，无黑色控制台）"
Write-Host "    命令行转换（python 版）：python md_to_pdf.py example.md"
