# md-to-pdf：Markdown → LaTeX → PDF

> 目录名与程序名统一为 **md-to-pdf**（2026-09-11，旧名 `md2pdf` 作废）：模块是 `md_to_pdf.py` 与 `md_to_pdf_gui.py`（Python 文件名用下划线，连字符无法 import），发行物是 `dist\md-to-pdf.exe`（v1.0.6）。

把 Markdown 转成 LaTeX 源码，再用 xelatex 编成 A4 文档 PDF。表格、代码高亮、数学公式都按 LaTeX 原生方式排版，不是浏览器打印。

产物写在源文件旁边：

- `<同名>.tex`：完整的 LaTeX 源码，可继续编辑
- `<同名>.pdf`：A4 文档
- `images/`：本地图片自动复制到这里

## 环境依赖

| 依赖 | 说明 | 安装 |
| --- | --- | --- |
| Python 3.x | 运行程序与 GUI | 需已安装 |
| xelatex | LaTeX 编译器。必须用它，否则中文与公式渲染不正确 | 见下方一键安装 |
| tkinterdnd2 | GUI 的原生拖拽 | `pip install tkinterdnd2` |

一键安装 LaTeX 引擎（Windows：下载 TinyTeX、配置清华镜像、补齐宏包，装一次即可）：

```bash
powershell -ExecutionPolicy Bypass -File install_tex.ps1
```

可复现的依赖安装命令（在项目目录执行）：

```bash
python -m pip install tkinterdnd2
```

xelatex 已装就不用再装 LaTeX。也可以用环境变量 `XELATEX_PATH` 指向 `xelatex.exe`。

## 运行 GUI（推荐）

```bash
python md_to_pdf_gui.py
```

窗口标题是「md-to-pdf 转换器」。把 `.md` 文件拖进窗口，或点「选择文件」。转换结果当场显示在窗口里；出错时只显示错误摘要，不打印后台堆栈。

