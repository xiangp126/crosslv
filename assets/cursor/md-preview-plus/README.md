# Markdown Preview Plus

VS Code 自带 Markdown 预览的增强。功能：
- 左侧目录侧栏，☰ 开关，拖动侧栏右边缘调宽度，长标题折行显示；
- 页内搜索：Cmd+F 打开，Enter / Shift+Enter 跳到下一个 / 上一个，↑ / ↓ 翻以前搜过的词，Aa / ab 切换区分大小写 / 全字匹配（⌥⌘C / ⌥⌘W），Esc 关闭。Cursor 自带的查找在预览里不能用；
- 正文占满窗口宽度，宽表格在宽度内换行；
- 正文、标题和代码的字号，代码用 Monaco 字体；
- diff 配色，与编辑器一致；
- 代码块右上角的 Copy：鼠标移到代码块上时出现，点一下复制整块代码（diff 带 `+` / `-`，不带最后一行后面的换行），按钮显示 Copied；
- 标题栏的 Preview / Markdown 切换按钮；Cmd+Shift+V 也是原地换成预览，不再开标题带 Preview 的面板（那种面板还能用 Cmd+K V 开）（Cursor 3.24.18 上正常；在隔离的 3.25.9 上按钮不出现、快捷键没反应，见 [md-preview-plus.md §5 第 14 项](../../../plans/md-preview-plus.md#14-本扩展标题栏的按钮不出现源码里-cmdshiftv-没反应)）；
- 点 md 链接新开 tab（靠远程设置，见[配套设置](#配套设置)）；
- 链接上右键（正文里的链接、侧边栏的目录项）：Copy Link Address（网页链接复制网址，本地文件复制绝对路径，`?v=` 和 `#` 后面的部分照带；目录项复制本文件的路径加 `#<标题的 id>`）、Copy Link Text，选中了文字时还有 Copy；别处右键仍是自带的 Cut / Copy / Paste；
- 带 commit 的源码行链接：`[VHCA.cpp:5149](../../utopx-psf/src/hca/VHCA.cpp?v=6faa4de858#L5149)`，`?v=` 后面是行号所指的 commit，一段行写 `#L5149-L5160`。点开时在当前编辑组打开 worktree 里的文件，停在这几行现在所在的行，行号变了状态栏说一声；这几行改了、删了，也打开 worktree 里的文件，选中现在顶替它们的行（全删了就停在删掉的地方）并弹通知，通知上的 Show as of <commit> 打开那个 commit 时的文件（只读）；文件不在 worktree 里了，直接打开那个 commit 时的文件；commit 里没有这个文件（或者没有这个 commit）就打开 worktree 的文件、停在原行号并警告；
- 给自带预览打补丁：tab 被别的 tab 盖住时不销毁，切回来不重新渲染、停在原处；`file#L79` 这种链接跳到那一行；别的 md 的 `xxx.md#锚点` 链接打开时滚到锚点；带 `?v=` 的链接交给本扩展（见[给自带预览打的补丁](#给自带预览打的补丁)）；
- 给 Cursor 本体打补丁：切回被盖住的预览 tab 时不闪（见[给 Cursor 本体打的补丁](#给-cursor-本体打的补丁)）；
- 页内跳转（点 `#锚点` 链接或侧边栏的目录项，按着 Cmd 点也算）之后能返回：按 ⌃⌥←（[keybindings.json](../keybindings.json) 里 Go Back 的键；Linux、Windows 上是 Ctrl+Alt+←），或编辑器默认的 Go Back 键（Mac 上 ⌃-，Linux 上 Ctrl+Alt+-，Windows 上 Alt+←），或点右下角的 ↩ Back，一次退一步；从另一个 md 点链接过来的，同样能退回那个 md 的 tab，停在点链接的地方；
- Cmd+双击跳到源码。

渲染仍由自带预览完成，本扩展只加样式和小脚本，所以打开时不闪。

## 给自带预览打的补丁

[preview_patch.js](preview_patch.js) 在 Cursor server 自带的 Markdown 扩展里（`~/.cursor-server/bin/linux-x64/<commit>/extensions/markdown-language-features/dist/extension.js`，`<commit>` 就是 Mac 上那个 Cursor 的 commit，About 里能看到）就地改八处。名字是脚本打印的名字：

| 处 | 名字 | 改了什么 | 为什么 |
|---|---|---|---|
| 1 | `keep preview tabs` | .md 预览 tab 要求保留页面（`retainContextWhenHidden`） | 自带预览不保留：tab 被同一组里别的 tab 盖住就销毁，切回来整页重建，大文件很慢，位置也只能大致恢复。VS Code 本身就是这样 |
| 2 | `keep Open Preview panels` | Open Preview 面板也要求保留页面 | 同上 |
| 3 | `update covered tabs in place` | 被保留的 tab 在盖住期间文件改了，就地更新 | 原来盖住期间文件一改就整页重载 |
| 4 | `links to #L<line> jump to the line` | 点 `file#L79` 这种链接跳到第 79 行 | 语言服务把行号放在 `positionOrRange` 里返回，这一版打开文件的代码读的是 `position`，所以只打开文件、不跳行。上游 VS Code 已经改成读 `positionOrRange` |
| 5 | `preview links go to md-preview-plus first` | 预览里点的链接先交给本扩展的命令 `mdPreviewPlus.openLink`；它只接带 `?v=<commit>` 的源码行链接，其余照原来的走 | 带 commit 的源码行链接要换算到现在的行；自带的预览把 `?` 后面的部分丢掉，打开 worktree 的文件，停在原来的行号 |
| 6 | `link opener reaches the previews` | 打开链接的代码拿到预览管理器按行号滚动预览的监视器 | 别的 md 的 `xxx.md#锚点`：语言服务把锚点解析成行号，打开链接的代码却只把它当文本选区交给 `vscode.open`，预览不认，只打开、不滚动 |
| 7 | `links to file#anchor open a new preview there` | 新开的预览从锚点那一行开始 | 同上 |
| 8 | `links to file#anchor scroll an open preview` | 已经开着的预览原地滚到锚点那一行，不重新渲染 | 同上 |

- Cursor 升级会换成没改过的新副本。扩展每次启动都检查一遍，没改的就改上，并弹窗提示 Reload Window。每一处各自独立，新版本里找不到的那处只弹警告、不动。
- 打补丁之前开的 Open Preview 面板（标题是 `Preview xxx.md` 的那种）不受影响：reload 时 Cursor 按它创建时的设置恢复，恢复后改不了，要关掉重开一次。.md 预览 tab 没有这个问题。
- 代价是内存：每个开着的预览 tab 都留在内存里。不用的 tab 关掉。
- 手动改：`node preview_patch.js <markdown-language-features 目录>`；撤销：`node preview_patch.js --revert <同一目录>`。扩展下次启动会再改回去，要长期关掉，先从 [extension.js](extension.js) 去掉 `patchBuiltinPreview()`。

## 给 Cursor 本体打的补丁

[client/](client/) 是另一个小扩展，只在本机（你面前那台电脑，比如 Mac）的 Cursor 里运行。它改 Cursor 安装目录里的 `out/vs/workbench/workbench.desktop.main.js`，共两处：

| 改了什么 | 为什么 |
|---|---|
| 预览被盖住时，把它当时的宽高固定成像素值；重新显示之前，恢复成跟着编辑区走 | 预览是盖在编辑区上的一层 webview，用 CSS anchor 定位到编辑区。tab 被盖住时编辑区移出页面，定位失效，藏着的 iframe 缩成默认的 300x150。切回来时先按 300 宽把整页排一遍、画出一帧小块，再按原宽重排，看起来就是闪两下。VS Code 1.142 也是同一段代码 |

- 同时改 `product.json` 里这个文件的校验值，否则 Cursor 会提示"安装已损坏"。
- md-preview-plus 每次启动都调用命令 `mdPreviewPlusClient.version` 问本机 Cursor 里的 client 是什么版本：命令不存在（没装），或者版本比自己包里带的旧，就装上。所以本机清空 `~/.cursor` 以后，再连一次服务器，client 就会装回来。**改了 `client/` 一定要升 `client/package.json` 的 version**，否则本机的旧 client 不会被换掉。
- client 每次启动都检查一遍，没改的就改上，然后弹窗提示退出 Cursor 再打开（按钮 Quit Cursor）。只 Reload Window 也能让改动生效，但 Cursor 只在启动时读一次校验值，reload 之后会报"安装已损坏"，直到下次完全退出再打开。
- 两处要么一起改，要么都不改。新版本里有一处对不上，就两处都不动，只弹警告。
- 手动改：`node webview_patch.js [<app 目录>]`，app 目录在 Mac 上默认是 `/Applications/Cursor.app/Contents/Resources/app`；Mac 上没有 node 的话，`node` 换成 `ELECTRON_RUN_AS_NODE=1 /Applications/Cursor.app/Contents/MacOS/Cursor`。撤销加 `--revert`。client 下次启动会再改回去。要长期关掉，先从 [extension.js](extension.js) 去掉 `installClient(context)`，再在本机卸载 Markdown Preview Plus (client)。

## 安装

在要用的远程机器上执行下面这条命令。前提是 Cursor 至少连过这台机器一次，`~/.cursor-server` 已经存在：

```bash
bash ~/myGit/crosslv/assets/cursor/md-preview-plus/build_vsix.sh
```

它做三件事：
- 打包（client 在包里）并装进这台机器的 Cursor server；
- 把装好的 `preview.css` 换成指向这里的软链接；
- 把远程设置 `~/.cursor-server/data/Machine/settings.json` 换成指向 [remote.settings.json](../remote.settings.json) 的软链接。两边内容不同时不换，提示先手动合并。

然后在 Cursor 里按 Cmd+Shift+P，执行 `Developer: Reload Window`。md-preview-plus 随后把 client 装进本机 Cursor，client 打好补丁后提示退出重开。

## 升级、重装以后

| 情况 | 要做的 |
|---|---|
| Cursor 升级，或者卸载后重装 | 可能同时弹出 Reload Window（自带预览的补丁）和 Quit Cursor（client）两个提示。点 Quit Cursor，再打开 Cursor，两边都生效。如果第一次启动就报了"安装已损坏"（client 打补丁赶在了完整性检查之前），也是退出再开就好 |
| 本机连 `~/.cursor` 一起删了 | 同上，client 由 md-preview-plus 自动装回 |
| 服务器上的 `~/.cursor-server` 被清掉，或者换了一台服务器 | 执行一次[安装](#安装)里的命令，再 Reload Window |
| 新版 Cursor 改了补丁对应的代码 | 弹 `not found …` 警告，对应的修复暂时失效，其他照常。要按新版本改 [preview_patch.js](preview_patch.js) 或 [client/webview_patch.js](client/webview_patch.js)，步骤见 [md-preview-plus.md §7.5](../../../plans/md-preview-plus.md#75-新版-cursor-补丁对不上)。括号里是 `EACCES`、`EPERM` 的话是没有写权限，不是代码变了 |

## 只改了样式或预览页脚本

装好的 [preview.css](preview.css) 就是这里的文件，改完把预览 tab 关掉再打开，或者执行 `Markdown: Refresh Preview`。

改了 [preview.js](preview.js)（目录、页内搜索、Cmd+双击）的话，先执行下面这条命令，再把预览 tab 关掉重开，不用重装，也不用 reload：

```bash
bash ~/myGit/crosslv/assets/cursor/md-preview-plus/build_vsix.sh --styles
```

## 本机安装

不连远程、在本机 Cursor 里用时，先打出安装包：

```bash
bash ~/myGit/crosslv/assets/cursor/md-preview-plus/build_vsix.sh --vsix ~/md-preview-plus.vsix
```

再在扩展面板右上角 `...` 里选 `Install from VSIX...`，选这个文件。client 同样会被自动装上。

## 配套设置

以下两项放在远程设置里。仓库里的副本是 [remote.settings.json](../remote.settings.json)。机器上的位置是 `~/.cursor-server/data/Machine/settings.json`，[安装](#安装)时它被换成指向仓库副本的软链接，所以在 Cursor 里改远程设置，改的就是仓库里的文件。

| 设置 | 作用 |
|---|---|
| `"workbench.editorAssociations": {"*.md": "vscode.markdown.preview.editor"}` | md 默认用自带预览打开 |
| `"markdown.preview.openMarkdownLinks": "inEditor"` | 点 md 链接新开 tab，不在当前 tab 里跳转 |

## 文件

| 文件 | 内容 |
|---|---|
| [package.json](package.json) | 扩展声明：预览样式和脚本、标题栏按钮、链接的右键菜单 |
| [extension.js](extension.js) | Preview / Markdown 按钮；链接右键菜单的三条复制命令；打开带 commit 的源码行链接（命令 `mdPreviewPlus.openLink`，commit 时的文件用只读的 `mpp-commit:` 打开）；启动时给自带预览打补丁，并把 client 装进本机 Cursor |
| [preview_patch.js](preview_patch.js) | 给自带预览打的补丁：被盖住的 tab 不销毁、文件改动时不重载、`#L` 行号链接跳到那一行、点的链接先交给本扩展、别的 md 的锚点滚到锚点 |
| [line_map.js](line_map.js) | 带 commit 的源码行链接：用 `git diff -U0` 算出这几行现在在第几行，或者已经变了；取 commit 时的文件 |
| [preview.js](preview.js) | 预览页里的脚本：目录侧栏和拖宽、页内搜索、只有 Cmd+双击才跳源码、右键链接时把链接交给菜单 |
| [preview.css](preview.css) | 版面、字号、表格、目录、搜索框、diff 颜色 |
| [client/package.json](client/package.json) | client 的扩展声明：只在本机 Cursor 里运行 |
| [client/extension.js](client/extension.js) | client 启动时给 Cursor 本体打补丁，提示退出重开；注册命令 `mdPreviewPlusClient.version`，md-preview-plus 靠它判断装没装、要不要重装 |
| [client/webview_patch.js](client/webview_patch.js) | 给 Cursor 本体打的补丁，连同校验值一起改；也能在命令行手动改、撤销 |
| [build_vsix.sh](build_vsix.sh) | 打包（连同 client）、安装、把样式和远程设置链到仓库；`--styles` 只更新预览页脚本 `preview.js` |
| [tools/](tools/) | 在隔离的 Cursor 里复测的脚本，用法见 [md-preview-plus.md §8](../../../plans/md-preview-plus.md#8-怎么测) |
| [plans/md-preview-plus.md](../../../plans/md-preview-plus.md) | 设计和维护记录：为什么这样做、每个问题的根因、怎么查、怎么测、经过 |
