#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md-latex-pdf — Markdown → LaTeX → PDF（用 xelatex 编译）。

排版走 LaTeX：衬线字体、章节自动编号、booktabs 表格、定理式彩色框，整体紧凑，
封面是纯色背景配黑字。支持的 Markdown 语法：
  标题 #~######（自动编号）、段落、粗体/斜体/删除线、行内代码、围栏代码块（语法高亮）、
  表格（对齐、长表自动转 longtable）、有序/无序/嵌套/任务列表、引用、分隔线、
  链接/自动链接、图片（本地图片自动复制进输出目录）、脚注、数学公式（LaTeX 渲染，
  不需要 KaTeX）、GitHub 风格告示框 >[!NOTE]/[!TIP]/[!IMPORTANT]/[!WARNING]/[!CAUTION]、
  引述标记 > ❗/⚠/💡（与告示框共用同一套彩色框）、强制分页 ::page。

用法：
    md-latex-pdf input.md [输出目录] [--header 页眉文字] [--cover-color #RRGGBB]
                    [--no-numbers] [--no-toc] [--toc-depth 3] [--keep-aux] [--open]
                    [--template 我的模板.tex]
    md-latex-pdf            # 不带参数启动图形界面（拖入 .md 即可转换）

排版规则放在可替换的模板文件里：缺省用 templates/default.tex，
用 --template 指向别的 .tex 就能整套换掉导言区与排版规则。
产物：<同名>.tex（可编辑的 LaTeX 中间产物）与 <同名>.pdf。
依赖：本机装上 xelatex（TinyTeX/MiKTeX/TeX Live 都行，见 install_tex.ps1）。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# SYMBOL_FALLBACKS —— 正文符号回退表（CJK 字体缺字形 → 等价的 LaTeX 数学命令）
# ---------------------------------------------------------------------------
# ctexart 的中文字体（SimSun/FangSong）只覆盖一部分数学符号。实测
# "0370-03FF / 2070-209F / 2190-21FF / 2200-22FF / 2460-24FF 五个区间共 705 个
# 已分配码位，SimSun 缺 562 个"：∈ ∪ ∩ ∧ ∨ → ← ↑ ↓ ∑ ∏ ∫ √ ∞ ≠ ≤ ≥ 这些有字形，
# 而 ∀ ∃ ∅ ⊂ ⊆ ⇒ ⇐ ⇔ ↦ ∂ ∇ ⊗ 以及上标 ⁴⁻ⁿ、下标 ₀₂ 等直接写进正文会渲染成**空白**
# （xelatex 只在 .log 里报一条 "Missing character"，PDF 上就是缺一块）。
# 处理办法是把这些缺字形的常用符号声明为活动字符，展开成等价的数学命令，交给数学
# 字体（Latin Modern Math）排；\ensuremath 幂等，所以在数学模式里写 $∀$ 同样正确。
# 表外的字符（包括 CJK 字体本来就有字形的 σ μ ∈ ∑ 等）保持原样，行为不变。
#
# 收录标准只有一条：实测确实画不出来。要么落在上述区间里但中文字体没字形，要么
# 落在区间外而西文主字体没字形（tests/measure_coverage.py 按这两条重算并列出多余条目）。
# 所以这里不放 ′ ″ ■ □ ▲ ● Ⅰ Ⅱ Ⅲ 这类"交给中文字体就行"的符号（它们在导言区
# 的 xeCJK 字符类声明里），也不放 ≮ ≯ ℧ 这类西文字体本来就有的符号。
# 例外：¹ ² ³ 单看能显示，可它们和 ⁴⁻ⁿ 是同一串角标，混用两种字体会大小不一，一并收进来。
#
# 扩展：在下面加一行（键 = 正文字符，值 = 等价的 LaTeX 代码），改完跑一遍
# test_symbol_fallback.py。它会逐符号编译，能抓出 "命令不存在" 这类错误。
SYMBOL_FALLBACKS: dict[str, str] = {
    # 逻辑与集合
    "∀": r"\ensuremath{\forall}",
    "∃": r"\ensuremath{\exists}",
    "∄": r"\ensuremath{\nexists}",
    "∅": r"\ensuremath{\varnothing}",
    "∉": r"\ensuremath{\notin}",
    "∋": r"\ensuremath{\ni}",
    "∌": r"\ensuremath{\not\ni}",
    "⊂": r"\ensuremath{\subset}",
    "⊃": r"\ensuremath{\supset}",
    "⊄": r"\ensuremath{\not\subset}",
    "⊆": r"\ensuremath{\subseteq}",
    "⊇": r"\ensuremath{\supseteq}",
    "⊊": r"\ensuremath{\subsetneq}",
    "⊋": r"\ensuremath{\supsetneq}",
    "∖": r"\ensuremath{\setminus}",
    # 箭头
    "↔": r"\ensuremath{\leftrightarrow}",
    "↕": r"\ensuremath{\updownarrow}",
    "⇐": r"\ensuremath{\Leftarrow}",
    "⇒": r"\ensuremath{\Rightarrow}",
    "⇔": r"\ensuremath{\Leftrightarrow}",
    "↦": r"\ensuremath{\mapsto}",
    "⇀": r"\ensuremath{\rightharpoonup}",
    "⇁": r"\ensuremath{\rightharpoondown}",
    # 运算符与关系
    "∬": r"\ensuremath{\iint}",
    "∂": r"\ensuremath{\partial}",
    "∇": r"\ensuremath{\nabla}",
    "−": r"\ensuremath{-}",
    "∓": r"\ensuremath{\mp}",
    "⋅": r"\ensuremath{\cdot}",
    "∘": r"\ensuremath{\circ}",
    "∗": r"\ensuremath{\ast}",
    "∙": r"\ensuremath{\bullet}",
    "≃": r"\ensuremath{\simeq}",
    "≅": r"\ensuremath{\cong}",
    "≪": r"\ensuremath{\ll}",
    "≫": r"\ensuremath{\gg}",
    "≺": r"\ensuremath{\prec}",
    "≻": r"\ensuremath{\succ}",
    "⊢": r"\ensuremath{\vdash}",
    "⊨": r"\ensuremath{\vDash}",
    "⊖": r"\ensuremath{\ominus}",
    "⊗": r"\ensuremath{\otimes}",
    "⊘": r"\ensuremath{\oslash}",
    "⋯": r"\ensuremath{\cdots}",
    "⋮": r"\ensuremath{\vdots}",
    # 上下界括号（数学里常用，中文字体没有）
    "⌈": r"\ensuremath{\lceil}", "⌉": r"\ensuremath{\rceil}",
    "⌊": r"\ensuremath{\lfloor}", "⌋": r"\ensuremath{\rfloor}",
    # 形近/不等号家族（\not 组合优先：amssymb 里 \napprox/\nsimeq/\nsubset 并不存在）
    "≢": r"\ensuremath{\not\equiv}",
    "≁": r"\ensuremath{\nsim}",
    "≄": r"\ensuremath{\not\simeq}",
    "≇": r"\ensuremath{\ncong}",
    "≉": r"\ensuremath{\not\approx}",
    "≊": r"\ensuremath{\approxeq}",
    "≂": r"\ensuremath{\eqsim}",
    "≀": r"\ensuremath{\wr}",
    "∼": r"\ensuremath{\sim}",
    "≲": r"\ensuremath{\lesssim}", "≳": r"\ensuremath{\gtrsim}",
    "≰": r"\ensuremath{\nleq}", "≱": r"\ensuremath{\ngeq}",
    "⊅": r"\ensuremath{\not\supset}",
    "⊈": r"\ensuremath{\nsubseteq}", "⊉": r"\ensuremath{\nsupseteq}",
    "∤": r"\ensuremath{\nmid}", "∦": r"\ensuremath{\nparallel}",
    # 其它常用运算符
    "∁": r"\ensuremath{\complement}",
    "∆": r"\ensuremath{\Delta}",
    "∎": r"\ensuremath{\blacksquare}",
    "∐": r"\ensuremath{\coprod}",
    "∔": r"\ensuremath{\dotplus}",
    "∭": r"\ensuremath{\iiint}",
    "∡": r"\ensuremath{\measuredangle}", "∢": r"\ensuremath{\sphericalangle}",
    # 数学字母（实变/代数讲义里的 ℝ ℕ ℤ ℚ ℂ）
    "ℝ": r"\ensuremath{\mathbb{R}}", "ℕ": r"\ensuremath{\mathbb{N}}",
    "ℤ": r"\ensuremath{\mathbb{Z}}", "ℚ": r"\ensuremath{\mathbb{Q}}",
    "ℂ": r"\ensuremath{\mathbb{C}}", "ℙ": r"\ensuremath{\mathbb{P}}",
    "ℍ": r"\ensuremath{\mathbb{H}}",
    "ℓ": r"\ensuremath{\ell}", "ℏ": r"\ensuremath{\hbar}",
    "℘": r"\ensuremath{\wp}", "ℵ": r"\ensuremath{\aleph}",
    "ℑ": r"\ensuremath{\Im}", "ℜ": r"\ensuremath{\Re}",
    "Å": r"\ensuremath{\text{\AA}}",
    # 勾叉（清单常用；pifont 已在模板里加载。编号按 ZapfDingbats 码位：
    # 0x33=✓ 0x34=✔ 0x37=✗ 0x38=✘，即 \ding{51/52/55/56}）
    "✓": r"\ding{51}", "✔": r"\ding{52}", "✗": r"\ding{55}", "✘": r"\ding{56}",
    # 复选框（中文字体没有 ☐☑☒；勾选框沿用本工具任务列表的 \square/\boxtimes 风格）
    "☐": r"\ensuremath{\square}", "☑": r"\ensuremath{\boxtimes}", "☒": r"\ensuremath{\boxtimes}",
    # 罗马数字补全：Ⅰ-Ⅻ 已在 xeCJK 字符类里由中文字体排，50/100/500/1000 中文字体没有
    "Ⅼ": r"\ensuremath{\mathrm{L}}", "Ⅽ": r"\ensuremath{\mathrm{C}}",
    "Ⅾ": r"\ensuremath{\mathrm{D}}", "Ⅿ": r"\ensuremath{\mathrm{M}}",
    # 带圈 11-20（①②…⑩ 中文字体有；两位数用圈起来的小号数字，实测圈宽不溢出）
    "⑪": r"\textcircled{\scriptsize 11}", "⑫": r"\textcircled{\scriptsize 12}",
    "⑬": r"\textcircled{\scriptsize 13}", "⑭": r"\textcircled{\scriptsize 14}",
    "⑮": r"\textcircled{\scriptsize 15}", "⑯": r"\textcircled{\scriptsize 16}",
    "⑰": r"\textcircled{\scriptsize 17}", "⑱": r"\textcircled{\scriptsize 18}",
    "⑲": r"\textcircled{\scriptsize 19}", "⑳": r"\textcircled{\scriptsize 20}",
    # 分数（中文字体没有 ⅓ ⅔ 等；西文 ½ ¼ ¾ 本来就有，不必管）
    "⅓": r"\ensuremath{\frac{1}{3}}", "⅔": r"\ensuremath{\frac{2}{3}}",
    "⅕": r"\ensuremath{\frac{1}{5}}", "⅖": r"\ensuremath{\frac{2}{5}}",
    "⅗": r"\ensuremath{\frac{3}{5}}", "⅘": r"\ensuremath{\frac{4}{5}}",
    "⅙": r"\ensuremath{\frac{1}{6}}", "⅚": r"\ensuremath{\frac{5}{6}}",
    "⅛": r"\ensuremath{\frac{1}{8}}", "⅜": r"\ensuremath{\frac{3}{8}}",
    "⅝": r"\ensuremath{\frac{5}{8}}", "⅞": r"\ensuremath{\frac{7}{8}}",
    # 角标：⁴⁵…⁹⁻ⁿ₀₁…₉ 中文字体没有字形；¹²³ 虽有（拉丁补充区）但同一串角标
    # 混用两种字形会大小不一，故一并走同一条路（数学字体）。
    "⁰": r"\ensuremath{^{0}}", "¹": r"\ensuremath{^{1}}", "²": r"\ensuremath{^{2}}",
    "³": r"\ensuremath{^{3}}", "⁴": r"\ensuremath{^{4}}", "⁵": r"\ensuremath{^{5}}",
    "⁶": r"\ensuremath{^{6}}", "⁷": r"\ensuremath{^{7}}", "⁸": r"\ensuremath{^{8}}",
    "⁹": r"\ensuremath{^{9}}", "⁺": r"\ensuremath{^{+}}", "⁻": r"\ensuremath{^{-}}",
    "⁼": r"\ensuremath{^{=}}", "⁽": r"\ensuremath{^{(}}", "⁾": r"\ensuremath{^{)}}",
    "ⁿ": r"\ensuremath{^{n}}", "₀": r"\ensuremath{_{0}}", "₁": r"\ensuremath{_{1}}",
    "₂": r"\ensuremath{_{2}}", "₃": r"\ensuremath{_{3}}", "₄": r"\ensuremath{_{4}}",
    "₅": r"\ensuremath{_{5}}", "₆": r"\ensuremath{_{6}}", "₇": r"\ensuremath{_{7}}",
    "₈": r"\ensuremath{_{8}}", "₉": r"\ensuremath{_{9}}", "₊": r"\ensuremath{_{+}}",
    "₋": r"\ensuremath{_{-}}", "₌": r"\ensuremath{_{=}}", "₍": r"\ensuremath{_{(}}",
    "₎": r"\ensuremath{_{)}}",
}

# ---------------------------------------------------------------------------
# EMOJI_ICONS —— 表情/警示符号回退表（❗ ⚠ 💡 → Segoe UI Symbol 的字形）
# ---------------------------------------------------------------------------
# 和 SYMBOL_FALLBACKS 不同：这三个是图形，没有等价的 LaTeX 数学写法，所以没法映射成
# 数学命令，只能切到一个这三个字形都齐的西文字体，再排原字符。
# 后果一样是空白：中文字体（SimSun/FangSong）和西文主字体 Latin Modern 都没有
# U+2757/U+26A0/U+1F4A1 的字形，直接写进正文 xelatex 只报一条 Missing character，
# PDF 上缺一块。Windows 自带的 Segoe UI Symbol 三个字形都有（含星平面 U+1F4A1）。
#
#   ❗ U+2757 → \mdpdfIconExcl    ⚠ U+26A0 → \mdpdfIconWarn    💡 U+1F4A1 → \mdpdfIconBulb
#
# 活动字符机制与 SYMBOL_FALLBACKS 共用（\mdpdfSymbol），正文、标题、表格单元格、
# 告示框、页眉、行内代码里的写法一致。机器上没有这个字体时走 \IfFontExistsTF 的空
# 分支，三个字符被丢弃，既不留空白格也不报错。
# U+FE0F（变体选择符，❗️/⚠️ 的第二个码位）是零宽控制符，在 convert_file 里直接删掉。
EMOJI_ICONS: dict[str, str] = {
    "❗": r"\mdpdfIconExcl",
    "⚠": r"\mdpdfIconWarn",
    "💡": r"\mdpdfIconBulb",
}
_EMOJI_FONT = "Segoe UI Symbol"

# 宏体里的 ❗ ⚠ 💡 在设置活动字符之前就被读进宏定义了（那时它们还是普通字符，
# catcode 12），所以展开时不会再次触发活动字符，不会无限递归。
_EMOJI_PREAMBLE = r"""
%----- 表情/警示符号 ❗ ⚠ 💡（切到 Windows 自带的 Segoe UI Symbol）-----
% 三个图标宏都必须在这里（活动字符声明之前）定义完；换字体只在图标宏内部生效，
% 正文其它字符不受影响。\mbox 是为了数学模式里也安全（$❗$ 与正文 ❗ 都能排）。
\IfFontExistsTF{__EMOJI_FONT__}{%
  \newfontfamily\mdpdfsymfont{__EMOJI_FONT__}%
  \newcommand\mdpdfIconExcl{\mbox{{\mdpdfsymfont ❗}}}%
  \newcommand\mdpdfIconWarn{\mbox{{\mdpdfsymfont ⚠}}}%
  \newcommand\mdpdfIconBulb{\mbox{{\mdpdfsymfont 💡}}}%
}{%
  \newcommand\mdpdfIconExcl{}%
  \newcommand\mdpdfIconWarn{}%
  \newcommand\mdpdfIconBulb{}%
}
"""

# 下面这个辅助宏把字符设成活动字符（active），并指向目标 LaTeX 代码：\lccode + \lowercase
# 是 LaTeX 里给任意 Unicode 字符下定义的通用手法（newunicodechar 内部同款做法），
# 有了它就不必额外依赖宏包。实测正文、标题、表格单元格、告示框、行内代码、围栏代码块、
# 封面与页眉里的这些符号都能正常排版（见 test_symbol_fallback.py）。
_SYMBOL_FALLBACK_PREAMBLE = r"""
%----- 正文符号回退（CJK 字体缺字形 → 数学字体）-----
% 见 SYMBOL_FALLBACKS：∀ ∃ ∅ ⊂ ⊆ ⇒ ⇐ ⇔ ↦ ∂ ∇ ⊗ 等中文字体没有字形，
% 直接写进正文会变成空白；这里把它们映射到等价的 LaTeX 数学命令。
\makeatletter
\newcommand\mdpdfSymbol[2]{%
  \begingroup
  \lccode`\~=`#1\relax
  \lowercase{\endgroup\def~}{#2}%
  \catcode`#1=\active}
\makeatother
"""


def symbol_fallback_preamble() -> str:
    """生成符号回退导言区（辅助宏 + 表情字体 + 每条字符映射一行）。"""
    lines = [_SYMBOL_FALLBACK_PREAMBLE,
             _EMOJI_PREAMBLE.replace("__EMOJI_FONT__", _EMOJI_FONT)]
    merged = {**SYMBOL_FALLBACKS, **EMOJI_ICONS}
    lines += [r"\mdpdfSymbol{" + ch + "}{" + rep + "}" for ch, rep in merged.items()]
    return "\n".join(lines) + "\n"

# ---------------------------------------------------------------------------
# 排版模板（LaTeX 导言区）
# ---------------------------------------------------------------------------
# 排版规则放在 templates 目录的模板文件里，脚本本身不写死：
#   default.tex   默认模板（紧凑讲义风格）
#   academic.tex  学术论文风格（论文版心与相应宏包）
# 不指定 --template 时用 default.tex。生成 .tex 时把模板拼在正文之前，并替换两个
# 占位符：
#   __SYMBOL_FALLBACKS__  正文符号回退表（必须紧接 \documentclass，见模板内注释）
#   __PAGE_HEADER__       页眉文字
# --template 既可给 .tex 路径，也可只给内置名（default / academic）。模板并非随便
# 一份导言区就能套：它必须自带本工具产出正文所需的定义（listings、tcolorbox、
# 符号回退表…），缺了会在 _template_missing_deps 里被挡下并列出补法。
# 打包 exe 时 templates 目录由 PyInstaller 收进解包目录（见 build_exe.ps1 --add-data）。
TEMPLATE_DIRNAME = "templates"
DEFAULT_TEMPLATE_NAME = "default.tex"
# 模板里的两个占位符。替换是**全文文本替换**（str.replace），所以模板注释里
# 一旦写出完整字面量，会被一起替换掉，导言区跟着错位。load_template 用"必须恰好
# 出现一次"把这种情况拦成明确报错，省得生成一份编译失败或符号空白的 .tex。
PLACEHOLDER_SYMBOLS = "__SYMBOL_FALLBACKS__"
PLACEHOLDER_HEADER = "__PAGE_HEADER__"


def templates_dir() -> Path:
    """模板目录：源码运行时取脚本同级的 templates；打包 exe 取 PyInstaller 解包目录。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / TEMPLATE_DIRNAME
        if bundled.is_dir():
            return bundled
    return Path(__file__).resolve().parent / TEMPLATE_DIRNAME


def default_template_path() -> Path:
    """默认模板路径（templates/default.tex）。"""
    return templates_dir() / DEFAULT_TEMPLATE_NAME


def builtin_templates() -> dict[str, Path]:
    """内置模板：名称（不含扩展名）→ 路径。供 --template 简称与 GUI 下拉用。"""
    d = templates_dir()
    if not d.is_dir():
        return {}
    return {p.stem: p for p in sorted(d.glob("*.tex"))}


def resolve_template_path(path: "str | os.PathLike[str] | None") -> Path:
    """把 --template 的值解析成模板文件路径。

    - 空值 → 默认模板；
    - 已是存在的文件 → 直接用（相对路径按当前工作目录解析）；
    - **不带目录分隔符**的名字（`academic`、`academic.tex`）→ 在内置 templates
      目录里找。

    带路径的写法一旦不存在就直接报错，不退回内置同名模板：否则
    `--template .\\default.tex` 打错字会静默用上内置模板，很难察觉。
    """
    if not path:
        return default_template_path()
    s = str(path)
    p = Path(s)
    if p.is_file():
        return p
    if os.sep not in s and "/" not in s:
        cands = [templates_dir() / s]
        if not s.endswith(".tex"):
            cands.append(templates_dir() / (s + ".tex"))
        for c in cands:
            if c.is_file():
                return c
    return p


def load_template(path: "str | os.PathLike[str] | None" = None,
                  notes: list[str] | None = None) -> str:
    r"""读取排版模板；path 为空（None/""）时用默认模板。

    硬校验（都是用户输入问题，报错要能直接定位）：

    1. 文件存在；
    2. \begin{document} 恰好一次。它是注入点，封面配色 / 编号深度 / 目录深度 /
       PDF 元数据都插在它前面。0 次则拼出的 .tex 不完整；多于一次说明注释里写了
       字面量，注入块会被插进注释（实测表现为 \hypersetup 未定义之类的编译失败）；
    3. 两个占位符至多一次。同理，多于一次必然是注释里写了字面量。

    **完整文档式模板**（自带正文与 \end{document}，如现成的论文 .tex）只取
    \begin{document} 之前的导言区，模板自带的正文 / 摘要 / 参考文献会被丢弃，
    并经 notes 回一条说明。md-latex-pdf 自己生成封面与正文，模板的正文只会
    拼出双 \end{document} 的坏文件。

    占位符缺失不在这里报错（由 build_tex 记警告），但生成器产出正文所依赖的
    定义（listings / tcolorbox / …）缺失会在 build_tex 里报硬错。
    """
    p = resolve_template_path(path)
    if not p.is_file():
        hint = ""
        builtins = builtin_templates()
        if builtins:
            hint = "；内置模板：" + "、".join(builtins)
        raise FileNotFoundError(
            f"排版模板不存在：{p}"
            f"（默认模板为 {default_template_path()}{hint}）")
    text = p.read_text(encoding="utf-8")
    n_doc = text.count(r"\begin{document}")
    if n_doc != 1:
        raise ValueError(
            f"模板里的 \\begin{{document}} 出现 {n_doc} 次，必须恰好一次：{p}\n"
            f"（常见原因：把 \\begin{{document}} 写进了注释。md-latex-pdf 做全文替换，"
            f"注释里的也会被注入块替换掉，导致导言区错位）")
    for token, what in ((PLACEHOLDER_SYMBOLS, "符号回退"), (PLACEHOLDER_HEADER, "页眉")):
        n = text.count(token)
        if n > 1:
            raise ValueError(
                f"模板里「{what}」占位符出现了 {n} 次，必须恰好一次：{p}\n"
                f"（常见原因：把 {token} 写进了注释；md-latex-pdf 做全文替换，"
                f"注释里的也会被替换掉，导致导言区错位）")
    # 完整文档式模板：截到 \begin{document} 为止（含它本身，它是注入点）
    end_doc = text.find(r"\end{document}")
    if end_doc > text.find(r"\begin{document}"):
        marker = r"\begin{document}"
        text = text[: text.find(marker) + len(marker)] + "\n"
        if notes is not None:
            notes.append(
                f"模板「{p.name}」是完整文档（自带正文与 \\end{{document}}）："
                f"已只取 \\begin{{document}} 之前的导言区，模板自带的正文/摘要/参考文献已忽略")
    return text


# 生成器产出的 LaTeX 依赖模板提供的定义。缺了只会变成 xelatex 里一句带行号的
# "Undefined control sequence" / "Environment ... undefined"，指不出该补什么。
# 每条：(正文/注入块里出现的标记, 模板里必须出现的字样, 缺了会怎样, 怎么补)。
# 标记为 None 表示"总是需要"（封面由 Python 生成，无条件用到）。
_TEMPLATE_DEPS = (
    (None, "ctex", "中文排版与封面字号 \\zihao",
     r"用 ctexart 文档类：\documentclass{ctexart}"),
    (None, "xcolor", "封面底色 \\pagecolor / 收尾的 \\nopagecolor",
     r"\usepackage{color,xcolor}"),
    (r"\begin{lstlisting}", "listings", "代码块",
     r"\usepackage{listings} 与 \lstset{...}"),
    (r"\begin{tipbox}", "tcolorbox", "告示框 > [!TIP] / 引述标记 > 💡",
     r"\usepackage[most]{tcolorbox} 与 \newtcolorbox{tipbox}..."),
    (r"\begin{warnbox}", "tcolorbox", "告示框 > [!WARNING] / 引述标记 > ⚠",
     r"\usepackage[most]{tcolorbox} 与 \newtcolorbox{warnbox}..."),
    (r"\begin{keybox}", "tcolorbox", "告示框 > [!IMPORTANT]",
     r"\usepackage[most]{tcolorbox} 与 \newtcolorbox{keybox}..."),
    (r"\begin{notebox}", "tcolorbox", "告示框 > [!NOTE]",
     r"\usepackage[most]{tcolorbox} 与 \newtcolorbox{notebox}..."),
    (r"\begin{cautionbox}", "tcolorbox", "告示框 > [!CAUTION] / 引述标记 > ❗",
     r"\usepackage[most]{tcolorbox} 与 \newtcolorbox{cautionbox}..."),
    (r"\begin{mdpdfquote}", "tcolorbox", "普通引用 > 文字",
     r"\usepackage[most]{tcolorbox} 与 \newtcolorbox{mdpdfquote}..."),
    (r"\sout{", "ulem", "删除线 ~~…~~", r"\usepackage[normalem]{ulem}"),
    (r"\SI{", "siunitx", "物理单位 \\SI", r"\usepackage{siunitx}"),
    (r"\ce{", "mhchem", "化学式 \\ce", r"\usepackage[version=4]{mhchem}"),
)


def _template_missing_deps(preamble: str, body: str) -> list[str]:
    """返回"正文用到了、但模板没提供定义"的说明列表（空 = 没问题）。

    纯文本匹配，不解析 LaTeX：检查的都是生成器固定输出的字样
    （如 \\begin{lstlisting}），模板提供方必须写出对应宏包名，误判概率极低。
    """
    problems: list[str] = []
    for marker, needs, what, fix in _TEMPLATE_DEPS:
        if marker is not None and marker not in body:
            continue  # 这篇 Markdown 没用到，不要求模板提供
        if needs not in preamble:
            where = "正文用到" if marker is not None else "每次转换都要"
            problems.append(f"{where}{what}，但模板里没有 {needs} → 请加 {fix}")
    return problems


# ---------------------------------------------------------------------------
# LaTeX 转义
# ---------------------------------------------------------------------------
_TEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "%": r"\%",
    "&": r"\&",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_TEX_ESC_RE = re.compile(r"([\\%&#_{}~^$])")


def tex_escape(s: str) -> str:
    """普通文本转义（LaTeX 特殊字符）。"""
    return _TEX_ESC_RE.sub(lambda m: _TEX_ESCAPES[m.group(1)], s)


def tex_escape_url(s: str) -> str:
    r"""URL 转义（\href / \url 参数内）。"""
    return _TEX_ESC_RE.sub(lambda m: _TEX_ESCAPES[m.group(1)], s.replace(" ", r"\%20"))


# ---------------------------------------------------------------------------
# 中文弯引号（smart quotes）
# 直引号 " / ' 原样进 LaTeX 会落到西文字体（Latin Modern）上，排出来是西文的
# 引号/撇号；转成中文弯引号 “ ” / ‘ ’ 后由中文字体按全角排。
# 行内代码/公式/链接里的引号在 md_inline 里先 stash 成占位符，不会误转。
# ---------------------------------------------------------------------------
_CJK_RANGE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]")


def _has_cjk(s: str) -> bool:
    """是否含中文字符（含 CJK 标点与全角符号）。"""
    return bool(_CJK_RANGE_RE.search(s))


def _convert_quote_pairs(s: str, q: str, open_q: str, close_q: str) -> str:
    """把 s 中成对的直引号 q 按出现顺序替换成 open_q / close_q（开/关交替）。

    单词中间的单引号（撇号，如 don't / it's）不算引号对；
    落单不成对的直引号保持原样，避免误伤英寸（5"）、撇号等用法。
    """
    idx: list[int] = []
    prev_c = ""
    for i, ch in enumerate(s):
        if ch != q:
            prev_c = ch
            continue
        nxt = s[i + 1] if i + 1 < len(s) else ""
        # 撇号：前后都是 ASCII 字母（don't / it's / rock 'n' roll）
        if (q == "'" and prev_c and nxt and prev_c.isascii() and prev_c.isalpha()
                and nxt.isascii() and nxt.isalpha()):
            prev_c = ch
            continue
        idx.append(i)
        prev_c = ch
    usable = len(idx) - (len(idx) % 2)  # 只转换完整配对
    if not usable:
        return s
    out = list(s)
    for k in range(0, usable, 2):
        out[idx[k]] = open_q
        out[idx[k + 1]] = close_q
    return "".join(out)


def smart_cjk_quotes(s: str, enabled: bool = True) -> str:
    """中文段落智能引号：成对 ASCII 直引号 → 中文弯引号 “ ” / ‘ ’。

    enabled=False（纯英文文档）或本段不含中文（纯英文段落/标题/单元格）时
    原样返回，免得把西文排版改坏；含中文的文本块里即使只引用英文短语
    （如 “smart quotes”）也转成中文引号。
    """
    if not enabled or not _has_cjk(s):
        return s
    s = _convert_quote_pairs(s, '"', "\u201c", "\u201d")
    s = _convert_quote_pairs(s, "'", "\u2018", "\u2019")
    return s


# ---------------------------------------------------------------------------
# 行内解析（Markdown inline → LaTeX）
# ---------------------------------------------------------------------------
def md_inline(text: str, ctx, _tokens: list | None = None) -> str:
    """处理行内标记：代码、数学、图片、链接、脚注、删除线、粗体、斜体、自动链接。

    _tokens: 递归解析时共享的占位符表。粗体/斜体/脚注/删除线的内容里若含已被
    stash 的行内片段（如数学公式、行内代码），必须沿用外层 tokens，否则还原时
    \x00N\x00 会指向新表而越界。
    """
    tokens: list[str] = _tokens if _tokens is not None else []

    def stash(s: str) -> str:
        tokens.append(s)
        return f"\x00{len(tokens) - 1}\x00"

    def restore(s: str) -> str:
        def rep(m):
            return tokens[int(m.group(1))]
        return re.sub(r"\x00(\d+)\x00", rep, s)

    # 1. 行内代码
    def repl_code(m):
        return stash(r"\texttt{" + tex_escape(m.group(1)) + "}")
    text = re.sub(r"`([^`\n]+)`", repl_code, text)

    # 2. 行内数学（原样透传给 LaTeX）
    def repl_math(m):
        return stash("$" + m.group(1) + "$")
    text = re.sub(r"\$([^$\n]+?)\$", repl_math, text)

    # 3. 图片 ![alt](url)
    def repl_img(m):
        alt, url = m.group(1), m.group(2).strip().strip('<>"')
        if re.match(r"^(https?|ftp)://", url):
            ctx.warnings.append(f"远程图片未下载（需联网）：{url}")
            return stash(rf"\includegraphics[width=0.8\linewidth]{{{tex_escape_url(url)}}}")
        src = (ctx.md_dir / url).resolve()
        if not src.exists():
            ctx.warnings.append(f"图片不存在，已忽略：{url}")
            return stash(tex_escape(f"[图片缺失: {url}]"))
        ext = src.suffix.lower()
        name = f"img_{hashlib.md5(str(src).encode('utf-8')).hexdigest()[:10]}{ext}"
        ctx.images[str(src)] = name
        fig = rf"\begin{{center}}\includegraphics[width=0.8\linewidth]{{images/{name}}}"
        if alt:
            fig += rf"\\\captionof{{figure}}{{{tex_escape(alt)}}}"
        fig += r"\end{center}"
        return stash(fig)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+(?:\s+[\"'][^\"']*[\"'])?)\)", repl_img, text)

    # 4. 脚注引用 [^n]
    def repl_fn(m):
        key = m.group(1)
        if key in ctx.footnotes:
            return stash(r"\footnote{" + md_inline(ctx.footnotes[key], ctx, tokens) + "}")
        return stash(tex_escape(f"[^{key}]"))
    text = re.sub(r"\[\^([\w-]+)\]", repl_fn, text)

    # 5. 删除线 ~~x~~
    def repl_strike(m):
        return stash(r"\sout{" + md_inline(m.group(1), ctx, tokens) + "}")
    text = re.sub(r"~~(.+?)~~", repl_strike, text)

    # 6. 粗体 / 斜体（嵌套内容递归处理后再包裹）
    def repl_bold(m):
        return stash(r"\textbf{" + md_inline(m.group(1), ctx, tokens) + "}")
    text = re.sub(r"\*\*(.+?)\*\*", repl_bold, text)

    def repl_italic(m):
        return stash(r"\emph{" + md_inline(m.group(1), ctx, tokens) + "}")
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", repl_italic, text)
    text = re.sub(r"(?<![\w\\])_([^_\n]+)_(?![\w])", repl_italic, text)

    # 7. 链接 [text](url) 与尖括号自动链接 <url>
    def repl_link(m):
        label, url = m.group(1), m.group(2).strip().strip('<>"')
        return stash(r"\href{" + tex_escape_url(url) + "}{" + md_inline(label, ctx, tokens) + "}")
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+(?:\s+[\"'][^\"']*[\"'])?)\)", repl_link, text)
    text = re.sub(r"<((?:https?|ftp)://[^>\s]+)>", lambda m: stash(r"\url{" + tex_escape_url(m.group(1)) + "}"), text)

    # 8. 裸 URL 自动链接
    def repl_autolink(m):
        url = re.sub(r"[),.;:!?]+$", "", m.group(1))
        return stash(r"\url{" + tex_escape_url(url) + "}")
    text = re.sub(r"(?<![\w=\"'])(https?://[^\s<>\x00]+)", repl_autolink, text)

    # 8.5 中文弯引号：直引号 " / ' → “ ” / ‘ ’（中文文档，见 smart_cjk_quotes）
    # 此时行内代码/公式/图片/链接/粗斜体等已 stash 为 \x00N\x00 占位符，
    # 其中的引号不会被改动；本步在 tex_escape 之前，替换结果不受转义影响。
    text = smart_cjk_quotes(text, ctx.cjk_mode)

    # 9. 其余特殊字符转义，再恢复已处理片段
    text = tex_escape(text)
    return restore(text)


# ---------------------------------------------------------------------------
# 块级解析（Markdown blocks → LaTeX）
# ---------------------------------------------------------------------------
_LST_LANGS = {
    "python": "Python", "py": "Python", "cpp": "C++", "c++": "C++", "cc": "C++",
    "c": "C", "java": "Java", "js": "", "javascript": "", "ts": "", "typescript": "",
    "bash": "bash", "sh": "bash", "shell": "bash", "sql": "SQL",
    "json": "", "html": "HTML", "css": "", "xml": "XML",
    "tex": "TeX", "latex": "TeX", "rust": "", "go": "Go",
    "ruby": "Ruby", "php": "PHP", "matlab": "Matlab", "lua": "Lua", "r": "R",
}
_HEADING_CMDS = {1: "section", 2: "subsection", 3: "subsubsection", 4: "paragraph"}


def _detect_min_heading_level(text: str) -> int:
    """检测正文中实际出现的最高标题级别（#=1、##=2…），跳过围栏代码块。

    用于「提级」：当正文没有一级标题（# 常被封面标题吸收，或正文本就不写 #），
    就把二级/三级标题向上提成 section/subsection，令自动编号从 1 开始，
    避免出现 0.1、0.2… 这类从 0 起的编号。找不出标题时返回 1。
    """
    min_level = 9
    in_fence = False
    fence_ch = ""
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^(?:`{3,}|~{3,})(.*)$", s)
        if m:
            ch = s[0]
            if not in_fence:
                in_fence, fence_ch = True, ch
            elif ch == fence_ch and re.match(r"^[" + re.escape(fence_ch) + r"]{3,}\s*$", s):
                in_fence = False
            continue
        if in_fence:
            continue
        m2 = re.match(r"^(#{1,6})\s+", line)
        if m2:
            lv = len(m2.group(1))
            if lv < min_level:
                min_level = lv
    return min_level if min_level <= 6 else 1


def is_block_start(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if re.match(r"^#{1,6}\s", line):
        return True
    if re.match(r"^(?:`{3,}|~{3,})", s):
        return True
    if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
        return True
    if line.startswith("|"):
        return True
    if s.startswith("::"):
        return True
    if line.startswith(">"):
        return True
    if re.match(r"^(\s*)([-*+]|\d+[.)、])\s+", line):
        return True
    return False


def render_code(lang: str, body: list[str], ctx) -> str:
    lst_lang = _LST_LANGS.get(lang.lower(), "")
    code = "\n".join(body)
    if "\\end{lstlisting}" in code:
        ctx.warnings.append("代码块含 \\end{lstlisting}，已按纯文本处理")
        inner = "\n".join(r"\texttt{" + tex_escape(l) + r"}" for l in body)
        return "\\begin{quote}\n" + inner + "\n\\end{quote}"
    opt = f"[language={lst_lang}]" if lst_lang else ""
    return "\\noindent " + f"\\begin{{lstlisting}}{opt}\n{code}\n\\end{{lstlisting}}"


def disp_width(s: str) -> int:
    """估算显示宽度：CJK 字符算 2 单位，其余算 1（表格列宽与引述标题共用）。"""
    return sum(2 if ord(c) > 0x2E7F else 1 for c in s)


def render_table(rows: list[str], ctx) -> str:
    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    def col_units(s: str) -> int:
        return disp_width(s)

    header = cells(rows[0])
    sep = cells(rows[1])
    aligns = []
    for s in sep:
        s = s.strip()
        if s.startswith(":") and s.endswith(":"):
            aligns.append("c")
        elif s.endswith(":"):
            aligns.append("r")
        else:
            aligns.append("l")
    body = [cells(r) for r in rows[2:] if cells(r) != [""]]
    # 估算各列最大内容宽度，超宽列转可换行 X 列（tabularx），短列保持自然宽度
    maxw = [0] * len(header)
    for row in [header] + body:
        for i, c in enumerate(row):
            if i < len(maxw):
                maxw[i] = max(maxw[i], col_units(c))
    _XMAP = {"l": "L", "c": "C", "r": "R"}
    wrap_spec = "".join(_XMAP[a] if maxw[i] >= 24 else a for i, a in enumerate(aligns))
    need_x = any(maxw[i] >= 24 for i in range(len(aligns)))
    long_table = len(body) > 24
    indent = r"\noindent "  # 表格为 \linewidth 级显示盒子，必须消段落缩进（\parindent=2em 会把整表右移）
    if long_table or not need_x:
        # 长表（longtable 不支持 X 列）或没有超宽列：自然宽度列
        env = "longtable" if long_table else "tabular"
        extra = "\\endfirsthead" if long_table else ""
        out = [indent + f"\\begin{{{env}}}{{{''.join(aligns)}}}", "\\toprule",
               " & ".join(md_inline(h, ctx) for h in header) + " \\\\",
               "\\midrule" + extra]
        for row in body:
            out.append(" & ".join(md_inline(c, ctx) for c in row) + " \\\\")
        out += ["\\bottomrule", f"\\end{{{env}}}"]
        return "\n".join(out)
    out = [indent + f"\\begin{{tabularx}}{{\\linewidth}}{{{wrap_spec}}}", "\\toprule",
           " & ".join(md_inline(h, ctx) for h in header) + " \\\\", "\\midrule"]
    for row in body:
        out.append(" & ".join(md_inline(c, ctx) for c in row) + " \\\\")
    out += ["\\bottomrule", "\\end{tabularx}"]
    return "\n".join(out)


def render_list(ordered: bool, items: list[tuple[str, str, list[str]]], ctx) -> str:
    env = "enumerate" if ordered else "itemize"
    out = [f"\\begin{{{env}}}"]
    if ordered:
        first = int(re.match(r"\d+", items[0][1]).group())
        if first != 1:
            out.append(f"\\setcounter{{enumi}}{{{first - 1}}}")
    for first_text, _marker, inner in items:
        tm = re.match(r"^\[([ xX])\]\s+(.*)$", first_text)
        if tm:
            box = "\\boxtimes" if tm.group(1).lower() == "x" else "\\square"
            out.append("\\item[$" + box + "$] " + md_inline(tm.group(2), ctx))
        else:
            out.append("\\item " + md_inline(first_text, ctx))
        if inner:
            out.append("\n\n".join(inner))
    out.append(f"\\end{{{env}}}")
    return "\n".join(out)


# GitHub 风格告示框 > [!TYPE]：类型 → (tcolorbox 环境, 缺省标题)。
# 五个环境由模板提供，配色在模板里改，这里只管选哪一个。
_GITHUB_ADMON = {
    "note": ("notebox", "注意"),
    "tip": ("tipbox", "提示"),
    "important": ("keybox", "重要"),
    "warning": ("warnbox", "警告"),
    "caution": ("cautionbox", "小心"),
}
_ADMON_MARKER_RE = re.compile(r"^\s*\[!(note|tip|important|warning|caution)\]\s*(.*)$", re.IGNORECASE)


def render_admon(kind: str, title: str, inner: list[str]) -> str:
    """渲染 GitHub 风格告示框（>[!NOTE]/[!TIP]/[!IMPORTANT]/[!WARNING]/[!CAUTION]）。"""
    env, default_title = _GITHUB_ADMON[kind]
    if not title:
        title = default_title
    body = "\n\n".join(inner) if inner else ""
    head = f"\\begin{{{env}}}[{tex_escape(title)}]"
    return head + ("\n" + body if body else "") + f"\n\\end{{{env}}}"


# 引述标记：以 ❗ / ⚠ / 💡 开头的引用块 → 对应彩色告示框。写起来比 >[!TYPE] 省事，
# 颜色与语义沿用上面那套环境：❗＝强调/易错（红）、⚠＝警告（橙）、💡＝思路/提示（绿）。
_QUOTE_MARKS = {
    "❗": ("cautionbox", "注意"),
    "⚠": ("warnbox", "警告"),
    "💡": ("tipbox", "提示"),
}
_QUOTE_MARK_RE = re.compile(r"^\s*([❗⚠💡])\s*(.*)$")
_QUOTE_TITLE_MAX = 16          # 标记行剩余文字超过这个显示宽度就不当标题
_QUOTE_TITLE_STOP = "。！？!?…"  # 以句末标点结尾的也不当标题（那是整句话，不是标题）


def render_quote(inner: list[str], ctx) -> str:
    """普通引用（`> 引用`，不带任何标记）→ 浅灰底 + 左侧竖条的 mdpdfquote 框。

    内容为空（孤零零一个 `>`）时什么都不输出，省得留一条空的灰条。
    """
    body = "\n\n".join(inner) if inner else ""
    if not body.strip():
        return ""
    return "\\begin{mdpdfquote}\n" + body + "\n\\end{mdpdfquote}"


def render_quote_mark(icon: str, text: str, rest: list[str], ctx) -> str:
    """把 [icon] 开头的引用块渲染成对应彩色告示框。

    标题规则：标记行剩下的文字够短（≤16 显示宽度、不以句末标点结尾）就当框标题，
    与 `> [!TIP] 快速检查` 的写法一致；否则标题用该类型的缺省名，这段话留在正文里
    （标记字符本身保留，读者仍能看出作者标的是哪一类）。
    """
    env, default_title = _QUOTE_MARKS[icon]
    keep_as_title = (bool(text) and disp_width(text) <= _QUOTE_TITLE_MAX
                     and text[-1] not in _QUOTE_TITLE_STOP)
    if keep_as_title:
        title, lines = text, rest
    else:
        title = default_title
        lines = ([f"{icon} {text}"] if text else []) + rest
    inner = parse_blocks(lines, ctx) if any(l.strip() for l in lines) else []
    body = "\n\n".join(inner) if inner else ""
    head = f"\\begin{{{env}}}[{tex_escape(title)}]"
    return head + ("\n" + body if body else "") + f"\n\\end{{{env}}}"


def parse_blocks(lines: list[str], ctx) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(lines)

    # 预扫描脚注定义（引用可能出现在定义之前）
    for ln in lines:
        mm = re.match(r"^\[\^([\w-]+)\]:\s*(.*)$", ln.strip())
        if mm:
            ctx.footnotes.setdefault(mm.group(1), mm.group(2))

    def close_para_join(items: list[str]) -> str:
        return " ".join(items)

    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue

        # 显示公式 $$ ... $$（多行）
        if s.startswith("$$"):
            if s.endswith("$$") and len(s) > 4:
                out.append("\\[" + s[2:-2].strip() + "\\]")
                i += 1
            else:
                buf = [s[2:]]
                i += 1
                while i < n:
                    cs = lines[i].strip()
                    if cs.endswith("$$"):
                        buf.append(cs[:-2])
                        i += 1
                        break
                    buf.append(lines[i])
                    i += 1
                out.append("\\[\n" + "\n".join(buf).strip() + "\n\\]")
            continue

        # 围栏代码块
        m = re.match(r"^(?:`{3,}|~{3,})(.*)$", s)
        if m and len(re.match(r"^(?:`{3,}|~{3,})", s).group(0)) >= 3:
            fence_ch = s[0]
            lang = m.group(1).strip()
            body: list[str] = []
            i += 1
            while i < n:
                cl = lines[i].strip()
                if cl and cl[0] == fence_ch and re.match(r"^(?:`{3,}|~{3,})\s*$", cl):
                    break
                body.append(lines[i])
                i += 1
            i += 1  # 跳过闭合围栏
            out.append(render_code(lang, body, ctx))
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            text = re.sub(r"^\d+(?:\.\d+)*[.、]?\s*", "", m.group(2).strip())  # 去掉手写编号，交给 LaTeX 自动编号
            # 提级：若正文最高只到二级标题（# 被封面标题吸收，或正文本就没有 # 章节），
            # 把顶级标题向上提成 \section，使编号从 1 开始——避免出现 0.1、0.2…
            eff = max(1, level - ctx.heading_shift)
            cmd = _HEADING_CMDS.get(eff, "paragraph")
            if cmd == "paragraph":
                # \paragraph 是 run-in（行内）标题，紧跟 tabularx 时标题与表格同段导致超宽行；
                # 追加 \mbox{}\par 强制结束标题段落（display 样式），避免表格溢出页面
                out.append(f"\\{cmd}{{{md_inline(text, ctx)}}}\\mbox{{}}\\par")
            else:
                out.append(f"\\{cmd}{{{md_inline(text, ctx)}}}")
            i += 1
            continue

        # 分隔线
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            out.append(r"\noindent\rule{\linewidth}{0.4pt}")
            i += 1
            continue

        # 表格
        if line.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            tbl: list[str] = []
            while i < n and lines[i].strip().startswith("|"):
                tbl.append(lines[i])
                i += 1
            out.append(render_table(tbl, ctx))
            continue

        # 强制分页
        if s == "::page":
            out.append(r"\clearpage")
            i += 1
            continue

        # 脚注定义
        m = re.match(r"^\[\^([\w-]+)\]:\s*(.*)$", s)
        if m:
            ctx.footnotes[m.group(1)] = m.group(2)
            i += 1
            continue

        # 原生 HTML 表格（LaTeX 模式不支持，跳过并提示）
        if line.lstrip().startswith("<table"):
            while i < n and "</table>" not in lines[i]:
                i += 1
            i += 1
            ctx.warnings.append("原生 HTML 表格已忽略（LaTeX 模式请改用 Markdown 表格）")
            continue

        # 引用 / GitHub 风格告示框 >[!NOTE]... / 引述标记 > ❗|⚠|💡
        if line.startswith(">"):
            q: list[str] = []
            while i < n and lines[i].startswith(">"):
                q.append(lines[i][2:] if lines[i].startswith("> ") else lines[i][1:])
                i += 1
            # 首个非空内容行若是告示框标记（>[!WARNING] 等）或引述标记（> ❗ 等），
            # 整块转彩色告示框
            admon = None
            mark = None
            for j, ql in enumerate(q):
                if not ql.strip():
                    continue
                mm = _ADMON_MARKER_RE.match(ql)
                if mm:
                    admon = (mm.group(1).lower(), mm.group(2).strip(), q[j + 1:])
                else:
                    mk = _QUOTE_MARK_RE.match(ql)
                    if mk:
                        mark = (mk.group(1), mk.group(2).strip(), q[j + 1:])
                break  # 只看第一段内容
            if admon:
                kind, title, rest = admon
                out.append(render_admon(kind, title, parse_blocks(rest, ctx)))
            elif mark:
                out.append(render_quote_mark(mark[0], mark[1], mark[2], ctx))
            else:
                # 普通引用：浅灰底 + 左侧竖条
                out.append(render_quote(parse_blocks(q, ctx), ctx))
            continue

        # 列表（含嵌套）
        m = re.match(r"^(\s*)([-*+]|\d+[.)、])\s+(.*)$", line)
        if m:
            indent = len(m.group(1))
            ordered = m.group(2)[0].isdigit()
            items: list[tuple[str, str, list[str]]] = []
            while i < n:
                lm = re.match(r"^(\s*)([-*+]|\d+[.)、])\s+(.*)$", lines[i])
                if lm and len(lm.group(1)) == indent and (lm.group(2)[0].isdigit()) == ordered:
                    first_text = lm.group(3)
                    marker = lm.group(2)
                    content_col = indent + len(marker) + 1
                    sub: list[str] = []
                    i += 1
                    while i < n:
                        l = lines[i]
                        if not l.strip():
                            sub.append("")
                            i += 1
                            continue
                        ls = len(l) - len(l.lstrip(" "))
                        if ls >= content_col:
                            sub.append(l)
                            i += 1
                            continue
                        break
                    inner_lines = [l[content_col:] if l.strip() else "" for l in sub]
                    inner = parse_blocks(inner_lines, ctx) if any(l.strip() for l in inner_lines) else []
                    items.append((first_text, marker, inner))
                else:
                    break
            out.append(render_list(ordered, items, ctx))
            continue

        # 普通段落
        para: list[str] = [line]
        i += 1
        while i < n:
            l = lines[i]
            if not l.strip() or is_block_start(l):
                break
            para.append(l)
            i += 1
        out.append(md_inline(close_para_join(p.strip() for p in para), ctx))

    return out


# ---------------------------------------------------------------------------
# Front matter / 封面元信息
# ---------------------------------------------------------------------------
def parse_front_matter(md_text: str) -> tuple[dict, str]:
    if md_text.startswith("\ufeff"):
        md_text = md_text.lstrip("\ufeff")
    meta = {
        "title": "未命名文档", "subtitle": "", "kicker": "讲义",
        "header": "", "foot": "", "cover": "", "items": [],
    }
    lines = md_text.splitlines()
    body_lines = lines

    if lines and lines[0].strip() == "---":
        end = next((j for j in range(1, len(lines)) if lines[j].strip() == "---"), None)
        if end is not None:
            front, body_lines = lines[1:end], lines[end + 1:]
            for ln in front:
                ln = ln.strip()
                if not ln:
                    continue
                m = re.match(r"^([\w\u4e00-\u9fff]+)\s*[:：]\s*(.*)$", ln)
                if m:
                    k, v = m.group(1).strip(), m.group(2).strip()
                    _store_meta(meta, k, v)
    else:
        idx = md_text.find("\n---\n")
        if idx != -1:
            front = md_text[:idx]
            # 只有当前缀像「封面」时才按 front matter 解析，否则这是一篇没有封面
            # 的普通正文，`---` 只是分隔线（不吞掉前面的段落）。判据（同时满足）：
            #   1) 首行是 `# 标题` / `## 副标题`；
            #   2) 每非空行都符合封面语法（标题行 / `键：值` 元信息行）；
            #   3) 前缀不超过 30 行（封面都很短，正文分隔线通常更靠后）。
            # 防止正文里的 `---` 分隔线被误当作 front matter 结束符、吞掉开头段落。
            nonempty = [ln.strip() for ln in front.splitlines() if ln.strip()]
            is_front = bool(nonempty) and len(nonempty) <= 30 \
                and (nonempty[0].startswith("# ") or nonempty[0].startswith("## "))
            for s in nonempty:
                if not is_front:
                    break
                if s.startswith("# ") or s.startswith("## "):
                    continue
                if re.match(r"^[\w\u4e00-\u9fff]+\s*[:：]\s*.*$", s):
                    continue
                is_front = False
            if is_front:
                body_lines = md_text[idx + 5:].splitlines() if idx + 5 < len(md_text) else []
                for ln in front.splitlines():
                    ln = ln.strip()
                    if not ln:
                        continue
                    if ln.startswith("# "):
                        meta["title"] = ln[2:].strip()
                    elif ln.startswith("## "):
                        meta["subtitle"] = ln[3:].strip()
                    elif "：" in ln:
                        k, v = ln.split("：", 1)
                        _store_meta(meta, k.strip(), v.strip())
                    elif ":" in ln:
                        k, v = ln.split(":", 1)
                        _store_meta(meta, k.strip(), v.strip())
    return meta, "\n".join(body_lines)


def _store_meta(meta: dict, k: str, v: str):
    kk = k.lower()
    if kk == "页眉":  # 中文关键词，等价于英文 header
        kk = "header"
    elif kk in ("页尾", "footer", "页脚"):  # 封面底部说明，等价于英文 foot
        kk = "foot"
    elif kk == "封面":  # 封面底色，等价于英文 cover
        kk = "cover"
    if kk in ("title", "subtitle", "kicker", "header", "foot", "cover"):
        meta[kk] = v
    else:
        meta["items"].append((k, v))


# ---------------------------------------------------------------------------
# 文档组装（生成 .tex）
# ---------------------------------------------------------------------------
def build_tex(meta: dict, body_md: str, opts: argparse.Namespace, ctx) -> str:
    title = opts.title or meta["title"]
    subtitle = opts.subtitle if opts.subtitle is not None else meta["subtitle"]
    header = opts.header if opts.header is not None else (meta["header"] or title)
    cover_color = opts.cover_color or meta["cover"] or "FFFFFF"
    cover_color = cover_color.lstrip("#").upper()
    if not re.match(r"^[0-9A-F]{6}$", cover_color):
        cover_color = "FFFFFF"
    no_numbers = opts.no_numbers
    # 封面/页眉等不走 md_inline 的直出文本同样做直引号→中文弯引号（中文文档）
    sq = lambda s: smart_cjk_quotes(s, ctx.cjk_mode)

    # ---- 封面：titlepage + 纯色背景（\pagecolor）+ 黑字 ----
    # 标题块落在页面上方约 30% 高度处（视觉重心偏上）；没有 kicker 栏目，也没有
    # 横线分隔；元信息居中，脚注小字沉底。
    cover = [r"\begin{titlepage}", r"\pagecolor{coverbg}", r"\thispagestyle{empty}",
             r"\color{black}", r"\centering"]
    cover.append(r"\vspace*{0.30\textheight}")
    cover.append(r"{\zihao{1}\bfseries " + tex_escape(sq(title)) + r"}\\[0.9em]")
    if subtitle:
        cover.append(r"{\zihao{3} " + tex_escape(sq(subtitle)) + r"}\\[3.2em]")
    else:
        cover.append(r"\vspace{3.2em}")
    cover.append(r"\vfill")
    if meta["items"]:
        for k, v in meta["items"]:
            cover.append(r"{\zihao{4} " + tex_escape(sq(f"{k}：{v}")) + r"}\\[0.7em]")
        cover.append(r"\vspace{0.5em}")
    cover.append(r"\vfill")
    if meta["foot"]:
        cover.append(r"{\zihao{-5}\color{black!70} " + md_inline(meta["foot"], ctx) + r"}\\[1.0em]")
    cover.append(r"\vspace*{1.1cm}")
    cover.append(r"\end{titlepage}")
    cover.append(r"\nopagecolor")
    cover.append(r"\setcounter{page}{1}")

    # ---- 正文 ----
    # 封面的一级标题（# 封面标题）不计数。若正文没有 # 一级标题（被封面吸收），
    # 则把整篇当作单一"章 1"，并把 section 计数预置为 1，让封面外的第一个二级标题
    # 按 1.1、1.2… 编号，免得出现 0.1、0.2… 或者孤立的 1。
    ctx.heading_shift = 0  # 保持常规映射：#→section、##→subsection、###→subsubsection
    section_pre = ""
    if _detect_min_heading_level(body_md) >= 2:
        section_pre = r"\setcounter{section}{1}"  # 隐含"第 1 章"，首个 ## 即 1.1
    body = parse_blocks(body_md.splitlines(), ctx)

    # ---- 组装（导言区 = 排版模板，默认 templates/default.tex，见 load_template）----
    author = next((v for k, v in meta["items"] if k in ("作者", "author")), "")
    secnum = 3 if not no_numbers else 0
    if opts.toc:
        # 目录页用罗马数字（i, ii, ...），正文再从 1 起编阿拉伯数字，
        # 使目录里的页码引用与正文页脚一致、正文首页为"第 1 页"。
        toc = [r"\pagenumbering{roman}", r"\tableofcontents", r"\clearpage",
               r"\pagenumbering{arabic}", r"\setcounter{page}{1}"]
    else:
        toc = []

    template = load_template(getattr(opts, "template", None), notes=ctx.warnings)
    # 占位符缺失不会让编译失败，后果都是"静默"的（符号空白 / 页眉不显示），
    # 所以这里要明确提示一句，否则用户只当"排版本来就这样"。
    if PLACEHOLDER_SYMBOLS not in template:
        ctx.warnings.append(
            f"模板缺少 {PLACEHOLDER_SYMBOLS}：正文与页眉里的 ∀ ⊆ ⇒ 等符号会静默渲染为空白")
    if PLACEHOLDER_HEADER not in template:
        ctx.warnings.append(
            f"模板缺少 {PLACEHOLDER_HEADER}：--header 与 front matter 的「页眉」将被忽略")
    preamble = template.replace(PLACEHOLDER_HEADER, tex_escape(sq(header)))
    preamble = preamble.replace(PLACEHOLDER_SYMBOLS, symbol_fallback_preamble())
    # --no-numbers 时去掉 "图 0.1" 这类带空 chapter/section 前缀的编号，
    # 让图/表/公式退化为纯连续编号（图1、表1、(1)），避免出现 "0.x" 前缀。
    counter_reset = (
        r"\renewcommand{\thefigure}{\arabic{figure}}"
        r"\renewcommand{\thetable}{\arabic{table}}"
        r"\renewcommand{\theequation}{\arabic{equation}}"
        if no_numbers else ""
    )
    # 生成器产出的正文依赖模板提供的定义（listings / tcolorbox / ulem / …）。
    # 缺了只会变成 xelatex 里一句带行号的 "Undefined control sequence"，
    # 完全指不出该补什么，所以在写 .tex 之前先查一遍，一次性把缺项说清。
    missing = _template_missing_deps(preamble, "\n".join(body))
    if missing:
        raise ValueError(
            "模板缺少 md-latex-pdf 产出所需的定义，编译必然失败：\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\n--template 指定的模板并非随便一份导言区就能用：它必须自带本工具"
            "\n产出的 LaTeX 所需定义。最省事的做法是复制 templates\\default.tex 再改样式，"
            "\n或用内置模板：--template academic")
    # 封面颜色 / 编号深度 / 目录深度 / PDF 元数据 由生成器注入。
    # 注入块必须自给自足：模板未必定义 \mdcovercolor、未必加载 hyperref。
    # \providecommand 在模板已定义时是 no-op（默认模板正是如此），
    # \ifdefined 守卫让没加载 hyperref 的模板也能编过。
    inject = "\n".join([
        r"\providecommand{\mdcovercolor}[1]{\definecolor{coverbg}{HTML}{#1}}",
        f"\\mdcovercolor{{{cover_color}}}",
        f"\\setcounter{{secnumdepth}}{{{secnum}}}",
        f"\\setcounter{{tocdepth}}{{{opts.toc_depth}}}",
        counter_reset,
        r"\ifdefined\hypersetup"
        f"\\hypersetup{{pdftitle={{{tex_escape(title)}}}, pdfauthor={{{tex_escape(author)}}}}}"
        r"\fi",
    ])
    preamble = preamble.replace("\\begin{document}", inject + "\n\n\\begin{document}")

    # 目录后、正文前注入 section 计数预置（正文无 # 一级标题时，令首个 ## = 1.1）
    toc_s = "\n\n".join(toc)
    pre_badge = (section_pre + "\n\n") if section_pre else ""
    doc = (preamble + "\n" + "\n\n".join(cover) + "\n\n"
           + toc_s + "\n\n" + pre_badge
           + "\n\n".join(body) + "\n\n\\end{document}\n")
    return doc


# ---------------------------------------------------------------------------
# 编译
# ---------------------------------------------------------------------------
def find_xelatex() -> Path:
    env = os.environ.get("XELATEX_PATH")
    if env and Path(env).exists():
        return Path(env)
    w = shutil.which("xelatex")
    if w:
        return Path(w)
    home = Path.home()
    cands = [
        home / "AppData/Local/Programs/TinyTeX/bin/windows/xelatex.exe",
        home / "AppData/Local/Programs/MiKTeX/miktex/bin/x64/xelatex.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "MiKTeX/miktex/bin/x64/xelatex.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "MiKTeX/miktex/bin/x64/xelatex.exe",
    ]
    for c in cands:
        if c.exists():
            return c
    for tl in (Path("C:/texlive"), Path("D:/texlive")):
        if tl.exists():
            hits = sorted(tl.glob("*/bin/windows/xelatex.exe"))
            if hits:
                return hits[0]
    raise RuntimeError(
        "未找到 xelatex。请安装 TinyTeX/MiKTeX/TeX Live，或设置环境变量 XELATEX_PATH。"
        "Windows 上可以运行 install_tex.ps1 装 TinyTeX。"
    )


_MISSING_CHAR_RE = re.compile(r"Missing character: There is no (\S+) \(U\+([0-9A-Fa-f]{2,6})\)")


def collect_missing_chars(log_text: str, warnings: list[str], limit: int = 20) -> None:
    """把 xelatex 的 "Missing character" 警告汇总成一条用户可读的提示。

    缺字形在 PDF 里表现为空白，不报错也不中断编译，很容易被当成"排版就是这样"。
    这里列出具体字符和码位，并给出 $...$ 的替代写法。常见符号已经由
    SYMBOL_FALLBACKS 兜住（❗ ⚠ 💡 见 EMOJI_ICONS），能走到这里的通常是两处都
    还没收录的冷僻字符。
    """
    found: dict[str, str] = {}
    for m in _MISSING_CHAR_RE.finditer(log_text):
        found.setdefault(m.group(2).upper(), m.group(1))
    if not found:
        return
    items = "、".join(f"{ch}(U+{code})" for code, ch in list(found.items())[:limit])
    more = "" if len(found) <= limit else f" 等共 {len(found)} 个"
    warnings.append(
        f"以下字符本机字体无字形，PDF 中显示为空白：{items}{more}"
        "。可改用 $...$ 包裹的等价写法（如 $\\forall$、$\\Leftarrow$、$\\varnothing$）；"
        "若该符号常用，可以加进 md_latex_pdf.py 的 SYMBOL_FALLBACKS 表。"
    )


def compile_tex(tex_path: Path, out_dir: Path, keep_aux: bool,
                warnings: list[str] | None = None) -> Path:
    exe = find_xelatex()
    pdf = out_dir / (tex_path.stem + ".pdf")
    # Windows 下必须把反斜杠转成正斜杠：xelatex 会把路径里的 \xxx 当控制序列解析。
    tex_arg = str(tex_path).replace("\\", "/")
    out_arg = str(out_dir).replace("\\", "/")
    base = [
        str(exe), "-interaction=nonstopmode", "-halt-on-error",
        "-synctex=0", "-file-line-error",
        f"-output-directory={out_arg}", tex_arg,
    ]
    # 循环编译直到 .aux 稳定（目录/引用需要多遍；上限 5 遍）
    # text=True 时必须显式 UTF-8 + errors="replace"：否则 Windows 下 Python 会按
    # GBK 解码 xelatex 的 UTF-8 中文输出，抛 UnicodeDecodeError。
    prev_hash = None
    for i in range(5):
        r = subprocess.run(base, cwd=out_dir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            log = out_dir / (tex_path.stem + ".log")
            tail = ""
            if log.exists():
                tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:])
            raise RuntimeError(f"xelatex 编译失败（exit {r.returncode}）：\n{tail}")
        aux = out_dir / (tex_path.stem + ".aux")
        if not aux.exists():
            break
        h = hashlib.md5(aux.read_bytes()).hexdigest()
        if h == prev_hash:
            break  # 引用/目录已稳定
        prev_hash = h
    # 兜底校验：即便 xelatex 返回 0，也确认 PDF 确实落盘（某些异常/缺宏包会返回
    # 0 却未产出文件，此时不能当作成功）。
    if not pdf.exists() or pdf.stat().st_size == 0:
        log = out_dir / (tex_path.stem + ".log")
        tail = ""
        if log.exists():
            tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:])
        raise RuntimeError(f"xelatex 未生成有效的 PDF（文件缺失或为空）：\n{tail}")
    if warnings is not None:
        log = out_dir / (tex_path.stem + ".log")
        if log.exists():
            collect_missing_chars(log.read_text(encoding="utf-8", errors="replace"), warnings)
    if not keep_aux:
        for ext in ("aux", "log", "out", "toc", "synctex.gz", "lof", "lot"):
            p = out_dir / (tex_path.stem + "." + ext)
            if p.exists():
                p.unlink()
    return pdf

# ---------------------------------------------------------------------------
# 可复用的转换入口（CLI 与 GUI 共用同一份逻辑）
# ---------------------------------------------------------------------------
def _is_ascii(s: str) -> bool:
    """判断字符串是否为纯 ASCII（xelatex 的 TEXMF_OUTPUT_DIRECTORY 只接受纯 ASCII）。"""
    try:
        s.encode("ascii")
        return bool(s)
    except UnicodeEncodeError:
        return False


def _default_opts(**overrides) -> argparse.Namespace:
    """构造一组与 CLI 默认一致的参数（供 GUI 调用 build_tex 使用）。"""
    d = dict(title=None, subtitle=None, header=None, cover_color=None,
             no_numbers=False, toc=True, toc_depth=3, keep_aux=False,
             template=None)
    d.update(overrides)
    return argparse.Namespace(**d)


def convert_file(md_path: str, out_dir: str | None = None, keep_aux: bool = False,
                 opts: argparse.Namespace | None = None,
                 out_stem: str | None = None) -> tuple[Path, Path, Ctx]:
    r"""核心转换：Markdown → <同名>.tex + <同名>.pdf。

    供 CLI（main）与 GUI（md_latex_pdf_gui）共用，转换逻辑只此一份。

    - md_path: 输入的 .md 文件；
    - out_dir: 输出目录，默认与 Markdown 文件同目录；
    - keep_aux: 是否保留编译中间文件（.aux/.log 等）；
    - opts: 已解析的 argparse.Namespace；缺省用默认值（与 CLI 默认一致）；
    - out_stem: 输出文件名（不含扩展名），默认取 Markdown 文件名（即 <同名>.tex/.pdf）。

    处理细节：
      - 输出目录含中文时（TinyTeX 的 putenv 不接受非 ASCII 输出路径），自动在纯
        ASCII 临时目录里 xelatex 编译，再把 .tex/.pdf/images 拷回目标目录；
      - 本地图片自动复制进输出目录 images/，并由 \graphicspath 引用。

    返回 (tex_path, pdf_path, ctx)。出错时抛异常（FileNotFoundError / RuntimeError 等）。
    """
    md_path = Path(md_path).resolve()
    if not md_path.exists():
        raise FileNotFoundError(f"文件不存在：{md_path}")
    out_dir = (Path(out_dir) if out_dir else md_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # utf-8-sig 自动剥掉文件开头的 BOM：否则首个 "# 标题" 因 \ufeff 前缀不识别为标题，
    # 导致第 1 个真实标题退化为正文、后续编号错乱（0.1 起编）。
    md_text = md_path.read_text(encoding="utf-8-sig")
    # U+FE0F（变体选择符，如 ❗️/⚠️ 的第二个码位）是零宽控制符：本机任何字体都没有
    # 它的字形，留着只会让 xelatex 报一条 Missing character；基字符不受影响，直接删。
    md_text = md_text.replace("\ufe0f", "")
    meta, body_md = parse_front_matter(md_text)

    if opts is None:
        opts = _default_opts(keep_aux=keep_aux)
    else:
        opts.keep_aux = keep_aux  # 以调用方为准，覆盖命令行缺省

    ctx = Ctx(md_path.parent, out_dir)
    ctx.cjk_mode = _has_cjk(md_text)  # 中文文档：直引号自动转中文弯引号
    tex_text = build_tex(meta, body_md, opts, ctx)

    out_stem = out_stem or md_path.stem

    # 输出目录必须纯 ASCII（TinyTeX putenv 限制）；否则在 ASCII 临时目录编译后再拷回。
    # Windows 的 %TEMP% 常以 8.3 短路径（如 C:\Users\XXXXXX~1\...）暴露，
    # xelatex 不接受短路径，所以用 resolve() 展开回长路径。
    work_dir = out_dir
    temp_dir = None
    if not _is_ascii(str(out_dir)):
        temp_dir = Path(tempfile.mkdtemp(prefix="md-latex-pdf_")).resolve()
        work_dir = temp_dir

    # 复制图片到工作目录 images/
    for src_str, name in ctx.images.items():
        src = Path(src_str)
        dst = work_dir / "images" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    tex_path = work_dir / (out_stem + ".tex")
    tex_path.write_text(tex_text, encoding="utf-8")

    try:
        pdf_path = compile_tex(tex_path, work_dir, keep_aux, warnings=ctx.warnings)
        if temp_dir is not None:
            final_tex = out_dir / (out_stem + ".tex")
            final_pdf = out_dir / (out_stem + ".pdf")
            shutil.copy2(tex_path, final_tex)
            if pdf_path.exists():
                shutil.copy2(pdf_path, final_pdf)
            img_src = temp_dir / "images"
            if img_src.exists():
                shutil.copytree(img_src, out_dir / "images", dirs_exist_ok=True)
            tex_path, pdf_path = final_tex, final_pdf
    finally:
        # 无论成功还是失败，都清理 ASCII 临时编译目录，避免残留（尤其编译报错时）
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return tex_path, pdf_path, ctx


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="md-latex-pdf", description="Markdown → LaTeX → PDF（用 xelatex 编译，LaTeX 风格紧凑排版）；不带参数或加 --gui 启动图形界面")
    ap.add_argument("input", nargs="?", default=None,
                    help="输入的 Markdown 文件（缺省启动图形界面）")
    ap.add_argument("outdir", nargs="?", default=None, help="输出目录（默认与输入同目录）")
    ap.add_argument("--header", help="页眉文字（覆盖 front matter 的 页眉/header）")
    ap.add_argument("--title", help="封面标题（覆盖 front matter）")
    ap.add_argument("--subtitle", help="封面副标题（覆盖 front matter）")
    ap.add_argument("--cover-color", default=None, help="封面纯色背景，如 #E4E9F0")
    ap.add_argument("--no-numbers", action="store_true", help="关闭章节自动编号")
    ap.add_argument("--toc", action=argparse.BooleanOptionalAction, default=True,
                    help="生成目录（默认开启；--no-toc 关闭）")
    ap.add_argument("--toc-depth", type=int, choices=[1, 2, 3, 4], default=3,
                    help="目录深度 1–4（默认 3 = 含三级标题；2 = 只到二级）")
    ap.add_argument("--keep-aux", action="store_true", help="保留编译中间文件（.aux/.log 等）")
    ap.add_argument("--template", default=None, metavar="模板",
                    help="排版模板：内置名（default / academic）或 .tex 文件路径；缺省用 default。"
                         "模板须自带生成器所需定义（listings/tcolorbox/符号回退表…）"
                         "并含 __PAGE_HEADER__ / __SYMBOL_FALLBACKS__ 占位符")
    ap.add_argument("--open", action="store_true", help="生成后打开 PDF")
    ap.add_argument("--gui", action="store_true",
                    help="启动图形界面（拖入 .md 文件即可转换）")
    ap.add_argument("--version", action="version", version=f"md-latex-pdf {VERSION}")
    args = ap.parse_args(argv)

    # 图形界面入口：无输入文件或显式 --gui
    if args.gui or args.input is None:
        try:
            from md_latex_pdf_gui import launch
        except ImportError as e:
            print(f"错误：无法加载图形界面（{e}）。请确认 md_latex_pdf_gui.py 与 md_latex_pdf.py 在同一目录。",
                  file=sys.stderr)
            return 1
        return launch()

    md_path = Path(args.input).resolve()
    if not md_path.exists():
        print(f"错误：文件不存在 {md_path}", file=sys.stderr)
        return 2
    out_dir = (Path(args.outdir) if args.outdir else md_path.parent).resolve()

    try:
        tex_path, pdf, ctx = convert_file(md_path, out_dir, keep_aux=args.keep_aux, opts=args)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        # ValueError 来自模板校验（如缺 \begin{document}），属用户输入问题，
        # 打一句错误就够了，用不着抛堆栈。
        print(f"错误：{e}", file=sys.stderr)
        return 1

    print(f"TeX : {tex_path}")
    for w in ctx.warnings:
        print(f"警告: {w}", file=sys.stderr)
    print(f"PDF : {pdf}")
    if args.open:
        os.startfile(str(pdf))  # type: ignore[attr-defined]  # startfile 需字符串路径
    return 0


class Ctx:
    """转换上下文：Markdown 文件所在目录、输出目录、脚注、图片映射、警告。"""

    def __init__(self, md_dir: Path, outdir: Path):
        self.md_dir = md_dir
        self.outdir = outdir
        self.footnotes: dict[str, str] = {}
        self.images: dict[str, str] = {}
        self.warnings: list[str] = []
        self.cjk_mode = False  # 文档含中文时为 True（启用直引号→中文弯引号）
        # 标题提级量：正文最高若有二级标题（# 被封面吸收），提级 1，令编号从 1 开始
        self.heading_shift = 0


if __name__ == "__main__":
    sys.exit(main())
