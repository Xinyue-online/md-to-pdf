# install_tex.ps1：装 TinyTeX（LaTeX 引擎），配好清华镜像和缺的宏包
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File install_tex.ps1
# 安装位置：%LOCALAPPDATA%\Programs\TinyTeX
#
# 说明：
#   md-latex-pdf 靠 xelatex 编译，没装 xelatex 什么都转不出来。这里下 TinyTeX-1 的
#   Windows 版（约 70MB 的 7-Zip 自解压包），用 curl -C - 断点续传，断了重跑接着下。
#   地址先走上海交大镜像，失败回退 GitHub 直连；国内网络慢就换 $mirror 里的镜像。
$ErrorActionPreference = "Stop"

$exe = Join-Path $env:TEMP "TinyTeX-1-windows.exe"
$dest = Join-Path $env:LOCALAPPDATA "Programs"
$tinytex = Join-Path $dest "TinyTeX"

# 取最新 release 里的 Windows 安装包地址
Write-Host "==> 查询 TinyTeX 最新版本 ..."
$api = Invoke-RestMethod "https://api.github.com/repos/rstudio/tinytex-releases/releases/latest" -UseBasicParsing
$asset = $api.assets | Where-Object { $_.name -like "TinyTeX-1-windows-*.exe" } | Select-Object -First 1
if (-not $asset) { throw "未找到 TinyTeX-1 Windows 安装包（release: $($api.tag_name)）" }
$url = $asset.browser_download_url
$expected = $asset.size

# 下载：本地已有文件就接着传；先去镜像，失败回退 GitHub
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
if ($size -lt $expected) { throw "下载不完整：$size / $expected bytes。重跑本脚本会接着续传。" }
Write-Host "    size: $size bytes"

Write-Host "==> SFX 解压到 $dest ..."
if (Test-Path $tinytex) { Write-Host "    目录已存在，覆盖解压..." }
& $exe "-o$dest" -y
if ($LASTEXITCODE -ne 0) { throw "SFX 解压失败（exit $LASTEXITCODE），TinyTeX 没装好，重跑本脚本会重新解压。" }

$tlmgr = Join-Path $tinytex "bin\windows\tlmgr.bat"
if (-not (Test-Path $tlmgr)) { throw "解压完没找到 $tlmgr，解压不完整，重跑本脚本再解一次。" }
Write-Host "==> tlmgr: $tlmgr"

# tlmgr 的包源换成清华（国内连得上；海外可以换成 https://mirrors.ctan.org/systems/texlive/tlnet）
Write-Host "==> 配置 tlmgr 镜像（清华 CTAN）..."
& $tlmgr option repository "https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet" 2>&1 | Out-Null
& $tlmgr update --self 2>&1 | Out-Null
& $tlmgr path add 2>&1 | Out-Null

# TinyTeX-1 缺的宏包（现在 TeX Live 的命名：mathrsfs 归在 jknapltx，algorithm 归在 algorithms）。
# 下面是 md-latex-pdf 两个模板（templates\default.tex、academic.tex）用到的全部宏包，
# 少一个就是文档里用到、编译直接报缺包：
#   表格  booktabs/tabularx/array/longtable/multicol/float/pifont
#   数学  amsthm/amssymb；物理单位 siunitx；化学/核素 mhchem
#   参考文献 natbib 只在 academic.tex 里用（本机 TinyTeX-1 自带，列在这儿是给别的机器）
# tlmgr 碰到已装的包是 no-op，重复装没关系。
Write-Host "==> 补装必需宏包 ..."
& $tlmgr install ctex xecjk fandol tcolorbox environ trimspaces ulem listings `
    mathrsfs subfig enumitem caption multirow makecell anyfontsize fancyhdr `
    jknapltx algorithms algorithmicx pdfpages tikzfill pdfcol natbib `
    booktabs tabularx array longtable multicol float pifont amsthm amssymb `
    graphicx xcolor geometry hyperref mhchem siunitx 2>&1 | Out-Null

$xelatex = Join-Path $tinytex "bin\windows\xelatex.exe"
Write-Host ""
Write-Host "==> 装完了。验证 xelatex："
& $xelatex --version | Select-Object -First 2
Write-Host ""
Write-Host "    之后就能跑：md-latex-pdf example.md"
