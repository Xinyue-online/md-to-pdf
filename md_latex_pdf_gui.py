#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""md-latex-pdf 的图形界面：把 .md 文件拖进窗口，转出 LaTeX 源码和 PDF。

- 窗口标题「md-latex-pdf 转换器」。拖入 Markdown（.md）文件，也可以点「选择文件」。
- 转换直接调 md_latex_pdf.py 的 convert_file，LaTeX 表格、代码高亮、数学公式这些都在。
- 产物 <同名>.tex 和 <同名>.pdf 落在 md 同一目录；同名文件已存在时先弹窗问要不要覆盖。
- 「排版模板」下拉里是内置模板（default / academic），也可以直接填或浏览一个 .tex 路径。
- 出错只在窗口里显示一句摘要，后台堆栈不往外打。

窗口风格：深色顶栏、卡片布局、彩色记录区。

依赖：
    python -m pip install tkinterdnd2        # 原生拖拽；没装就退回「选择文件」按钮
    本机还要有 xelatex（运行 install_tex.ps1 可装 TinyTeX）。
"""
import os
import queue
import re
import sys
import threading
from pathlib import Path

# 脚本所在目录不一定在 sys.path 里，先补上，才 import 得到同目录的 md_latex_pdf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import md_latex_pdf

# 目录层级下拉的文字 → (是否生成目录, tocdepth)。「无目录」表示不生成目录页。
TOC_CHOICES = ("无目录", "1 级", "2 级", "3 级", "4 级")
TOC_DEFAULT = "3 级"

# 排版模板下拉里「（默认）」指 md_latex_pdf 的 default.tex，其余选项是内置模板名。
# 下拉框可编辑，所以往里粘一个 .tex 路径也认。
TEMPLATE_DEFAULT_LABEL = "（默认）"


def template_options() -> list[str]:
    """下拉候选：默认项，加上 templates 目录里的内置模板名（default / academic 等）。"""
    return [TEMPLATE_DEFAULT_LABEL] + sorted(md_latex_pdf.builtin_templates())


def template_value(choice: str) -> str | None:
    """把下拉框（或输入框）里的文字换成 convert_file 的 template 参数；None 表示用默认模板。"""
    v = (choice or "").strip()
    if not v or v == TEMPLATE_DEFAULT_LABEL:
        return None
    return v


def toc_options(choice: str) -> tuple[bool, int]:
    """把「N 级 / 无目录」这段下拉文字转成 convert_file 要的 (toc, toc_depth)。

    下拉是只读的，值只会来自 TOC_CHOICES。真拿到认不出的文字就按「无目录」算：
    少一个目录页能接受，凭空多出一个用户没选的目录不行。
    """
    m = re.match(r"\s*([1-4])\s*级", choice or "")
    if not m:
        return False, 3
    return True, int(m.group(1))


# tkinterdnd2 提供真正的 OS 级拖拽；没装就退回「选择文件」按钮。
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except Exception:  # noqa: BLE001
    _HAS_DND = False

_FONT = "Microsoft YaHei UI"
# ---- 配色 ----
_BG = "#eef1f7"
_CARD = "#ffffff"
_BORDER = "#d9dfec"
_HEAD = "#2b3a67"
_HEAD_SUB = "#b7c2e8"
_ACCENT = "#2f6bff"
_ACCENT_DARK = "#2454d0"
_TEXT = "#243044"
_MUTED = "#7b8799"
_ZONE_ACTIVE = "#e8f1ff"
_OK = "#1f8a4c"
_ERR = "#d33a3a"


def _short_error(exc: Exception) -> str:
    """把异常压成一句短摘要，堆栈不外露。

    xelatex 编译失败时，异常消息是 "xelatex 编译失败（exit N）：\n" 接上 log 尾部，
    而 log 尾部常常是 "Output written on ...(N pages)." 这种成功行。直接取最后一行
    会把真正的报错（比如 "Undefined control sequence"）盖掉。所以先找 file-line-error
    行（...tex:NNNN: ... 那种），再找 LaTeX 的 "! ..." 行，都没有才退回最后一行。
    """
    text = str(exc).replace("\r\n", "\n").strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return f"{exc.__class__.__name__}: {exc}"
    # 优先：file-line-error 行，形如 c:/xxx/yyy.tex:2261: Undefined control sequence.
    for ln in lines:
        if re.search(r"\.tex:\d+:", ln):
            return ln[:200]
    # 其次：LaTeX 错误行 "! ..."
    for ln in lines:
        if ln.startswith("!"):
            return ln[1:].strip()[:200]
    # 兜底：最后一行（普通异常的消息本身就是错误）
    return lines[-1][:200]


def _card(parent):
    """白底卡片，外面那圈细边框由外层 Frame 画。返回 (外框, 内芯)。"""
    outer = tk.Frame(parent, bg=_BORDER, bd=0, highlightthickness=1,
                     highlightbackground=_BORDER, highlightcolor=_BORDER)
    inner = tk.Frame(outer, bg=_CARD)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    return outer, inner


class MdToPdfApp:
    """单窗口 GUI：拖入 .md，转出 <同名>.tex 和 <同名>.pdf。"""

    def __init__(self):
        # import 成功不代表 tkdnd（Tcl 扩展）加载得起来，打包成 exe 缺数据文件就会翻车。
        # 所以实例化时再试一次，不行就退回纯 tk，窗口总归要能开。
        self._dnd = False
        if _HAS_DND:
            try:
                self.root = TkinterDnD.Tk()
                self._dnd = True
            except Exception:  # noqa: BLE001
                self.root = tk.Tk()
        else:
            self.root = tk.Tk()
        self.root.title("md-latex-pdf 转换器")
        self.root.geometry("640x690")
        self.root.minsize(580, 610)
        self.root.configure(bg=_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        self.last_pdf: Path | None = None
        self._busy = False
        # Tk 控件不是线程安全的，工作线程只往队列里塞结果，由主线程的 _poll 消费。
        self._queue: "queue.Queue[tuple]" = queue.Queue()

        self._build_ui()
        self._register_drop()
        self.root.after(100, self._poll)

    # ---- UI 构建 ----
    def _build_ui(self):
        # 顶栏
        head = tk.Frame(self.root, bg=_HEAD)
        head.pack(fill="x")
        tk.Label(head, text="md-latex-pdf 转换器", font=(_FONT, 16, "bold"),
                 bg=_HEAD, fg="#ffffff").pack(pady=(14, 0), padx=18, anchor="w")
        tk.Label(head, text="把 Markdown 拖进来，就在文件所在目录生成 LaTeX 源码 + A4 PDF",
                 font=(_FONT, 9), bg=_HEAD, fg=_HEAD_SUB).pack(pady=(2, 14), padx=18, anchor="w")

        body = tk.Frame(self.root, bg=_BG)
        body.pack(fill="both", expand=True, padx=16, pady=14)

        # 1) 拖放卡片
        drop_card, self.drop_zone = _card(body)
        drop_card.pack(fill="x")
        self.drop_zone.configure(height=112)
        self.drop_zone.pack_propagate(False)
        tk.Label(self.drop_zone, text="把 Markdown 文件拖到这里", font=(_FONT, 14, "bold"),
                 bg=_CARD, fg="#33415f").pack(pady=(24, 4))
        tk.Label(self.drop_zone,
                 text="支持多文件 · 产物 <同名>.tex + <同名>.pdf 写到文件所在目录 · 排版走 LaTeX",
                 font=(_FONT, 9), bg=_CARD, fg=_MUTED).pack()
        self.drop_label = self.drop_zone.winfo_children()[0]

        # 2) 选项行：目录层级（无目录 / 1–4 级）
        opt_card, opt_inner = _card(body)
        opt_card.pack(fill="x", pady=(10, 0))
        tk.Label(opt_inner, text="目录层级", font=(_FONT, 9, "bold"),
                 bg=_CARD, fg="#33415f").pack(side="left", padx=(14, 8), pady=9)
        self.toc_var = tk.StringVar(value=TOC_DEFAULT)
        ttk.Combobox(opt_inner, textvariable=self.toc_var, values=list(TOC_CHOICES),
                     state="readonly", width=8, font=(_FONT, 9)).pack(side="left", pady=9)
        tk.Label(opt_inner, text="（# 记 1 级、## 记 2 级…；选「无目录」则不生成目录页）",
                 font=(_FONT, 8), bg=_CARD, fg=_MUTED).pack(side="left", padx=10)

        # 2b) 选项行：排版模板（「（默认）」就是 templates\default.tex）
        tpl_card, tpl_inner = _card(body)
        tpl_card.pack(fill="x", pady=(8, 0))
        tpl_row = tk.Frame(tpl_inner, bg=_CARD)
        tpl_row.pack(fill="x")
        tk.Label(tpl_row, text="排版模板", font=(_FONT, 9, "bold"),
                 bg=_CARD, fg="#33415f").pack(side="left", padx=(14, 8), pady=9)
        # 右侧按钮先 pack，可拉伸的下拉框后 pack。Tk 按 pack 顺序分空间，
        # 下拉框若先 pack 又带 expand=True，会把剩余宽度吃光，按钮就被挤出可视区。
        self._add_btn(tpl_row, "默认", self._reset_template, padx=(0, 14), side="right")
        self._add_btn(tpl_row, "浏览…", self._choose_template, padx=(0, 6), side="right")
        self.template_var = tk.StringVar(value=TEMPLATE_DEFAULT_LABEL)
        # state="normal" 让下拉框可编辑，能直接粘 .tex 路径，不必先选内置模板
        ttk.Combobox(tpl_row, textvariable=self.template_var, values=template_options(),
                     state="normal", width=16, font=(_FONT, 9)).pack(
            side="left", fill="x", expand=True, pady=9)
        tk.Label(tpl_inner,
                 text="内置模板：" + "、".join(sorted(md_latex_pdf.builtin_templates()))
                      + "（default = 紧凑讲义；academic = 学术论文版心）；也可直接填 .tex 路径",
                 font=(_FONT, 8), bg=_CARD, fg=_MUTED).pack(anchor="w", padx=14, pady=(0, 8))

        # 3) 记录卡片
        log_card, log_inner = _card(body)
        log_card.pack(fill="both", expand=True, pady=(14, 0))
        tk.Label(log_inner, text="转换记录", font=(_FONT, 9, "bold"),
                 bg=_CARD, fg=_MUTED).pack(anchor="w", padx=14, pady=(8, 2))
        log_area = tk.Frame(log_inner, bg=_CARD)
        log_area.pack(fill="both", expand=True, padx=14, pady=(2, 12))
        self.status = tk.Text(log_area, wrap="word", state="disabled",
                              bg="#fbfcfe", fg=_TEXT, font=(_FONT, 9),
                              relief="flat", bd=0, highlightthickness=1,
                              highlightbackground="#e6eaf3", padx=8, pady=6)
        sb = tk.Scrollbar(log_area, command=self.status.yview)
        self.status.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.status.pack(side="left", fill="both", expand=True)
        self.status.tag_configure("ok", foreground=_OK)
        self.status.tag_configure("err", foreground=_ERR)
        self.status.tag_configure("dim", foreground=_MUTED)

        # 4) 按钮行
        acts = tk.Frame(body, bg=_BG)
        acts.pack(fill="x", pady=(12, 2))
        tk.Label(acts, text="需要本机有 xelatex（没有就装一下：看 README，或跑 install_tex.ps1）",
                 font=(_FONT, 8), bg=_BG, fg=_MUTED).pack(side="left")
        btns = tk.Frame(acts, bg=_BG)
        btns.pack(side="right")
        self._add_btn(btns, "选择文件", self._choose_files, primary=True, padx=(0, 8))
        self._add_btn(btns, "打开最新PDF", self._open_pdf, padx=(0, 8))
        self._add_btn(btns, "清空记录", self._clear)

        if not self._dnd:
            self._log("拖拽没启用（缺 tkinterdnd2，或 tkdnd 没加载起来）。可以先用「选择文件」，"
                      "或者 pip install tkinterdnd2 之后重启。", "dim")

    def _add_btn(self, parent, text, cmd, primary=False, padx=(0, 0), side="left"):
        if primary:
            b = tk.Button(parent, text=text, command=cmd, font=(_FONT, 10),
                          bg=_ACCENT, fg="#ffffff", activebackground=_ACCENT_DARK,
                          activeforeground="#ffffff", relief="flat", bd=0,
                          padx=14, pady=6, cursor="hand2")
        else:
            b = tk.Button(parent, text=text, command=cmd, font=(_FONT, 10),
                          bg="#e7ebf5", fg=_TEXT, activebackground="#d5dcec",
                          activeforeground=_TEXT, relief="flat", bd=0,
                          padx=12, pady=6, cursor="hand2")
        b.pack(side=side, padx=padx)
        return b

    # ---- 拖拽注册 ----
    def _register_drop(self):
        if not self._dnd:
            return
        # 窗口和拖放区都注册：拖到窗口空白处也认
        for w in (self.root, self.drop_zone):
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)
                w.dnd_bind("<<DropEnter>>", self._on_drop_enter)
                w.dnd_bind("<<DropLeave>>", self._on_drop_leave)
            except Exception:  # noqa: BLE001
                pass

    def _on_drop_enter(self, _event):
        self.drop_zone.configure(bg=_ZONE_ACTIVE)
        self.drop_label.configure(bg=_ZONE_ACTIVE)

    def _on_drop_leave(self, _event):
        self.drop_zone.configure(bg=_CARD)
        self.drop_label.configure(bg=_CARD)

    # ---- 交互入口 ----
    def _on_drop(self, event):
        self.drop_zone.configure(bg=_CARD)
        try:
            paths = list(self.root.tk.splitlist(event.data))
        except Exception:  # noqa: BLE001
            paths = str(event.data).split()
        self._handle_paths(paths)

    def _choose_files(self):
        files = filedialog.askopenfilenames(
            title="选择 Markdown 文件",
            filetypes=[("Markdown", "*.md"), ("全部文件", "*.*")],
            parent=self.root)
        if files:
            self._handle_paths(files)

    def _choose_template(self):
        """挑一个 .tex 排版模板。取消对话框就保持原值。"""
        cur = template_value(self.template_var.get())
        init = Path(cur).parent if cur else None
        path = filedialog.askopenfilename(
            title="选择排版模板（.tex）",
            initialdir=str(init) if init and init.is_dir() else str(md_latex_pdf.templates_dir()),
            filetypes=[("LaTeX 模板", "*.tex"), ("全部文件", "*.*")],
            parent=self.root)
        if path:
            self.template_var.set(path)

    def _reset_template(self):
        """把模板换回内置默认项。"""
        self.template_var.set(TEMPLATE_DEFAULT_LABEL)

    # ---- 转换调度 ----
    def _handle_paths(self, paths):
        md_paths = [p for p in paths if Path(p).suffix.lower() == ".md"]
        if not md_paths:
            self._log("没找到 .md 文件，已忽略。", "err")
            return
        # 覆盖确认要弹窗，只能放在主线程，工作线程不碰 GUI
        jobs = []
        for p in md_paths:
            md = Path(p).resolve()
            jobs.append((md, self._resolve_out_stem(md)))
        # 选项读值也放主线程（tk 变量不能跨线程访问），跟 jobs 一起交给工作线程
        toc, toc_depth = toc_options(self.toc_var.get())
        template = template_value(self.template_var.get())
        # 这里和转换时走同一套解析（内置名或路径），先确认模板在不在，再起线程
        if template is not None and not md_latex_pdf.resolve_template_path(template).is_file():
            self._log(f"排版模板不存在：{template}", "err")
            return
        opts = md_latex_pdf._default_opts(toc=toc, toc_depth=toc_depth, template=template)
        self._busy = True
        self._log(f"开始转换 {len(jobs)} 个文件…（目录层级：{self.toc_var.get()}；"
                  f"排版模板：{Path(template).stem if template else '默认'}）", "dim")
        threading.Thread(target=self._worker, args=(jobs, opts), daemon=True).start()

    def _resolve_out_stem(self, md: Path) -> str:
        """定下输出文件名：同名 .tex/.pdf 已存在就先问要不要覆盖，不覆盖就换个带序号的名字。"""
        stem = md.stem
        had = [f"{stem}.tex", f"{stem}.pdf"]
        if any((md.parent / n).exists() for n in had):
            overwrite = messagebox.askyesno(
                "覆盖确认",
                f"「{stem}」已有同名文件：\n{stem}.tex\n{stem}.pdf\n\n覆盖它们吗？\n"
                "（选「否」会改用带序号的输出文件名，原文件留着）",
                parent=self.root)
            if not overwrite:
                i = 2
                while True:
                    cand = f"{stem} ({i})"
                    if not (md.parent / f"{cand}.tex").exists() and \
                       not (md.parent / f"{cand}.pdf").exists():
                        return cand
                    i += 1
        return stem

    def _worker(self, jobs, opts):
        """后台线程里逐个转换，结果丢进队列交给主线程，这里不碰 Tk。"""
        for md, out_stem in jobs:
            try:
                tex, pdf, ctx = md_latex_pdf.convert_file(md, out_dir=md.parent,
                                                       out_stem=out_stem, opts=opts)
                msg = f"✓ {md.name} -> {tex.name} + {pdf.name}"
                if ctx.warnings:
                    msg += "\n    警告：" + "；".join(ctx.warnings)
                else:
                    msg += "\n    输出目录：" + str(md.parent)
                self._queue.put(("log", msg, "ok"))
                self._queue.put(("last_pdf", pdf, None))
            except Exception as e:  # noqa: BLE001  异常在这里收成一句摘要，堆栈不往外抛
                self._queue.put(("log", f"✗ {md.name} 失败：{_short_error(e)}", "err"))
        self._queue.put(("done", None, None))

    def _poll(self):
        """在主线程的主循环里取队列，更新完 GUI 再排下一次。"""
        try:
            while True:
                kind, payload, tag = self._queue.get_nowait()
                if kind == "log":
                    self._log(payload, tag)
                elif kind == "last_pdf":
                    self.last_pdf = Path(payload)
                elif kind == "done":
                    self._busy = False
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    # ---- GUI 反馈 ----
    def _log(self, text, tag=None):
        self.status.configure(state="normal")
        self.status.insert("end", text + "\n", tag or ())
        self.status.see("end")
        self.status.configure(state="disabled")

    def _clear(self):
        self.status.configure(state="normal")
        self.status.delete("1.0", "end")
        self.status.configure(state="disabled")

    def _open_pdf(self):
        if self.last_pdf and self.last_pdf.exists():
            os.startfile(str(self.last_pdf))  # type: ignore[attr-defined]  # startfile 需字符串路径
        else:
            messagebox.showinfo("提示", "还没生成 PDF，或者文件已经被移走了。", parent=self.root)


def launch() -> int:
    """开窗口跑主循环。脚本直接运行和 md_latex_pdf.py --gui 都走这里。"""
    app = MdToPdfApp()
    app.root.mainloop()
    return 0


def _run_cli(argv) -> int:
    """命令行模式：整件事交给 md_latex_pdf.main。

    `md-latex-pdf.exe 讲义.md` 一条命令直接转出 PDF，不弹窗口。
    打包时用的是 --windowed，没有控制台，sys.stdout/stderr 可能是 None，
    这时 print 会直接崩，所以先兜底成安全对象。退出码照旧反映转换结果，文件也照常产出。
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
    return md_latex_pdf.main(argv)


if __name__ == "__main__":
    # 同一个 exe 两种用法：带 .md 参数就走命令行转换，双击或没参数就开窗口
    if len(sys.argv) > 1:
        sys.exit(_run_cli(sys.argv[1:]))
    sys.exit(launch())
