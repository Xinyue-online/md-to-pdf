#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md-to-pdf 图形界面——把 .md 文件拖进窗口即可转换为 LaTeX 源码 + PDF。

- 窗口标题「md-to-pdf 转换器」，把 Markdown（.md）文件拖进来（或点「选择文件」）。
- 转换逻辑复用 md_to_pdf.py 的 convert_file（LaTeX 表格 / 代码高亮 / 数学公式等特性全部保留）。
- 产物 <同名>.tex 与 <同名>.pdf 写入当前 md 所在目录；同名文件已存在时弹出覆盖确认。
- 出错时在窗口内显示错误摘要，不打印后台堆栈。

界面风格与 video-to-md（D:/workspace/_skill_tool/video-to-md）保持一致：深色顶栏 + 卡片式布局 + 彩色记录区。

依赖：
    python -m pip install tkinterdnd2        # 原生拖拽（缺失时自动退回「选择文件」按钮）
    及本机 xelatex（运行 install_tex.ps1 一键安装 TinyTeX）。
"""
import os
import queue
import re
import sys
import threading
from pathlib import Path

# 确保能导入同目录的 md-to-pdf 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import md_to_pdf

# 目录层级下拉：选项文字 → (是否生成目录, tocdepth)。「无目录」= 关闭目录页。
TOC_CHOICES = ("无目录", "1 级", "2 级", "3 级", "4 级")
TOC_DEFAULT = "3 级"


def toc_options(choice: str) -> tuple[bool, int]:
    """把「N 级 / 无目录」下拉文字转成 convert_file 需要的 (toc, toc_depth)。

    下拉是只读的，取值只可能来自 TOC_CHOICES；万一拿到认不出的文字，
    按「无目录」处理（宁可不出目录页，也不要擅自加一个用户没选的目录）。
    """
    m = re.match(r"\s*([1-4])\s*级", choice or "")
    if not m:
        return False, 3
    return True, int(m.group(1))


# tkinterdnd2 提供真正的 OS 级拖拽；未安装时优雅退回「选择文件」按钮
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except Exception:  # noqa: BLE001
    _HAS_DND = False

_FONT = "Microsoft YaHei UI"
# ---- 配色（与 video-to-md 一致）----
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
    """把异常压成一句短的错误摘要（不抛堆栈）。

    xelatex 编译失败的异常消息 = "xelatex 编译失败（exit N）：\n" + log 尾部，
    而 log 尾部常以 "Output written on ...(N pages)."（成功行）收尾——直接取
    最后一行会掩盖真正的报错（如 "Undefined control sequence"）。故优先挑
    file-line-error 行（...tex:NNNN: ...，如 -file-line-error 的输出）或
    LaTeX 的 "! ..." 错误行；都找不到时才退回最后一行。
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
    """带细边框的白色卡片：返回 (外框, 内芯)。"""
    outer = tk.Frame(parent, bg=_BORDER, bd=0, highlightthickness=1,
                     highlightbackground=_BORDER, highlightcolor=_BORDER)
    inner = tk.Frame(outer, bg=_CARD)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    return outer, inner


