# install_tex.ps1 — 一键安装 TinyTeX（LaTeX 引擎）并配置清华镜像 + 必需宏包
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File install_tex.ps1
# 安装位置：%LOCALAPPDATA%\Programs\TinyTeX
#
# 说明：
#   md-to-pdf 依赖 xelatex 编译。本脚本下载 TinyTeX-1 Windows 版（约 70MB，7-Zip
#   自解压包），支持断点续传（curl -C -）。下载源优先国内镜像（上海交大 SJTU），
#   失败自动回退 GitHub 直连。国内网络慢时可将 $url 换成任意可用镜像。
$ErrorActionPreference = "Stop"

$exe = Join-Path $env:TEMP "TinyTeX-1-windows.exe"
$dest = Join-Path $env:LOCALAPPDATA "Programs"
$tinytex = Join-Path $dest "TinyTeX"

# 获取最新 release 的 Windows 安装包地址
Write-Host "==> 查询 TinyTeX 最新版本 ..."
$api = Invoke-RestMethod "https://api.github.com/repos/rstudio/tinytex-releases/releases/latest" -UseBasicParsing
$asset = $api.assets | Where-Object { $_.name -like "TinyTeX-1-windows-*.exe" } | Select-Object -First 1
if (-not $asset) { throw "未找到 TinyTeX-1 Windows 安装包（release: $($api.tag_name)）" }
$url = $asset.browser_download_url
$expected = $asset.size

# 下载（复用已有文件 + curl 断点续传；优先国内镜像，失败回退 GitHub）
$mirror = "https://mirrors.sjtug.sjtu.edu.cn/github-release/rstudio/tinytex-releases/releases/download/$($api.tag_name)/$($asset.name)"
$used = $mirror
if (Test-Path $exe) {
    $cur = (Get-Item $exe).Length
    if ($cur -ge $expected) {
        Write-Host "==> 已存在完整安装包，跳过下载"
    } else {
        Write-Host "==> 已有 $([math]::Round($cur/1MB,1)) MB，断点续传 ..."
        & curl.exe -sL -C - --retry 5 --retry-delay 5 --retry-all-errors --connect-timeout 20 -o $exe $used 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "    镜像失败，回退 GitHub ..."
            & curl.exe -sL -C - --retry 5 --retry-delay 5 --retry-all-errors --connect-timeout 20 -o $exe $url 2>$null
        }
    }
} else {
    Write-Host "==> 下载 $($asset.name)（$($used)）..."
    & curl.exe -sL --retry 5 --retry-delay 5 --retry-all-errors --connect-timeout 20 -o $exe $used 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    镜像失败，回退 GitHub ..."
        & curl.exe -sL --retry 5 --retry-delay 5 --retry-all-errors --connect-timeout 20 -o $exe $url 2>$null
    }
}
$size = (Get-Item $exe).Length
if ($size -lt $expected) { throw "下载不完整：$size / $expected bytes，请重跑本脚本续传" }
Write-Host "    size: $size bytes"

Write-Host "==> SFX 解压到 $dest ..."
if (Test-Path $tinytex) { Write-Host "    目录已存在，覆盖解压..." }
& $exe "-o$dest" -y
if ($LASTEXITCODE -ne 0) { throw "SFX 解压失败（exit $LASTEXITCODE）" }

$tlmgr = Join-Path $tinytex "bin\windows\tlmgr.bat"
if (-not (Test-Path $tlmgr)) { throw "解压后未找到 tlmgr.bat" }
Write-Host "==> tlmgr: $tlmgr"

# 使用清华镜像（国内可达；海外可改为 https://mirrors.ctan.org/systems/texlive/tlnet）
Write-Host "==> 配置 tlmgr 镜像（清华 CTAN）..."
& $tlmgr option repository "https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet" 2>&1 | Out-Null
& $tlmgr update --self 2>&1 | Out-Null
& $tlmgr path add 2>&1 | Out-Null

# TinyTeX-1 缺失的宏包（TL2026 命名：mathrsfs 在 jknapltx、algorithm 在 algorithms）。
# 覆盖 md-to-pdf 模板（templates\default.tex 与 academic.tex）用到的全部宏包，
# 避免"内容用到→编译失败"：
#   表格  booktabs/tabularx/array/longtable/multicol/float/pifont
#   数学  amsthm/amssymb；物理单位 siunitx；化学/核素 mhchem
#   参考文献 natbib 只在 academic.tex 里用（本机 TinyTeX-1 自带，列在这里是为别的机器）
# 注：tlmgr 对已存在的包是 no-op，重复安装无害。
Write-Host "==> 补装必需宏包 ..."
& $tlmgr install ctex xecjk fandol tcolorbox environ trimspaces ulem listings `
    mathrsfs subfig enumitem caption multirow makecell anyfontsize fancyhdr `
    jknapltx algorithms algorithmicx pdfpages tikzfill pdfcol natbib `
    booktabs tabularx array longtable multicol float pifont amsthm amssymb `
    graphicx xcolor geometry hyperref mhchem siunitx 2>&1 | Out-Null

$xelatex = Join-Path $tinytex "bin\windows\xelatex.exe"
Write-Host ""
Write-Host "==> 完成。验证："
& $xelatex --version | Select-Object -First 2
Write-Host ""
Write-Host "    现在可用：md-to-pdf example.md"
