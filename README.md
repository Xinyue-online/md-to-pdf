# md-to-pdf —— Markdown → LaTeX → PDF

> 目录名与程序名均已统一为 **md-to-pdf**（2026-09-11；旧名 `md2pdf` 作废）：模块 `md_to_pdf.py` / `md_to_pdf_gui.py`（Python 文件名用下划线，连字符名无法 import），发行物 `dist\md-to-pdf.exe`（v1.0.6）。

把 Markdown 直接转成 **LaTeX 源码**，再用 **xelatex** 编成 A4 文档 PDF。表格、代码高亮、数学公式等 LaTeX 高级特性全部保留，是 **LaTeX 级排版**（不是浏览器打印）。

产物写在**源文件旁边**：

- `<同名>.tex` —— 完整可编辑的 LaTeX 源码
- `<同名>.pdf` —— A4 文档 PDF
- `images/` —— 本地图片自动复制至此

## 环境依赖

| 依赖 | 说明 | 安装 |
| --- | --- | --- |
| Python 3.x | 运行程序与 GUI | 需已安装 |
| xelatex | LaTeX 编译器（**必须**，用 xelatex 才能正确渲染中文与公式） | 见下方一键安装 |
| tkinterdnd2 | GUI 原生拖拽 | `pip install tkinterdnd2` |

一键安装 LaTeX 引擎（Windows：下载 TinyTeX + 清华镜像 + 必需宏包，一次即可）：

```bash
powershell -ExecutionPolicy Bypass -File install_tex.ps1
```

> 若依赖安装方式有差异，用下面这条**可复现安装命令**（在项目目录执行）：
>
> ```bash
> python -m pip install tkinterdnd2
> ```
>
> xelatex 已装则无需再装 LaTeX；也可设环境变量 `XELATEX_PATH` 指向 `xelatex.exe`。

## 运行 GUI（推荐）

```bash
python md_to_pdf_gui.py
```

窗口标题「**md-to-pdf 转换器**」。把 `.md` 文件拖进窗口（或点「选择文件」），转换结果会**当场显示在窗口里**；出错时窗口内只显示**错误摘要**，不弹后台堆栈。

- **输出位置**：与拖入的 `.md` **同目录**，文件名与原文件同名（`<同名>.tex` + `<同名>.pdf`）。
- **目录层级**（v1.0.6 起）：窗口里的下拉框选 `无目录` / `1 级` / `2 级` / `3 级` / `4 级`（默认 `3 级`），等价于命令行的 `--no-toc` / `--toc-depth N`；转换记录里会回显本次用的档位。该设置只影响**目录页**（`#` 记 1 级、`##` 记 2 级…），不改变正文章节编号。
- **覆盖保护**：同名 `.tex/.pdf` 已存在时会弹窗询问是否覆盖；选「否」自动改用带序号的文件名，不会静默覆盖。
- 也可以不带参数运行 `python md_to_pdf.py`，同样打开 GUI。

> **打包版无黑框（双模式）**：用 `build_exe.ps1` 打包出的 `dist\md-to-pdf.exe` 是 **windowed（无控制台）构建**——双击/启动不会再弹黑色控制台。
>
> - **双击 / 不带参数** → 打开「md-to-pdf 转换器」拖放窗口（GUI）。
> - **带 .md 参数** → 走命令行转换，输出 `<同名>.tex` + `<同名>.pdf`，退出码 0/1（供脚本与 DSH 格式转换入口 format-convert-router 调用）。
>
> 若需要命令行打印输出（TeX/PDF 路径、stderr 详情），请用 `python md_to_pdf.py <文件>`（windowed 版 exe 无控制台，stdout/stderr 会被静默处理，但转换照常完成、退出码正确）。

## 命令行（进阶）

```bash
python md_to_pdf.py example.md                # 输出 example.tex + example.pdf 到 md 旁
python md_to_pdf.py example.md out/           # 指定输出目录
python md_to_pdf.py example.md --toc-depth 2  # 目录只要一二级
python md_to_pdf.py example.md --no-toc       # 不要目录
python md_to_pdf.py example.md --cover-color #DCE3EC --open   # 换封面底色并打开
```

参数：`--header`、`--title`、`--subtitle`、`--cover-color`、`--no-numbers`、`--toc/--no-toc`、`--toc-depth N`(1–4)、`--keep-aux`、`--open`、`--gui`、`--version`。

> GUI 与命令行共用同一套转换逻辑，LaTeX 表格/公式等特性完全一致。

