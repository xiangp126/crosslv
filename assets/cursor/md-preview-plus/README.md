# Markdown Preview Plus

VS Code 自带 Markdown 预览的增强。功能：
- 左侧目录侧栏，☰ 开关，拖动侧栏右边缘调宽度；
- 页内搜索：Cmd+F 打开，Enter / Shift+Enter 跳到下一个 / 上一个，↑ / ↓ 翻以前搜过的词，Aa / ab 切换区分大小写 / 全字匹配（⌥⌘C / ⌥⌘W），Esc 关闭。Cursor 自带的查找在预览里不能用；
- 正文占满窗口宽度，宽表格在宽度内换行；
- 正文、标题和代码的字号，代码用 Monaco 字体；
- diff 配色，与编辑器一致；
- 标题栏的 Preview / Markdown 切换按钮；Cmd+Shift+V 也是原地换成预览，不再开标题带 Preview 的面板（那种面板还能用 Cmd+K V 开）；
- md 预览 tab 自动固定，点链接新开 tab；
- 给自带预览打补丁：tab 被别的 tab 盖住时不销毁，切回来不重新渲染、停在原处；`file#L79` 这种链接跳到那一行（见[给自带预览打的补丁](#给自带预览打的补丁)）；
- Cmd+双击跳到源码。

渲染仍由自带预览完成，本扩展只加样式和小脚本，所以打开时不闪。

## 给自带预览打的补丁

[preview_patch.js](preview_patch.js) 在 Cursor server 自带的 Markdown 扩展里（`~/.cursor-server/bin/linux-x64/<commit>/extensions/markdown-language-features/dist/extension.js`）就地改四处：

| 改了什么 | 为什么 |
|---|---|
| .md 预览 tab 和 Open Preview 面板都要求保留页面（`retainContextWhenHidden`） | 自带预览不保留：tab 被同一组里别的 tab 盖住就销毁，切回来整页重建，大文件很慢，位置也只能大致恢复。VS Code 本身就是这样 |
| 被保留的 tab 在盖住期间文件改了，就地更新 | 原来盖住期间文件一改就整页重载 |
| 点 `file#L79` 这种链接跳到第 79 行 | 语言服务把行号放在 `positionOrRange` 里返回，这一版打开文件的代码读的是 `position`，所以只打开文件、不跳行。上游 VS Code 已经改成读 `positionOrRange` |

- Cursor 升级会换成没改过的新副本。扩展每次启动都检查一遍，没改的就改上，并弹窗提示 Reload Window。每一处各自独立，新版本里找不到的那处只弹警告、不动。
- 打补丁之前开的 Open Preview 面板（标题是 `Preview xxx.md` 的那种）不受影响：reload 时 Cursor 按它创建时的设置恢复，恢复后改不了，要关掉重开一次。.md 预览 tab 没有这个问题。
- 代价是内存：每个开着的预览 tab 都留在内存里。不用的 tab 关掉。
- 手动改：`node preview_patch.js <markdown-language-features 目录>`；撤销：`node preview_patch.js --revert <同一目录>`。扩展下次启动会再改回去，要长期关掉，先从 [extension.js](extension.js) 去掉 `patchBuiltinPreview()`。

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
| [extension.js](extension.js) | Preview / Markdown 按钮，预览 tab 自动固定，启动时给自带预览打补丁 |
| [preview_patch.js](preview_patch.js) | 给自带预览打的补丁：被盖住的 tab 不销毁、文件改动时不重载、`#L` 行号链接跳到那一行 |
| [preview.js](preview.js) | 预览页里的脚本：目录侧栏和拖宽、页内搜索、只有 Cmd+双击才跳源码 |
| [preview.css](preview.css) | 版面、字号、表格、目录、搜索框、diff 颜色 |
| [build_vsix.sh](build_vsix.sh) | 打包、安装、只更新样式 |
