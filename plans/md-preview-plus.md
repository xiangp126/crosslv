# Markdown Preview Plus：Cursor 里看 md 的预览扩展

扩展 [md-preview-plus](../assets/cursor/md-preview-plus/) 的设计和维护记录。Peter 在 Mac 上用 Cursor，通过 Remote-SSH 连 m-fwdev-167 看 md 文档，用的是 VS Code 自带的 Markdown 预览加这个扩展。本文写清它做什么、为什么这样做、碰到过的每个问题和根因、怎么检查和测试、出了问题怎么查。安装和日常用法在扩展目录的 [README.md](../assets/cursor/md-preview-plus/README.md)。

| | |
|---|---|
| 现状（2026-10-22） | 功能都在用。10-20 晚上修了 Peter 报的两个 bug（§5 第 15、16 项）；10-22 Peter 确认正文链接上的右键菜单好了，又报侧边栏的目录项上右键仍是没用的 Cut / Copy / Paste，当天修好（第 16 项）。同一天按 Peter 的要求加了页内跳转后的返回（第 17 项），装了 VT100 扩展让 `.log` 里的颜色码显示成颜色（第 18 项，当晚又卸掉）；0.2.4 14:33 装到了服务器。10-22 晚上 Peter 又报了几件：跳过去以后不出现 ↩ Back（第 17 项）；VT100 切回 tab 先露原样再上色（第 18 项；Peter 定卸掉，20:47 从服务器卸了，设置一起删了）；代码块没有一键复制（第 20 项，0.2.5 加上，20:26 装到服务器，Peter Reload Window 后在 Mac 上试）；源码行链接会漂移（第 21 项，Peter 定：链接带 commit，点开时换算到 worktree 里现在的行）；Peter 定修跨文件锚点（第 19 项）。第 17、19、21 项 21:16 在隔离的 3.26.13 里测完；0.2.6 21:19 装到服务器，服务器补丁第 5～8 处 21:20 手动打上，Peter 21:27 Reload。之后 Peter 用自己的后退键仍回不去：他的 keybindings.json 把 Go Back 改成了 ⌃⌥←，preview.js 在 Mac 上只认 ⌃-；改成也认 ⌃⌥←，0.2.7 22:04 装到服务器，Peter 22:25 Reload。之后 Peter 又定两件：`?v=` 链接所引的行改过时也打开真实 worktree、选中替换它的几行，旧版本只在点提示里的按钮时才开（第 21 项）；在别的文件跳过来的页里按后退回到原来那个文件（第 17 项，记录 60 分钟有效）。两件 0.2.8 23:57 装到服务器，等 Peter Reload 后在 Mac 上试。PSF 文档里的代码行链接 22:03 全部改成 `?v=` 写法（第 21 项）。服务器和 Cursor 应用的补丁都验证过，Peter 10-19 在 Mac 上确认切回不闪；10-20 确认 Mac 上的 client 是服务器自动装上的，标题栏按钮和 Cmd+Shift+V 也正常；当前稳定版 3.26.13 在隔离环境里两组补丁都打得上。升级、重装 Cursor 后一般只需点一次 Quit Cursor 再打开；Mac 上改 app 包要不要"App 管理"权限，要等下次升级才知道 |
| 装着的版本 | 服务器：Cursor server `be4c9e5350d77747b42cd467cbd3370a753d4640`（3.24.18），扩展 `markdown-preview-plus.md-preview-plus` 0.2.8（10-22 23:57 装）。Mac：Cursor 3.24.18（VS Code 1.128.0），client `markdown-preview-plus.md-preview-plus-client` 0.1.0 |
| 代码 | crosslv `assets/cursor/md-preview-plus/`：服务器那一半在根目录，`client/` 是 Mac 那一半，`tools/` 是测试脚本；远程设置在 [remote.settings.json](../assets/cursor/remote.settings.json) |
| 提交 | [0d7f44b](https://github.com/xiangp126/crosslv/commit/0d7f44b) 第一版；[24d740f](https://github.com/xiangp126/crosslv/commit/24d740f) 服务器补丁；[6b8971b](https://github.com/xiangp126/crosslv/commit/6b8971b) Cursor 应用补丁、升级后自动恢复；[beb9707](https://github.com/xiangp126/crosslv/commit/beb9707) 测试脚本、本文、删 MPE 残留、删 `keepActivePreviewTab()`、作者改名；10-20 晚上和 10-22 的改动（第 15～21 项）还没提交 |

## 1. 名词

- **Cursor 应用**（也说 Cursor.app）：Mac 上的 Cursor 程序本身，窗口、编辑区、预览外框都是它画的。VS Code 叫它 workbench。
- **Cursor server**：Cursor 连服务器时在服务器上跑的那一半，装在 `~/.cursor-server/bin/linux-x64/<commit>/`，`<commit>` 是 Mac 上那个 Cursor 的 commit（About Cursor 里能看到）。Markdown 扩展和 md-preview-plus 都在这一半里运行。服务器的 home 是 NFS，所有 lab 机共用同一个 `~/.cursor-server`。
- **client**：本扩展的第二个扩展 `markdown-preview-plus.md-preview-plus-client`，只在 Mac 的 Cursor 里运行，专门给 Cursor 应用打补丁。
- **补丁的叫法**：服务器上 8 处，名字以 [preview_patch.js](../assets/cursor/md-preview-plus/preview_patch.js) 打印的为准：`keep preview tabs`、`keep Open Preview panels`、`update covered tabs in place`、`links to #L<line> jump to the line`、`preview links go to md-preview-plus first`、`link opener reaches the previews`、`links to file#anchor open a new preview there`、`links to file#anchor scroll an open preview`，依次叫第 1～8 处。Cursor 应用上 2 处，名字以 [client/webview_patch.js](../assets/cursor/md-preview-plus/client/webview_patch.js) 为准：`release() keeps the size`、`_show() re-anchors first`。"第 N 项"指 §5 的一节。
- **Mac 上的 agent**：Peter 在 Mac 上开的 Claude Code 会话。服务器上的 agent 碰不到 Mac，Mac 那一侧的事都经 Peter 转给它。
- **MPE**：Markdown Preview Enhanced，试过、不用的另一个预览扩展。
- **psf-sanity-baseline-test (506ffde3)、utopx-b3 (5b4a60d7，原名 utopx-81)**：做这件事的两个 Claude 会话，前者做到 10-19 14:29，后者接手；10-20 晚上到 10-22 下午（第 15～19 项）由前者做，10-22 晚上 Peter 又交回给后者。
- 文中 KB 按 1024 字节算。

## 2. 为什么这样做

- **不用 Cursor 自带的 md 视图**（打开 `.md` 后右上角能切 Preview / Markdown 的那个）：它遇到列表项里的代码块会吞掉后面的章节，切模式、切 tab 时会把文件改写回磁盘（§5 第 1、2 项）。远程设置 `"workbench.editorAssociations": {"*.md": "vscode.markdown.preview.editor"}` 让 md 默认用 VS Code 自带的预览打开。
- **不用 MPE**：打开时白闪、大文件很慢（第 3 项）。10-19 卸载，10-20 残留删干净。
- **在自带预览上自己做扩展**：用 `markdown.previewStyles`、`markdown.previewScripts` 往自带预览里加样式和脚本，渲染仍由自带预览完成，所以打开时不闪。`markdown.styles` 设置不行：自带预览只放行工作区和扩展目录里的资源。
- **两组补丁**：被盖住的 tab 不重建、`#L` 跳行要改服务器上自带的 Markdown 扩展（§4.1）；切回不闪要改 Mac 上的 Cursor 应用（§4.2）。都由扩展在启动时自动打，升级后自动重打。
- **否掉的做法**：

| 做法 | 为什么不用 |
|---|---|
| `markdown.links.openLocation: beside`，代码开在旁边一栏，预览就不被盖住 | Peter 10-19："hate it"。md 链接也走这个设置，md→md 会一栏栏往右开 |
| 点 `#L` 链接时在预览里弹浮层显示代码 | Peter 10-19："except for 2, find the real fix solution"，要真修 |
| 页面侧减轻闪：记下排版宽度，视口变成 300x150 时用 CSS 保住 | 总时长从 1.1 s 缩到 0.3 s，仍有约 125 ms 空白帧 |
| 只把正文居中的扩展 md-preview-layout | 没人要，Peter："自带的直接就能用啊"，当即删掉 |
| `keepActivePreviewTab()`：把斜体的预览 tab 转成常驻 | Peter 的设置 `workbench.editor.enablePreview: false` 下不起作用；10-20 Peter 定删掉 |
| 给 microsoft/vscode 报第 7 项的 bug | Peter 10-20 定不报 |
| VT100 扩展把 `.log` 里的颜色码显示成颜色（第 18 项） | 切回 tab 先露原样 1～3.5 s；改成在 Mac 本地跑要手动装、改设置，加缓存要长期维护第三方扩展的补丁。Peter 10-22："if too complex, uninstall it permanently"，当晚卸掉 |

## 3. 功能和实现

| 功能 | 实现 |
|---|---|
| md 默认用预览打开 | 远程设置 `workbench.editorAssociations` |
| 左侧目录：☰ 开关，拖侧栏右边缘调宽，长标题折行 | [preview.js](../assets/cursor/md-preview-plus/preview.js)；内容变化时用 MutationObserver 重建，每帧最多一次；折行靠 `preview.css`（第 15 项） |
| 页内搜索：Cmd+F、Enter / Shift+Enter、↑↓ 翻历史、Aa / ab、Esc | `preview.js`，在 window 的 capture 阶段截下按键，不让 Cursor 那个搜不到东西的查找框弹出（第 4 项） |
| 正文占满宽度、字号（正文 13.5px、目录 12.5px）、表格在宽度内换行、diff 用编辑器配色 | [preview.css](../assets/cursor/md-preview-plus/preview.css) |
| 标题栏 Preview / Markdown 按钮，Cmd+Shift+V 原地换成预览 | [extension.js](../assets/cursor/md-preview-plus/extension.js)、[package.json](../assets/cursor/md-preview-plus/package.json)；Peter 的 3.24.18 上正常，隔离的 3.25.9 上不工作（第 14 项） |
| 只有 Cmd+双击才跳源码 | `preview.js` 拦下没按 Cmd 的 dblclick |
| 页内跳转后返回：点 `#锚点` 链接或目录项之后（按着 Cmd、Shift 点也算），按 ⌃⌥←（Peter 的 Go Back 键；Linux、Windows 上是 Ctrl+Alt+←）或编辑器默认的 Go Back 键（Mac ⌃-、Linux Ctrl+Alt+-、Windows Alt+←），或点右下角 ↩ Back，一次退一步；从别的 md 点链接过来的，同样退回那个文件的 tab，停在点链接的地方 | `preview.js` 在 window 的 capture 阶段记下点击前的滚动位置，最多 50 层；跳到别的 md 记在所有预览共用的 localStorage 里，退回时用脚本点一个指向原文件的临时链接；没有可退的时这些键照常交给 Cursor（第 17 项） |
| 预览里点 md 链接开新 tab | 远程设置 `"markdown.preview.openMarkdownLinks": "inEditor"` |
| 链接上右键（正文里的链接、侧边栏的目录项）：Copy Link Address、Copy Link Text，选中文字时还有 Copy | `preview.js` 右键时把链接交给菜单，`package.json` 的 `webview/context` 菜单，`extension.js` 写剪贴板（第 16 项） |
| 代码块右上角的 Copy：鼠标移到代码块上时出现，点一下复制整块代码，按钮显示 Copied | `preview.js` 在每个代码块前面插一个高度为 0 的 `<mpp-copy>` 放按钮，不放进代码块里；样式在 `preview.css`（第 20 项） |
| 被盖住的 tab 不重建、`#L` 跳行、别的 md 里的 `#锚点` 跳到锚点 | 服务器补丁（§4.1）；锚点见第 19 项 |
| 带 commit 的源码行链接 `[VHCA.cpp:5149](../../utopx-psf/src/hca/VHCA.cpp?v=6faa4de858#L5149)`：打开 worktree 里的文件，停在这一行现在的行号；这一行改了、删了，也打开 worktree 里的文件，选中现在顶替它的行，通知上的按钮 Show as of 打开那个 commit 时的文件（只读）；文件不在了才直接打开 commit 时的文件；右键 Copy Link Address 带上 `?v=` | 服务器补丁第 5 处把预览里点的链接先交给 [extension.js](../assets/cursor/md-preview-plus/extension.js) 的 `openLink`，换算在 [line_map.js](../assets/cursor/md-preview-plus/line_map.js)（第 21 项） |
| 切回不闪 | Cursor 应用补丁（§4.2） |

远程设置在服务器上是 `~/.cursor-server/data/Machine/settings.json`，它是指向 crosslv [remote.settings.json](../assets/cursor/remote.settings.json) 的软链接；在 Cursor 里改远程设置，改的就是仓库里的文件（server 写设置时遇到软链接不做原子替换，写穿到目标）。装好的 `preview.css` 也是指向源码的软链接。

## 4. 两组补丁

### 4.1 服务器上自带的预览

[preview_patch.js](../assets/cursor/md-preview-plus/preview_patch.js) 就地改 `~/.cursor-server/bin/linux-x64/<commit>/extensions/markdown-language-features/dist/extension.js`：

| 处 | 名字 | 匹配 | 加上 | 为什么 |
|---|---|---|---|---|
| 1 | `keep preview tabs` | `registerCustomEditorProvider(…webviewOptions:{enableFindWidget:!0` | `,retainContextWhenHidden:!0` | 自带预览不保留页面：tab 被同组别的 tab 盖住就销毁，切回来整页重建 |
| 2 | `keep Open Preview panels` | `createWebviewPanel(…{enableFindWidget:!0` | `,retainContextWhenHidden:!0` | 同上，对 Open Preview 面板 |
| 3 | `update covered tabs in place` | `\|\|!this._webviewPanel.visible` | `&&!this._webviewPanel.options?.retainContextWhenHidden` | 原来被盖住时文件一改就整页重载 |
| 4 | `links to #L<line> jump to the line` | `let x=await this._client.resolveLinkTarget(…);` | `x&&(x.position??=x.positionOrRange?.start??x.positionOrRange);` | 语言服务把行号放在 `positionOrRange` 里返回，这一版读 `position` |
| 5 | `preview links go to md-preview-plus first` | `async _onDidClickPreviewLink(l){` | `if(await require("vscode").commands.executeCommand("mdPreviewPlus.openLink",l,this.resource).then(h=>h===!0,()=>!1))return;` | 预览里点的链接先交给本扩展的命令 `mdPreviewPlus.openLink`（链接原文、这篇文档）：它只接带 `?v=<commit>` 的源码行链接（第 21 项），打开了返回 true；返回 false、出错、本扩展没在跑，都照原来的走 |
| 6 | `link opener reaches the previews` | `this._topmostLineMonitor=new …;` | `this._opener._topmostLineMonitor=this._topmostLineMonitor;` | 别的 md 里的 `#锚点`（第 19 项）：打开链接的代码拿到预览管理器按行号滚动预览的那个监视器 |
| 7 | `links to file#anchor open a new preview there` | `if(!x)return;let u=….Uri.from(x.uri);` | `x.position&&this._topmostLineMonitor?.setPreviousStaticEditorLine({uri:u,line:x.position.line});` | 新开的预览从锚点那一行开始；行号是第 4 处填上的 `position` |
| 8 | `links to file#anchor scroll an open preview` | `return ….commands.executeCommand("vscode.open",u,{selection:x.position?…})` | `.then(()=>x.position&&this._topmostLineMonitor?.updateLine(u,x.position.line))` | 已经开着的预览，切过去以后原地滚到那一行，不重新渲染 |

- md-preview-plus 每次启动检查一遍，没改的就改上；Markdown 扩展已经在跑时弹 Reload Window。每处各自独立，新版本里找不到的那处只弹警告 `md-preview-plus: not found in this Markdown preview, so not patched: …`，不动文件。只给 md-preview-plus 自己所在的那个 Cursor server 版本打。
- 代价是内存：每个开着的预览 tab 都常驻。打补丁之前开的 `Preview xxx.md` 面板，reload 后按创建时的选项恢复，仍会销毁，关掉重开一次就好。
- 手动：`node preview_patch.js [--revert] <markdown-language-features 目录>`。

### 4.2 Mac 上的 Cursor 应用

[client/webview_patch.js](../assets/cursor/md-preview-plus/client/webview_patch.js) 改 `/Applications/Cursor.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js` 里 `OverlayWebview` 的两处（Cursor 3.24.18 和 3.25.9 的压缩代码里各正好出现一次），根因见第 7 项：

```diff
 release(e){… this._overlayLayout&&(
+    this._options.retainContextWhenHidden&&this._anchorState?.anchorElement.isConnected&&
+    (r=>{r.width>0&&r.height>0&&(this._overlayLayout.content.style.width=r.width+"px",
+        this._overlayLayout.content.style.height=r.height+"px")})(this._overlayLayout.content.getBoundingClientRect()),
     this._overlayLayout.content.style.visibility="hidden"),this._options.retainContextWhenHidden?…
 _show(e){… this._overlayLayout&&(
+    this._overlayLayout.reapplyLayoutStyles(),
     this._overlayLayout.content.style.visibility="visible")
```

- 藏起来的那一刻锚点还在，把当时的宽高写死成像素值；重新显示前恢复"跟着锚点走"，显示以后窗口或分栏变了，预览照样跟着变。两处要么一起改要么都不改。
- 同时改 `/Applications/Cursor.app/Contents/Resources/app/product.json` 的 `checksums` 里这个文件的 sha256（base64，去掉末尾的 `=`），否则 Cursor 提示安装已损坏。
- client 每次启动检查一遍，没改的就改上，弹 Quit Cursor：Cursor 只在启动时读一次校验值，只 reload 会报"安装已损坏"（第 11 项）。对不上时弹 `md-preview-plus-client: not found in this Cursor, so not patched: …`，不动文件；没有写权限时也是这句，括号里是 `EPERM`。
- md-preview-plus 每次启动调用命令 `mdPreviewPlusClient.version` 问本机 client 的版本：命令不存在（没装），或者比自己包里带的旧，就用 `workbench.extensions.installExtension` 把包里的 `client.vsix` 装到本机（Cursor 先把服务器上的 vsix 下载到本机再装）。所以 **改了 `client/` 必须升 `client/package.json` 的 version**，否则到不了 Mac。
- 手动：`node webview_patch.js [--revert] [<app 目录>]`，默认 `/Applications/Cursor.app/Contents/Resources/app`；Mac 上没有 node 就用 `ELECTRON_RUN_AS_NODE=1 /Applications/Cursor.app/Contents/MacOS/Cursor`。

## 5. 问题和根因

### 1 自带 md 视图吞掉章节

文档 6 章只显示 4 章，文件本身完整。Cursor 自带 md 视图遇到嵌在列表项里的 fenced 代码块，把这一章连同后面的章节都丢掉（3.24.18）。机理看不到，10-17 用单变量对照证实：两份文档只差 §5 的两个代码块在不在列表项里，Peter："A全部显示,B只到第4章"。修法：不用这个视图；写 md 时代码块不放进列表项（skill `markdown-docs` 的 Structure 一节）。引用块里的代码块没做对照。查一份文档：用 markdown-it 解析，看 `fence` token 的 `level` 是否大于 0。

### 2 自带 md 视图改写文件

文档"自己变了格式"：裸 URL 变成 `[URL](URL)`，`` `l-fwreg-*` `` 被拆坏，表格补空格。它是所见即所得的编辑器，切 Preview / Markdown 或切 tab 时把整个文件重新写回磁盘，不提示。10-17 21:59 Page_Supplier 的 TRACKING.md 被整篇改写，论坛有同类报告 [forum 153590](https://forum.cursor.com/t/153590)、[forum 162540](https://forum.cursor.com/t/162540)。修法同上。

### 3 MPE 白闪、慢

webview 页面出来之前那一帧是白的。MPE 要先初始化、读配置、编译 `style.less`、解析 md，页面要等 4.2 MB 的 React 脚本跑完才有内容，所以白得久。自带预览只加载 16 KB 的 `index.js` 和 5 KB 的 `markdown.css`，本扩展在首帧之后才加脚本和样式，看不到白。试过 `previewColorScheme: editorColorScheme` 和暗色主题，渲染中仍白闪。10-19 卸载；10-20 删掉了设置里的两行、`mpe.style.less`、`~/.local/state/crossnote/` 和服务器上的扩展目录。

### 4 预览里 Cmd+F 搜不到

Markdown 扩展给预览开了 `enableFindWidget`，但 Cursor 里所有 webview 的查找框都弹得出来、搜不到东西；2.2.14 起就有人报，官方说是已知 bug、没有修复时间（[forum 145932](https://forum.cursor.com/t/145932)）。修法：`preview.js` 自己做页内搜索，高亮用 CSS Custom Highlight API，不改 DOM。

### 5 被盖住的预览 tab 切回来整页重建

在预览里点链接跳到别的 tab，再切回来，整页重新渲染（大文档要好几秒），位置只按滚动比例大致恢复；VS Code 原版也这样。webview 默认在不可见时销毁，要保留得在创建时传 `retainContextWhenHidden`，自带预览没传。修法：服务器补丁第 1～3 处。证据：Peter 10-19 13:52 确认 `.md` 预览 tab 切回不再重建；第 3 处用 `tools/covered_update.mjs` 测，打补丁时页面不重建、内容更新、位置不变，只去掉第 3 处做对照，页面整页重建、位置偏 18 px。

### 6 file#L79 链接只开文件不跳行

点链接时扩展先问语言服务链接指向哪里，返回值把行号放在 `positionOrRange` 里，这一版打开文件的代码读的是 `position`；上游 `openDocumentLink.ts` 已经改成读 `positionOrRange`。修法：服务器补丁第 4 处。证据：隔离的 Cursor 里点测试文档的 `sample.cpp#L79`，状态栏 `Ln 79, Col 1`。

### 7 切回被盖住的预览时闪两下

在长文档的预览里点代码链接，代码在同一组打开、盖住预览；再点回预览 tab，先出现旧画面，接着几乎全空、只有左上角一小块，然后才正常。

webview 不在编辑区的 DOM 里，而是单独一层盖在整个窗口上，用 CSS anchor 定位把位置和宽高绑到编辑区容器（`width: anchor-size(width)` 等，`overlayLayoutElement.ts` 的 `reapplyLayoutStyles()`）。tab 被盖住时，`EditorPanes` 先调 `release()` 把 webview 设成 `visibility: hidden`，再把编辑区容器移出 DOM；锚点没了，`anchor-size()` 失效，iframe 退回浏览器默认的 300x150。点回 tab 时，页面先按 300 宽把整篇排一遍，画出一帧只有左上角有内容的画面，再按原宽排一遍。只有被盖住时不销毁的 webview 才会碰到；文档小的时候一闪而过，少有人注意。VS Code 1.142 和上游 main 是同一段代码（[overlayWebview.ts](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/webview/browser/overlayWebview.ts)、[overlayLayoutElement.ts](https://github.com/microsoft/vscode/blob/main/src/vs/base/browser/overlayLayoutElement.ts)；对照代码，没跑 VS Code）。修法：§4.2。

证据，隔离的 Cursor 3.25.9 里点回 tab 之后：

| 版本 | 被盖住时的 iframe | 画面 | 页面里 |
|---|---|---|---|
| 原版 | 300x150 | +142 ms 旧画面，+970 ms 空白帧，+1113 ms 正常 | 按 300 宽排 918 ms，再按 1000x676 排 129 ms |
| 改 Cursor 应用两处 | 1000x676 | +76 ms 正常，没有空白帧 | 不重排 |
| 只改页面 | 300x150 | +183～231 ms 空白帧，+308 ms 正常 | |

用固定测试文档复测：原版 +1028 ms 空白帧，补丁版 +71 ms 正常。Peter 10-19 21:25 在 Mac 上（3.24.18）确认"不闪了"。

### 8 表格第一列被挤得一字一行

第一版给所有单元格加了 `overflow-wrap: anywhere`：它把任意位置都算作断点，计入列的最小宽度，短列（7 位 change 号）被挤成一字一行。修法：只让表格里的代码随处断行（`.markdown-body table code`），代码外的长词靠自带 `markdown.css` 的 `word-wrap: break-word`。证据：隔离的 Cursor 里测试文档的 change 号一行显示，列宽 80 px。

### 9 改了源码里的 preview.css 预览不变

预览加载的是装在 `~/.cursor-server/extensions/<id>-<版本>/` 里的副本。修法：`build_vsix.sh` 装完把装好的 `preview.css` 换成指向源码的软链接，改完执行 `Markdown: Refresh Preview` 或关掉重开；`preview.js` 仍是拷贝，改了跑 `build_vsix.sh --styles`。

### 10 换了扩展 ID 没 reload，目录点了不跳

10-18 md-preview-toc 改名为 md-preview-plus 后没 reload：旧扩展在当前窗口里卸不掉，新扩展又被动态加进来，两份侧栏脚本互相把对方的改动当成正文变化，每帧重建一次（1 秒内侧栏 DOM 变动 780 次），目录链接在按下和松开之间被换成新元素，点了不跳。修法：Reload Window。命令行装的扩展，正在跑的窗口有时动态加载、有时不加载，所以装完一律 Reload Window，再在 `~/.cursor-server/data/logs/*/exthost*/remoteexthost.log` 里确认 `_doActivateExtension`。

### 11 打完 Cursor 应用补丁只 reload，报安装已损坏

```text
Your Cursor installation appears to be corrupt. Please reinstall.
```

主进程只在启动时从磁盘读一次 `product.json`，之后每个窗口的完整性检查都拿内存里的旧校验值去比磁盘上的文件。补丁写盘后只 reload，就报损坏，补丁本身已经生效；完全退出再打开就干净了。Cursor 没有"重启整个应用"的命令，所以 client 的按钮是 `workbench.action.quit`，再手动打开。升级后第一次启动 client 当场打补丁，实测那次没报（完整性检查先跑完了），但这是时序，不是保证；万一报了，也是退出再开就好。

### 12 快捷键打开的预览标题带 Preview

自带预览有两种：`Preview xxx.md` 是 Open Preview 打开的独立面板，Cmd+Shift+V、Cmd+K V、源码 tab 上的 "Open Preview to the Side" 开的都是它；`xxx.md` 是这个文件的 custom editor，资源管理器、Cmd+P、md 链接开的是它。所以本扩展把 Cmd+Shift+V 绑到"原地换成 custom editor"的命令上。当时同一个键上有三方：

| 谁 | 绑定 | 在扩展清单里排第几 |
|---|---|---|
| 本扩展 | `shift+cmd+v` → `mdPreviewPlus.showPreview` | 1 |
| MPE 0.8.27（已删） | `cmd+k v` → `openPreviewToTheSide`；`cmd+shift+v` → `openPreview` | 1、2 |
| Peter 本机 | `ctrl+alt+m` → `markdown.showPreview`（10-20 删掉）；去掉了 `shift+cmd+v` → `markdown.showPreview` | 用户自己的绑定 |

按 VS Code 的源码（没在 Cursor 上实测）：扩展的每条键位权重是 400 加它在该扩展清单里的序号，自带扩展是 300 加序号（[keybindingService.ts](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/services/keybinding/browser/keybindingService.ts)、[keybindingsRegistry.ts](https://github.com/microsoft/vscode/blob/main/src/vs/platform/keybinding/common/keybindingsRegistry.ts)）；查找时从后往前，第一个 `when` 成立的生效（[keybindingResolver.ts](https://github.com/microsoft/vscode/blob/main/src/vs/platform/keybinding/common/keybindingResolver.ts)）；用户 `keybindings.json` 的绑定总是赢。当时 MPE 的 402 压过本扩展的 401。Peter 一直按的是 ctrl+alt+m，它开的就是带前缀的面板；10-20 Peter 把这个键位删了。

### 13 改 publisher 等于换了扩展 ID

扩展列表里"作者"显示的是 `publisherDisplayName`；本地装的 VSIX 没有市场信息，就显示 `package.json` 的 `publisher`。它是扩展 ID（`<publisher>.<name>`）的一部分，不能有空格，改它就是另一个扩展，装好的目录名是小写的 `<publisher>.<name>-<版本>`。迁移：服务器上先 `"$(ls -td ~/.cursor-server/bin/linux-x64/*/ | head -1)bin/cursor-server" --uninstall-extension <旧 ID>`，再 `build_vsix.sh`，然后 Reload Window；Mac 上先卸掉旧的 client，再 Reload Window（md-preview-plus 只看版本号，旧 client 在就不装新的）。10-19 依次试过 `PeterX`、`peter`，最后定为 `markdown-preview-plus`。

### 14 本扩展标题栏的按钮不出现，源码里 Cmd+Shift+V 没反应

只在隔离的 3.25.9 上看到（10-22 隔离的 3.26.13 上也一样），没修。Peter 10-20 在他的 3.24.18（远程窗口）上确认按钮都在、Cmd+Shift+V 能原地换成预览。可能是 3.25.9 改了什么，也可能和隔离环境是本地窗口有关，没查；Cursor 升级到 3.25 以后要再看一次。预览 tab 的标题栏上只有自带的 Show Source，没有本扩展的 Markdown 按钮；点 Show Source 打开的源码 tab 是 Cursor 自带 md 视图的 Markdown 模式（编辑区上方有 `.markdown-mode-tab`），不是普通文本编辑器，所以本扩展 Preview 按钮的条件 `activeEditor == 'workbench.editors.files.textFileEditor'` 不成立；在里面按 Ctrl+Shift+V 没反应。Markdown 按钮的条件和 Show Source 一样却没出现，快捷键为什么不触发，都没查。复现：`tools/accept.mjs` 第 5 项。

### 15 目录里的长标题只显示一行

Peter 10-20："侧边栏的标题不会折叠吗？目前无论多长都显示在第一行"。目录项的样式是 `white-space: nowrap`、`overflow: hidden`、`text-overflow: ellipsis`，超出侧栏宽度的部分截成"…"。修法：去掉这三行，加 `overflow-wrap: anywhere`（长的英文词也能断开），长标题折成几行，每一行都从这一项的缩进处开始；目录项上原来为截断准备的 `title` 提示一起去掉。证据：隔离的 Cursor 3.25.9 里打开 Page_Supplier 的 Defects.md 副本，侧栏 280 px 时 "#27 随机补页给 PSF 发普通 PROVIDE_PAGES" 原来截成一行（262 / 306 px），改后折成两行，没有被截的项；`accept.mjs` 第 2 项查测试文档第 43 节的长标题。

### 16 链接上右键的 Cut / Copy / Paste 没用

Peter 10-20："在超链接上右键单击，出现 cut copy 和 paste，但是使用发现这几个按钮都没用"。这三项是 webview 自带的右键菜单，点了以后对页面执行 `document.execCommand`，只作用于选中的文字：在链接上右键时什么也没选中，Copy 不复制任何东西；预览是只读的，Cut 和 Paste 从来不起作用。先选中文字再右键，Copy 是好的。

修法：在链接上右键时，菜单换成链接自己的几项。webview 的宿主页（Cursor 安装目录里的 `out/vs/workbench/contrib/webview/browser/pre/index.html`）在 `contextmenu` 时从目标元素往上收集 `data-vscode-context`，作为 `webview/context` 菜单的上下文和命令的参数；其中 `preventDefaultContextMenuItems: true` 去掉自带的三项。
- `preview.js` 在 window 的 capture 阶段（先于宿主页的监听）给被右键的链接写 `data-vscode-context`：`webviewSection: 'mppLink'`、链接地址 `mppHref`、链接文字 `mppText`、当时选中的文字 `mppSelection`。地址：网页链接原样；本地文件按文档自己的 URI（页面里 `vscode-markdown-preview-data` 的 `source`）解析成绝对路径，`#` 后面的部分照带。远程窗口里 `source` 是 `vscode-remote://…`，同样解析成服务器上的路径。
- `package.json` 的 `webview/context` 在 `webviewSection == 'mppLink'` 时显示 Copy Link Address、Copy Link Text，有选中的文字时再加 Copy。三条命令在 `extension.js` 里，用 `vscode.env.clipboard` 写剪贴板；远程窗口里写的是本机的剪贴板。页面自己收不到菜单项被点的消息，所以写剪贴板要放在扩展里。
- 不在链接上（正文、侧边栏的空白处）右键时不写这个属性，菜单还是自带的三项。

10-22 Peter："你之前已经修复了md 正文右键按钮无效的问题，但是侧边栏依旧有这个问题"。侧边栏的目录项也是链接（`href` 是 `#<标题的 id>`），0.2.2 的 `preview.js` 却跳过了本扩展自己节点里的链接（`a.closest(OWN)`），所以目录项上还是自带的三项。修法：去掉这个排除。目录项的地址按同样的规则解析成这个文件的绝对路径加 `#<标题的 id>`，链接文字就是标题。

证据（隔离的 Cursor 3.25.9）：改前在链接上右键是 Cut / Copy / Paste，点 Copy 后剪贴板不变；改后是 Copy Link Address / Copy Link Text，本地链接复制出绝对路径（`logs/…log#L5364` 复制成带 `#L5364` 的绝对路径），网页链接复制出网址，先选中文字再右键多一项 Copy、复制的是选中的文字；正文和目录上右键仍是 Cut / Copy / Paste。`accept.mjs` 第 4 项查这些，0.2.1 上不过，0.2.2 上过。

侧边栏的证据（隔离的 Cursor 3.26.13）：0.2.2 上目录项右键是 Cut / Copy / Paste，剪贴板不变；0.2.3 上是 Copy Link Address / Copy Link Text，第 70 节复制出 `…/long.md#70-第-70-节`，Copy Link Text 复制出标题全文；侧边栏空白处仍是 Cut / Copy / Paste。`accept.mjs` 第 4 项加查了目录项，0.2.2 上不过，0.2.3 上过。

### 17 页内跳转以后回不去

Peter 10-22："点击了run log #4之后跳转的是对的,但是跳转之后怎么再跳到原来的位置呢?"。点 `#锚点` 链接时，webview 的外壳（Cursor 安装目录里 `out/vs/workbench/contrib/webview/browser/pre/index.html` 的 `handleInnerClick`）直接对目标元素 `scrollIntoView()`，不进浏览历史；Cursor 的 Go Back 只记编辑器里的光标位置，管不到预览的滚动位置。修法：`preview.js` 在 window 的 capture 阶段（先于外壳的处理）看点击：左键（按着 Cmd、Shift 这些键也算，见下）、点的是指向本页存在的元素的 `#` 链接（目录项也是），就先记下当时的 `scrollY`；在预览里按编辑器的 Go Back 键或点右下角的 ↩ Back，滚回最近记下的位置。按钮只在有可退的位置时显示；没有可退的位置时 Go Back 键不拦，照常交给 Cursor。

外壳的这段处理要求 `event.isTrusted`：用脚本调 `a.click()` 点出来的事件不算，浏览器会按普通链接导航，以 `<base>` 为基准把 iframe 导航走，预览就坏了，测试时要用调试协议发真实的鼠标事件。从别的文件链过来的 `xxx.md#锚点` 不滚动，见第 19 项。

证据（隔离的 Cursor 3.26.13）：测试文档里点 `#run-25` 的链接，第 25 行停在顶端，↩ Back 出现；按 Ctrl+Alt+- 回到点击前的 5484，按钮消失；点目录项再点 ↩ Back 也回到 5484。`accept.mjs` 第 2 项加查了这一项。

10-22 晚上 Peter 报 Mac 上"没出现 ↩ Back"：点 `#run-N` 链接跳得对，↩ Back 却不出现。当时推断是按着 Cmd 点的（Mac 上没看到；不是全部原因，见下一段）：外壳的 `handleInnerClick` 不看修饰键，按着 Cmd 点也照样跳；原来的 `preview.js`（服务器上装的 0.2.5 也是）只在不带修饰键时记位置，按着 Cmd 点就跳了、没记，↩ Back 不出现。修法：左键就记，不管按没按 Cmd、Shift 这些键。证据（隔离的 Cursor 3.26.13，`anchors.md` 里的 `#run-25` 链接和目录项 Run log）：旧的 `preview.js` 上，按着 Meta 点链接、按着 Meta 或 Shift 点目录项，页面都跳了，↩ Back 不出现，和 Peter 看到的一样；改后普通、Meta、Shift 三种点法，链接和目录项都跳到顶端、出现 ↩ Back，Ctrl+Alt+- 和 ↩ Back 都回到 0。`accept.mjs` 第 2 项加了按着 Meta 点目录项、再点 ↩ Back。装上以后 Mac 上还不出现，先看 Reload Window 过没有（第 10 项）：没 reload 的窗口里，预览跑的可能还是旧的 `preview.js`。

10-22 晚上 Peter 又说："单击就跳转到 run log #1 的位置…然后我希望用通用回退的快捷键回退到之前的位置,可还是不work"。他是单击的，按着 Cmd 点那条推断解释不了。原因是键对不上：Peter 的 [keybindings.json](../assets/cursor/keybindings.json) 把 Go Back（`workbench.action.navigateBack`）绑在 ⌃⌥←（`ctrl+alt+left`）上，去掉了默认的 ⌃-；`preview.js` 在 Mac 上只认 ⌃-。他按 ⌃⌥←，`preview.js` 不拦，键交给 Cursor，Cursor 的 Go Back 退的是编辑器里的位置，预览停在跳过去的地方。修法：`isBackKey` 在所有平台上都认 Ctrl+Alt+←（Mac 上就是 ⌃⌥←），各平台默认的键照旧（Mac ⌃-、Linux Ctrl+Alt+-、Windows Alt+←）；↩ Back 的提示写出两个键：Mac `⌃⌥← or ⌃-`，Linux `Ctrl+Alt+← or Ctrl+Alt+-`，Windows `Alt+← or Ctrl+Alt+←`。仍然只在有可退的位置时拦，否则照常交给 Cursor。Mac 上 Go 菜单里的 Back 也带着 ⌃⌥← 这个快捷键，不过按键先到页面，页面拦下（`preventDefault`）以后不再交给菜单（读的 Chromium 148、Electron 42 的代码，没在 Mac 上试）。

证据（隔离的 Cursor 3.26.13，调试协议发真的鼠标和键盘事件，`anchors.md`）：

| 操作 | 旧的 `preview.js` | 改后 |
|---|---|---|
| 单击 `#run-25` 链接（0 → 10277），按 Ctrl+Alt+← | 停在 10277，↩ Back 还在，键交给了 Cursor | 回到 0，按钮消失，键没交给 Cursor |
| 单击目录项 Run log（2000 → 9356），按 Ctrl+Alt+← | 停在 9356，↩ Back 还在，键交给了 Cursor | 回到 2000，按钮消失，键没交给 Cursor |
| 同样两种点法，按 Ctrl+Alt+- | 回到 0、2000，按钮消失 | 同左 |
| 没有可退的位置，按 Ctrl+Alt+← | 页面不动，键交给了 Cursor | 同左 |

"键交给了 Cursor"看的是 workbench 的 window 上有没有收到 webview 转上来的那个按键（`isTrusted` 为 false 的 keydown）。`isBackKey` 和提示还在 Mac、Linux、Windows 三种 `navigator.platform` 下跑了：改前三个平台都不认 Ctrl+Alt+←，改后都认，⌃-（Mac）、Ctrl+Alt+-（Linux）、Alt+←（Windows）照旧。`accept.mjs` 第 2 项加了再点一次目录项、按 Ctrl+Alt+←。

10-22 深夜 Peter 在 Mac 上（0.2.7）：在 Tracking.md 的预览里点 `[Ledger.md §10.144](Ledger.md#10144-…)`，Ledger 的预览打开在 §10.144（第 19 项的补丁管用），按 ⌃⌥← 却回不到 Tracking.md。`preview.js` 的回退记录是每一页自己的，Ledger 那一页不知道是从 Tracking 跳过来的。Peter："改，但是不要影响已有功能"。

先查（隔离的 Cursor 3.26.13，测试环境的 `keybindings.json` 照 Peter 的写了两条：ctrl+alt+left → `workbench.action.navigateBack`（when `canNavigateBack`），ctrl+- 上去掉 navigateBack；A 是 xa.md，B 是 xb.md，A 停在 9025 点 `xb.md#target`）：
- B 原来关着，或者开着被盖住，B 自己没有页内跳转：按 Ctrl+Alt+←，`preview.js` 不拦，键交给 Cursor；Cursor 自己的 Go Back 回到 A 的 tab，A 还在 9025。再按一次，Cursor 按它的编辑器历史接着往前退（这里退到更早开过的 xb.md）。
- B 里有更早的页内跳转：第一下被 `preview.js` 拿去退 B 自己的位置（滚到 0），留在 B；第二下才交给 Cursor，回到 A。Peter 遇到的应是这种：Ledger 里常点 `#run-N`。
- 测试环境里点完 A 的链接，整个窗口没有一个 frame 有焦点（`document.hasFocus()` 为 false），调试协议发的键哪儿也没到；在 B 的正文上点一下，键才进 B。Mac 上点完链接焦点在哪，没看到。

修法（只改 `preview.js`，不加键位，不加服务器补丁）：
- 左键点一个指向别的 .md 文件的链接（按没按 Cmd 这些键都算；相对路径，带不带 `#` 都算）：把 `{ from: 本页文件的绝对路径, to: 目标文件的绝对路径, time }` 记进 localStorage 的 `md-preview-plus-file-jumps`，最多 50 条。所有预览是同一个 origin（实测三个预览都是同一个 `vscode-webview://…`），B 的页面读得到 A 记下的。只记真的点击（`isTrusted`），回退时脚本点的那一下不算。页内跳转的记录也带上时间。
- 按 Go Back 键或点 ↩ Back：找最新一条 `to` 是本页的记录，它比本页最新的页内跳转新（或本页没有页内跳转），就删掉它，回到 `from`：在页面里放一个指向 `from`（相对本页目录的路径）的临时 `<a>`，用脚本点它。预览自己的点击处理（`media/index.js` 在 document 的 capture 阶段）不看 `isTrusted`，没有 scheme 的链接就发 `openLink` 给扩展并 `preventDefault`，iframe 不会被导航走（上面说的导航走只发生在 `#` 链接上：`index.js` 对 `#` 链接直接 return，外壳又不认脚本点的）。扩展切到 A 的 tab，它被盖住时没销毁，还停在点链接的地方；A 关了就和点一个指向它的链接一样，新开一个 tab。不是这种情况就照旧退本页的位置；都没有就照旧把键交给 Cursor。
- ↩ Back 在有这样一条记录时也显示；别的页面改了记录（`storage` 事件）或页面显示出来（`visibilitychange`）时重算。
- 每条记录只在点链接以后一小时内有效（为了"不要影响已有功能"）：过了一小时的不算，下次写记录时删掉；↩ Back 只因为这样一条记录才显示的，到它过期时页面自己再算一次，按钮随之藏起来。所以没有记录，或者记录都过了一小时，键和按钮跟以前完全一样：有页内跳转就退页内，没有就把键交给 Cursor。记录在 localStorage 里，所有预览共用，退回去用掉的马上删，最多 50 条。

证据（隔离的 Cursor 3.26.13，调试协议发的真鼠标和键盘事件，A 停在 9025 点链接；"改前"是旧的 `preview.js`）：

| 情况 | 改前 | 改后 |
|---|---|---|
| A → B（B 原来关着），在 B 里按 Ctrl+Alt+← | B 没有 ↩ Back；键交给 Cursor，它的 Go Back 回到 A | B 有 ↩ Back；键没交给 Cursor，回到 A，A 在 9025；B 的页面没被导航走，它的 ↩ Back 随即消失 |
| 同上，点 B 的 ↩ Back | 没有按钮，留在 B | 回到 A，A 在 9025 |
| A → B（B 开着、被盖住），按 Ctrl+Alt+← | 同第一行 | B 的 ↩ Back 马上出现（`storage` 事件到了被盖住的页面），回到 A |
| A → B，在 B 里再跳一次 `#run-25`，按两次 | 第一下 B 回到 0；第二下交给 Cursor，回到 A | 第一下 B 回到 0；第二下回到 A，键没交给 Cursor |
| B 里原来有一次页内跳转，再 A → B，按一下；回到 B 再按 | 第一下留在 B（滚到 0）；回到 B 再按交给 Cursor | 第一下回到 A；回到 B 再按，B 退到原来的 0 |
| 没有回 B 的记录，B 也没有页内跳转 | 键交给 Cursor | 同左 |
| A → B 以后，把这条记录的时间改到 61 分钟以前 | B 没有 ↩ Back，键交给 Cursor | 同左；下次点链接写记录时，这条被删掉，只剩新的一条 |
| 把记录的时间改到再过 5 秒就满一小时 | B 没有 ↩ Back | B 的 ↩ Back 先显示，6 秒后自己藏起来 |

已有功能（改后）：`accept.mjs` 1～4、6、7、13～16 通过，5 不过（第 14 项）；`covered_update.mjs` 不重建、位置不变；`flash.mjs` 切回不闪；`anchors.md` 里链接和目录项、普通 / Meta / Shift 三种点法、Ctrl+Alt+- / Ctrl+Alt+← / ↩ Back 三种退法，18 种全过；long.md 里先点目录项（1000 → 140381），再点 `sample.cpp#L79` 打开代码，在代码里按 Ctrl+Alt+←（Cursor 的 Go Back）回到预览，再在预览里按 Ctrl+Alt+← 或点 ↩ Back，都回到 1000，和改前一样。`accept.mjs` 加了第 16 项：other.md → anchors.md，anchors.md 关着时按 Ctrl+Alt+←，开着被盖住时点 ↩ Back，都回到 other.md；旧的 `preview.js` 上第 16 项不过（anchors.md 没有 ↩ Back）。

### 18 日志里的颜色码显示成乱码

Peter 10-22："why are so many garbled text in the run log? how to eliminate them in display"。utopx 打的日志带 ANSI 颜色码（文件名那一列前面是 `ESC[34m`，行尾 `ESC[0m`），per_run 把输出原样存进 `.log`，编辑器里就显示成 `[34m…[0m`；Run log #1 的日志 5440 行里有 3895 行带。Peter 要只改显示、不动文件，像 vim 的 AnsiEsc.vim 那样。

试过的两个扩展（都从 Open VSX 下载，看了清单和代码）：

| 扩展 | 编辑器里的控制码 | 选哪些文件 | 结论 |
|---|---|---|---|
| `iliazeus.vscode-ansi` 1.1.7 | 写死成 50% 透明，不能隐藏；去掉控制码的只有另开的只读预览 | 语言模式要设成 `ANSI Text` | 不用 |
| `Tobias-Faller.vt100-syntax-highlighting` 1.1.0 | 样式由设置 `vt100.escape-sequence` 给，`text-decoration` 里带上 `display: none` 就不显示 | `vt100.decorate-includes` 按语言 ID 匹配的正则，`.log` 的语言 ID 是 `log`，不用改语言模式 | 用 |

它在 workspace 一侧运行，装在服务器上：`"$(ls -td ~/.cursor-server/bin/linux-x64/*/ | head -1)bin/cursor-server" --install-extension <vsix>`。设置写在远程设置里（`remote.settings.json`）。控制码只是不显示，还在文件里，所以行号、`#L` 链接都不变；复制选中的文字时会带上它们。`.out` 文件的语言 ID 是 `plaintext`，没有包括进来。

证据（隔离的 Cursor 3.26.13）：打开 Run log #1 日志的副本，语言模式仍是 Log，控制码不显示，文件名那列显示成蓝色、第 1 行绿色（截图在会话的 scratchpad，没留）。

10-22 晚上 Peter："打开log，过了一会确实渲染颜色出来了，但是从别的tab再返回到这个log，它又会恢复原样再重新渲染一次"。根因（读了扩展的代码，在服务器上用它自己的代码量过）：颜色是挂在编辑器上的装饰，tab 切回来是一个新的编辑器，要重新给；这个扩展在每次可见编辑器变化时把整篇重新解析一遍（`out/decorationManager.js` 第 18～20 行），不缓存，也没有防抖、缓存一类的设置。一篇 5762 行、834 KB 的日志算出 2.6 万个区间，约 400 KiB，要从服务器上的扩展宿主发到 Mac 再画；解析加打包在服务器上约 0.1 s，Peter 的连接往返约 420 ms，整个估计 1～3.5 s（按测到的往返时间和 TCP 窗口估算，没在 Mac 上量）。办法有两个，待 Peter 定：让它在 Mac 本地的扩展宿主里跑（Mac 上装一份，用户设置加 `"remote.extensionKind": {"tobias-faller.vt100-syntax-highlighting": ["ui"]}`），估计切回只露约 0.1 s；或者给它加缓存、先画看得见的那一屏（它是 MIT 许可，可以改）。Peter 10-22 晚上定："if too complex, uninstall it permanently"。两个办法一个要在 Mac 上手动装、改设置，一个要长期维护第三方扩展的补丁，20:47 从服务器卸掉，`remote.settings.json` 里的两项设置一起删了；`.log` 里的控制码又照原样显示。

### 19 跨文件的锚点链接只打开、不滚动

10-22 在隔离的 Cursor 3.26.13 里测：从另一个 md 点 `anchors.md#run-25` 或 `anchors.md#run-log`（标题锚点也一样），只是打开或切到 `anchors.md` 的预览，停在它上次的位置，不滚到锚点；同一个文件里的 `#run-25` 能跳（第 17 项）。Page_Supplier 的文档里跨文件的 `Ledger.md#run-N` 只打开 Ledger。

原因（读 3.24.18 服务器上 Markdown 扩展的代码，下面的对照证实）：语言服务能把标题锚点和 `<a id>` 都解析成目标文件的行号；`openMarkdownLinks: inEditor` 下，打开链接的代码只把这个行号作为 `selection` 交给 `vscode.open`，预览这个 custom editor 不认 `selection`，锚点就丢了。

修法（10-22 晚上 Peter 定修）：服务器补丁第 6～8 处。预览管理器里有个按行号滚动预览的监视器（编辑器滚动时预览跟着滚就靠它）：第 6 处把它交给打开链接的代码；第 7 处在打开之前记下锚点的行，新开的预览从这一行开始；第 8 处在 `vscode.open` 之后让已经开着的预览原地滚到这一行，不重新渲染。行号是第 4 处填上的 `position`。

中文标题的锚点：预览给标题的 id 是 `encodeURI` 过的 slug（`### 10.117 teardown 修复上机` 的 id 是 `10117-teardown-%E4%BF%AE%E5%A4%8D%E4%B8%8A%E6%9C%BA`），渲染时链接里的中文也被编成 `%E…`，所以链接写原样的中文还是写百分号编码，到扩展这里是同一个链接。跨文件时语言服务先解码，再按它自己的 slug 规则（不编码）找标题；同一页里由外壳按 id 找元素。两种写法都落在标题上。

证据（隔离的 Cursor 3.26.13，调试协议的真鼠标点击；前两行是 `accept.mjs` 第 15 项，后两行是 scratch 里照 Page_Supplier 写的 Tracking.md、Ledger.md）：

| 链接 | 目标关着：新开的 tab | 目标开着、被盖住：切过去 |
|---|---|---|
| `anchors.md#run-25`（表格行里的 `<a id>`） | 锚点在顶上 10 px | 同一页（没重建）滚到 10 px |
| `anchors.md#run-log`（标题） | 0～1 px | 同一页滚到 0 px |
| `Ledger.md#10128-拿回-012mars-在-012-上的回归全挂`，标题是 `### 10.128 拿回 012,MARS 在 012 上的回归全挂` | -1 px | 同一页滚到 0 px |
| 同上，写成百分号编码 `Ledger.md#10128-%E6%8B%BF%E5%9B%9E-…` | 0 px | 同一页滚到 0 px |

同一页的 `[§10.117](#10117-teardown-修复上机)`：普通点和按着 Meta 点都跳到 0 px，出现 ↩ Back，Ctrl+Alt+- 或 ↩ Back 回到原处。对照：同一个 Cursor 撤掉第 5～8 处，上表八次点击都停在页首（scrollY 0），锚点在下面 9356～30663 px。3.24.18 服务器上的语言服务（`dist/serverWorkerMain.js`）和预览页的脚本（`media/index.js`）与 3.26.13 的逐字节相同。

### 20 代码块没有一键复制

Peter 10-22："md里显示的diff右上角为什么没有一键拷贝的按钮"。修法：`preview.js` 给每个代码块（diff、bash、text 等）加一个 Copy 按钮，鼠标移到代码块上时在右上角出现，键盘 Tab 也能到。点一下复制 `code` 的文字：diff 带 `+` / `-`，去掉最后一行后面的换行，粘贴出来的命令不会自己执行；先用 `navigator.clipboard.writeText`，被拒时退回到临时的 textarea 加 `document.execCommand('copy')`；按钮显示 Copied 或 Copy failed 1.5 秒。按钮上的字由 `preview.css` 按 `data-state` 画出来，页面里没有这段文字，页内搜索和选中复制都碰不到它。

按钮放在代码块前面一个高度为 0 的 `<mpp-copy>` 里，不放进 `pre`：预览更新内容时逐块比较新旧，`pre` 里多了一个按钮就永远比不上，代码块的 `data-line` 不再更新，而预览跟着编辑器滚动、Cmd+双击开源码都按这个行号走。放进 `pre` 时实测改文件以后第一个代码块的 `data-line` 成了 67、105，应为 31、29。`<mpp-copy>` 每次更新被丢掉，`build()` 再加回来；`OWN` 里加了 `mpp-copy` 和 `#mpp-copy-text`。留下一点：列表项或引用块里有代码块时，同一块里别的元素在更新后 `data-line` 不刷新，代码块自己是对的；写 md 的规矩本来就不把代码块放进列表。

剪贴板：3.26.13 的 webview 外壳页给内层 iframe 写了 `allow="cross-origin-isolated; autoplay; clipboard-read; clipboard-write;"`。Mac 上 3.24.18 的外壳页服务器上没有，没看到；`writeText` 被拒时走 textarea 那条路。

证据（隔离的 Cursor 3.26.13）：0.2.4 上 `accept.mjs` 第 13 项不过（没有按钮）；改后亮、暗两种主题都过：点 diff 代码块的按钮，剪贴板是文件里那一块的 6 行，按钮显示 Copied，2 秒后回到 Copy；`writeText` 被拒时 textarea 那条路也复制对；改文件以后 85 个按钮都在，`data-line` 29 → 31 → 29，和 0.2.4 一样；`covered_update.mjs`、`flash.mjs` 和以前一样。

### 21 源码行链接会漂移

文档里引用源码的行，写的是指向 worktree 的相对链接，比如 `[VHCA.cpp:5149](../../utopx-psf/src/hca/VHCA.cpp#L5149)`。worktree 换到别的 commit，或者有了改动，第 5149 行就成了别的代码；链接照样打开，指错了也看不出来。

Peter 10-22 晚上定：链接带上行号所指的 commit；点开时仍然打开 worktree 里的文件，但停在这几行现在所在的行；开在当前编辑组，不要 beside。当晚又定（"改"）：这几行改了、删了也打开 worktree 里真的文件，停在现在顶替它们的行；那个 commit 时的只读副本只在他要看时才开（点通知上的按钮）。

写法：`[VHCA.cpp:5149](../../utopx-psf/src/hca/VHCA.cpp?v=6faa4de858#L5149)`，`?v=` 后面是 7～40 位的 commit；一段行写 `#L5149-L5160`。不带 `?v=` 的链接、md 链接、网页链接都和以前一样。

点开时（[extension.js](../assets/cursor/md-preview-plus/extension.js) 的 `openLink`，换算在 [line_map.js](../assets/cursor/md-preview-plus/line_map.js)）：
- 在文件所在的目录（目录也没了就往上找还在的）用 `git rev-parse` 认 commit，再跑 `git diff --no-color --no-ext-diff -U0 <commit> -- <文件>`：commit 对 worktree，没提交的改动也算。按每个 hunk 的 `@@ -a,b +c,d @@` 换算：整个在引用的行前面的 hunk，行号加 d - b；改了、删了引用的行，或者在一段行中间插了行，就是"变了"，这时取顶替它们的行：hunk 拿掉的行由它的新行 c～c+d-1 顶替，d 为 0（只删不加）就取删掉的地方后面那一行 c+1。一段行的头和尾各算各的：没被拿掉就是它现在的行；被拿掉了，头取那个 hunk 的第一个新行，尾取最后一个新行。
- 没变：在当前编辑组用普通的文本编辑器打开 worktree 的文件，光标在这一行的行首，一段行就选中这几行；行号变了，状态栏显示 5 秒 `VHCA.cpp:5149 at 6faa4de858 is line 5161 now`。文件已经在别的编辑组开着时也开在当前组（自带的 `#L` 链接会去那个组）。
- 变了：同样打开 worktree 的文件，选中顶替它们的行，弹通知 `VHCA.cpp:5139 changed after 36823bfb33; these are the lines that replaced it in the worktree.`；全删了、没有行顶替时，光标停在删掉的地方后面那一行，通知是 `… was deleted after …; the cursor is where it was in the worktree.`。通知上有按钮 `Show as of 36823bfb33`，点了打开那个 commit 时的文件，只读，停在引用的行号：内容来自 `git show <commit>:<路径>`，URI 是 `mpp-commit:<文件的绝对路径>?<commit>`，所以语言模式照样按扩展名认。
- 文件不在 worktree 里了：没有别的可开，直接打开那个 commit 时的文件，停在引用的行号，弹通知 `VHCA.cpp:5149 is not in the worktree as it was at 6faa4de858: this is the file as of that commit, read-only.`。
- 仓库里没有这个 commit，或者这个 commit 里没有这个文件（commit 之后才加进来的；文件不在 git 仓库里也一样）：打开 worktree 的文件，停在引用的行号，弹警告 `md-preview-plus: VHCA.cpp is not in commit … of its repository, so … is opened in the file as it is now, where it may be other code.`

接线：服务器补丁第 5 处让预览把每个被点的链接先交给命令 `mdPreviewPlus.openLink`，它只认上面这种写法，打开了返回 true，其余返回 false；返回 false、出错、本扩展没在跑，都照原来的走。原来的路上，语言服务解析链接时丢掉 `?` 后面的部分，打开 worktree 的文件，停在 `#L` 的行号。右键 Copy Link Address 也带上 `?v=`（`preview.js` 的 `linkAddress()` 原来只取路径和 `#` 后面的部分）。

证据：
- 单元测试：在 scratch 里建临时 git 仓库测 `line_map.js`，38 个用例全过：上面插行、删行，紧挨着插，上一行改了，没提交的改动，worktree 换到后面的 commit 再加没提交的改动；引用的行改了、换成 2 行（上面另加 5 行）、删了（上面另删 3 行）、第 1 行删了；一段行（中间插行、里面改、头一行删了、最后一行换成 3 行、最后 3 行删了、上面来的 hunk 拿掉头 2 行、全删、全换成 2 行、紧挨着前后改）；文件删了，目录删了，commit 不存在，不在 git 仓库里，commit 之后才加的文件，没跟踪的文件。
- 隔离的 Cursor 3.26.13，用调试协议的真鼠标点击 scratch 里的 vtest.md，链接都带第一个 commit `314a1ceb04`；都开在当前编辑组，tab 数加 1；通知上的按钮在通知中心里点：

| 情况 | 打开的 | 状态栏、通知 |
|---|---|---|
| 没变 | worktree 的文件，`Ln 30, Col 1` | 没有 |
| 上面加了 5 行，没提交 | worktree，`Ln 35`，就是引用的那行代码 | `moved.cpp:30 at 314a1ceb04 is line 35 now` |
| 后一个 commit 在上面加了 4 行 | worktree，`Ln 34` | `later.cpp:30 at 314a1ceb04 is line 34 now` |
| 引用的行改了 | worktree，选中顶替它的第 30 行（`Ln 30, Col 47 (46 selected)`，是改过的代码）；点按钮 `Show as of 314a1ceb04`，commit 时的文件另开一个 tab，`Ln 30` 是改之前的那行 | 通知 `edited.cpp:30 changed after 314a1ceb04; these are the lines that replaced it in the worktree.` |
| 引用的行删了 | worktree，光标在 `Ln 30, Col 1`，是原来的第 31 行；按钮打开 commit 时的文件，`Ln 30` 是删掉的那行 | 通知 `deleted.cpp:30 was deleted after 314a1ceb04; the cursor is where it was in the worktree.` |
| `#L28-L32`，上面加了 2 行 | worktree，选中 30～34 行 | `range.cpp:28-32 at 314a1ceb04 is lines 30-34 now` |
| `#L28-L32`，第 30 行换成了 2 行 | worktree，选中 28～33 行；按钮打开 commit 时的文件，选中 28～32 行 | 通知 `rangechg.cpp:28-32 changed after 314a1ceb04; these are the lines that replaced them in the worktree.` |
| 文件删了 | commit 时的文件，`Ln 30` | 通知 `gone.cpp:30 is not in the worktree as it was at 314a1ceb04: …` |
| commit 不在仓库里 | worktree，`Ln 30` | 警告 `md-preview-plus: same.cpp is not in commit 0123456789 of its repository, …` |
| 按着 Meta 点，上面加了 2 行 | worktree，`Ln 32` | `cmd.cpp:30 at 314a1ceb04 is line 32 now` |
| 普通的 `sample.cpp#L79` | `Ln 79`，和以前一样 | 没有 |
| md 链接 | 新 tab，和以前一样 | 没有 |

- 真文件：utopx-psf 的 `VHCA.cpp` 对 commit `36823bfb33`，带没提交的改动。23:03 之前 hunk 是 `-2479,0 +2480,3`、`-2493,0 +2497,7`、`-5139 +5149`，`line_map.js` 算出 L5149 → 5159 没变、L5139 → 5149 变了。23:03 这个文件又被改过，第三个 hunk 成了 `-5099 +5109`：在隔离的 Cursor 里点 `#L5149` 停在 5159，状态栏 `VHCA.cpp:5149 at 36823bfb33 is line 5159 now`；点 `#L5099` 选中 worktree 的第 5109 行（新代码 `{return (IsPsf() && IsIcmMngGlobalEnabled()) ? …}`），通知带 `Show as of 36823bfb33`，点了打开 commit 时的文件，停在 5099（旧代码 `{return HCA_STAGE_RECLAIM_PAGES_REGULAR;}`）。只是打开，文件没动。
- commit 时的文件是只读的：打字改不动，同一个键在 worktree 的文件里改得动（撤回了，没存；上一版测的，这个视图没改）。隔离的 3.26.13 不弹通知气泡，通知只进右下角的通知中心。在 `?v=` 链接上右键点 Copy Link Address，复制出 `…/ws/repo/pinned.cpp?v=f547e22326#L20`。对照：同一个 Cursor 撤掉第 5～8 处，"上面加了 5 行"那个链接打开在第 30 行，那一行已经是 `// moved line 25`。`accept.mjs` 第 14 项查行号变了和行改了两种，行改了的那种连按钮一起查。
- 没在 Peter 的环境里试：第 5 处在 3.24.18（be4c9e53）的原版和现在打了 4 处的文件上都正好匹配一次，打、重打、撤都对；预览页脚本和语言服务与 3.26.13 逐字节相同，点链接的那段代码只差压缩后的变量名。隔离的是本地窗口，Peter 用 Remote-SSH 窗口：`mpp-commit:` 的内容和 git 都在服务器上的扩展宿主里，远程窗口里没试过；Mac 上的通知弹不弹气泡没看到。


10-22 晚上 Peter 又定：代码行只链本地 worktree，不链 gerrit 文件页和 gitiles。skill `markdown-docs` 照此改了；PSF 的 Ledger、Tracking、Defects 和 10-22 的报告 22:03 改写了 201 处代码行链接，每处的 commit 取自链接本身（patchset 的 revision、gitiles 的 commit 或 tag）或条目写的那棵树当时的 HEAD。被钉住的 commit 多数只挂在 reflog 上或什么都没挂，`git gc` 以后可能被清掉，那时链接退回按原行号打开现在的文件并弹警告；Peter 定给它们建引用：10-22 22:38 在 utopx、golan_fw 和 hca_fwv_shared 里给链接钉住的 21 个 commit 各建了一个 `refs/keep/psf/<10 位 SHA>`（只有它们用到的对象约 32 MiB，本来就在磁盘上）；skill `markdown-docs` 也规定以后钉一个 commit 就在同一步建引用。
## 6. 安装、升级、重装

步骤在 [README.md](../assets/cursor/md-preview-plus/README.md) 的"安装""升级、重装以后""只改了样式或预览页脚本"几节。要点：

| 情况 | 要做的 |
|---|---|
| Cursor 升级，或者卸载后重装 | 可能同时弹 Reload Window（服务器补丁）和 Quit Cursor（client）。点 Quit Cursor，再打开，两边都生效 |
| Mac 上连 `~/.cursor` 一起删了 | 同上；连上服务器后 md-preview-plus 先把 client 装回来 |
| 服务器上 `~/.cursor-server` 被清掉，或换了服务器 | `bash ~/myGit/crosslv/assets/cursor/md-preview-plus/build_vsix.sh`，再 Reload Window。它装扩展，并把装好的 `preview.css` 和远程设置链回 crosslv |
| 弹 `not found …` 警告 | 新版 Cursor 改了补丁对应的代码，对应的修复先失效；括号里是 `EACCES`、`EPERM` 的话是没权限。按 §7.5 改 |

## 7. 怎么查

### 7.1 Mac 那一侧

服务器上的 agent 连不到 Mac，只能请 Peter 自己查，或者请他转给 Mac 上的 agent。给 Mac 的长文本别从终端复制：同时给文件路径让他在 Cursor 里打开复制，并给关键段的 sha256 让对方核对（10-19 从终端复制的说明到了 Mac 少了两段）。

| 查什么 | 怎么查 | 正常 |
|---|---|---|
| Cursor 版本 | Cursor 菜单 → About Cursor | 和服务器上 `<commit>` 目录一致 |
| client 装没装 | 扩展列表搜 Markdown Preview Plus，或 `ls ~/.cursor/extensions \| grep md-preview-plus-client` | 作者 markdown-preview-plus 的 client 一个，版本等于 `client/package.json` 的 |
| Cursor 应用补丁在不在 | `grep -c 'reapplyLayoutStyles(),this._overlayLayout' /Applications/Cursor.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js` | 1 |
| 没权限改 app 包 | client 弹 `… not found in this Cursor, so not patched: all of it (EPERM …)`，macOS 可能另弹"已阻止修改 App" | 系统设置 → 隐私与安全性 → App 管理，给 Cursor 打开，再退出重开 |

日志在 `~/Library/Application Support/Cursor/logs/<时间>/window1/`（按 Linux 版的布局推断，没在 Mac 上看过）：`exthost/exthost.log` 里有 client 每次的激活，`renderer.log` 里有 `Installation has been modified on disk`。警告只以通知弹出（右下角铃铛），不进日志。

### 7.2 服务器那一侧

补丁不打日志，数插进去的字符串出现几次。文件是压缩过的，几处补丁在同一行，要用 `grep -oF '<字符串>' <文件> | wc -l`；`grep -c` 数的是行，会把第 1、2 处数成 1。

| 补丁 | 字符串 | 次数 |
|---|---|---|
| 第 1、2 处 | `,retainContextWhenHidden:!0` | 2 |
| 第 3 处 | `&&!this._webviewPanel.options?.retainContextWhenHidden` | 1 |
| 第 4 处 | `.position??=` | 1 |
| 第 5 处 | `executeCommand("mdPreviewPlus.openLink"` | 1 |
| 第 6 处 | `this._opener._topmostLineMonitor=` | 1 |
| 第 7 处 | `setPreviousStaticEditorLine({uri:` | 1 |
| 第 8 处 | `_topmostLineMonitor?.updateLine(` | 1 |

扩展日志在 `~/.cursor-server/data/logs/*/exthost*/remoteexthost.log`，grep `md-preview-plus` 能看到每次激活的时间。

### 7.3 验收

改了代码、升级了 Cursor、或者 Peter 说某项坏了，按这张表逐项查。在隔离的 Cursor 里（§8）：第 1～7、13～16 行用 `tools/accept.mjs`，第 8 行用 `covered_update.mjs`，第 9、10 行用 `flash.mjs`，第 11 行照 §8 的"模拟升级"走。在 Peter 的窗口里只能请他照"怎么查"手动看。

| # | 功能 | 怎么查 | 通过 |
|---|---|---|---|
| 1 | md 用预览打开 | 资源管理器里单击一个 `.md` | tab 标题就是 `xxx.md`，内容是渲染后的，不是 `Preview xxx.md`，也不是源码 |
| 2 | 目录和返回 | 点 ☰，点目录里一项，按 Go Back 键（Mac ⌃-，Linux Ctrl+Alt+-）；按着 Cmd 再点一次，点 ↩ Back；再点一次，按 ⌃⌥←（Linux Ctrl+Alt+←）；拖侧栏右边缘；看长标题 | 侧栏开合；正文跳到那一节，右下角出现 ↩ Back；Go Back 回到点击前的位置；按着 Cmd 点也出现 ↩ Back，点它回到原处；⌃⌥← 也回到点击前的位置；宽度跟着变，重开后还在；长标题折成几行，没有截成"…"的 |
| 3 | 页内搜索 | 预览里 Cmd+F，输入一个词，Enter、↑、Aa、ab、Esc | 右上角出现搜索框和 `n of m`，Enter 跳下一处，↑ 翻出搜过的词，开关生效，Esc 关闭；Cursor 自己的查找框不出现 |
| 4 | 链接 | 点预览里指向另一个 `.md` 的链接；在这个链接上右键，点 Copy Link Address；在侧边栏的一项上右键，点 Copy Link Address；在正文上右键 | 新开一个 tab，当前 tab 还在；链接上的菜单是 Copy Link Address、Copy Link Text，复制出那个文件的绝对路径；目录项上的菜单也是这两项，复制出本文件的绝对路径加 `#<标题的 id>`；正文上的菜单仍是 Cut / Copy / Paste |
| 5 | 切换按钮和快捷键 | 看预览标题栏有没有 Markdown 按钮；打开源码看有没有 Preview 按钮，按 Cmd+Shift+V | 两个按钮都在，同一个 tab 原地换成预览。Peter 的 3.24.18 上通过，隔离的 3.25.9 上不过（第 14 项） |
| 6 | 双击 | 在预览里双击、Cmd+双击 | 双击不跳；Cmd+双击打开源码 |
| 7 | 样式 | 看 diff 代码块和第一列是 change 号的表 | diff 增删行暗色主题 `#b5cea8`、`#ce9178`，浅色 `#098658`、`#a31515`，没有行底色；change 号一行显示 |
| 8 | 被盖住不重建 | 长文档滚到中间，点代码链接，再点回预览；被盖住时改文件用 `covered_update.mjs` | 立即回到原位置，没有白屏；脚本输出 `rebuilt false`、`updated true`，前后滚动值相同 |
| 9 | 切回不闪 | 同上，看切回的那一下；或 `flash.mjs` + `analyze.py` | 没有一帧空白；`page log` 里没有 `resize … 300 150` |
| 10 | `#L` 跳行 | 点 `[x](file#L79)` 这种链接 | 光标停在第 79 行（状态栏 `Ln 79`） |
| 11 | 升级后恢复 | Cursor 升级重启后 | 弹 Quit Cursor（可能还有 Reload Window）；点它再打开后没有提示、没有"已损坏"，再查 1～10 |
| 12 | 日志颜色 | 10-22 卸掉了 VT100（第 18 项），不再查 | — |
| 13 | 代码块复制 | 鼠标移到一个 diff 代码块上，点右上角的 Copy，再粘贴 | 按钮出现，显示 Copied，1.5 秒后回到 Copy；粘贴出来的是那一块的代码，带 `+` / `-` |
| 14 | 带 commit 的源码行链接 | 点一个 `[x](file?v=<commit>#L20)` 链接，这一行在那个 commit 之后被上面加的行挤到了第 23 行；再点一个之后被改了的第 40 行 | 前一个打开 worktree 的文件，状态栏 `Ln 23`，另显示 `… is line 23 now`；后一个也打开 worktree 的文件，选中顶替它的第 43 行，有通知 `… changed after …; these are the lines that replaced it in the worktree.`，通知上的按钮 Show as of 打开那个 commit 时的文件，`Ln 40` 是改之前的那行，只读 |
| 15 | 别的 md 里的锚点 | 从另一个 md 点 `xxx.md#锚点`（标题，和表格里的 `<a id>`），一次在目标关着时点，一次在它开着、被盖住时点 | 关着：新开 tab，锚点在顶上；开着：切过去，原地滚到锚点，不重新渲染 |
| 16 | 退回别的 md | 在一个 md 里点指向另一个 md 的链接（目标关着、开着被盖住各一次），在目标页按 Go Back 键（⌃⌥←，Linux Ctrl+Alt+←）或点 ↩ Back | 目标页出现 ↩ Back；按键或点按钮回到原来那个 md 的 tab，停在点链接的地方 |

### 7.4 Peter 说"切回又闪了"

1. Cursor 是不是升级了；升级后有没有点 Quit Cursor 退出重开过。
2. 通知中心（右下角铃铛）里有没有 `not found in this Cursor` 或 `not found in this Markdown preview` 的警告：括号里是 `EPERM`、`EACCES` 就是没权限，否则是新版本改了代码（§7.5）。
3. Mac 上的 client 是不是现在的 ID 和版本，Cursor 应用补丁在不在（§7.1）。
4. 服务器上第 1、2 处补丁在不在（§7.2）：不在的话切回是整页重建，不是闪。
5. 是不是打补丁前开的 `Preview xxx.md` 面板：那种仍会重建，关掉重开就好。
6. 还不清楚，就在隔离的 Cursor 里用同版本复测（§8）。

### 7.5 新版 Cursor 补丁对不上

1. 拿新版本的文件：服务器那一半在 `~/.cursor-server/bin/linux-x64/<新 commit>/extensions/markdown-language-features/dist/extension.js`；Cursor 应用那一半要下载同版本的 Linux 安装包（§8），取 `usr/share/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js`。Cursor 只发当前稳定版，旧版本下载不到。
2. 拷一份副本，在副本上跑 `node preview_patch.js <目录副本>` 和 `node client/webview_patch.js <app 目录副本>`，看哪一处 `not found`。
3. 到新代码里找那一处。有的词不止一处：`this._overlayLayout.content.style.visibility="hidden"` 有两处，一处在 `get overlayLayout()` 里、一处在 `release(` 里，补丁在后者；`resolveLinkTarget(` 有三处，补丁在 `let <变量>=await this._client.resolveLinkTarget(…);` 那一处。其余的词：`registerCustomEditorProvider(`、`createWebviewPanel(`、`!this._webviewPanel.visible`、`this._overlayLayout.content.style.visibility="visible"`，以及新代码要调用的 `reapplyLayoutStyles(){`、`this._anchorState={anchorElement:`。
4. 改 `preview_patch.js` 的 `SITES` 正则或 `client/webview_patch.js` 的 `SITES` 原文，在副本上确认打、重打、`--revert` 都对；在隔离的 Cursor 里按 §7.3 测。
5. 改了 client 就升它的 version；`build_vsix.sh`；Peter Reload Window，再按升级流程退出重开。

## 8. 怎么测

在隔离的 Cursor 里测，不碰自己的 `~/.cursor`、`~/.cursor-server`。要在 Linux 机器上（m-fwdev-167 就行），有 TigerVNC 的 `Xvnc`，`xauth`、`mcookie`、`xdpyinfo`，`curl`、`ar`、带 xz 的 `tar`，Node 22 以上（全局的 `fetch`、`WebSocket`），以及带 numpy 和 PIL 的 python3：m-fwdev-167 上用 `/usr/bin/python3`，PATH 上排第一的 `~/.usr/bin/python3` 没有 numpy。

`tools/` 里：`start.sh` 起一个私有 Xvnc 上的 Cursor（HOME、user-data、extensions 都在测试目录里，调试端口 9339；`--ozone-platform=headless` 在 GTK 里段错误，所以用 Xvnc，它的 VNC 只开 0600 的 unix socket）；`open.sh` 在里面打开文件（启动时传进去的 md 会被 Cursor 自带的 md 视图接走，要等窗口出来再开）；`make_sample.py` 生成固定的测试工作区；`accept.mjs`、`covered_update.mjs`、`flash.mjs` + `analyze.py` 是检查；`cdp.mjs` 是调试协议客户端和公共步骤，每个检查开始时自动藏起 Cursor 的登录层、关掉右边的 Agents 面板（它把预览挤到不到 500 像素宽，点不中链接）。测试文档第 43 节的标题故意写得很长，测目录折行；`accept.mjs` 读剪贴板之前用调试协议的 `Browser.grantPermissions` 给 workbench 开读剪贴板的权限，不然 `navigator.clipboard.readText()` 报 Read permission denied。

**搭环境、测一遍**：

```bash
T=~/myGit/crosslv/assets/cursor/md-preview-plus/tools
W=<scratch dir>; mkdir -p $W/pkg $W/app
curl -sL 'https://www.cursor.com/api/download?platform=linux-x64&releaseTrack=stable'   # JSON 里的 debUrl、version、commitSha
curl -sL -o $W/pkg/cursor.deb '<debUrl>'
(cd $W/app && ar p ../pkg/cursor.deb data.tar.xz | tar -xJf -)
C=$W/app/usr/share/cursor
bash $T/../build_vsix.sh --vsix $W/plus.vsix
HOME=$W/work/home $C/bin/cursor --user-data-dir=$W/work/user-data --extensions-dir=$W/work/extensions --install-extension $W/plus.vsix
/usr/bin/python3 $T/make_sample.py $W/ws                 # long.md（552 KB，第 42 节有指向 src/sample.cpp#L79 和 other.md 的链接）；other.md 里有带 commit 的源码行链接（git 仓库 repo/）和指向 anchors.md 锚点的链接
bash $T/start.sh $C $W/work $W/ws                         # 放到后台
node $T/center.mjs 5                                      # 一直等到窗口出来，再打印通知中心
bash $T/open.sh $C $W/work $W/ws/long.md
node $T/accept.mjs                                        # §7.3 第 1～7、13～16 行
node $T/covered_update.mjs $W/ws/long.md 'sample.cpp#L79' # 第 8 行
node $T/flash.mjs $W/out 'sample.cpp#L79'                 # 第 9、10 行
/usr/bin/python3 $T/analyze.py $W/out
```

**原版、补丁版、模拟升级**。这个 Cursor 里也装着 md-preview-plus，它一启动就把 client 装上，client 又立刻给 `$C` 打补丁，但当次窗口已经加载了原版代码，下次启动才用上补丁。服务器那一半的补丁在这里打在 `$C/resources/app/extensions/markdown-language-features/dist/extension.js`。

```bash
pkill -f "$C/cursor"; sleep 5; pkill -9 -f "$C/cursor"          # 停；上一个没退干净时它占着 9339 端口，start.sh 会拒绝启动
# 测补丁版：停掉以后重新 start.sh、center.mjs、open.sh，再测（要退出重开，不要 reload）
# 测原版：停掉，撤掉 Cursor 应用的补丁，再启动，在这第一次启动里测
node $T/../client/webview_patch.js --revert $C/resources/app
# 模拟升级后第一次启动（§7.3 第 11 行）：停掉，两边都撤掉，再启动
node $T/../client/webview_patch.js --revert $C/resources/app
node $T/../preview_patch.js --revert $C/resources/app/extensions/markdown-language-features
bash $T/start.sh $C $W/work $W/ws                               # 放到后台
node $T/center.mjs 15                                           # 应有 Quit Cursor；预览 tab 是恢复出来的话还有 Reload Window
grep -c 'modified on disk' $(ls -td $W/work/user-data/logs/*/ | head -1)window1/renderer.log   # 应为 0
# 再停掉、启动：center.mjs 应为空，accept.mjs、flash.mjs 和平时一样
```

- `analyze.py` 每帧一行，`background_share` 接近 1 的是空白帧；`page log` 里有 `resize … 300 150` 就是闪了；`cursor after the link` 是 §7.3 第 10 行的结果。
- 测试用的设置由 `start.sh` 写进 `$W/work/user-data/User/settings.json`，和 Peter 的一致（含 `workbench.editor.enablePreview: false`；不加的话 md 链接开在斜体的预览 tab 里）。
- `start.sh` 会恢复上次留下的 tab，`accept.mjs` 假定只开着 `long.md`：跑之前先把别的 tab 关掉，否则第 4 项会因为目标文件已经开着、不新开 tab 而不过。
- 隔离的 3.26.13 不弹通知气泡，通知只进右下角的通知中心（铃铛 `#status.notifications`）；`accept.mjs` 第 14 项点铃铛打开它读，读完关上。通知中心开着时盖住预览右下角的 ↩ Back，点不到。
- 测试 HOME 的 `argv.json`（`$W/work/home/.cursor/argv.json`）要有 `"password-store": "basic"`：这个 X server 里没有 OS keyring，Cursor 会弹原生对话框"An OS keyring couldn't be identified…"，它占着窗口焦点，调试协议发的键全丢。
- 点完一个 md 里指向另一个 md 的链接，测试的窗口里没有 frame 有焦点：先在目标页的正文上点一下（别点到链接上），键才进页面。要看 Cursor 自己的 Go Back，在测试的 `User/keybindings.json` 里加 Peter 的那两条键位；`accept.mjs` 不靠它（`preview.js` 自己认 Ctrl+Alt+←）。

测过的结果（新的在上）：

| 时间 | 测什么 | 结果 |
|---|---|---|
| 10-22 23:52～23:56 | 退回别的 md 的记录一小时后作废（第 17 项）：A → B 的六种情况；一条时间改到 61 分钟以前的记录；一条再过 5 秒就满一小时的记录；`accept.mjs`；`covered_update.mjs` | 六种都对；61 分钟的记录不算（B 没有 ↩ Back，键交给 Cursor），下次写记录时被删掉；快到期的那条 ↩ Back 到期后自己藏起来；`accept.mjs` 1～4、6、7、13～16 通过，5 不过（第 14 项）；不重建、位置不变 |
| 10-22 23:18～23:47 | 退回别的 md（第 17 项）：先查 Cursor 自己的 Go Back（测试环境加了 Peter 的两条键位）；改后逐个测 A → B 的六种情况，旧的 `preview.js` 各跑一次对照；已有功能：`accept.mjs`（加了第 16 项，旧的 `preview.js` 上也跑一次）、`covered_update.mjs`、`flash.mjs`、页内回退 18 种、点代码链接再用 Cursor 的 Go Back 回来以后的页内回退 | 改后六种都对，旧的五种不对、一种一样（第 17 项的表）；`accept.mjs` 1～4、6、7、13～16 通过，5 不过（第 14 项），旧的 `preview.js` 上 16 不过；不重建、位置不变，切回不闪，`Ln 79, Col 1`；页内回退 18 种全过；代码链接那条改前改后都回到 1000 |
| 10-22 23:02～23:12 | 源码行链接变了也打开 worktree 的文件（第 21 项）：`line_map.js` 单元测试；utopx-psf 的 `VHCA.cpp` 真文件换算；隔离的 3.26.13 里逐个点 vtest.md 的 12 种链接，变了的三种点通知中心里的 Show as of 按钮；隔离的 Cursor 里点 `VHCA.cpp` 的两个链接；`accept.mjs`（第 14 项改了）；`covered_update.mjs` | 单元测试 38 个用例全过；`accept.mjs` 1～4、6、7、13～15 通过，5 不过（第 14 项）；不重建、位置不变；各种情况见第 21 项 |
| 10-22 21:51～21:59 | ⌃⌥← 返回（第 17 项）：`isBackKey` 和提示在 Mac、Linux、Windows 三种 `navigator.platform` 下改前改后各跑一次；隔离的 3.26.13 里 `anchors.md` 的专项测试（单击 `#run-25` 链接、目录项 Run log 以后按 Ctrl+Alt+← 或 Ctrl+Alt+-，没有可退的位置时按 Ctrl+Alt+←），旧的 `preview.js` 和改后各跑一次；`accept.mjs`（第 2 项加了 Ctrl+Alt+←）；`covered_update.mjs` | 改前三个平台都不认 Ctrl+Alt+←，改后都认，默认的键照旧；旧的 `preview.js` 上按 Ctrl+Alt+← 不回去，改后回到原处、键不交给 Cursor（第 17 项的表）；`accept.mjs` 第一次 4 不过：`start.sh` 打开的文件夹恢复了上次留下的 tab，other.md 已经开着，点链接只是切过去（tab 数 5 → 5）；关掉 long.md 以外的 tab 重跑，1～4、6、7、13～15 通过，5 不过（第 14 项），第 2 项点目录项 85136 → 140381，Ctrl+Alt+← 回到 85136；不重建、位置不变 |
| 10-22 20:42～21:16 | 源码行链接（第 21 项）、别的 md 里的锚点（第 19 项）、按着 Cmd 点以后的 ↩ Back（第 17 项）：`line_map.js` 单元测试；`preview_patch.js` 在 3.24.18（be4c9e53）和 3.26.13 各自的原版、打了 4 处的文件上打、重打、撤；隔离的 3.26.13 里逐个点 `?v=` 链接的各种情况、跨文件锚点（目标关着、开着被盖住）、中文标题的锚点、带修饰键的页内跳转；`accept.mjs`（加了第 14、15 项，第 2 项加了按着 Meta 点）；`covered_update.mjs`、`flash.mjs`；右键复制 `?v=` 链接；对照：撤掉第 5～8 处、换回旧的 `preview.js` | 单元测试 30 个用例全过；第 5～8 处在四个文件里都正好匹配一次，打、重打不变，撤销后和原版逐字节相同，`node --check` 过；`accept.mjs` 1～4、6、7、13～15 通过，5 不过（第 14 项）；不重建、位置不变，切回不闪，`Ln 79, Col 1`；各种情况和对照见第 17、19、21 项 |
| 10-22 19:54～20:17 | 0.2.5 的复制按钮（第 20 项）：`accept.mjs`（加了第 13 项）在 0.2.4 上跑一次，改后亮、暗主题各一次；`covered_update.mjs`、`flash.mjs`；改文件以后的按钮和 `data-line` | 0.2.4 上 13 不过（没有按钮）；改后 1～4、6、7、13 通过，5 不过（第 14 项）；不重建、位置不变，切回不闪，`Ln 79, Col 1`；改文件以后 85 个按钮都在，`data-line` 和 0.2.4 一样 |
| 10-22 14:28～14:32 | 0.2.4（返回，第 17 项）和 VT100（第 18 项）：返回的专项测试；`accept.mjs`（第 2 项加了返回）；`covered_update.mjs`、`flash.mjs`；打开带颜色码的日志截图 | 返回：链接和目录项跳转后 Go Back、↩ Back 都回到原位；`accept.mjs` 1～4、6、7 通过，5 不过（第 14 项）；不重建、位置不变，切回不闪，`Ln 79, Col 1`；日志控制码不显示、按颜色显示 |
| 10-22 00:40～00:46 | 隔离的 Cursor 换成当前稳定版 3.26.13；侧边栏目录项右键（第 16 项）改前改后：`accept.mjs`（第 4 项加查目录项）在 0.2.2 和 0.2.3 上各跑一次；`covered_update.mjs`、`flash.mjs` | 0.2.2 上 4 不过（目录项上是 Cut / Copy / Paste，什么也没复制）；0.2.3 上 1～4、6、7 通过，5 不过（第 14 项）；不重建、位置不变，切回不闪，`Ln 79, Col 1`；两组补丁在 3.26.13 上都打上了；`center.mjs` 在 3.26.13 上找不到铃铛图标，打不出通知 |
| 10-20 22:44～22:58 | 第 15、16 项改前改后；`accept.mjs`（加了这两项）在 0.2.1 和 0.2.2 上各跑一次；`covered_update.mjs`、`flash.mjs` | 0.2.1 上 2、4 不过（长标题一行、截掉 1 项；链接上的菜单是 Cut / Copy / Paste，什么也没复制）；0.2.2 上 1～4、6、7 通过，5 不过（第 14 项）；不重建、位置不变，切回不闪，`Ln 79, Col 1` |
| 10-19 23:55～10-20 00:05 | `accept.mjs`；模拟升级后第一次启动、退出重开 | 1～4、6、7 通过，5 不过（第 14 项）；第一次启动弹 Quit Cursor 和 Reload Window，没有"已损坏"；退出重开后没有提示，切回不重排 |
| 10-19 23:32～23:38 | 固定测试文档：切回、`#L79`、第 3 处补丁带对照、表格 | 原版 +1028 ms 空白帧，补丁版 +71 ms 正常；`Ln 79, Col 1`；第 3 处有效；change 号一行 |
| 10-19 21:44～21:54 | client 自动安装、升级后第一次启动、退出重开 | 自动装上并打补丁；只弹一条 Quit Cursor；重开后无提示 |
| 10-19 19:03～19:09 | 切回闪两下：原版、改 Cursor 应用、只改页面 | 见第 7 项的表 |

## 9. 改代码的规矩

- **先在隔离的 Cursor 里试**。`build_vsix.sh` 装进的是 Peter 正在用的 `~/.cursor-server`（所有 lab 机共用），装好的 `preview.css` 又是源码的软链接，改了立刻影响他。在隔离的 Cursor 里试：`build_vsix.sh --vsix $W/plus.vsix`，用 §8 那条 `--install-extension` 命令加 `--force` 装进测试目录，再退出重开；那里装的 `preview.css` 是普通文件，改了源码要重装。
- `preview.js` 里的 MutationObserver 必须跳过本扩展自己加的节点（`OWN` 列出的侧栏、☰、拖宽条、搜索框），否则自己改自己、每帧重建，症状像第 10 项。
- 键盘和双击要在 window 的 capture 阶段截，抢在预览自己的处理和 Cursor 之前。
- **改了 `client/` 必须升 `client/package.json` 的 version**（§4.2）。
- crosslv 的工作区常有别的会话暂存的改动：提交时用 `git commit -- <路径>`，别 `git add -A`。
- 改完按 §7.3 查一遍。

## 10. 经过

逐条的经过在两个会话的记录里：psf-sanity-baseline-test (506ffde3) 的 `~/.claude/projects/-auto-fwgwork1-pexiang-utopx-master/506ffde3-eb16-4a34-8fcb-ada6db7ef3cd.jsonl`，utopx-81 (5b4a60d7) 的 `~/.claude/projects/-auto-fwgwork1-pexiang-utopx/5b4a60d7-01be-419d-98d6-b1e1d0db4bff.jsonl`。

| 日期 | 进展 |
|---|---|
| 10-17 | Peter 发现 Page_Supplier 的 TRACKING.md "少了几章"；A/B 对照证实是 Cursor 自带 md 视图吞章节；又查出它会改写文件。试 MPE，嫌白闪、慢放弃；开始在自带预览上自建目录扩展 md-preview-toc |
| 10-18 | 目录侧栏、标题栏按钮、样式、diff 配色（试了五六版，定为编辑器的配色）、Cmd+双击、全宽和拖宽、页内搜索；md 默认用预览打开、md 链接开新 tab；改名 md-preview-plus；Peter 手动提交第一版 [0d7f44b](https://github.com/xiangp126/crosslv/commit/0d7f44b) |
| 10-19 | 上午：被盖住的 tab 不重建、`#L` 跳行、Cmd+Shift+V 原地换成预览；14:31 交给 utopx-81。下午：样式软链接、卸 MPE、表格列宽；查清切回闪两下的根因（第 7 项），Mac 上的 agent 打上补丁，Peter 21:25 确认不闪；client 自动安装、升级后自动恢复，push 到 [6b8971b](https://github.com/xiangp126/crosslv/commit/6b8971b)；作者改名；写交接文档，psf-sanity-baseline-test 审了两轮 |
| 10-20 | 验收脚本、照文档实测升级流程，发现第 14 项；按 Peter 的决定删 MPE 残留、删 `keepActivePreviewTab()`，文档合并成本文；Peter 删掉 Mac 上的 ctrl+alt+m，确认 Mac 上 client 已装、标题栏按钮和 Cmd+Shift+V 正常；Peter 定文档里的代码位置默认写成 `#L` 链接（skill `markdown-docs`） |
| 10-20 晚上 | Peter 报两个 bug：目录长标题只显示一行（第 15 项）、链接上右键的 Cut / Copy / Paste 没用（第 16 项）。在隔离的 Cursor 里复现、修好，验收脚本加了这两项，0.2.2 装到服务器 |
| 10-22 | Peter 确认正文链接上的右键菜单好了，报侧边栏的目录项上仍是 Cut / Copy / Paste（第 16 项）；在隔离的 Cursor 3.26.13 里复现、修好，验收脚本第 4 项加查目录项，0.2.3 装到服务器。下午按 Peter 的要求加了页内跳转后的返回（第 17 项），装了 VT100 扩展显示日志颜色（第 18 项），0.2.4 装到服务器；查出跨文件锚点不滚动（第 19 项） |
| 10-22 晚上 | Peter 把 md-preview-plus 的事交回 utopx-b3 (5b4a60d7)。加了代码块的复制按钮（第 20 项），0.2.5 20:26 装到服务器；查清 VT100 切回先露原样的根因（第 18 项）和跨文件锚点丢在哪里（第 19 项）；Peter 定源码行链接带 commit、点开时换算到 worktree 里现在的行（第 21 项），定修跨文件锚点（第 19 项）；Peter 报跳过去以后不出现 ↩ Back（第 17 项，原因是推断的）。三件都改好，加了服务器补丁第 5～8 处，21:16 在隔离的 3.26.13 里测完；0.2.6 21:19 装到服务器，补丁第 5～8 处 21:20 打上。VT100 按 Peter 的决定 20:47 卸掉；Peter 用 ⌃⌥← 后退回不去，查出是他的 keybindings.json 改了 Go Back 的键，0.2.7 22:04 装上；Peter 定代码行只链本地 worktree，skill `markdown-docs` 跟着改，PSF 文档的代码行链接 22:03 改成 `?v=` 写法；Peter 定 `?v=` 链接所引的行改过时也打开真实 worktree，跨文件跳过来以后能后退回原文件，0.2.8 23:57 装上 |

走过的弯路，以及下次该用的判据：

| 当时的判断 | 实际 | 判据 |
|---|---|---|
| 10-17 章节消失是因为成对的 `---` 被当成文件头；又认定格式化弄坏了文件，依据过时的记忆把 Peter 定好的相对链接改了回去 | 是列表里的代码块；链接写法是定好的规则 | 动文档格式前先查当前规则；没有单变量对照证实之前，不下结论，不改 skill 的规则和模板 |
| 10-18 "Restart Extension Host 就够" | 扩展宿主根本没激活新装的扩展 | 说"生效了"之前先看日志里有没有 `_doActivateExtension` |
| 10-18 md 链接复用 tab 是因为斜体预览 tab，加了 `keepActivePreviewTab()` | 是 `openMarkdownLinks` 默认 `inPreview` | 先核对用户的设置（`enablePreview: false`）再下诊断 |
| 10-18 Peter 说第 37 行有个点，只看了 30～45 行，答"没有" | 第 137 行有个孤立的逗号 | 用户说某行有怪字符，就搜整个文件，连相近的行号一起看 |
| 10-18 有人把字号改回 14px，凭"像撤销"又改回 13px | 没问就改了别人的改动 | 别人改过的地方，改回去之前先问 |
| 10-19 "Cmd+Shift+V 会盖过原来的 Open Preview""现在按应该已经是原地换成预览了" | MPE 也绑了这个键，而且排在前面；Peter 按的其实是 ctrl+alt+m | 说"快捷键生效了"之前，把这个键在所有已装扩展和用户 keybindings.json 里的绑定全列出来，再请 Peter 按一次 |
| 10-19 "切回闪两下在服务器这边解决不了" | 改 Cursor 应用两处就好 | 问题在客户端时，先拿同版本的客户端代码来读、来跑，再说能不能修 |
| 10-19 夜里把 23:5x 心算成"10-20 00:30"写进文档 | 和日志对不上 | 往文档里写时间之前先跑 `date` |
| 10-22 晚上 Peter 说跳过去回不来，先猜他是按着 Cmd 点的链接 | 他的 keybindings.json 把 Go Back 改成了 ⌃⌥←，preview.js 只认 ⌃- | 用户说某个快捷键不管用，先看他的 keybindings.json 里这个命令绑在哪个键上 |
