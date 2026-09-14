# md-latex-pdf

版本：1.0.0

Markdown 先翻译成 LaTeX 源码，再交给 xelatex 编译成 A4 文档 PDF。表格、代码高亮、数学公式都走 LaTeX 原生排版，不经过浏览器打印。

产物落在源文件旁边：

- `<同名>.tex`：完整的 LaTeX 源码，可以接着改
- `<同名>.pdf`：A4 文档
- `images/`：md 里引用的本地图片复制到这里

## 环境依赖

| 依赖 | 用途 | 安装 |
| --- | --- | --- |
| Python 3.x | 运行程序与图形界面 | 自备 |
| xelatex | LaTeX 编译器。中文和公式都靠它，换别的引擎会出错 | 见下 |
| tkinterdnd2 | 让图形界面能接收拖进来的文件 | `pip install tkinterdnd2` |

Windows 上装 LaTeX 引擎，装到 `%LOCALAPPDATA%\Programs\TinyTeX`：

```bash
powershell -ExecutionPolicy Bypass -File install_tex.ps1
```

脚本先从上海交大镜像取 TinyTeX-1 安装包，取不到就回退 GitHub 直连；解压完把 tlmgr 的包源换成清华 CTAN，再补上 TinyTeX-1 没带的宏包。装一次就够。

本机已经有 TeX Live、MiKTeX 或别的 TinyTeX 就不用跑这个脚本。也可以用环境变量 `XELATEX_PATH` 指向 `xelatex.exe`。

```bash
python -m pip install tkinterdnd2
```

## 用法

### 图形界面

```bash
python md_latex_pdf_gui.py
```

把 `.md` 拖进窗口（可以一次拖多个），或者点「选择文件」。转换结果直接显示在窗口里，出错只给一句摘要，不抛后台堆栈。

