# Markdown Preview Plus

VS Code 自带 Markdown 预览的增强。功能：
- 左侧目录侧栏，☰ 开关，拖动侧栏右边缘调宽度；
- 页内搜索：Cmd+F 打开，Enter / Shift+Enter 跳到下一个 / 上一个，↑ / ↓ 翻以前搜过的词，Aa / ab 切换区分大小写 / 全字匹配（⌥⌘C / ⌥⌘W），Esc 关闭。Cursor 自带的查找在预览里不能用；
- 正文占满窗口宽度，宽表格在宽度内换行；
- 正文、标题和代码的字号，代码用 Monaco 字体；
- diff 配色，与编辑器一致；
- 标题栏的 Preview / Markdown 切换按钮；
- md 预览 tab 自动固定，点链接新开 tab；
- Cmd+双击跳到源码。

渲染仍由自带预览完成，本扩展只加样式和小脚本，所以打开时不闪。

## 安装

在要用的远程机器上执行下面这条命令。前提是 Cursor 至少连过这台机器一次，`~/.cursor-server` 已经存在：

```bash
bash ~/myGit/crosslv/assets/cursor/md-preview-plus/build_vsix.sh
```

然后在 Cursor 里按 Cmd+Shift+P，执行 `Developer: Reload Window`。

## 只改了样式或目录脚本

适用于只改了 [preview.css](preview.css) 或 [preview.js](preview.js) 的情况，不用重装，也不用 reload：

```bash
bash ~/myGit/crosslv/assets/cursor/md-preview-plus/build_vsix.sh --styles
```

执行后把预览 tab 关掉再打开即可。

## 本机安装

不连远程、在本机 Cursor 里用时，先打出安装包：

```bash
bash ~/myGit/crosslv/assets/cursor/md-preview-plus/build_vsix.sh --vsix ~/md-preview-plus.vsix
```

再在扩展面板右上角 `...` 里选 `Install from VSIX...`，选这个文件。

## 配套设置

以下两项放在远程设置里。仓库里的副本是 [remote.settings.json](../remote.settings.json)，机器上的位置是 `~/.cursor-server/data/Machine/settings.json`。

| 设置 | 作用 |
|---|---|
| `"workbench.editorAssociations": {"*.md": "vscode.markdown.preview.editor"}` | md 默认用自带预览打开 |
| `"markdown.preview.openMarkdownLinks": "inEditor"` | 点 md 链接新开 tab，不在当前 tab 里跳转 |

## 文件

| 文件 | 内容 |
|---|---|
| [package.json](package.json) | 扩展声明：预览样式和脚本、标题栏按钮 |
| [extension.js](extension.js) | Preview / Markdown 按钮，预览 tab 自动固定 |
| [preview.js](preview.js) | 预览页里的脚本：目录侧栏和拖宽、页内搜索、只有 Cmd+双击才跳源码 |
| [preview.css](preview.css) | 版面、字号、表格、目录、搜索框、diff 颜色 |
| [build_vsix.sh](build_vsix.sh) | 打包、安装、只更新样式 |
