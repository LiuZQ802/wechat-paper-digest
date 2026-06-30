# wechat-paper-digest

一个 [Claude Code](https://github.com/anthropics/claude-code) skill：把论文 PDF 批量转换成公众号"论文荐读"排版的 markdown 文章，并生成可一键复制粘贴进秀米（xiumi.us）/公众号编辑器的样式预览。

## 这是什么

输入一批论文 PDF，输出每篇论文的：

- 封面截图（自动判断 PDF 哪一页同时展示期刊/题目/单位/作者，而不是简单截第一页）
- 2-4 张从正文里挑出来的重要图表，配图说
- 一篇组织好的 `article.md` 正文（内容导读、研究内容、本文引用信息，可选作者介绍）
- `meta.md`（建议标题、分享摘要）
- `preview.html`：带深蓝（可换色）样式、16px正文/18px标题、重点字加粗变色的预览页，附"复制正文"按钮

设计细节和取舍见 [docs 设计文档思路]，简要说：秀米没有公开 API，做不到真正程序化导入，所以采用"生成带样式的HTML → 复制富文本 → 粘贴进秀米"的折中方案；图片本身粘贴不过去，需要照着文中的"图N"标记手动拖图。

## 安装

把整个文件夹放进 Claude Code 的个人 skills 目录：

```bash
git clone https://github.com/<your-username>/wechat-paper-digest.git "$HOME/.claude/skills/wechat-paper-digest"
```

Windows 上是 `%USERPROFILE%\.claude\skills\wechat-paper-digest`。

### 依赖

- Python 3，需要 `PyMuPDF` 和 `pdfplumber`：
  ```bash
  pip install pymupdf pdfplumber
  ```
- 可选：如果用 MinerU 引擎（见下），还需要 `requests`（通常已自带）。
- 可选：本地装有 Chrome 或 Edge，用于 Claude 自动截图检查 `preview.html` 渲染效果（没有也不影响核心功能，只是跳过这一步自检）。

## 使用

在 Claude Code 里新建一个文件夹放论文：

```
papers/
  paper1.pdf
  paper2.pdf
  authors.json     <- 可选：本组成员名单，姓名 -> {affiliation, title}，用于判断"本组文章"
  notes.json        <- 可选：按文件名覆盖 {color, focus, is_own_group}
  engine.json        <- 可选：{"engine": "pymupdf" | "mineru_api", "mineru_api_token": "..."}
```

然后在对话里说类似："用 wechat-paper-digest 处理 papers/ 文件夹"，或者直接 `/wechat-paper-digest`，Claude 会按 [SKILL.md](SKILL.md) 里的流程逐篇处理，输出到你指定的 `output/` 目录。

### 两种 PDF 解析引擎

- `pymupdf`：本地解析，无需联网，啥都不用配。局限：只能抓 PDF 里以"嵌入图片"形式存在的图，论文里**矢量绘制**的示意图（很多方法框架图都是这么画的）抓不到。
- `mineru_api`：调用 [MinerU](https://mineru.net) 的云端解析 API，按论文原始阅读顺序返回内容，图表定位更准，矢量图也能截出来。需要去 mineru.net 注册账号、在"API管理"页面建一个 token，通过环境变量 `MINERU_API_TOKEN` 或 `papers/engine.json` 里的 `mineru_api_token` 字段提供。免费额度：每账号每天1000页优先解析，超出后仍可用但优先级降低。

如果 `papers/` 目录下没有 `engine.json`，Claude 会在处理前先问你用哪个引擎，选完之后写入 `engine.json` 永久生效，不会每次都问。

### 写作风格

正文生成时按 [references/writing-style.md](references/writing-style.md) 的标准把关：每句话要让读者一眼看懂在说什么具体的事，"显著提升""有效解决""具有重要意义"这类没有信息量的修饰词，必须紧跟着具体数字或事实，否则会被打回重写。

## 已知局限

- 秀米没有公开 API，无法做到真正的"一键导入"——只能做到"一键复制格式化文本，手动拖图"。
- `pymupdf` 引擎抓不到矢量绘制的图，遇到这种情况建议切换 `mineru_api`。
- 封面/图表位置判断不确定时，Claude 会主动问你而不是瞎猜——这是设计如此，不是 bug。
- `authors.json`/`notes.json` 需要你自己维护，不会自动同步。

## License

Apache License 2.0，见 [LICENSE](LICENSE)。