## 怎么写 Markdown

md-to-pdf 是**自定义解析器**（非 GitHub/CommonMark 全集），只用下面这些语法即可；原生 HTML 表格等会被忽略。

### 封面 front matter（可选）

文档开头、以**单独一行 `---` 结束**：

```markdown
# 文档标题
## 副标题（可省略）

页眉：页眉文字（默认取标题）
页尾：封面底部说明文字
封面：#EAF2FB   （封面底色，默认白 #FFFFFF）
作者：张三
版本：v1.0
---
```

- `#` 第一行 → 封面大标题；`##` → 副标题；其余行显示为「键：值」封面条目。
- 特殊关键词：`页眉`/`header`（页眉文字，默认取标题）、`页尾`/`foot`/`footer`/`页脚`（封面底部小字）、`封面`/`cover`（封面底色 `#RRGGBB`，必须 6 位 hex，否则回退白色）、其余如 `作者`/`版本` 显示为条目。
- 封面行值**只放纯文字**，不做行内解析（`$公式$`/`**粗体**` 不生效）。不需要封面就直接从正文开始（自动套默认「未命名文档」封面）。

### 标题

`#`~`######` 对应 `\section`~`\paragraph`，**由 LaTeX 自动编号**，所以别手写编号（如 `# 第1章`、`## 1.1`），否则重复。两个标题文字完全相同会横幅「重复目标」警告，写标题时注意区分。

```markdown
# 一级标题
## 二级标题
### 三级标题
```

### 列表

无序 `-`/`*`、有序 `1.`，可嵌套；任务列表 `- [ ]` 空、`- [x]` 勾选。

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

行内用反引号 `` `code` ``；多行用**三个反引号围栏**并标注语言（python/cpp/java/sql/html/xml/go/lua/tex/ruby/php/matlab/bash 等有高亮；json/css/js/rust 无内置高亮但内容正常）。

````markdown
```python
print("hello")
```
````

- 别输出嵌套三重反引号；代码里别出现 `\end{lstlisting}`（会整块降级纯文本并告警）。

### 链接与图片

```markdown
[文字](https://example.com)      # 链接
<https://example.com>             # 自动链接
![说明](图片.png)                 # 图片（拷入输出 images/）
```

### 数学公式（LaTeX）

行内 `$...$`；独立段 `$$...$$`（独占段落）。公式由 LaTeX **原生渲染**，支持 `\frac`、`\sum`、`\text{}` 等完整语法；常用宏 `\dif`、`\dfrac` 已内置。**不要**用 `\[...\]` / `\(...\)`（原样显示）；正文里的真实美元符（价格 `$5`）写 `\$5` 或放行内代码 `` `$5` ``。粗体可嵌公式：`**安培力 $F_A$ 方向**`。正文可直接写希腊字母（3σ、均值 μ）与常用数学符号（∀ ⇐ ∪ ⊆ ∂ 等，见下节）。化学/核素符号（同位素、核反应）用 mhchem 的 `\ce{...}`：`$\ce{^{1}_{1}p}$`、`$$\ce{^{238}_{92}U \to ^{234}_{90}Th + ^{4}_{2}He}$$`；物理单位用 siunitx：`$\SI{9.8}{\m\per\s^2}$`、`$\unit{\kg}$`（模板已内置 `\usepackage{mhchem}` 与 `\usepackage{siunitx}`）。

```markdown
质能方程 $E=mc^2$，正态分布

$$f(x)=\frac{1}{\sqrt{2\pi}\sigma}e^{-\frac{(x-\mu)^2}{2\sigma^2}}$$
```

### 正文符号：∀ ⇐ ⊆ ∂ ⊗ Ⅰ Ⅱ ■ ● 等（v1.0.5 起，表情标记 v1.0.6 起）

正文符号走三条路，走错任何一条，符号在 PDF 里就是**空白**（xelatex 只在 `.log` 里报 `Missing character`，不报错、不中断，最容易当成"排版就是这样"）：