- **输出位置**：与拖入的 `.md` 同目录，文件名相同（`<同名>.tex` + `<同名>.pdf`）。
- **目录层级**：下拉框选 `无目录` / `1 级` / `2 级` / `3 级` / `4 级`（默认 `3 级`），等价于命令行的 `--no-toc` 与 `--toc-depth N`。该设置只影响目录页（`#` 记 1 级、`##` 记 2 级），不改变正文章节编号。
- **覆盖保护**：同名 `.tex` 或 `.pdf` 已存在时弹窗询问。选「否」会自动改用带序号的文件名，不会静默覆盖。
- **排版模板**：见 [换排版规则](#换排版规则)。
- 不带参数运行 `python md_to_pdf.py` 也会打开 GUI。

打包版是「无黑框」双模式：`build_exe.ps1` 产出的 `dist\md-to-pdf.exe` 是 windowed 构建，启动不弹控制台。

- 双击或不带参数：打开转换窗口。
- 带 `.md` 参数：走命令行转换，输出 `<同名>.tex` 与 `<同名>.pdf`，退出码 0 或 1（供脚本与 DSH 的格式转换入口 `format-convert-router` 调用）。

需要看命令行的输出（TeX/PDF 路径、stderr 详情）时用 `python md_to_pdf.py <文件>`。windowed 版 exe 没有控制台，stdout 与 stderr 会被静默处理，但转换照常完成、退出码正确。

## 命令行

```bash
python md_to_pdf.py example.md                # 输出 example.tex 与 example.pdf 到 md 旁
python md_to_pdf.py example.md out/           # 指定输出目录
python md_to_pdf.py example.md --toc-depth 2  # 目录只要一二级
python md_to_pdf.py example.md --no-toc       # 不要目录
python md_to_pdf.py example.md --cover-color #DCE3EC --open   # 换封面底色并打开
```

参数：`--header`、`--title`、`--subtitle`、`--cover-color`、`--no-numbers`、`--toc/--no-toc`、`--toc-depth N`(1–4)、`--keep-aux`、`--open`、`--template 模板`、`--gui`、`--version`。

GUI 与命令行共用同一套转换逻辑，表格、公式等特性完全一致。

## 怎么写 Markdown

md-to-pdf 用的是自定义解析器，不是 GitHub 或 CommonMark 全集。按本文列出的语法写即可，原生 HTML 表格之类会被忽略。

写完先过一遍文末的[输出前自检清单](#输出前自检清单)，转换后按[生成后的校验](#生成后的校验)检查。

### 封面 front matter（可选）

写在文档开头，以单独一行 `---` 结束：

```markdown
# 文档标题
## 副标题（可省略）

页眉：页眉文字（默认取标题）
页尾：封面底部说明文字
封面：#EAF2FB（封面底色，默认白 #FFFFFF）
作者：张三
版本：v1.0
---
```

`#` 第一行是封面大标题，`##` 是副标题，其余行按「键：值」显示成封面条目。

特殊关键词：

| 关键词 | 含义 |
| --- | --- |
| `页眉` 或 `header` | 页眉文字，默认取标题 |
| `页尾`（旧名 `foot` / `footer` / `页脚`） | 封面底部的小字说明 |
| `封面`（旧名 `cover`） | 封面纯色底色 `#RRGGBB`，必须是 6 位 hex，否则回退白色 |
| `作者`、`版本` 等 | 封面上的「键：值」条目 |

几点注意：

- 封面行的值只放纯文字，不做行内解析。`$公式$` 和 `**粗体**` 都不会生效。
- 隐式封面的判定条件：前缀以 `# 标题` 开头，每个非空行都是标题或「键：值」，且不超过 30 行。正文里的 `---` 分隔线不会被误判成封面，但在文件最前面写一个「像封面」的短前缀再加 `---`，会被当成真封面。
- 不需要封面就直接从正文写起，会套用默认的「未命名文档」封面。

### 标题

`#` 到 `######` 对应 `\section` 到 `\paragraph`，由 LaTeX 自动编号。所以不要手写编号（`# 第1章`、`## 1.1 xxx`），否则会重复。两个标题文字完全相同会触发 hyperref 的「重复目标」警告，写标题时注意区分。

```markdown
# 一级标题
## 二级标题
### 三级标题
```

编号起点：封面的一级标题（`# 封面标题`）不计数。如果正文没有 `#` 一级标题（被封面吸收了），md-to-pdf 会把整篇当作一章，封面外第一个 `##` 编号为 1.1，其后是 1.2、1.3，再下面的 `###` 是 1.1.1。既不会出现 0.1 这种编号，也不会把 `##` 提升成单独的一章。习惯上正文章节用 `#`、二级用 `##`，最直观。

目录收几级是转换选项，不是 md 语法：命令行用 `--toc-depth N`(1–4) 或 `--no-toc`，GUI 用「目录层级」下拉。它只影响目录页。

### 列表

无序用 `-` 或 `*`，有序用 `1.`，都可以嵌套。任务列表写 `- [ ]`（未完成）和 `- [x]`（已完成）。

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

行内用反引号。多行用三个反引号围栏，并标注语言。有语法高亮的是 python、c、cpp、java、sql、html、xml、go、lua、tex、ruby、php、matlab、bash 等；json、css、js、rust 没有内置高亮，但内容正常显示。

````markdown
```python
print("hello")
```
````

不要输出嵌套的三重反引号。代码里不要出现 `\end{lstlisting}`，否则整块会降级成纯文本并给出告警。

### 链接与图片

```markdown
[文字](https://example.com)      # 链接
<https://example.com>             # 自动链接
![说明](图片.png)                 # 图片，会复制到输出的 images/
```

### 数学公式

行内用 `$...$`，独立成段用 `$$...$$`（独占段落）。公式由 LaTeX 原生渲染，支持 `\frac`、`\sum`、`\text{}` 等完整语法，常用宏 `\dif`、`\dfrac` 已内置。

不要用 `\[...\]` 和 `\(...\)`，这两者不会被识别，会原样显示。正文里真实的美元符号（比如价格 `$5`）要写 `\$5`，或者放进行内代码 `` `$5` ``。

粗体里可以嵌公式：`**安培力 $F_A$ 方向**`。

化学与核素符号用 mhchem 的 `\ce{...}`，物理单位用 siunitx：

```markdown
$\ce{^{1}_{1}p}$、$\ce{^{238}_{92}U \to ^{234}_{90}Th + ^{4}_{2}He}$
$\SI{9.8}{\m\per\s^2}$、$\unit{\kg}$
```

模板里已经装了 `mhchem` 与 `siunitx`。

```markdown
质能方程 $E=mc^2$，正态分布

$$f(x)=\frac{1}{\sqrt{2\pi}\sigma}e^{-\frac{(x-\mu)^2}{2\sigma^2}}$$
```

### 正文符号

中文字体只覆盖一部分符号。没字形又没兜住的符号写成正文会变成空白：xelatex 只在 `.log` 里写一条 `Missing character`，不报错也不中断，很容易以为排版本来就是这样。所以 md-to-pdf 内置了三条路，写作者不必关心走了哪条。

| 情况 | 怎么处理 | 例子 |
| --- | --- | --- |
| 中文字体本来就有字形 | 直接写正文 | `3σ`、`x∈A`、`∑`、`a≤b`、`±`、`①②③` |
| 中文字体有、西文字体没有（交给中文字体排） | 直接写正文 | 罗马数字 `Ⅰ Ⅱ Ⅲ Ⅻ ⅰ`、`′ ″`、`■ □ ▲ △ ▼ ▽ ◆ ◇ ○ ◎ ●`、`★ ☆ ♀ ♂`、制表符 `─ │ ┌ ┐ └ ┘ ├ ┤ ┼`、`▁ ▂ █ ▌`、`℅ ℉ ℡ ― ⌒` |
| 两个字体都没有、但有 LaTeX 等价写法（`SYMBOL_FALLBACKS`，153 个） | 直接写正文，不必包 `$...$` | `∀ ∃ ∄ ∅ ⊂ ⊆ ⇐ ⇒ ⇔ ↦ ∂ ∇ ⊗`、角标 `⁴⁻ⁿ ₀₁₂`、`⌈ ⌉ ⌊ ⌋`、`ℝ ℕ ℤ ℚ ℂ ℓ ℏ ℵ`、`✓ ✔ ✗ ✘ ☑`、`⅓ ⅔ ⅝`、`Ⅼ Ⅽ Ⅾ Ⅿ`、`⑪ ⑫ ⑳` |
| 表情标记：两个字体都没有，也没有 LaTeX 写法（`EMOJI_ICONS`，切到 Segoe UI Symbol） | 直接写正文 | `❗`(U+2757)、`⚠`(U+26A0)、`💡`(U+1F4A1) |
| 三条路都没收录的冷僻符号 | 用 `$...$` 包数学命令 | `$\gtrsim$`、`$\nvdash$` |
| 常用但没收录 | 加进 `SYMBOL_FALLBACKS` 或 `EMOJI_ICONS`，或按 `measure_coverage.py` 的输出补字符类声明，改完跑 `python test_symbol_fallback.py` | — |

```markdown
对 ∀ε>0，存在 ∃δ>0；A ⊂ B ⊆ C；x ↦ y；a ⇔ b；10⁻³、v₀、x²+y²。
定理 Ⅰ、引理 Ⅱ；■ 重点 ▲ 提示；∀x∈ℝ，⌈x⌉ ≥ x。
❗ 易错：安培力方向；⚠ 警告：单位统一；💡 思路：先画受力图。
```

- 数学模式不受影响：`$∀$`、`$\Leftarrow$` 照旧正确，回退用的是 `\ensuremath`，可以重复包。`$❗$` 与正文写法一致。
- 页眉、封面（front matter 的值）、表格单元格、告示框、行内代码里的符号同样生效。
- 收录标准来自实测。`measure_coverage.py` 用系统字体的 cmap 加一次编译，算出「该交给中文字体的码位」和「仍然空白的码位」；回退表只收后者里有 LaTeX 等价写法的。所以 `≮ ≯ ℧` 这类西文字体本来就有的符号不在表里。
- 表情标记依赖 Windows 自带的 `Segoe UI Symbol`。非 Windows 机器上通常没有这个字体，此时 `❗ ⚠ 💡` 会被丢弃，不留空白格也不报错。跨平台文稿建议改用文字表述或 `> [!TIP]`。
- 已知限制：PDF 书签与文档属性里的符号会被 hyperref 省略（会有一条 `Token not allowed in a PDF string` 警告）。只影响书签文字，不影响页面显示。
- 想确认没有漏网之鱼，加 `--keep-aux` 后查 `.log` 里 `Missing character` 的条数，应为 0。这个警告从 v1.0.5 起也会自动打印出来。

### 表格

第二行的对齐行 `|:---|:---:|` 必须有。长文本列会自动换行（显示宽度 ≥24 转 tabularx），超过 24 行会自动转 longtable 跨页。单元格内容做行内解析。

不要用原生 HTML `<table>`，会被忽略并告警。避免超长且不可断的词，Overfull 多数来自行尾的长串。

```markdown
| 列A | 列B |
|:---|:---:|
| 甲 | 1 |
| 乙 | 2 |
```

### 告示框、要点框、普通引用

三种写法都在 `>` 引述里，互不冲突，选一种用。

**① GitHub 风格**（推荐，语义最全）

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

大小写不敏感。自定义标题要与 `[!类型]` 写在同一行：`> [!TIP] 快速检查`。标题另起一行会被当正文渲染。相邻告示框之间必须空行分隔。框内容支持粗体、公式、行内代码、列表、多段。

按语义选型：补充说明用 `NOTE`，易错用 `WARNING` 或 `CAUTION`，重点记忆用 `IMPORTANT`。

**② 引述标记**（写起来最省事，复用同一套彩色框）

```markdown
> 💡 思路
> 先画受力图，再判断含安培力的方向。

> ⚠ 单位换算最容易出错，务必逐项核对一遍再往下算。

> ❗ 易错提醒
> 磁通量变化率要取绝对值。
```

对应关系：`❗` 是红框「注意」，`⚠` 是橙框「警告」，`💡` 是绿框「提示」，与 `CAUTION` / `WARNING` / `TIP` 同色。

标题规则：标记行剩下的文字够短（显示宽度 ≤16，且不以 `。！？!?…` 结尾）就当框标题，`> 💡 思路` 得到绿框「思路」；否则用该类型的缺省名当标题，那段话连同标记留在正文里。所以 `> ⚠ 单位换算最容易出错，务必逐项核对一遍再往下算。` 得到的是橙框「警告」加正文那句原话，这是有意设计的。

标记后面的空格可有可无，`> ❗ 易错` 与 `> ❗易错` 同义。只认首行的标记（前面允许空行）。`> ⚠️` 里的 U+FE0F 变体选择符会被自动删掉，不影响识别。标题写成长句时不要指望它成为标题。相邻告示框之间同样要空行分隔。

**③ 普通引用**（不加任何标记）

```markdown
> 数据清洗是整个分析流程中最耗时的一步，通常占全部工作量的 60% 以上。
```

不带标记的 `> 引用` 会渲染成浅灰底加左侧竖条的中性框（可跨页），用来区分引述别人的话与自己的话，不必加任何标记。支持多段、列表、公式、粗体，内部再嵌一层引用也正常。孤零零一个空引用 `>` 不输出任何内容。想让它变成彩色框，就在首行加 `❗` `⚠` `💡`，或改用 `> [!TYPE]`。

**旧式写法已禁用**（2026-09-11 起）：`::tip` / `::warn` / `::key` … `::end`。解析器仍兼容它们，示例见 `example.md`，但新写的 md 一律不要用。语义对应 `TIP`=`::tip`、`WARNING`=`::warn`、`IMPORTANT`=`::key`。

### 引号

中文段落里，全角弯引号 “ ” ‘ ’ 原样全角渲染；包住中文的半角直引号 `"…"` 与 `'…'` 会自动转成中文弯引号。

纯英文段落、行内代码、代码块内都不转换。单词内的撇号（`don't`）和落单的引号（英寸 `5"`）不受影响。

### 其它语法

| 写法 | 效果 |
| --- | --- |
| `**粗体**`、`*斜体*`、`_斜体_`、`~~删除线~~` | 行内强调 |
| `> 引用` | 浅灰底加左侧竖条的中性框 |
| `---` | 分隔线 |
| `::page` | 单独一行，强制分页 |
| `[^1]` 与 `[^1]: 内容` | 脚注。定义位置随意，会预扫描 |

### 在 md 里画线桥与标注箭头

`$$...$$` 的内容会原样进 `\[...\]`，而模板通过 tcolorbox 已经带进了 tikz。所以不用改本工具，就能在 md 里直接写 tikz，化学的单线桥、双线桥，以及受力箭头这类「锚在公式某个字符上的箭头」都这么做。

写法与自检以同级工具目录的 `line-bridge\README.md` 为准（`gen` 生成图块、`apply` 把 `![](images/xxx.png)` 换成图块、`check` 量最终 PDF 自检、`measure` 实测元素半宽）。这里不重复它的版式参数，只留三条与本工具强相关、最容易踩的约束：

1. **宏用 `\gdef`。** `$$…$$` 会变成 `\[…\]`，自成一组，块里的 `\def` 出了这块就失效，后续各块会报 `Undefined control sequence`。
2. **`\usetikzlibrary{…}` 不能在数学模式里执行**，会报 `Missing $ inserted`。别指望 `calc`，核心 tikz 的 `node[midway,above]`、`(x.north)` 够用。
3. **占位块必须留宽度。** overlay 箭头不占版面，而 `\rule{0pt}{…}` 是零宽度，完全不参与版面高度，写了等于没写，标签会压住上一段文字。`\rule[raise]{w}{h}` 的上沿在 `raise+h`，所以「上方留 A、下方留 B」要写 `\rule[-B]{..}{A+B}`。工具会自动生成，不要手改。

### 输出前自检清单

1. 封面（如果需要）：`# 标题` 开头，加关键词，单独一行 `---` 结束。底部说明用「页尾」。
2. 数学都在 `$…$` 或 `$$…$$` 内，正文没有裸 `$`（能直写的常用符号例外，见[正文符号](#正文符号)）。
3. 标题没有手写编号，没有重复标题。
4. 提示与警告用 `> [!TYPE]` 或引述标记 `> ❗` `> ⚠` `> 💡`。自定义标题写在同一行，告示框之间留空行。旧式 `::tip` / `::warn` / `::key` 不写。
5. 表格有对齐行，没有 HTML 表格。代码围栏配对。
6. 没有把 `---` 放在「像封面」的前缀之后（除非确实想写封面）。
7. 目录层级按需选：命令行 `--toc-depth N`（`--no-toc` 关闭），或 GUI 的「目录层级」下拉。

## MD 与 PDF 的关系

md-to-pdf 不把 Markdown 当纯文本排版，而是先翻译成 LaTeX 源码，再交给 xelatex 编译，所以不需要 KaTeX 这类前端库。

```text
example.md ──► md-to-pdf ──► example.tex ──► xelatex（循环编译到引用稳定）──► example.pdf
```

- 公式：md 里写 `$...$` 或 `$$...$$`，进 LaTeX 后是原生公式，不是图片。
- 代码：围栏代码块交给 `listings` 做语法高亮。
- 表格：Markdown 表格转成 `booktabs` 三线表，超宽自动换行，超行数跨页。
- 目录与链接：由 hyperref 生成，PDF 里可以点击跳转。

生成的 `.tex` 是完整的 LaTeX，可以继续编辑。想加自定义环境（定理、算法等）就直接改 `.tex`。

手动编译要跑两遍：`xelatex 讲义.tex` 执行两次，否则目录页与交叉引用还是 `??`。工具内部是循环编译到 `.aux` 稳定，最多 5 遍。图片靠导言区的 `\graphicspath{{./}{./images/}}` 定位，所以要在 `.tex` 所在目录编译。输出目录含中文时建议改放纯 ASCII 路径，这是 TinyTeX 的 putenv 限制（工具会自动绕道临时目录）。

想改所有后续转换的排版规则，见下一节。

## 换排版规则

用 `--template` 指定模板文件即可整体换一套排版规则。模板都在 `templates\`：

| 模板 | 风格 | 说明 |
| --- | --- | --- |
| `default.tex` | 紧凑讲义，版心 2cm | 默认。不指定 `--template` 时用它 |
| `academic.tex` | 学术论文，版心 1.25in / 1in | 由 `latex模板/article-cn/ctexart-temp.tex` 派生，带 natbib |

```bash
python md_to_pdf.py 讲义.md --template academic          # 内置名即可
python md_to_pdf.py 讲义.md --template academic.tex      # 带扩展名也行
copy templates\default.tex 我的模板.tex                  # 想自己改就从默认模板复制
python md_to_pdf.py 讲义.md --template 我的模板.tex      # 再指向它
```

- GUI 同款：「排版模板」是可编辑下拉框，可以选 `（默认）`、`academic`、`default`，也可以直接粘路径或点「浏览…」。
- 打包版 exe 也支持 `--template`，换模板不必重新打包。改了模板文件本身或改了 py，才需要重跑 `build_exe.ps1`。
- 模板里新增的宏包要先装：`tlmgr install <包名>`。
- 改完跑一次 `python md_to_pdf.py example.md --template <你的模板>` 验证。

### 模板不是任意 LaTeX 导言区都能套

md-to-pdf 产出的正文用到一批模板必须提供的定义：`listings`（代码块）、`tcolorbox` 加六个框环境（告示框与普通引用）、`ulem`（删除线）、`siunitx`、`mhchem`、`ctex` 与 `xcolor`（封面）。把一份现成的论文 `.tex` 直接丢给 `--template` 会失败，因为那些模板没有这些定义。

缺什么会在写 `.tex` 之前查出来，报错逐条列出「正文用到 X，但模板里没有 Y，请加 Z」，而不是让你去看 xelatex 带行号的 `Undefined control sequence`。

最省事的做法是复制 `templates\default.tex` 或 `academic.tex` 再改样式，不要从零写导言区。

如果给的是完整文档式模板（自带摘要、正文与 `\end{document}` 的成稿 `.tex`），md-to-pdf 只取 `\begin{document}` 之前的导言区，模板自带的正文会被丢弃并给出告警。否则会拼出两个 `\end{document}` 的坏文件。

模板契约：三样东西不能少，照抄内置模板即可。

| 标记 | 作用 | 缺失或挪位的后果 |
| --- | --- | --- |
| `__SYMBOL_FALLBACKS__` | 换成正文符号回退表。必须紧接 `\documentclass` | 挪到 `\fancyhead` 之后，页眉里的 `∀` 会变空白。整个删掉，正文与页眉的 `∀ ⊆ ⇒` 会静默变空白（xelatex 只在 `.log` 写 `Missing character`，不报错） |
| `__PAGE_HEADER__` | 换成 `--header` 或 front matter 的页眉文字 | 页眉不显示，转换结束时会告警 |
| `\begin{document}` | 正文起点。md-to-pdf 在它前面插入封面配色、编号深度、目录深度与 PDF 元数据，再拼上封面、目录、正文 | 报错。0 次或多次都不接受 |

三个标记都必须恰好出现一次。它们走的是全文文本替换，所以写进注释里也会被替换掉，导致导言区错位（表现为 `\hypersetup` 或 `\IfFontExistsTF` 未定义之类的编译错误）。`load_template()` 会把这种情况拦成明确报错，不会生成坏文件。

注入块是自给自足的：`\mdcovercolor` 用 `\providecommand` 兜底，`\hypersetup` 有 `\ifdefined` 守卫，所以模板不定义它们也能编过。

封面版式不在模板里。封面由 `build_tex()` 用 Python 拼，改封面版式要动代码。

## 目录结构

```text
md-to-pdf/
├─ md_to_pdf.py          # 核心转换 + 命令行
├─ md_to_pdf_gui.py      # 图形界面（拖拽入口）
├─ templates/            # 排版模板（--template 或 GUI 下拉选）
│  ├─ default.tex        #   默认：紧凑讲义版心
│  └─ academic.tex       #   学术论文版心
├─ test_symbol_fallback.py  # 符号自测：字符类清单、逐符号编译、栅格抽查、页眉与引述用例（需 xelatex）
├─ measure_coverage.py   # 符号覆盖实测：算该交给中文字体的码位与仍空白的码位
├─ install_tex.ps1       # 一键安装 TinyTeX
├─ build_exe.ps1         # 打包单文件 exe（无控制台，可选）
└─ example.md            # 示例文档
```

首次装完 xelatex 与 tkinterdnd2 后：

```bash
python md_to_pdf_gui.py                # 打开 GUI，把 example.md 拖进去
python md_to_pdf.py example.md         # 命令行转换，得到 example.tex 与 example.pdf
```

打包「无黑框」图形界面 exe（双击即用，不弹控制台）：

```bash
powershell -ExecutionPolicy Bypass -File build_exe.ps1
# 产物：dist\md-to-pdf.exe
```

未安装 `tkinterdnd2` 时，GUI 会提示「拖拽不可用」，但仍可用「选择文件」完成转换。

## 生成后的校验

转换成功（退出码 0）不等于排版没问题。LaTeX 的多数问题只写进 `.log`，不报错也不中断。要复核时加 `--keep-aux` 保留中间文件，然后查三项：

| 查什么 | 怎么查 | 期望 |
| --- | --- | --- |
| 缺字形（PDF 里就是空白） | 在 `.log` 里搜 `Missing character` | 0 条。有的话按警告提示改用 `$...$`，或把该符号补进 `SYMBOL_FALLBACKS` |
| 溢出行 | 在 `.log` 里搜 `Overfull \hbox` | 0 条。多数是行尾长串不可断词，调整措辞 |
| 页数与产物 | `.log` 末尾的 `Output written on ... (N pages)` | 页数与预期相符，`<同名>.pdf` 非空 |

从 v1.0.5 起，`Missing character` 会自动汇总成一条警告输出（命令行打到 stderr，GUI 显示在结果窗口），不必手动翻 `.log`。

改过符号相关配置（`SYMBOL_FALLBACKS`、`EMOJI_ICONS`、`\xeCJKDeclareCharClass`）之后，跑 `python test_symbol_fallback.py`（`--quick` 只抽查 8 个）。要重算哪些码位该交给中文字体，跑 `python measure_coverage.py`。

## 相关资料

本 README 是 md-to-pdf 的项目总览，也是本工具的权威文档：转换命令、参数、排版模板、Markdown 写法与产物校验都在这里。在 DSH 中它由唯一格式转换技能 `format-convert-router` 统一索引。

技能文档位于 DSH 技能池 `<DSH_HOME>\skills\`，相对该目录：

- 技能总索引：`format-convert-router\references\README.md`
- 技能路由表：`format-convert-router\SKILL.md`
- 本工具没有 `references\docs\md-to-pdf.md`，本 README 就是它的权威操作文档
- 全部工具清单：技能池内 `_skill_tool\README.md`（本仓库之外的工具总索引）

本 README 内部的地图：

- 怎么转换（命令、参数、产物验证：退出码、页数、Overfull、图片）：[命令行](#命令行)、[生成后的校验](#生成后的校验)
- 怎么写 md（封面 front matter、数学公式、标题编号起点、告示框、表格、代码与易错点）：[怎么写 Markdown](#怎么写-markdown)
- 怎么换排版规则：[换排版规则](#换排版规则)
