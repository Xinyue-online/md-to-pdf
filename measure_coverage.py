#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure_coverage.py — 符号覆盖实测工具（改符号相关配置时用）。

回答两个问题，避免靠猜：
  1. **哪些码位该交给中文字体**（导言区的 xeCJK 字符类声明）？
     答案 = 「SimSun 与 FangSong 都有字形」且「西文主字体 Latin Modern 没有」。
     前者用 fontTools 读系统字体得到，后者靠实测（不带字符类声明编译一遍，
     日志里的 Missing character 就是 LM 没有的）。**每段必须连续**——段内一旦夹着
     LM 本来就能显示的字符，声明过去反而会把它弄坏，所以脚本只输出连续段。
  2. **哪些符号仍然画不出来、需要进 SYMBOL_FALLBACKS？**
     判定：在字符类区间内 → 看中文字体有没有字形；在区间外 → 看 LM 有没有字形。
     脚本会顺手检查当前回退表：哪些是多余的（本来就能显示）、哪些仍是 broken。

跑法（需要 xelatex）：
    python measure_coverage.py            # 打印报告 + 可直接粘贴的声明片段
    python measure_coverage.py --blocks   # 额外逐区块列出"现在还是空白"的字符

注意：脚本里的 DECLARED 必须与导言区那段声明的码位保持一致（改了导言区就改这里）。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from fontTools.ttLib import TTFont, TTCollection

HERE = Path(__file__).resolve().parent
WORK = HERE / "_symtest"
sys.path.insert(0, str(HERE))
import md_to_pdf  # noqa: E402

# 扫描的区块（中文技术文档里可能出现的符号区）
BLOCKS = [(0x2000, 0x206F, "常用标点"), (0x20A0, 0x20BF, "货币"),
          (0x2100, 0x214F, "字母式符号 ℂ ℓ ℏ"), (0x2150, 0x218F, "数字式 Ⅰ ⅰ ⅓"),
          (0x2190, 0x21FF, "箭头"), (0x2200, 0x22FF, "数学运算符"),
          (0x2300, 0x23FF, "杂项技术 ⌈⌉"), (0x2460, 0x24FF, "带圈字符 ①②"),
          (0x2500, 0x257F, "制表符"), (0x2580, 0x259F, "方块元素"),
          (0x25A0, 0x25FF, "几何图形 ■▲●"), (0x2600, 0x26FF, "杂项符号 ★☆"),
          (0x2700, 0x27BF, "装饰符号 ✓✗"), (0x2E80, 0x2EFF, "CJK 部首"),
          (0x3000, 0x303F, "CJK 标点"), (0x3200, 0x32FF, "带圈 CJK ㈠"),
          (0x3300, 0x33FF, "CJK 兼容 ㌀"), (0xFE10, 0xFE4F, "CJK 兼容形式"),
          (0xFF00, 0xFFEF, "全角形式")]
SKIP_CAT = {"Cn", "Cc", "Cs", "Cf", "Co", "Zl", "Zp"}

# 与导言区 xeCJK 字符类声明一致的码位（改导言区后同步这里）
DECLARED = [(0x0370, 0x03FF), (0x2015, 0x2015), (0x2032, 0x2033), (0x2035, 0x2035),
            (0x2070, 0x209F), (0x2105, 0x2105), (0x2109, 0x2109), (0x2121, 0x2121),
            (0x2160, 0x216B), (0x2170, 0x2179), (0x2190, 0x21FF), (0x2200, 0x22FF),
            (0x2312, 0x2312), (0x2460, 0x24FF), (0x2500, 0x254B), (0x2550, 0x2573),
            (0x2581, 0x258F), (0x2593, 0x2595), (0x25A0, 0x25A1), (0x25B2, 0x25B3),
            (0x25BC, 0x25BD), (0x25C6, 0x25C7), (0x25CB, 0x25CB), (0x25CE, 0x25CF),
            (0x25E2, 0x25E5), (0x2605, 0x2606), (0x2609, 0x2609), (0x2640, 0x2640),
            (0x2642, 0x2642)]

FONTS = {"SimSun": r"C:\Windows\Fonts\simsun.ttc",
         "FangSong": r"C:\Windows\Fonts\simfang.ttf"}


def font_coverage(path: str) -> set[int]:
    try:
        fonts = TTCollection(path).fonts
    except Exception:
        fonts = [TTFont(path, fontNumber=0, lazy=True)]
    cov: set[int] = set()
    for f in fonts:
        for t in f["cmap"].tables:
            if t.isUnicode():
                cov |= set(t.cmap.keys())
    return cov


