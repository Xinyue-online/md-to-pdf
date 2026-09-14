#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_symbol_fallback.py — 正文符号能不能排出来的回归自测。

背景见 md_latex_pdf.py 里 SYMBOL_FALLBACKS 与 xeCJK 字符类两处注释。缺字形的符号
在 PDF 里就是空白：xelatex 只在 .log 里写一行 "Missing character"，不报错也不中断，
没人会注意到，所以这些符号得专门测。符号分三条路，每条都要守住：

  A. CJK 字符类（导言区那条 \\xeCJKDeclareCharClass）：中文字体有字形、西文主字体
     没有的码位。罗马数字 Ⅰ Ⅱ Ⅲ、制表符 ─ │、■ □ ▲ ●、′ ″ 都在这里；
  B. SYMBOL_FALLBACKS 回退表：两个字体都没有字形，但有 LaTeX 等价写法的符号，
     如 ∀ ⇐ ⊆ ⊂ ∂ ∇ ⊗ ℝ ⌈ ∵ ✓；
  C. EMOJI_ICONS 图标表：三个表情/警示标记 ❗(U+2757) ⚠(U+26A0) 💡(U+1F4A1)，
     中文字体与 Latin Modern 都没字形，映射到 Windows 自带 Segoe UI Symbol。
     U+FE0F 变体选择符（❗️/⚠️ 的第二个码位）在转换时直接删掉，不能出现在 .log 里。

跑法（需要 xelatex，在仓库根目录执行）：
    python tests/test_symbol_fallback.py            # 全量：逐符号编译 + 字符类清单 + 栅格 + 页眉 + 引述标记
    python tests/test_symbol_fallback.py --quick    # 只抽 11 个符号（改完表快速看一眼）

检查五件事：
  1. 回退表里每个符号（含 ❗ ⚠ 💡）单独编译无报错、无 "Missing character"；
  2. 字符类清单（含 Ⅰ Ⅱ Ⅲ）同样无报错、无缺字；
  3. 栅格抽查：把「甲 X 乙」渲染成位图数墨点，比只有「甲 乙」的对照多出墨点，
     才算真的画出了字形。缺字形时宽度还在、墨迹没有，只比宽度会误判；
  4. 页眉里的符号。页眉在导言区就被读成记号，最容易漏，见导言区注释；
  5. 引述渲染：`> ❗` / `> ⚠` / `> 💡` 是否落成对应彩色告示框（短文本当标题、
     长句留正文），不带标记的普通引用是否落成中性的灰底竖条框。
退出码 0 = 全通过，1 = 有失败项。中间产物写在 _symtest/（可随时删除）。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 脚本住在 tests/ 下，模块在上一层
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import md_latex_pdf  # noqa: E402

WORK = Path(__file__).resolve().parent / "_symtest"
PRE = ("\\documentclass[zihao=-4]{ctexart}\n\\usepackage{amsmath,amsthm,amssymb}\n"
       "\\usepackage{pifont}\n"  # 勾叉映射用 \ding
       "\\pagestyle{empty}\n")

# 走 CJK 字符类声明的符号（不在 SYMBOL_FALLBACKS 里）。罗马数字 Ⅰ Ⅱ Ⅲ 最容易缺，
# 其余是同一段声明覆盖到的常用符号，顺手一起守住。
CJK_CLASS_SYMBOLS = (
    "Ⅰ Ⅱ Ⅲ Ⅳ Ⅴ Ⅵ Ⅶ Ⅷ Ⅸ Ⅹ Ⅺ Ⅻ ⅰ ⅱ ⅲ ⅳ ⅴ "          # 罗马数字
    "′ ″ ‵ ― ⌒ ℅ ℉ ℡ "                                    # 角分秒、其它
    "─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼ ═ ║ ╔ ╗ ╚ ╝ "                 # 制表符
    "▁ ▂ ▃ █ ▌ ▓ "                                         # 方块元素
    "■ □ ▲ △ ▼ ▽ ◆ ◇ ○ ◎ ● ◢ ◣ ◤ ◥ ★ ☆ ☉ ♀ ♂ "          # 几何图形
    "① ② ③ ⑩ ⑴ ⒈ "                                       # 带圈数字
    "σ μ π Ω ∈ ∑ ∏ ∫ √ ∞ ≠ ≤ ≥ ± × ÷ ∴ ∵ → ← ↑ ↓ ↖ ↗ ↘ ↙"  # 中文字体本来就有的
)

# 栅格抽查挑的符号：回退表（∀ ⇐ ∂ ⊗ ℝ ⌈ ✓）、字符类（Ⅰ ■ ─ ★）、图标表（❗ ⚠ 💡）各取几个
RASTER_SYMBOLS = "∀⇐⊆⊂∂∇⊗∅∃₀⁴↦Ⅰ■─★⌈✓❗⚠💡"

