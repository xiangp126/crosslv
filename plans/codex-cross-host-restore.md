# codex 跨机器恢复：jcl 的恢复前预检

Last updated: 2026-10-23 22:40 CST

`~/.codex` 在 NFS 上，几台开发机共用。tmux 恢复（prefix+R 或 `jcl restore`）可能在另一台机器上把 codex 会话接回来。为此，恢复命令里每个 `codex resume <id>` 前面都先跑一次 `jcl codex-preflight <id>`，它做两件事：

- 处理原机器死机时留在 NFS 服务器上的写锁；
- 在本机先把 codex 的冷启动跑一遍。

这样恢复出来的 TUI 不会再卡在锁上，也不会撞上 15 秒的启动超时。claude 不需要这一步，不受影响。

## 现状

| 项 | 内容 |
|---|---|
| 状态 | 2026-10-23 实现完毕，在 l-fwdev-014 上用 `jcl restore codex` 同时恢复了两个 codex 会话，都成功；尚未提交 |
| codex | 0.163.0（nvm 下的 npm 包） |
| 代码 | [jcl](../nv-tools/jcl)：`codex-preflight` 子命令和它用到的函数，`resume_record(rec, preflight=True)` |
| 配置 | [tmux.conf](../track-files/tmux.conf)：`@resurrect-processes` 加了 `"~jcl codex-preflight"` |
| 补全 | [jcl_completion.bash](../completion/jcl_completion.bash)：加入 `codex-preflight` |
| 测试 | [test_jcl.py](../tests/test_jcl.py)：6 个新测试，另改了 `test_patch_resurrect_codex_and_claude` |
| 提交 | 无 |

## 名词

