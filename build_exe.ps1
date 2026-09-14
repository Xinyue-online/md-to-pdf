# build_exe.ps1：用 PyInstaller 把 md-latex-pdf 打包成单文件 exe
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File build_exe.ps1
# 产物：
#   dist\md-latex-pdf.exe（单文件，--windowed 不带控制台，双击直接开窗口）
#
# 说明：
#   - 入口是 md_latex_pdf_gui.py；核心转换 md_latex_pdf.py 被它 import，会跟着打进去；
#   - 要带 --collect-data tkinterdnd2，把 tkdnd（Tk 拖拽扩展）的二进制和 Tcl 脚本收进 exe。
#     少了它，打包版启动时 tkdnd 加载失败，拖放没反应，只能退回「选择文件」；
#   - 目标机器仍要装 xelatex，见 install_tex.ps1。
#
# 想要命令行版 exe（带控制台，方便脚本调用）：入口换成 md_latex_pdf.py，--windowed
# 换成 --console，--name 改成 md-latex-pdf-cli。两个名字不冲突，可以各打一个。
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# 1. 装 PyInstaller（已经装了就不重复装）
python -m pip show pyinstaller 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "==> 安装 PyInstaller ..."
    python -m pip install pyinstaller
}

# 2. 打包：GUI 入口、不带控制台、收集 tkdnd 数据。产物名就是 md-latex-pdf.exe（无后缀）。
# 下面三条是打包时最容易踩的：
# 注意 1：md-latex-pdf.spec 会被 PyInstaller 按这条命令行重写，--add-data 对应的 datas
#         也在里面。手改 spec 没用，下次打包就覆盖掉了。
# 注意 2：本脚本含中文，必须存成「UTF-8 with BOM」。没 BOM 时 Windows PowerShell 5.1
#         按 ANSI 解码，中文变乱码、字符串终止符被吃掉，脚本直接解析不过。
# 注意 3：dist\md-latex-pdf.exe 正在运行（GUI 还开着）时无法覆盖，PyInstaller 报
#         PermissionError，先关窗口再打包。下面显式查退出码，免得没打成功还打印完成。
Write-Host "==> PyInstaller 打包 md-latex-pdf.exe（不带控制台）..."
# --add-data 把 templates\ 一起收进 exe（运行时解包到 sys._MEIPASS）。不打包的话，exe
# 找不到默认模板，启动就报「排版模板不存在」。换模板不用重新打包，--template 可以指向
# 外部的 .tex。
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name md-latex-pdf `
    --collect-data tkinterdnd2 `
    --add-data "templates;templates" `
    md_latex_pdf_gui.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Error "PyInstaller 打包失败（exit $LASTEXITCODE）。如果报的是 PermissionError 指着 dist\md-latex-pdf.exe，说明 exe 正在运行：关掉 md-latex-pdf 窗口再重跑本脚本。其他错误看上面 PyInstaller 的输出。"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "==> 完成：dist\md-latex-pdf.exe（双击即打开转换窗口，不带控制台）"
Write-Host "    不想开窗口就用 python 版：python md_latex_pdf.py example.md"