| 路 | 解决什么 | 例子 |
| --- | --- | --- |
| **① xeCJK 字符类**（交给中文字体） | 中文字体有字形、西文主字体（Latin Modern）没有的码位 | 罗马数字 `Ⅰ Ⅱ Ⅲ Ⅻ ⅰ ⅱ`、`′ ″`、`■ □ ▲ △ ▼ ▽ ◆ ◇ ○ ◎ ●`、`★ ☆ ♀ ♂`、制表符 `─ │ ┌ ┐ └ ┘ ├ ┤ ┼`、方块 `▁ ▂ █ ▌`、`℅ ℉ ℡ ― ⌒` |
| **② `SYMBOL_FALLBACKS` 回退表**（映射成 LaTeX 数学命令） | 两个字体都没有字形、但有等价写法的符号（153 个） | `∀ ∃ ∄ ∅ ⊂ ⊆ ⇐ ⇒ ⇔ ↦ ∂ ∇ ⊗`、角标 `⁴⁻ⁿ ₀₁₂`、`⌈ ⌉ ⌊ ⌋`、`ℝ ℕ ℤ ℚ ℂ ℓ ℏ ℵ`、`∆ ∎ ∐ ∭`、`∼ ≲ ≳ ≰ ≱ ≢ ⊈ ⊉`、`✓ ✔ ✗ ✘ ☐ ☑`、`⅓ ⅔ ⅝`、`Ⅼ Ⅽ Ⅾ Ⅿ`、`⑪ ⑫ ⑳` |
| **③ `EMOJI_ICONS` 图标表**（切到 Windows 自带的 Segoe UI Symbol） | 表情/警示标记：中文字体与 Latin Modern 都没有字形，也没有 LaTeX 等价写法 | `❗`(U+2757)、`⚠`(U+26A0)、`💡`(U+1F4A1)；`❗️ ⚠️ 💡️` 里那个零宽的 U+FE0F 变体选择符会被直接删掉 |

三条路对用户都是透明的——正文直接写即可，不必包 `$...$`：

```markdown
对 ∀ε>0，存在 ∃δ>0；A ⊂ B ⊆ C；x ↦ y；a ⇔ b；10⁻³、v₀、x²+y²。
定理 Ⅰ、引理 Ⅱ；■ 重点 ▲ 提示；∀x∈ℝ，⌈x⌉ ≥ x。
❗ 易错：安培力方向；⚠ 警告：单位统一；💡 思路：先画受力图。
```

- **数学模式不受影响**：`$∀$`、`$\Leftarrow$` 照旧正确（回退用 `\ensuremath`，幂等）；三条路都没收录的冷僻符号仍可写成 `$...$`（如 `$\gtrsim$`）；表情标记进数学模式也安全（`$❗$` 与正文写法一致）；
- 收录标准是**实测**：`measure_coverage.py` 用系统字体 cmap + 一次编译实测算出「该交给中文字体的码位」和「仍然空白的码位」，回退表只收后者里有 LaTeX 等价写法的（所以 `≮ ≯ ℧` 这类西文字体本来就有的符号不在表里）；
- **表情标记的字体依赖**：③ 用的是 Windows 自带的 `Segoe UI Symbol`（非 Windows 机器上通常没有）。字体缺失时导言区走 `\IfFontExistsTF` 的空分支，`❗ ⚠ 💡` 被**丢弃**——不会报错，也不会留空白格；
- 要加符号：`SYMBOL_FALLBACKS`（数学符号）或 `EMOJI_ICONS`（表情标记）加一行，或按 `measure_coverage.py` 输出的片段补一句 `\xeCJKDeclareCharClass`（注意每段必须连续），改完跑 `python test_symbol_fallback.py` 自测；
- **已知限制**：PDF 书签与文档属性（元数据）里的数学记号会被 hyperref 省略（`Token not allowed in a PDF string` 警告），只影响书签文字，不影响页面显示。

```markdown
| 逻辑 | 集合 | 箭头 | 角标 | 其它 | 表情标记 |
|:---|:---|:---|:---|:---|:---|
| ∀ ∃ ∄ | ⊆ ⊇ ⊊ | ⇒ ⇔ ↦ | 10⁻³ v₀ | Ⅰ Ⅱ ■ ● ✓ | ❗ ⚠ 💡 |
```

### 表格

第二行对齐行 `|:---|:---:|` 必须有；长文本列自动换行（≥24 显示宽度转 tabularx）、>24 行自动转 longtable 跨页；单元格内容做行内解析。**别用原生 HTML 表格**；避免超长不可断词（Overfull 多为行尾碎片，调整措辞）。

```markdown
| 列A | 列B |
|:---|:---:|
| 甲 | 1 |
| 乙 | 2 |
```

### 告示框 / 要点框（三种写法）

GitHub 风格（推荐，语义最全）：

```markdown
> [!WARNING]
> 最容易漏的是安培力
> 最容易漏的是安培力，最容易画错方向的也是安培力。
```

