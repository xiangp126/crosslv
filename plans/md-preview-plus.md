# Markdown Preview Plus：Cursor 里看 md 的预览扩展

扩展 [md-preview-plus](../assets/cursor/md-preview-plus/) 的设计和维护记录。Peter 在 Mac 上用 Cursor，通过 Remote-SSH 连 m-fwdev-167 看 md 文档，用的是 VS Code 自带的 Markdown 预览加这个扩展。本文写清它做什么、为什么这样做、碰到过的每个问题和根因、怎么检查和测试、出了问题怎么查。安装和日常用法在扩展目录的 [README.md](../assets/cursor/md-preview-plus/README.md)。

| | |
|---|---|
| 现状（2026-10-20） | 功能都在用；服务器和 Cursor 应用的补丁都验证过，Peter 10-19 在 Mac 上确认切回不闪；10-20 确认 Mac 上的 client 是服务器自动装上的，标题栏按钮和 Cmd+Shift+V 也正常。升级、重装 Cursor 后一般只需点一次 Quit Cursor 再打开；Mac 上改 app 包要不要"App 管理"权限，要等下次升级才知道 |
| 装着的版本 | 服务器：Cursor server `be4c9e5350d77747b42cd467cbd3370a753d4640`（3.24.18），扩展 `markdown-preview-plus.md-preview-plus` 0.2.1。Mac：Cursor 3.24.18（VS Code 1.128.0），client `markdown-preview-plus.md-preview-plus-client` 0.1.0 |
| 代码 | crosslv `assets/cursor/md-preview-plus/`：服务器那一半在根目录，`client/` 是 Mac 那一半，`tools/` 是测试脚本；远程设置在 [remote.settings.json](../assets/cursor/remote.settings.json) |
| 提交 | [0d7f44b](https://github.com/xiangp126/crosslv/commit/0d7f44b) 第一版；[24d740f](https://github.com/xiangp126/crosslv/commit/24d740f) 服务器补丁；[6b8971b](https://github.com/xiangp126/crosslv/commit/6b8971b) Cursor 应用补丁、升级后自动恢复；[beb9707](https://github.com/xiangp126/crosslv/commit/beb9707) 测试脚本、本文、删 MPE 残留、删 `keepActivePreviewTab()`、作者改名 |

## 1. 名词

- **Cursor 应用**（也说 Cursor.app）：Mac 上的 Cursor 程序本身，窗口、编辑区、预览外框都是它画的。VS Code 叫它 workbench。
- **Cursor server**：Cursor 连服务器时在服务器上跑的那一半，装在 `~/.cursor-server/bin/linux-x64/<commit>/`，`<commit>` 是 Mac 上那个 Cursor 的 commit（About Cursor 里能看到）。Markdown 扩展和 md-preview-plus 都在这一半里运行。服务器的 home 是 NFS，所有 lab 机共用同一个 `~/.cursor-server`。
- **client**：本扩展的第二个扩展 `markdown-preview-plus.md-preview-plus-client`，只在 Mac 的 Cursor 里运行，专门给 Cursor 应用打补丁。
- **补丁的叫法**：服务器上 4 处，名字以 [preview_patch.js](../assets/cursor/md-preview-plus/preview_patch.js) 打印的为准：`keep preview tabs`、`keep Open Preview panels`、`update covered tabs in place`、`links to #L<line> jump to the line`，依次叫第 1～4 处。Cursor 应用上 2 处，名字以 [client/webview_patch.js](../assets/cursor/md-preview-plus/client/webview_patch.js) 为准：`release() keeps the size`、`_show() re-anchors first`。"第 N 项"指 §5 的一节。
- **Mac 上的 agent**：Peter 在 Mac 上开的 Claude Code 会话。服务器上的 agent 碰不到 Mac，Mac 那一侧的事都经 Peter 转给它。
- **MPE**：Markdown Preview Enhanced，试过、不用的另一个预览扩展。
- **psf-sanity-baseline-test (506ffde3)、utopx-81 (5b4a60d7)**：做这件事的两个 Claude 会话，前者做到 10-19 14:29，后者接手。
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
| 把 `file:line` 的写法改成 `#L` 链接 | Peter 10-20 定不改，仍写在反引号里 |

## 3. 功能和实现

| 功能 | 实现 |
|---|---|
| md 默认用预览打开 | 远程设置 `workbench.editorAssociations` |
| 左侧目录：☰ 开关，拖侧栏右边缘调宽 | [preview.js](../assets/cursor/md-preview-plus/preview.js)；内容变化时用 MutationObserver 重建，每帧最多一次 |
| 页内搜索：Cmd+F、Enter / Shift+Enter、↑↓ 翻历史、Aa / ab、Esc | `preview.js`，在 window 的 capture 阶段截下按键，不让 Cursor 那个搜不到东西的查找框弹出（第 4 项） |
| 正文占满宽度、字号（正文 13.5px、目录 12.5px）、表格在宽度内换行、diff 用编辑器配色 | [preview.css](../assets/cursor/md-preview-plus/preview.css) |
| 标题栏 Preview / Markdown 按钮，Cmd+Shift+V 原地换成预览 | [extension.js](../assets/cursor/md-preview-plus/extension.js)、[package.json](../assets/cursor/md-preview-plus/package.json)；Peter 的 3.24.18 上正常，隔离的 3.25.9 上不工作（第 14 项） |
| 只有 Cmd+双击才跳源码 | `preview.js` 拦下没按 Cmd 的 dblclick |
| 预览里点 md 链接开新 tab | 远程设置 `"markdown.preview.openMarkdownLinks": "inEditor"` |
| 被盖住的 tab 不重建、`#L` 跳行 | 服务器补丁（§4.1） |
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

文档 6 章只显示 4 章，文件本身完整。Cursor 自带 md 视图遇到嵌在列表项里的 fenced 代码块，把这一章连同后面的章节都丢掉（3.24.18）。机理看不到，10-17 用单变量对照证实：两份文档只差 §5 的两个代码块在不在列表项里，Peter："A全部显示,B只到第4章"。修法：不用这个视图；写 md 时代码块不放进列表项（skill feature-delivery `references/documents.md` §6）。引用块里的代码块没做对照。查一份文档：用 markdown-it 解析，看 `fence` token 的 `level` 是否大于 0。

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

只在隔离的 3.25.9 上看到，没修。Peter 10-20 在他的 3.24.18（远程窗口）上确认按钮都在、Cmd+Shift+V 能原地换成预览。可能是 3.25.9 改了什么，也可能和隔离环境是本地窗口有关，没查；Cursor 升级到 3.25 以后要再看一次。预览 tab 的标题栏上只有自带的 Show Source，没有本扩展的 Markdown 按钮；点 Show Source 打开的源码 tab 是 Cursor 自带 md 视图的 Markdown 模式（编辑区上方有 `.markdown-mode-tab`），不是普通文本编辑器，所以本扩展 Preview 按钮的条件 `activeEditor == 'workbench.editors.files.textFileEditor'` 不成立；在里面按 Ctrl+Shift+V 没反应。Markdown 按钮的条件和 Show Source 一样却没出现，快捷键为什么不触发，都没查。复现：`tools/accept.mjs` 第 5 项。

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

扩展日志在 `~/.cursor-server/data/logs/*/exthost*/remoteexthost.log`，grep `md-preview-plus` 能看到每次激活的时间。

### 7.3 验收

改了代码、升级了 Cursor、或者 Peter 说某项坏了，按这张表逐项查。在隔离的 Cursor 里（§8）：第 1～7 行用 `tools/accept.mjs`，第 8 行用 `covered_update.mjs`，第 9、10 行用 `flash.mjs`，第 11 行照 §8 的"模拟升级"走。在 Peter 的窗口里只能请他照"怎么查"手动看。

| # | 功能 | 怎么查 | 通过 |
|---|---|---|---|
| 1 | md 用预览打开 | 资源管理器里单击一个 `.md` | tab 标题就是 `xxx.md`，内容是渲染后的，不是 `Preview xxx.md`，也不是源码 |
| 2 | 目录 | 点 ☰，点目录里一项，拖侧栏右边缘 | 侧栏开合；正文跳到那一节；宽度跟着变，重开后还在 |
| 3 | 页内搜索 | 预览里 Cmd+F，输入一个词，Enter、↑、Aa、ab、Esc | 右上角出现搜索框和 `n of m`，Enter 跳下一处，↑ 翻出搜过的词，开关生效，Esc 关闭；Cursor 自己的查找框不出现 |
| 4 | md 链接 | 点预览里指向另一个 `.md` 的链接 | 新开一个 tab，当前 tab 还在 |
| 5 | 切换按钮和快捷键 | 看预览标题栏有没有 Markdown 按钮；打开源码看有没有 Preview 按钮，按 Cmd+Shift+V | 两个按钮都在，同一个 tab 原地换成预览。Peter 的 3.24.18 上通过，隔离的 3.25.9 上不过（第 14 项） |
| 6 | 双击 | 在预览里双击、Cmd+双击 | 双击不跳；Cmd+双击打开源码 |
| 7 | 样式 | 看 diff 代码块和第一列是 change 号的表 | diff 增删行暗色主题 `#b5cea8`、`#ce9178`，浅色 `#098658`、`#a31515`，没有行底色；change 号一行显示 |
| 8 | 被盖住不重建 | 长文档滚到中间，点代码链接，再点回预览；被盖住时改文件用 `covered_update.mjs` | 立即回到原位置，没有白屏；脚本输出 `rebuilt false`、`updated true`，前后滚动值相同 |
| 9 | 切回不闪 | 同上，看切回的那一下；或 `flash.mjs` + `analyze.py` | 没有一帧空白；`page log` 里没有 `resize … 300 150` |
| 10 | `#L` 跳行 | 点 `[x](file#L79)` 这种链接 | 光标停在第 79 行（状态栏 `Ln 79`） |
| 11 | 升级后恢复 | Cursor 升级重启后 | 弹 Quit Cursor（可能还有 Reload Window）；点它再打开后没有提示、没有"已损坏"，再查 1～10 |

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

`tools/` 里：`start.sh` 起一个私有 Xvnc 上的 Cursor（HOME、user-data、extensions 都在测试目录里，调试端口 9339；`--ozone-platform=headless` 在 GTK 里段错误，所以用 Xvnc，它的 VNC 只开 0600 的 unix socket）；`open.sh` 在里面打开文件（启动时传进去的 md 会被 Cursor 自带的 md 视图接走，要等窗口出来再开）；`make_sample.py` 生成固定的测试工作区；`accept.mjs`、`covered_update.mjs`、`flash.mjs` + `analyze.py` 是检查；`cdp.mjs` 是调试协议客户端和公共步骤，每个检查开始时自动藏起 Cursor 的登录层、关掉右边的 Agents 面板（它把预览挤到不到 500 像素宽，点不中链接）。

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
/usr/bin/python3 $T/make_sample.py $W/ws                 # long.md（552 KB，第 42 节有指向 src/sample.cpp#L79 和 other.md 的链接）
bash $T/start.sh $C $W/work $W/ws                         # 放到后台
node $T/center.mjs 5                                      # 一直等到窗口出来，再打印通知中心
bash $T/open.sh $C $W/work $W/ws/long.md
node $T/accept.mjs                                        # §7.3 第 1～7 行
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

测过的结果（新的在上）：

| 时间 | 测什么 | 结果 |
|---|---|---|
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
| 10-20 | 验收脚本、照文档实测升级流程，发现第 14 项；按 Peter 的决定删 MPE 残留、删 `keepActivePreviewTab()`，文档合并成本文；Peter 删掉 Mac 上的 ctrl+alt+m，确认 Mac 上 client 已装、标题栏按钮和 Cmd+Shift+V 正常 |

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