def measured_lm_missing(chars: list[str]) -> set[int]:
    """不带字符类声明编译一遍：日志里的 Missing character = Latin Modern 没有的码位。"""
    WORK.mkdir(exist_ok=True)
    tex = WORK / "lm_probe.tex"
    tex.write_text(
        "\\documentclass[zihao=-4]{ctexart}\n\\usepackage{amsmath,amsthm,amssymb}\n"
        "\\pagestyle{empty}\n\\begin{document}\n"
        + "\n".join(" ".join(chars[i:i + 20]) + r" \par" for i in range(0, len(chars), 20))
        + "\n\\end{document}\n", encoding="utf-8")
    subprocess.run([str(md_to_pdf.find_xelatex()), "-interaction=nonstopmode", "-synctex=0",
                    "-output-directory=" + WORK.as_posix(), tex.as_posix()],
                   cwd=WORK, capture_output=True)
    log = (WORK / "lm_probe.log").read_text(encoding="utf-8", errors="replace")
    return {int(m.group(2), 16) for m in
            re.finditer(r"Missing character: There is no (\S+) \(U\+([0-9A-Fa-f]{4,6})\)", log)}


def main() -> int:
    ap = argparse.ArgumentParser(description="符号覆盖实测（xeCJK 字符类 + 回退表）")
    ap.add_argument("--blocks", action="store_true", help="逐区块列出仍然空白的字符")
    args = ap.parse_args()
    WORK.mkdir(exist_ok=True)

    cov = {name: font_coverage(path) for name, path in FONTS.items()}
    cjk_lacks = {c for c in range(0x2000, 0x10000)
                 if any(c not in cov[n] for n in FONTS)
                 and unicodedata.category(chr(c)) not in SKIP_CAT}
    chars = [chr(c) for lo, hi, _ in BLOCKS for c in range(lo, hi + 1)
             if unicodedata.category(chr(c)) not in SKIP_CAT]
    lm_missing = measured_lm_missing(chars)
    print(f"扫描 {len(chars)} 个码位；中文字体缺 {len(cjk_lacks)}；Latin Modern 缺 {len(lm_missing)}")

    # ---- 1. 该交给中文字体的码位（要连续段）----
    fix = sorted(c for c in (ord(ch) for ch in chars)
                 if all(c in cov[n] for n in FONTS) and c in lm_missing
                 and not any(lo <= c <= hi for lo, hi in DECLARED))
    runs: list[list[int]] = []
    for c in fix:
        if runs and c == runs[-1][1] + 1:
            runs[-1][1] = c
        else:
            runs.append([c, c])
    print(f"\n== 建议补进 xeCJK 字符类的码位：{len(fix)} 个 / {len(runs)} 段 ==")
    snippet = ", ".join(f'"{a:04X} -> "{b:04X}' if b > a else f'"{a:04X}' for a, b in runs)
    print("  " + snippet if fix else "  （无：导言区声明已覆盖）")

    # ---- 2. 仍然画不出来的码位（该进回退表）----
    def broken(code: int) -> bool:
        in_decl = any(lo <= code <= hi for lo, hi in DECLARED)
        return (code in cjk_lacks) if in_decl else (code in lm_missing)

    still = sorted(c for c in (ord(ch) for ch in chars) if broken(c))
    print(f"\n== 两条路都救不了、仍然是空白的码位：{len(still)} 个 ==")

    # ---- 3. 现有回退表体检 ----
    redundant = [ch for ch in md_to_pdf.SYMBOL_FALLBACKS if not broken(ord(ch))]
    print(f"\n== 当前回退表 {len(md_to_pdf.SYMBOL_FALLBACKS)} 条 ==")
    print("  多余（本来就能显示，可删；¹²³ 是为角标统一而有意保留）：",
          " ".join(f"{c}(U+{ord(c):04X})" for c in redundant) or "无")
    covered = {c for c in still if not any(ord(ch) == c for ch in md_to_pdf.SYMBOL_FALLBACKS)}
    print(f"  仍是空白且表里没收的码位：{len(covered)} 个（多数没有 LaTeX 等价写法）")

    if args.blocks:
        print("\n== 逐区块：仍然空白的字符 ==")
        for lo, hi, name in BLOCKS:
            bad = [chr(c) for c in range(lo, hi + 1) if c in still]
            if bad:
                shown = " ".join(bad[:60]) + (" …" if len(bad) > 60 else "")
                print(f"  {name} U+{lo:04X}-U+{hi:04X}（{len(bad)}）: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