- **NLM（Network Lock Manager）**：NFSv3 的加锁协议。NFS 协议本身没有锁操作，`flock()` 和 `fcntl()` 加的锁由内核线程 `lockd` 发给服务器上的 `nlockmgr`（RPC 程序号 100021），记录在服务器上。`/labhome` 的挂载选项是 `vers=3,local_lock=none`，flock 也走这条路。
- **NSM（Network Status Monitor）**：客户端上的 `rpc.statd`，对应服务器上的 `status`（RPC 程序号 100024）。客户端重新开机时，`rpc.statd` 通知服务器，服务器据此删掉这个客户端名下的所有锁。客户端死机后一直不开机，它的锁就一直留在服务器上。
- **线程写锁**：codex 打开一个会话前，对 `~/.codex/thread-writer-locks/<id>.lock` 调 `try_lock()`；拿不到就报 `thread … already has an active writer`（[writer_lock.rs:65-70](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/rollout/src/writer_lock.rs#L65-L70)）。正常放锁时 codex 会删掉这个文件（[writer_lock.rs:174-195](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/rollout/src/writer_lock.rs#L174-L195)）。
- **sqlite_home**：`config.toml` 里设的是 `/var/tmp/pexiang-codex-sqlite`，每台机器各有一份。里面放状态库、日志库和分页历史索引；会话正文 rollout 在 NFS 上，大家共用。

## 遇到的三个问题

2026-10-21 16:49，在 l-fwdev-014 上用 prefix+R 恢复 m-fwdev-167 10:54 的存档。claude 全部恢复成功，两个 codex pane 各自栽在一个问题上。第三个问题排在它们后面，前两关过了也会撞上。

### 死机留下的写锁

167 在 10-21 12:46 到 16:49 之间掉线，之后一直 ping 不通，当时有 4 个 codex 会话开着：

- `01a11eb2`、`01a12f97` 两个 CLI 会话；
- Codex Desktop 的 `01a0c7de` 和它的 guardian 子会话 `01a15c83`。

它们的写锁一直留在服务器上。在 014 上用 `F_GETLK` 查（只查不加锁），4 个都是写锁，而 014 的 `/proc/locks` 里没有本机持有者：

```text
01a11eb2-….lock  HELD(type=write pid=-144754)  local holders: 0
01a12f97-….lock  HELD(type=write pid=-144761)  local holders: 0
01a0c7de-….lock  HELD(type=write pid=-324990)  local holders: 0
01a15c83-….lock  HELD(type=write pid=-325019)  local holders: 0
```

把锁文件改名移走之后，旧文件上的锁还在（锁跟着 inode 走），原位置就空出来了。codex 下次打开会话时会在原位置新建一个锁文件。

### 同时首启撞迁移

014 的本机状态库停在 10-08 的版本。prefix+R 同一秒在两个 pane 里启动了 codex，两个进程同时给这个库做迁移。%26 先建好了索引，%21 再建同一个索引就失败了：

```text
Codex couldn't start because its local database appears to be damaged.
  Cause: … failed to migrate state DB at /var/tmp/pexiang-codex-sqlite/state_5.sqlite: while executing migration 58: error returned from database: (code: 1) index idx_threads_archive_created …
```

库其实没坏，迁移 58–61 已经由 %26 在 16:49:24 做完。

### 冷启动吃掉 account/read 的 15 秒

TUI 启动后发出的第一个请求是 `account/read`，整个过程只给 15 秒（[workspace_routing.rs:425-435](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/app-server/src/request_processors/account_processor/workspace_routing.rs#L425-L435)）。%26 就停在这一步：

```text
Error: account/read failed during TUI bootstrap: account/read failed: workspace routing discovery timed out (code -32603)
```

**冷启动确实很慢。** 2026-10-23 在 014 上用 `codex --no-daemon app-server` 连测三次：

| 次序 | `initialize` | `account/read` |
|---|---|---|
| 第 1 次 | 13.30 s | 1.14 s |
| 第 2 次 | 0.32 s | 0.64 s |
| 第 3 次 | 0.33 s | 0.35 s |

**已排除的原因：**

- 网络：带令牌请求 `wham/accounts/check` 只要 0.6–1.8 s；
- NFS 加锁；
- autofs；
- 云端配置包：拉取 0.4–0.8 s；
- MCP 请求头 helper：不开线程时不调用。

冷启动里具体是哪一步慢，没有追到：今天的 app-server 都没往日志库写记录。第一次启动时 `plugins/cache/openai-curated-remote/openai-templates` 被更新过，也就是下载了一个远端插件包，这是最可疑的一处。不管是哪一步，预热都能把它吸收掉。

## 预检做什么

`jcl codex-preflight <id>` 返回 0，后面的 `codex resume` 才会运行。

**第一步，检查写锁。** 判断"锁在不在本机"只看 `/proc/locks`；`F_GETLK` 只用来判断有没有人持有。

| 写锁状态 | 处理 |
|---|---|
| 文件不存在，或者没人持有 | 放行 |
| 本机进程持有 | 会话已在这台机器上打开，报出 pid，返回 1 |
| 别的机器持有 | 从快照 `~/.claude/tmux-snapshot.json` 查这个会话上次在哪台机器，探测那台机器：TCP 22 和 ping，各等 2 秒 |
| ↳ 连得上 | 会话还在那边跑，提示先去那边退出，返回 1，不动锁 |
| ↳ 名字解析不了，或者快照里没有这个会话 | 打印手动 `mv` 命令，返回 1 |
| ↳ 两样都不通 | 持有 `.coordination.lock` 的情况下，把锁文件挪到 `~/.codex/thread-writer-locks.stale/<id>.lock.<host>.<时间>`，然后放行。`.stale` 里锁已经没了的旧文件，顺手删掉 |

**第二步，预热。**

1. 在 `<sqlite_home>/.jcl-codex-warm.lock` 上排队。这把锁在 `/var/tmp`，每台机器一把。
2. 排到的第一个进程起一次 `codex --no-daemon app-server`，只发 `initialize` 和 `account/read`，不建会话；然后写下 `<sqlite_home>/.jcl-codex-warm`，内容是 codex 版本号。
3. 10 分钟内来的其他预检，看到这个标记就直接放行。

调用的是 nvm 下 npm 包里的原生二进制，定位方式和 `~/.bashrc` 里的 `codex` 包装函数一样，避开 `codex.js` 的 autofs 查找。

**哪些路径带预检。** 只有恢复会换机器，所以只在恢复时加：

| 路径 | 是否带预检 |
|---|---|
| `jcl restore` 敲进 pane 的命令 | 带 |
| `jcl patch-resurrect` 写进存档的命令（prefix+R 用） | 带 |
| `restart`、`set` | 不带，它们在同一台机器上重启 |
| `exit-session` 打印的提示 | 不带 |
| 手动敲的 `codex` | 不带 |

**tmux.conf 为什么要配合改。** tmux-resurrect 只重新运行以 `@resurrect-processes` 里某个名字开头的命令；列表项以 `~` 开头时，命令里含有该字符串就算匹配（[process_restore_helpers.sh:100](../../../.tmux/plugins/tmux-resurrect/scripts/process_restore_helpers.sh?v=cff343cf9e#L100)）。存档里的 codex 命令现在以 `jcl codex-preflight` 开头，所以列表里加了 `"~jcl codex-preflight"`。

## 为什么这样做

被否掉的做法：

- **挂载选项 `local_lock=flock`**：要 root 才能改，影响所有程序，而且两台机器之间就不再互斥了。014 上会话还开着时，167 也能打开同一个会话，两个进程同时写一个 rollout。
- **把 `thread-writer-locks` 链接到本地盘**：同样失去跨机器的互斥。
- **每台机器各用一个 `CODEX_HOME`**：会话就不再共享了。
- **在 bashrc 的 `codex` 包装函数里做预检**：会改变手动敲 `codex` 的行为；而且已经开着的 shell 里还是旧的包装函数，`codex` 收到新参数就会报错，10-08 的 `--no-daemon` 就出过这种事。现在的做法是一条普通的 `jcl … && codex …` 命令，新旧 shell 都能跑。
- **tmux-resurrect 的 inline strategy（`codex->jcl … *`）**：codex 得由 jcl 来启动，包装函数里的 ja 和 `--no-daemon` 都要再抄一份。
- **每个 codex 版本只预热一次**：冷启动和版本无关，隔几个小时机器又会变冷。
- **用 `codex migrate-rollouts --apply` 预热**：在 014 上 0.7 s 就失败了，`thread 01a158d9-… is missing its SQLite metadata`。原因是 014 的本机状态库里没有 167 上后来新建的会话。
- **用 `F_GETLK` 返回的 pid 正负判断本机还是远端**：不可靠，见下面的历史。

## 怎么确认它在工作

**正在运行的 tmux 是否认得新命令：**

```bash
tmux show -gv @resurrect-processes
```

```text
claude codex "~jcl codex-preflight"
```

**恢复命令是否带上了预检**（2026-10-23 在 014 上实测）：

```bash
jcl restore codex --dry-run
```

```text
[dry-run] 3:9.1 [codex 01a11eb2-382c-7f70-b029-83dab6f870bd]: cd '/auto/fwgwork1/pexiang/bugZilla/Page_Supplier' && jcl codex-preflight 01a11eb2-382c-7f70-b029-83dab6f870bd && codex resume 01a11eb2-382c-7f70-b029-83dab6f870bd --model gpt-6-sol -c 'model_reasoning_effort="max"'
```

**恢复后。**

- `jcl list` 里两个 pane 的会话 id 和原来一致；
- 原位置新建了锁文件，持有者是本机的 codex 进程；
- 用的还是原来的 rollout 文件，没有新的 rollout 产生；
- 本机的 `/var/tmp/pexiang-codex-sqlite/.jcl-codex-warm` 记着当前的 codex 版本。

## 测试

```bash
cd /labhome/pexiang/myGit/crosslv && python3 -m unittest tests.test_jcl
```

```text
Ran 106 tests in 6.988s

OK
```

## 回到 167 的步骤

尚未实跑。

1. **在 014 上退出 codex。** 运行 `jcl exit-session codex`：先存快照，再正常退出。codex 正常退出时会删掉自己的锁文件，锁随之释放。
2. **在 167 上恢复。** 167 开机后，用 prefix+R 或 `jcl restore codex`。预检看到锁是空的，做一次预热后恢复。
3. **如果忘了在 014 上退出。** 预检会发现锁在别的机器手里，而快照主机 014 连得上，于是提示先去 014 退出，不会抢锁。
4. **清理旧锁文件。** `~/.codex/thread-writer-locks.stale/` 里那 4 个旧文件，在 167 开机后（它的旧锁随之被服务器删掉）可以删：`rm -r ~/.codex/thread-writer-locks.stale`。下一次挪锁时预检也会顺手删掉。

## 改代码的规矩

- 判断锁的持有者在不在本机，只看 `/proc/locks`。
- 动 `thread-writer-locks/` 里的文件之前，先拿 `.coordination.lock`。这是 codex 自己创建和删除锁文件时的规矩。
- 只挪"别的机器持有、而且快照里的主机连不上"的锁；连得上就绝不碰。
- 恢复命令的开头变了，`tmux.conf` 的 `@resurrect-processes` 必须同步改，否则 prefix+R 会悄悄不恢复 codex pane，而且没有任何提示。
- 预检只放在恢复路径上；同一台机器上的操作不带。

## 历史

1. **2026-10-21 16:49，014 上 prefix+R：** claude 全部恢复成功；%21 撞上迁移失败，%26 撞上 `account/read` 超时。
2. **2026-10-23 排查。** 依次排除了网络、NFS 加锁、autofs、云端配置；在 codex 0.163.0 源码里找到 15 秒的超时和写锁逻辑；用 `F_GETLK` 加 `/proc/locks` 确认 4 把锁都在别的客户端手里，而且时间线只对得上 167。
3. **错误判断一：** 以为 `account/read` 超时是本机每次启动都要做的全量 rollout 迁移耗掉的（[startup.rs:87-88](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/thread-store/src/local/rollout_migration/startup.rs#L87-L88)）。实测 `migrate-rollouts --apply` 0.7 s 就因缺元数据失败，耗不掉 15 秒。之后改为直接测 `account/read`，才发现是冷启动。
4. **错误判断二：** 以为 `F_GETLK` 返回负 pid 就说明锁在别的机器上。实际上 014 本机的 `claude mcp list` 持有 `~/.claude/.codex-mcp-refresh.lock` 时，`F_GETLK` 读到的也是 `-203621`，因为 NFS 上的 flock 由服务器回答。于是改成以 `/proc/locks` 为准。前面对那 4 把锁的结论不受影响：当时同时查过 `/proc/locks`，本机确实没有持有者。
5. **2026-10-23 22:03：** 4 把 167 的锁在持有 `.coordination.lock` 的情况下移到了 `thread-writer-locks.stale/`。
6. **2026-10-23 22:20：** `jcl restore codex` 同时恢复两个会话。预检排队，只做了一次预热（标记写于 22:20:57），两个 TUI 都顺利过了 `account/read`。"Resuming session…" 用了约 40 s，因为 014 第一次读这两个 12–15 MB 的 rollout、建本机分页索引。之后 `01a12f97` 回到 3:6.1，`01a11eb2` 回到 3:9.1，历史都在。