- 类型与配色：`NOTE` 蓝 / `TIP` 绿 / `IMPORTANT` 紫 / `WARNING` 橙 / `CAUTION` 红，大小写不敏感；缺省标题 注意/提示/重要/警告/小心；自定义标题 `> [!TIP] 快速检查`（标题与 `[!类型]` 同行）。
- **相邻告示框之间必须空行分隔**；框内容支持粗体、公式、行内代码、列表、多段；不以 `[!...]` 开头的 `>` 引用仍是普通引用（见下方「普通引用」）。
- 按语义选型：补充说明用 `NOTE`，易错用 `WARNING`/`CAUTION`，重点记忆用 `IMPORTANT`。

引述标记（v1.0.6 起，写起来最省事，复用同一套彩色框）：

```markdown
> 💡 思路
> 先画受力图，再判断含安培力的方向。

> ⚠ 单位换算最容易出错，务必逐项核对一遍再往下算。

> ❗ 易错提醒
> 磁通量变化率要取绝对值。
```

- 标记与框的对应：`❗`→红「注意」（cautionbox）、`⚠`→橙「警告」（warnbox）、`💡`→绿「提示」（tipbox）；标记后面空格可有可无（`> ❗ 易错` 与 `> ❗易错` 同义），后面没有文字也可以（`> 💡` 单独一行 → 绿框「提示」，正文从下一行起）。
- 标题规则：标记行剩下的文字**够短**（≤16 显示宽度、不以 `。！？!?…` 结尾）就当框标题，例如 `> 💡 思路` → 绿框标题「思路」；否则标题用该类型的缺省名（注意/警告/提示），这段话连同标记本身留在正文里——所以 `> ⚠ 单位换算最容易出错，务必逐项核对一遍再往下算。` 得到的是橙框「警告」+ 正文那整句话。
- 只有**首行**看标记（与 `[!TYPE]` 相同的判定位置，前面允许空行）；`> ⚠️ xxx` 里的 U+FE0F 变体选择符会被自动删掉，不影响识别。

普通引用（**不带任何标记**的 `> 引用`）本身也有渲染（v1.0.6 起）：浅灰底 + 左侧竖条的中性框（`mdpdfquote`，可跨页），与上面五种彩色告示框同族但不抢眼——引述别人的话一眼可辨，不再只是两侧缩进、和正文混在一起。内容支持多段、列表、公式、粗体，内部再嵌一层引用也正常；孤零零一个 `>`（空引用）不输出任何东西。

旧式写法（解析器仍兼容，写新 md 时禁用）：`::tip` / `::warn` / `::key` … `::end`，默认标题 要点/注意/核心；`::tip` 同行只放短纯文字标题（只转义、不做行内解析），正文从下一行写；语义对应 `TIP`=::tip、`WARNING`=::warn、`IMPORTANT`=::key。**示例见 `example.md`；2026-09-11 起新文稿一律用 `> [!TYPE]` 或上面的引述标记，写作规范见 `写md的注意事项.md`。**

### 引号

中文段落里：全角弯引号 “ ” ‘ ’ 原样全角渲染；半角直引号 `"…"` / `'…'` 包中文时**自动转中文弯引号**。纯英文段落 / 行内代码 / 代码块内不转换；单词内撇号（don't）、落单引号（英寸 5"）不受影响。

### 其他

`**粗体**` / `*斜体*` / `_斜体_` / `~~删除线~~`、`> 引用`（浅灰底中性框，见「告示框」一节）、`---` 分隔线、`::page`（单独一行）= 强制分页、脚注 `[^1]`。

### 输出前自检清单

1. 封面（若需要）：`# 标题` 开头 + 关键词 + 单独 `---`；底部说明用 **页尾**。
2. 所有数学都在 `$…$` / `$$…$$` 内，正文无裸 `$`。
3. 标题无手写编号、无重复标题。
4. 提示/警告一律用 `> [!TYPE]` 或引述标记 `> ❗` / `> ⚠` / `> 💡`（自定义标题同行写，告示框之间空行）；旧式 `::tip/::warn/::key` 不写。
5. 表格有对齐行、无 HTML 表格；代码围栏配对。
6. 未把 `---` 放在“像封面”的前缀后（除非真想写封面）。
7. 目录层级按需选：CLI `--toc-depth N`（`--no-toc` 关闭）/ GUI 的「目录层级」下拉。

## LaTeX 提示：MD 与 PDF 的关系