- **输出位置**：和拖入的 `.md` 同目录、同名，产出 `<同名>.tex` 和 `<同名>.pdf`。
- **目录层级**：下拉选「无目录 / 1 级 / 2 级 / 3 级 / 4 级」，默认 3 级，等价于命令行的 `--no-toc` 与 `--toc-depth N`。这项只影响目录页，正文的章节编号不受影响。
- **覆盖保护**：同名 `.tex` 或 `.pdf` 已经存在会先问一句。选「否」就改用带序号的文件名，不会静默覆盖。
- **排版模板**：可编辑的下拉框，「（默认）」指内置的 `default.tex`；也可以直接粘一个 `.tex` 路径，或点「浏览…」挑文件。详见[换排版规则](#换排版规则)。

不带参数运行 `python md_latex_pdf.py` 同样打开界面。

打包出来的 exe 是无控制台的双模式：

- 双击或不带参数：打开转换窗口。
- 带 `.md` 参数：走命令行转换。成功返回 0，转换失败返回 1，输入文件不存在或参数写错返回 2。

exe 是 GUI 子系统程序（`--windowed` 构建），双击运行时没有控制台，什么输出都看不到。从命令行调用它要把这点记在心里：PowerShell 的 `&` 和 cmd 都不会等它跑完，拿到的是启动那一刻的码，转换还在后台接着跑。要等结果用 `Start-Process -Wait`，或者在调用后面接个管道让它挂住：

```powershell
& .\dist\md-latex-pdf.exe 讲义.md out | Out-Null
```

要看转换过程的完整输出，用 `python md_latex_pdf.py <文件>`。那是控制台程序，不会脱离，退出码与输出都正常。

### 命令行

```bash
python md_latex_pdf.py example.md                # 输出 example.tex 与 example.pdf，落在 md 旁边
python md_latex_pdf.py example.md out/           # 指定输出目录
python md_latex_pdf.py example.md --toc-depth 2  # 目录只收一二级
python md_latex_pdf.py example.md --no-toc       # 不要目录页
python md_latex_pdf.py example.md --cover-color #DCE3EC --open   # 换封面底色并打开
```

参数：`--header`、`--title`、`--subtitle`、`--cover-color`、`--no-numbers`、`--toc/--no-toc`、`--toc-depth N`（1–4）、`--keep-aux`、`--open`、`--template 模板`、`--gui`、`--version`。

界面和命令行共用同一套转换逻辑，表格、公式这些行为完全一致。

## 怎么写 Markdown

解析器是自己写的，不是 GitHub 或 CommonMark 全集。按本文列出的语法写就行，原生 HTML 表格之类会被忽略。

写完先过一遍文末的[输出前自检清单](#输出前自检清单)，转换后按[生成后的校验](#生成后的校验)复查。

### 封面 front matter（可选）

写在文件开头，以单独一行 `---` 结束：

```markdown
# 文档标题
## 副标题（可省略）

页眉：页眉文字（默认取标题）
页尾：封面底部说明文字
封面：#EAF2FB（封面底色，不写就是白色 #FFFFFF）
作者：张三
版本：v1.0
---
```

第一行 `#` 是封面大标题，`##` 是副标题，其余行按「键：值」显示成封面条目。

识别得出的关键词：

| 关键词 | 含义 |
| --- | --- |
| `页眉` 或 `header` | 页眉文字，默认取标题 |
| `页尾`、`页脚` 或 `footer` | 封面底部的小字说明 |
| `封面` 或 `cover` | 封面纯色底色，要写六位 hex `#RRGGBB`，写错就回退成白色 |
| 其余 | 一律原样显示成封面上的「键：值」条目，比如 `作者`、`版本` |

几点注意：

- 封面行的值只当纯文字，不做行内解析，`$公式$` 和 `**粗体**` 在这里都不生效。
- 判定条件：前缀以 `# 标题` 开头，每个非空行都是标题或「键：值」，且不超过 30 行。正文里的 `---` 不会被误判成封面；但若文件最前面就是一段「像封面」的短内容再跟一个 `---`，那会被当成真封面。
- 不需要封面就直接从正文写起，此时套用默认的「未命名文档」封面。

### 标题

`#` 到 `######` 依次对应 `\section` 到 `\paragraph`，编号交给 LaTeX 自动生成。不要手写编号（`# 第1章`、`## 1.1 xxx`），会和自动编号打架。两个标题文字完全一样会触发 hyperref 的「重复目标」警告，起标题时留意区分。

```markdown
# 一级标题
## 二级标题
### 三级标题
```

编号起点：封面的一级标题不计数。如果正文里没有 `#` 一级标题（被封面吸收了），整篇会被当成一章，封面之外第一个 `##` 编号成 1.1，接着 1.2、1.3，再往下的 `###` 是 1.1.1。既不会冒出 0.1 这种编号，也不会把 `##` 硬提成单独一章。习惯上正文章节用 `#`、下一层用 `##`，看着最顺。

目录收几级是转换选项，不属于 md 语法：命令行用 `--toc-depth N`（1–4）或 `--no-toc`，界面用「目录层级」下拉。它只管目录页。

### 列表

无序用 `-` 或 `*`，有序用 `1.`，都能嵌套。任务列表写 `- [ ]`（未完成）和 `- [x]`（已完成）。

```markdown
- 项目一
- 项目二
  - 子项
1. 第一步
2. 第二步
- [x] 已完成
- [ ] 待完成
```

### 代码块

行内用反引号。多行用三个反引号围栏，并标上语言。带语法高亮的有 python、c、cpp、java、sql、html、xml、go、lua、tex、ruby、php、matlab、bash 等；json、css、js、rust 没有内置高亮，内容照常显示。

````markdown
```python
print("hello")
```
````

不要输出嵌套的三重反引号。代码里也别出现 `\end{lstlisting}`，否则整块降级成纯文本并给出告警。

### 链接与图片

```markdown
[文字](https://example.com)      # 链接
<https://example.com>             # 自动链接
![说明](图片.png)                 # 图片，复制到输出的 images/
```

### 数学公式

行内用 `$...$`，独立成段用 `$$...$$`（独占一个段落）。公式交给 LaTeX 原生渲染，`\frac`、`\sum`、`\text{}` 这些完整语法都能用，`\dif`、`\dfrac` 之类的常用宏已经内置。

`\[...\]` 和 `\(...\)` 不认，写出来会原样显示。正文里真实的美元符号（比如价格 `$5`）要写 `\$5`，或者放进行内代码 `` `$5` `` 。

粗体里可以嵌公式：`**安培力 $F_A$ 方向**`。

化学与核素符号用 mhchem 的 `\ce{...}`，物理单位用 siunitx：

```markdown
$\ce{^{1}_{1}p}$、$\ce{^{238}_{92}U \to ^{234}_{90}Th + ^{4}_{2}He}$
$\SI{9.8}{\m\per\s^2}$、$\unit{\kg}$
```

模板里已经装了 `mhchem` 和 `siunitx`。

```markdown
质能方程 $E=mc^2$，正态分布

$$f(x)=\frac{1}{\sqrt{2\pi}\sigma}e^{-\frac{(x-\mu)^2}{2\sigma^2}}$$
```

### 正文符号

中文字体只覆盖一部分符号。既没字形、又没人兜底的符号写进正文会变成空白：xelatex 只在 `.log` 里留一句 `Missing character`，既不报错也不中断，很容易让人以为排版本来就是这样。md-latex-pdf 内置了三条路，写的时候不必操心走的是哪一条。

| 情况 | 怎么处理 | 例子 |
| --- | --- | --- |
| 中文字体本来就有字形 | 直接写正文 | `3σ`、`x∈A`、`∑`、`a≤b`、`±`、`①②③` |
| 中文字体有、西文字体没有，交给中文字体排 | 直接写正文 | 罗马数字 `Ⅰ Ⅱ Ⅲ Ⅻ ⅰ`、`′ ″`、`■ □ ▲ △ ▼ ▽ ◆ ◇ ○ ◎ ●`、`★ ☆ ♀ ♂`、制表符 `─ │ ┌ ┐ └ ┘ ├ ┤ ┼`、`▁ ▂ █ ▌`、`℅ ℉ ℡ ― ⌒` |
| 两个字体都没有、但有 LaTeX 等价写法（`SYMBOL_FALLBACKS`，153 个） | 直接写正文，不必包 `$...$` | `∀ ∃ ∄ ∅ ⊂ ⊆ ⇐ ⇒ ⇔ ↦ ∂ ∇ ⊗`、角标 `⁴⁻ⁿ ₀₁₂`、`⌈ ⌉ ⌊ ⌋`、`ℝ ℕ ℤ ℚ ℂ ℓ ℏ ℵ`、`✓ ✔ ✗ ✘ ☑`、`⅓ ⅔ ⅝`、`Ⅼ Ⅽ Ⅾ Ⅿ`、`⑪ ⑫ ⑳` |
| 表情标记：两个字体都没有，也没有 LaTeX 写法（`EMOJI_ICONS`，切到 Segoe UI Symbol） | 直接写正文 | `❗`(U+2757)、`⚠`(U+26A0)、`💡`(U+1F4A1) |
| 三条路都没收录的冷僻符号 | 用 `$...$` 包数学命令 | `$\gtrsim$`、`$\nvdash$` |
| 常用却没收录 | 加进 `SYMBOL_FALLBACKS` 或 `EMOJI_ICONS`，或者按 `measure_coverage.py` 的输出补字符类声明，改完跑 `python tests/test_symbol_fallback.py` | — |

```markdown
对 ∀ε>0，存在 ∃δ>0；A ⊂ B ⊆ C；x ↦ y；a ⇔ b；10⁻³、v₀、x²+y²。
定理 Ⅰ、引理 Ⅱ；■ 重点 ▲ 提示；∀x∈ℝ，⌈x⌉ ≥ x。
❗ 易错：安培力方向；⚠ 警告：单位统一；💡 思路：先画受力图。
```

- 数学模式不受影响：`$∀$`、`$\Leftarrow$` 照旧正确，回退用的是 `\ensuremath`，重复包一层也没事。`$❗$` 与正文写法结果一致。
- 页眉、封面、表格单元格、告示框、行内代码里的符号同样生效。
- 收录标准来自实测。`measure_coverage.py` 用系统字体的 cmap 加一次编译，算出哪些码位该交给中文字体、哪些仍然空白；回退表只收后者里能写出 LaTeX 等价式的那些。所以 `≮ ≯ ℧` 这类西文字体本来就有的符号不在表里。
- 表情标记依赖 Windows 自带的 `Segoe UI Symbol`。别的系统上通常没有这个字体，此时 `❗ ⚠ 💡` 会被丢弃，不留空白格也不报错。要跨平台就别用它们，改成文字表述或 `> [!TIP]` 框。
- PDF 书签和文档属性里的符号会被 hyperref 省略，编译时伴随一句 `Token not allowed in a PDF string` 警告。这只影响书签文字，页面显示正常。
- 想确认没有漏网的，加 `--keep-aux` 后在 `.log` 里数 `Missing character` 的条数，应该是 0。这条警告本身也会自动汇总打印出来。

### 表格

第二行的对齐行 `|:---|:---:|` 必须写。列内容显示宽度到 24 就转成可换行的 `tabularx` 列，正文超过 24 行则整表转 `longtable` 跨页。单元格内容做行内解析。

原生 HTML `<table>` 会被忽略并给出告警。也尽量避免超长且不可断的词，`Overfull` 大多是行尾长串造成的。

```markdown
| 列A | 列B |
|:---|:---:|
| 甲 | 1 |
| 乙 | 2 |
```

### 告示框、引述标记、普通引用

三种写法都长在 `>` 引述里，互不冲突，挑一种用就行。

**① GitHub 风格告示框**（语义最全，推荐）

```markdown
> [!WARNING]
> 最容易漏的是安培力，最容易画错方向的也是安培力。
```

| 类型 | 配色 | 缺省标题 |
| --- | --- | --- |
| `NOTE` | 蓝 | 注意 |
| `TIP` | 绿 | 提示 |
| `IMPORTANT` | 紫 | 重要 |
| `WARNING` | 橙 | 警告 |
| `CAUTION` | 红 | 小心 |

类型大小写不敏感。自定义标题必须与 `[!类型]` 写在同一行，`> [!TIP] 快速检查` 这样；标题另起一行会被当成正文渲染。相邻告示框之间要空一行隔开。框内容支持粗体、公式、行内代码、列表和多段。

按语义挑：补充说明用 `NOTE`，易错用 `WARNING` 或 `CAUTION`，要记牢的用 `IMPORTANT`。

**② 引述标记**（写起来最省事，复用同一套彩色框）

```markdown
> 💡 思路
> 先画受力图，再判断含安培力的方向。

> ⚠ 单位换算最容易出错，务必逐项核对一遍再往下算。

> ❗ 易错提醒
> 磁通量变化率要取绝对值。
```

`❗` 是红框「注意」，`⚠` 是橙框「警告」，`💡` 是绿框「提示」，与 `CAUTION`、`WARNING`、`TIP` 同色。

标题规则：标记行剩下的文字够短就当框标题，条件是显示宽度不超过 16、且不以 `。！？!?…` 结尾。`> 💡 思路` 得到绿框「思路」；否则用该类型的缺省名当标题，那段话连同标记留在正文里。所以 `> ⚠ 单位换算最容易出错，务必逐项核对一遍再往下算。` 得到的是橙框「警告」加正文那句原话，这是有意设计的。

标记后面的空格可有可无，`> ❗ 易错` 和 `> ❗易错` 一样。只认首行的标记，前面允许有空行。`> ⚠️` 里的 U+FE0F 变体选择符会被自动删掉，不影响识别。相邻告示框之间同样要空行分隔。

**③ 普通引用**（不加任何标记）

```markdown
> 数据清洗是整个分析流程中最耗时的一步，通常占全部工作量的 60% 以上。
```

不带标记的 `> 引用` 渲染成浅灰底加左侧竖条的中性框，可跨页，用来区分引述别人的话和自己写的话。支持多段、列表、公式、粗体，内部再嵌一层引用也正常。孤零零一个空引用 `>` 不输出任何内容。想让它变成彩色框，就在首行加 `❗` `⚠` `💡`，或者改用 `> [!TYPE]`。

### 引号

中文段落里，全角弯引号 “ ” ‘ ’ 原样全角渲染；包住中文的半角直引号 `"…"` 与 `'…'` 会自动转成中文弯引号。

纯英文段落、行内代码、代码块内都不转换。单词里的撇号（`don't`）和落单的引号（英寸 `5"`）不受影响。

### 其它语法

| 写法 | 效果 |
| --- | --- |
| `**粗体**`、`*斜体*`、`_斜体_`、`~~删除线~~` | 行内强调 |
| `> 引用` | 浅灰底加左侧竖条的中性框 |
| `---` | 分隔线 |
| `::page` | 单独一行，强制分页 |
| `[^1]` 与 `[^1]: 内容` | 脚注。定义写在哪里都行，会预扫描 |

### 在 md 里写 tikz

`$$...$$` 的内容原样进 `\[...\]`，而模板通过 tcolorbox 已经把 tikz 带进来了。所以不用改本工具，就能在 md 里直接写 tikz：化学的单线桥、双线桥，以及受力箭头这类「锚在公式某个字符上的箭头」，都这么画。

下面三条最容易踩：

1. **宏用 `\gdef`。** `$$…$$` 会变成 `\[…\]`，自成一组，块里的 `\def` 出了这块就失效，后续各块会报 `Undefined control sequence`。
2. **`\usetikzlibrary{…}` 不能在数学模式里执行**，会报 `Missing $ inserted`。别指望 `calc`，核心 tikz 的 `node[midway,above]`、`(x.north)` 够用。
3. **占位块必须留宽度。** overlay 箭头不占版面，而 `\rule{0pt}{…}` 是零宽度，完全不参与版面高度，写了等于没写，标签会压住上一段文字。`\rule[raise]{w}{h}` 的上沿在 `raise+h`，所以「上方留 A、下方留 B」要写 `\rule[-B]{..}{A+B}`。

### 输出前自检清单

1. 封面（如果需要）：`# 标题` 开头，加关键词，用单独一行 `---` 结束。底部说明用「页尾」。
2. 数学都在 `$…$` 或 `$$…$$` 里，正文没有裸 `$`（能直写的常用符号不在此列，见[正文符号](#正文符号)）。
3. 标题没有手写编号，也没有重复标题。
4. 提示与警告用 `> [!TYPE]` 或引述标记 `> ❗` `> ⚠` `> 💡`。自定义标题写在同一行，告示框之间留空行。
5. 表格有对齐行，没有 HTML 表格。代码围栏配对。
6. 没有把 `---` 放在「像封面」的前缀之后，除非确实想写封面。
7. 目录层级按需选：命令行 `--toc-depth N`（`--no-toc` 关闭），或界面的「目录层级」下拉。

## MD 与 PDF 的关系

Markdown 在这里不是拿去当纯文本排版的。它先被翻译成 LaTeX 源码，再交给 xelatex 编译，所以不需要 KaTeX 这类前端库。

```text
example.md ──► md-latex-pdf ──► example.tex ──► xelatex（循环编译到引用稳定）──► example.pdf
```

- 公式：md 里写 `$...$` 或 `$$...$$`，进 LaTeX 后是原生公式，不是图片。
- 代码：围栏代码块交给 `listings` 做语法高亮。
- 表格：Markdown 表格转成 `booktabs` 三线表，超宽自动换行，行数过多自动跨页。
- 目录与链接：由 hyperref 生成，PDF 里可以点击跳转。

生成的 `.tex` 是完整的 LaTeX，可以继续编辑。想加自定义环境（定理、算法之类）直接改 `.tex` 就行。

手动编译要跑两遍：`xelatex 讲义.tex` 执行两次，否则目录页和交叉引用还是 `??`。工具内部是循环编译到 `.aux` 稳定，最多 5 遍。图片靠导言区的 `\graphicspath{{./}{./images/}}` 定位，所以要在 `.tex` 所在目录编译。输出目录含中文时建议换到纯 ASCII 路径，这是 TinyTeX 的 putenv 限制（工具会自动绕道临时目录）。

想换掉后续所有转换的排版规则，见下一节。

## 换排版规则

用 `--template` 指定模板文件，就能整体换一套排版规则。模板都放在 `templates\`：

| 模板 | 风格 | 说明 |
| --- | --- | --- |
| `default.tex` | 紧凑讲义，版心 2cm | 默认。不指定 `--template` 时用它 |
| `academic.tex` | 学术论文，版心 1.25in / 1in | 带 natbib |

```bash
python md_latex_pdf.py 讲义.md --template academic          # 内置名就行
python md_latex_pdf.py 讲义.md --template academic.tex      # 带扩展名也认
copy templates\default.tex 我的模板.tex                      # 想自己改就从默认模板复制一份
python md_latex_pdf.py 讲义.md --template 我的模板.tex       # 再指向它
```

- 界面同款：「排版模板」是可编辑下拉框，能选「（默认）」、「academic」、「default」，也能直接粘路径或点「浏览…」。
- 打包出来的 exe 同样支持 `--template`，换模板不必重新打包。只有改了模板文件本身、或者改了 py，才需要重跑 `build_exe.ps1`。
- 模板里新加的宏包得先装上：`tlmgr install <包名>`。
- 改完拿 `python md_latex_pdf.py example.md --template <你的模板>` 跑一次验证。

### 模板不是任意 LaTeX 导言区都能套

本工具产出的正文用了一批必须由模板提供的定义：`listings`（代码块）、`tcolorbox` 加六个框环境（告示框与普通引用）、`ulem`（删除线）、`siunitx`、`mhchem`、`ctex` 与 `xcolor`（封面）。把一份现成的论文 `.tex` 直接丢给 `--template` 会失败，因为它没有这些定义。

缺什么会在写出 `.tex` 之前查出来，报错逐条列出「正文用到 X，但模板里没有 Y，请加 Z」，而不是等你在 xelatex 带行号的 `Undefined control sequence` 里找。

最省事的做法是复制 `templates\default.tex` 或 `academic.tex` 再改样式，不要从零写导言区。

如果给的是一份完整文档式模板（自带摘要、正文和 `\end{document}` 的成稿 `.tex`），本工具只取 document 环境之前的导言区，模板自带的正文会被丢弃并给出告警。不这么处理就会拼出两个 `\end{document}` 的坏文件。

模板契约：三样东西不能少，照抄内置模板即可。

| 标记 | 作用 | 缺失或挪位的后果 |
| --- | --- | --- |
| `__SYMBOL_FALLBACKS__` | 换成正文符号回退表。必须紧接 `\documentclass` | 挪到 `\fancyhead` 之后，页眉里的 `∀` 会变空白。整个删掉，正文与页眉的 `∀ ⊆ ⇒` 会静默变空白（xelatex 只在 `.log` 写 `Missing character`，不报错） |
| `__PAGE_HEADER__` | 换成 `--header` 或 front matter 里的页眉文字 | 页眉不显示，转换结束时告警 |
| `\begin{document}` | 正文起点。工具在它前面插入封面配色、编号深度、目录深度与 PDF 元数据，再拼上封面、目录、正文 | 报错。出现 0 次或多次都不接受 |

三个标记都必须恰好出现一次。替换走的是全文文本替换，所以写进注释里也会被换掉、导致导言区错位（表现为 `\hypersetup` 或 `\IfFontExistsTF` 未定义之类的编译错误）。`load_template()` 会把这种情况拦成明确报错，不会生成坏文件。

注入块是自给自足的：`\mdcovercolor` 用 `\providecommand` 兜底，`\hypersetup` 有 `\ifdefined` 守卫，所以模板里不定义它们也能编过。

封面的版式不在模板里。封面由 Python 拼出来，要改封面样子得动代码。

## 目录结构

```text
md-latex-pdf/
├─ md_latex_pdf.py             # 核心转换 + 命令行
├─ md_latex_pdf_gui.py         # 图形界面（拖拽入口）
├─ templates/                  # 排版模板（--template 或界面下拉选）
│  ├─ default.tex              #   默认：紧凑讲义版心
│  └─ academic.tex             #   学术论文版心
├─ tests/
│  ├─ test_symbol_fallback.py  # 符号自测：字符类清单、逐符号编译、栅格抽查、页眉与引述用例
│  ├─ measure_coverage.py      # 符号覆盖实测：算出该交给中文字体的码位与仍然空白的码位
│  └─ cases/                   # 回归用例 md
├─ install_tex.ps1             # 一键安装 TinyTeX
├─ build_exe.ps1               # 打包单文件 exe
└─ example.md                  # 示例文档，覆盖全部语法
```

装好 xelatex 与 tkinterdnd2 之后：

```bash
python md_latex_pdf_gui.py                # 打开界面，把 example.md 拖进去
python md_latex_pdf.py example.md         # 命令行转换，得到 example.tex 与 example.pdf
```

## 生成后的校验

转换成功（退出码 0）不等于排版没问题。LaTeX 的多数问题只写进 `.log`，既不报错也不中断。加 `--keep-aux` 保留中间文件，然后查三项：

| 查什么 | 怎么查 | 期望 |
| --- | --- | --- |
| 缺字形（PDF 上就是空白） | 在 `.log` 里搜 `Missing character` | 0 条。有的话按提示改用 `$...$`，或把该符号补进 `SYMBOL_FALLBACKS` |
| 溢出行 | 在 `.log` 里搜 `Overfull \hbox` | 0 条。大多是行尾的不可断长串，改措辞即可 |
| 页数与产物 | `.log` 末尾的 `Output written on ... (N pages)` | 页数与预期相符，`<同名>.pdf` 非空 |

`Missing character` 会自动汇总成一条警告（命令行打到 stderr，界面显示在结果区），不必手动翻 `.log`。

改过符号相关配置（`SYMBOL_FALLBACKS`、`EMOJI_ICONS`、`\xeCJKDeclareCharClass`）之后，跑 `python tests/test_symbol_fallback.py`（加 `--quick` 只抽查 11 个）。要重算哪些码位该交给中文字体，跑 `python tests/measure_coverage.py`。

## 打包 exe

```bash
powershell -ExecutionPolicy Bypass -File build_exe.ps1
# 产物：dist\md-latex-pdf.exe
```

PyInstaller 单文件、`--windowed`，双击即用，不弹控制台。`templates\default.tex` 会被一起打进 exe，所以解包后能找到默认模板。目标机器仍然需要 xelatex。

装了 `tkinterdnd2` 才能拖拽；没装的话界面会提示「拖拽不可用」，但「选择文件」照常可用。

## 许可

MIT，见 [LICENSE](LICENSE)。