class MdToPdfApp:
    """单窗口 GUI：拖入 .md → 转换成 <同名>.tex + <同名>.pdf。"""

    def __init__(self):
        # tkinterdnd2 导入成功不代表 tkdnd(Tcl 扩展) 一定能加载（如打包 exe 缺数据文件），
        # 因此实例化时再试一次；失败则退回纯 tk，保证窗口始终能开。
        self._dnd = False
        if _HAS_DND:
            try:
                self.root = TkinterDnD.Tk()
                self._dnd = True
            except Exception:  # noqa: BLE001
                self.root = tk.Tk()
        else:
            self.root = tk.Tk()
        self.root.title("md-to-pdf 转换器")
        self.root.geometry("640x620")
        self.root.minsize(580, 540)
        self.root.configure(bg=_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        self.last_pdf: Path | None = None
        self._busy = False
        # 工作线程不直接碰 Tk；通过队列把结果送回主线程，由 _poll 在主循环里消费。
        self._queue: "queue.Queue[tuple]" = queue.Queue()

        self._build_ui()
        self._register_drop()
        self.root.after(100, self._poll)

    # ---- UI 构建 ----
    def _build_ui(self):
        # 顶栏
        head = tk.Frame(self.root, bg=_HEAD)
        head.pack(fill="x")
        tk.Label(head, text="md-to-pdf 转换器", font=(_FONT, 16, "bold"),
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
        tk.Label(self.drop_zone, text="请拖入 md 文件", font=(_FONT, 14, "bold"),
                 bg=_CARD, fg="#33415f").pack(pady=(24, 4))
        tk.Label(self.drop_zone,
                 text="支持多文件 · 输出 <同名>.tex + <同名>.pdf 到 md 所在目录 · LaTeX 级排版",
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
        tk.Label(acts, text="需要本机 xelatex（缺失时点看 README / 运行 install_tex.ps1）",
                 font=(_FONT, 8), bg=_BG, fg=_MUTED).pack(side="left")
        btns = tk.Frame(acts, bg=_BG)
        btns.pack(side="right")
        self._add_btn(btns, "选择文件", self._choose_files, primary=True, padx=(0, 8))
        self._add_btn(btns, "打开最新PDF", self._open_pdf, padx=(0, 8))
        self._add_btn(btns, "清空记录", self._clear)

        if not self._dnd:
            self._log("拖拽不可用（未加载 tkinterdnd2/tkdnd），请用「选择文件」，或运行 "
                      "pip install tkinterdnd2 后重启。", "dim")

    def _add_btn(self, parent, text, cmd, primary=False, padx=(0, 0)):
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
        b.pack(side="left", padx=padx)
        return b

    # ---- 拖拽注册 ----
    def _register_drop(self):
        if not self._dnd:
            return
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

    # ---- 转换调度 ----
    def _handle_paths(self, paths):
        md_paths = [p for p in paths if Path(p).suffix.lower() == ".md"]
        if not md_paths:
            self._log("未识别到 .md 文件，已忽略。", "err")
            return
        # 覆盖确认在主线程弹窗，避免工作线程操作 GUI
        jobs = []
        for p in md_paths:
            md = Path(p).resolve()
            jobs.append((md, self._resolve_out_stem(md)))
        # 选项也在主线程读（tk 变量不跨线程碰），随 jobs 一起交给工作线程
        toc, toc_depth = toc_options(self.toc_var.get())
        opts = md_to_pdf._default_opts(toc=toc, toc_depth=toc_depth)
        self._busy = True
        self._log(f"开始转换 {len(jobs)} 个文件…（目录层级：{self.toc_var.get()}）", "dim")
        threading.Thread(target=self._worker, args=(jobs, opts), daemon=True).start()

    def _resolve_out_stem(self, md: Path) -> str:
        """决定输出文件名。同名 .tex/.pdf 已存在时询问是否覆盖；否则加序号避免覆盖。"""
        stem = md.stem
        had = [f"{stem}.tex", f"{stem}.pdf"]
        if any((md.parent / n).exists() for n in had):
            overwrite = messagebox.askyesno(
                "覆盖确认",
                f"「{stem}」已有同名 .tex/.pdf：\n{stem}.tex\n{stem}.pdf\n\n是否覆盖？\n"
                "（选「否」将自动改用带序号的输出文件名，保留原文件）",
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
        """后台线程：逐文件转换，结果经队列送回主线程（不直接碰 Tk）。"""
        for md, out_stem in jobs:
            try:
                tex, pdf, ctx = md_to_pdf.convert_file(md, out_dir=md.parent,
                                                       out_stem=out_stem, opts=opts)
                msg = f"✓ {md.name} -> {tex.name} + {pdf.name}"
                if ctx.warnings:
                    msg += "\n    警告：" + "；".join(ctx.warnings)
                else:
                    msg += "\n    输出目录：" + str(md.parent)
                self._queue.put(("log", msg, "ok"))
                self._queue.put(("last_pdf", pdf, None))
            except Exception as e:  # noqa: BLE001  在窗口内显示摘要，不抛堆栈
                self._queue.put(("log", f"✗ {md.name} 失败：{_short_error(e)}", "err"))
        self._queue.put(("done", None, None))

    def _poll(self):
        """主线程事件循环里消费队列，更新 GUI 后重新排下一次。"""
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
            messagebox.showinfo("提示", "尚未生成 PDF，或文件已不存在。", parent=self.root)


def launch() -> int:
    """启动 GUI 主循环（供脚本自身及 md_to_pdf.py --gui 调用）。"""
    app = MdToPdfApp()
    app.root.mainloop()
    return 0


def _run_cli(argv) -> int:
    """命令行模式：交给核心转换（md_to_pdf.main）。

    这是给 DSH 格式转换入口（format-convert-router）用的：`md-to-pdf.exe 讲义.md` 直接转 PDF，
    不弹窗口。打包的 exe 是 --windowed（无控制台），sys.stdout/stderr 可能为 None，
    print 会崩，故先兜底成安全对象；退出码仍据转换结果返回，文件照常产出。
    """
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
    return md_to_pdf.main(argv)


if __name__ == "__main__":
    # 单文件 exe 双模式：带 .md 参数 → CLI 转换；双击/无参数 → 打开 GUI
    if len(sys.argv) > 1:
        sys.exit(_run_cli(sys.argv[1:]))
    sys.exit(launch())