# 引述用例：(Markdown 片段, .tex 里必须出现的那一行)。短文本当标题，长句或句末带标点的
# 留正文；不带标记的普通引用走中性的灰底竖条框（mdpdfquote），不会误落成彩色告示框。
QUOTE_MARK_CASES = [
    ("> 💡 思路\n> 先画受力图，再判断方向。", r"\begin{tipbox}[思路]"),
    ("> ⚠ 单位换算最容易出错，务必逐项核对一遍再往下算。", r"\begin{warnbox}[警告]"),
    ("> ❗ 易错提醒\n> 磁通量变化率要取绝对值。", r"\begin{cautionbox}[易错提醒]"),
    ("> ❗ 这条很长的一句话应该留在正文里：安培力方向的判断是本章最容易出错的地方。",
     r"\begin{cautionbox}[注意]"),
    ("> ⚠️ 单位统一", r"\begin{warnbox}[单位统一]"),
    ("> ❗紧贴标记也认", r"\begin{cautionbox}[紧贴标记也认]"),
    ("> 💡", r"\begin{tipbox}[提示]"),
    ("> 普通引用走浅灰底 + 左侧竖条的中性框。", r"\begin{mdpdfquote}"),
]


def cjk_class_declaration() -> str:
    """从真实导言区里取出 xeCJK 字符类那一段声明，内容跨多行。

    形如 \\xeCJKDeclareCharClass{CJK}{<多行码位列表>}。第一个花括号里是字符类名，
    要取的是第二个花括号配对结束的位置。
    """
    raw = md_latex_pdf.load_template()
    start = raw.index("\\xeCJKDeclareCharClass")

    def group_end(open_idx: int) -> int:
        depth = 0
        for i in range(open_idx, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    return i
        raise AssertionError("导言区里的 \\xeCJKDeclareCharClass 花括号不配对")

    first = raw.index("{", start)          # {CJK}
    second = raw.index("{", group_end(first) + 1)  # 码位列表
    return raw[start:group_end(second) + 1]


def full_symbol_preamble() -> str:
    """等价于真实导言区里与符号相关的部分（字符类声明 + 回退表）。"""
    return cjk_class_declaration() + "\n" + md_latex_pdf.symbol_fallback_preamble()


def compile_doc(name: str, body: str, preamble_extra: str = "") -> Path:
    """编译一个最小文档，返回 PDF 路径（日志留在 _symtest/<name>.log）。"""
    tex = WORK / f"{name}.tex"
    tex.write_text(PRE + preamble_extra + "\n\\begin{document}\n" + body + "\n\\end{document}\n",
                   encoding="utf-8")
    subprocess.run(
        [str(md_latex_pdf.find_xelatex()), "-interaction=nonstopmode", "-synctex=0",
         "-file-line-error", "-output-directory=" + WORK.as_posix(), tex.as_posix()],
        cwd=WORK, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return WORK / f"{name}.pdf"


def compile_problems(name: str) -> list[str]:
    log = (WORK / f"{name}.log").read_text(encoding="utf-8", errors="replace")
    out = []
    errs = [ln.strip() for ln in log.splitlines()
            if ln.startswith("! ") or re.match(r"^\S+\.tex:\d+:", ln)]
    if errs:
        out.append("报错：" + " | ".join(errs[:2]))
    miss = missing_chars(name)
    if miss:
        out.append("缺字形：" + " ".join(miss[:40]))
    return out


def missing_chars(name: str) -> list[str]:
    log = (WORK / f"{name}.log").read_text(encoding="utf-8", errors="replace")
    return sorted({m.group(1) for m in
                   re.finditer(r"Missing character: There is no (\S+) ", log)})


def dark_pixels(pdf: Path, page: int = 0, dpi: int = 200) -> int:
    import pymupdf
    pix = pymupdf.open(pdf)[page].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return sum(1 for b in pix.samples if b < 160)


def check_each_symbol(quick: bool) -> list[str]:
    symbols = list(md_latex_pdf.SYMBOL_FALLBACKS) + list(md_latex_pdf.EMOJI_ICONS)
    if quick:
        symbols = [c for c in "∀⇐⊂∂⊗₀⁴↦❗⚠💡" if c in md_latex_pdf.SYMBOL_FALLBACKS
                   or c in md_latex_pdf.EMOJI_ICONS]
    fails = []
    print(f"== A) 回退表逐符号编译校验（{len(symbols)} 个，含图标表 ❗ ⚠ 💡）")
    for ch in symbols:
        name = f"c{ord(ch):04X}"
        compile_doc(name, f"甲 {ch} 乙 \\par\n数学模式：${ch}$ \\par", full_symbol_preamble())
        problems = compile_problems(name)
        if problems:
            fails.append(f"{ch} U+{ord(ch):04X}: {'; '.join(problems)}")
        print(f"  {'OK ' if not problems else 'FAIL'} {ch} U+{ord(ch):04X}")
    return fails


def check_cjk_class_symbols() -> list[str]:
    """守住 xeCJK 字符类那一段声明（罗马数字、制表符、几何图形等）。"""
    symbols = CJK_CLASS_SYMBOLS.split()
    print(f"== B) 字符类声明：交给中文字体的符号（{len(symbols)} 个）")
    body = "\n".join(" ".join(symbols[i:i + 15]) + r" \par"
                     for i in range(0, len(symbols), 15))
    compile_doc("cjkclass", body, cjk_class_declaration() + "\n")
    problems = compile_problems("cjkclass")
    print(f"  {'OK ' if not problems else 'FAIL'} {problems or '全部有字形'}")
    return [f"字符类清单：{'；'.join(problems)}"] if problems else []


def check_raster() -> list[str]:
    fails = []
    print("== C) 栅格抽查：确认真的画出了墨迹（不带声明走的是空白）")
    base = dark_pixels(compile_doc("base", "甲 乙"))
    for ch in RASTER_SYMBOLS:
        new = dark_pixels(compile_doc(f"r{ord(ch):04X}", f"甲 {ch} 乙", full_symbol_preamble()))
        old = dark_pixels(compile_doc(f"o{ord(ch):04X}", f"甲 {ch} 乙", "% 无字符类、无回退表"))
        ok = new > base and old <= base  # 带声明的要盖过空白对照，不带声明的应与对照持平
        print(f"  {'OK ' if ok else 'FAIL'} {ch}: 对照 {base} / 无声明 {old} / 有声明 {new}")
        if not ok:
            fails.append(f"{ch}: 对照 {base} 无声明 {old} 有声明 {new}")
    return fails


def check_header() -> list[str]:
    print("== D) 页眉里的符号（导言区就把它读成记号，最容易漏）")
    md = WORK / "header.md"
    md.write_text("# 无符号封面\n\n页眉：∀ 页眉 Ⅰ ⇐ 💡 ❗\n---\n\n# 正文\n\n内容 ■。\n",
                  encoding="utf-8")
    subprocess.run([sys.executable, str(Path(md_latex_pdf.__file__)), str(md), "--keep-aux"],
                   cwd=WORK, capture_output=True, text=True, encoding="utf-8", errors="replace")
    problems = compile_problems("header")
    print(f"  {'OK ' if not problems else 'FAIL'} 页眉文档：{problems or '无报错、无缺字'}")
    return problems


def check_quote_marks() -> list[str]:
    """引述渲染：> ❗ / > ⚠ / > 💡 落成对应彩色告示框，普通引用落成中性灰底框。"""
    print("== E) 引述渲染：标记 → 彩色告示框、普通引用 → 中性灰底框")
    md = WORK / "quotemarks.md"
    md.write_text("# 引述标记\n\n" + "\n\n".join(c[0] for c in QUOTE_MARK_CASES) + "\n",
                  encoding="utf-8")
    subprocess.run([sys.executable, str(Path(md_latex_pdf.__file__)), str(md), "--keep-aux"],
                   cwd=WORK, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tex = (WORK / "quotemarks.tex").read_text(encoding="utf-8", errors="replace")
    fails = []
    for src, want in QUOTE_MARK_CASES:
        head = src.splitlines()[0]
        ok = want in tex
        print(f"  {'OK ' if ok else 'FAIL'} {head} → {want}")
        if not ok:
            fails.append(f"引述标记未渲染成 {want}：{head}")
    problems = compile_problems("quotemarks")
    print(f"  {'OK ' if not problems else 'FAIL'} 编译：{problems or '无报错、无缺字'}")
    if problems:
        fails.append(f"引述标记文档：{'；'.join(problems)}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser(description="md-latex-pdf 正文符号回退自测")
    ap.add_argument("--quick", action="store_true", help="只抽 11 个符号（快速回归）")
    args = ap.parse_args()
    # Windows 控制台常是 GBK，❗ ⚠ 💡 打不出来会抛 UnicodeEncodeError。这里让 stdout
    # 把编不出的字符换成 "?"，同一行还带着码位 U+2757，不影响判读。
    try:
        sys.stdout.reconfigure(errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    WORK.mkdir(exist_ok=True)

    fails = check_each_symbol(args.quick)
    fails += check_cjk_class_symbols()
    if not args.quick:
        fails += check_raster() + check_header() + check_quote_marks()
    print()
    if fails:
        print(f"失败 {len(fails)} 项：")
        for f in fails:
            print("  X", f)
        return 1
    print("全部通过：字符类声明、回退表、图标表三条路上的符号都排得出来，引述渲染（彩色/中性）也正确。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