md-to-pdf 不是把 MD 当纯文本排版，而是把它**翻译成 LaTeX 源码**再交给 xelatex 编译，所以机制上不需要 KaTeX 等前端库：

```text
example.md ──► md-to-pdf ──► example.tex ──► xelatex（循环编译至引用稳定）──► example.pdf
```

- **公式**：md 里写 `$...$` / `$$...$$`，进 LaTeX 后是**原生公式**（不是图片），支持 `\frac`、`\dfrac`、`\text` 等宏；
- **代码**：围栏代码块 → `listings` 语法高亮；
- **表格**：Markdown 表格 → `booktabs` 三线表（超宽自动换行、超行数跨页）；
- **目录/链接**：由 hyperref 生成，PDF 里可点击跳转。

生成的 `.tex` 是**完整可编辑的 LaTeX**——想加自定义环境（定理、算法等）直接改 `.tex`，再手动用 xelatex 编译即可。

## 最小可测试结构

```text
md-to-pdf/
├─ md_to_pdf.py          # 核心转换 + 命令行
├─ md_to_pdf_gui.py      # 图形界面（拖拽入口）
├─ test_symbol_fallback.py  # 符号自测：字符类清单 + 回退表逐符号 + 栅格 + 页眉 + 引述标记（需 xelatex）
├─ measure_coverage.py   # 符号覆盖实测：算该交给中文字体的码位 / 仍空白的码位
├─ install_tex.ps1    # 一键安装 TinyTeX
├─ build_exe.ps1      # 打包单文件 exe（--windowed 无黑框，可选）
└─ example.md         # 示例文档
```

运行（首次装完 xelatex + tkinterdnd2 后）：

```bash
python md_to_pdf_gui.py                # 打开 GUI，把 example.md 拖进去
python md_to_pdf.py example.md         # 命令行一次转换 → 得到 example.tex + example.pdf
```

打包「无黑框」图形界面 exe（双击即用，不弹控制台）：

```bash
powershell -ExecutionPolicy Bypass -File build_exe.ps1
# 产物：dist\md-to-pdf.exe
```

> 未安装 `tkinterdnd2` 时 GUI 会提示「拖拽不可用」，但仍可用「选择文件」完成转换。

## 生成后的校验

转换成功（退出码 0）**不等于**排版没问题——LaTeX 的多数问题只写进 `.log`、不报错也不中断。要复核时加 `--keep-aux` 保留中间文件，再查三项：

| 查什么 | 怎么查 | 期望 |
| --- | --- | --- |
| 缺字形（PDF 里就是空白） | `.log` 里搜 `Missing character` | 0 条；有则按警告提示改用 `$...$`，或把该符号补进 `SYMBOL_FALLBACKS` |
| 溢出行 | `.log` 里搜 `Overfull \hbox` | 0 条（多见于行尾长串不可断词，调整措辞） |
| 页数与产物 | `.log` 末尾 `Output written on ... (N pages)` | 页数与预期相符，`<同名>.pdf` 非空 |

> v1.0.5 起，`Missing character` 会自动汇总成一条警告输出（CLI 打到 stderr，GUI 显示在结果窗口），不必手动翻 `.log`。
>
> 符号相关配置（`SYMBOL_FALLBACKS`、`EMOJI_ICONS`、`\xeCJKDeclareCharClass`）改过之后跑 `python test_symbol_fallback.py`（字符类清单 + 逐符号编译 + 栅格抽查 + 页眉用例 + 引述标记用例，`--quick` 只抽 8 个）；要重算「哪些码位该交给中文字体」跑 `python measure_coverage.py`。

## 相关资料

本 README 是 md-to-pdf 工具的**项目总览**，在 DSH 中由唯一格式转换技能 **`format-convert-router`** 统一索引。

技能文档（位于 DSH 技能池 `<DSH_HOME>\skills\`，相对该目录）：

- 技能总索引：`format-convert-router\references\README.md`
- 技能路由表：`format-convert-router\SKILL.md`
- 本工具**没有** `references\docs\md-to-pdf.md`——本 README 就是它的权威操作文档。
- 全部工具清单：技能池内 `_skill_tool\README.md`（本仓库之外的工具总索引）

- **怎么转换**（`dist\md-to-pdf.exe` 的命令、参数、产物验证：退出码/页数/Overfull/图片）→ 本 README「命令行 / 产物校验」等章节；
- **怎么写 md**（封面 front matter 关键词、LaTeX 数学、标题编号起点、告示框/表格/代码等语法与易错点）→ 本仓库的 `写md的注意事项.md`。
