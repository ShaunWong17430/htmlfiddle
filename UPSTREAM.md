# 上游来源与本地补丁

本项目的编辑器引擎和前端**不是**我写的，来自开源项目
**[alienzhou/html-workbench](https://github.com/alienzhou/html-workbench)**，
我把它从 DSH 插件壳里摘出来、做成不需要 DSH 的独立运行版本。
这里记录来源、哈希、以及我做的唯一一处修改，便于你日后核对或跟随上游升级。

> **许可状态请先读 [NOTICE](NOTICE) 第 1 节。** 上游仓库当前**没有 LICENSE 文件**，
> 本文件不再为上游代码宣称 MIT。这一节只讲技术血缘，不讲授权。

## 1. 来源

血缘关系是这样的一条链：

```
alienzhou/html-workbench（开源仓库）
        │  skill/html-workbench/{scripts/workbench.py, assets/workbench.html}
        ▼
@vibe-x/dsh-html-workbench（同一仓库 dsh-plugin/ 下的 npm 分发包，v0.3.0）
        │  把上面两个文件打包进 DSH 插件
        ▼
htmlfiddle（本项目）：去掉 DSH 壳，加自己的启动器，独立运行
```

| 项目 | 值 |
| --- | --- |
| 上游仓库 | https://github.com/alienzhou/html-workbench |
| 取用提交 | `8418087d48bbbfd2c774cea0aa34ad03a37b0a9f`（2026-08-19） |
| 上游路径 | `skill/html-workbench/scripts/workbench.py`、`skill/html-workbench/assets/workbench.html` |
| 引擎版本 | `SERVICE_VERSION = "2.1.0"` |
| 插件壳版本 | `@vibe-x/dsh-html-workbench` `0.3.0` |
| 取用时间 | 2026-09-12 |

溯源是**用哈希验出来的**，不是猜的：从上游仓库 `main` 分支直接下载这两个文件算 SHA-256，
结果分别是 `b8f172b7…`（workbench.py）与 `2f1d4437…`（workbench.html），
与本机 DSH 插件包里的文件、以及第 2 节记录的上游哈希逐字节一致。

DSH 插件是"薄壳"：它只负责在右侧栏挂面板、拉起服务、把选区上下文塞进聊天框。
真正的编辑器是一个**零第三方依赖的 Python 标准库 HTTP 服务**（`workbench.py`）
加一个 GrapesJS 前端页（`workbench.html`），两者之间只用 `/api/*` 通信。
因此摘掉 DSH 壳即可独立运行——本项目做的就是这件事。

## 2. 文件对照与哈希

上游文件：

| 文件 | 状态 | SHA-256 |
| --- | --- | --- |
| `assets/workbench.html` | **原样未改**（与上游逐字节一致） | `2f1d44373ea6521df6dab86a995a4bebec3f1beaf8f11b07b6639b110b657369` |
| `scripts/workbench.py` | 上游 `b8f172b773f6fdd32ac98060bffeb2db2592169834f928f55176a8abfdfa7517` → 打补丁后 `ccb7428ad9261e894b6d80d2cb0ae6f0c50f2c2cc1e151926c47a2c1bf497378` | 见第 3 节 |
| `vendor/grapes.min.js` | 原样（上游锁定版本，BSD-3-Clause） | `66155421db3a640add8eaf77391b6a744d36af80833cd91d44f8d3220fb76231` |
| `vendor/grapes.min.css` | 原样（上游锁定版本，BSD-3-Clause） | `fb55e939b3349c280d68c0617dc87e56baa3eab55ea56a1855db9f5efcc7268d` |

本项目新增（全部为独立实现，不修改上游逻辑）：

| 文件 | 作用 | SHA-256 |
| --- | --- | --- |
| `scripts/launcher.py` | 启动器：挑文件 / 最近文件 / 新建模板 / 拉服务 / 开浏览器 / status / stop | `6b75fdb46164eaec6051c46ddae9b4b3687da26d240bb10befe5397ef59e4188` |
| `scripts/find-python.bat` | Python 解释器探测（见第 4 节：为什么不能用 `where`） | `a9b2c38299358612e8297cc1b78156668a8ab925d200647ca7279515cb029793` |
| `start-workbench.bat` | Windows 双击 / 拖拽入口 | `b80636e3919acbeb1e480e98ebcad7c93256d8fabe9896dadfa1796c999448f8` |
| `stop-workbench.bat` | Windows 停止入口 | `f8ba0625ccf584a7878989b62e289da1a12456f5e74b27f2daa4447fd058e377` |
| `start-workbench.command` | macOS / Linux 入口 | `011ced8a2dc152e6988a0de453c61d3ff0aaee1aef544cce5411a6b6dfc1ce44` |

`vendor/` 里两个文件的哈希是 `workbench.py` 里 `VENDOR_ASSETS` 硬编码的期望值，
**逐字节一致**，所以引擎启动时校验通过、直接使用本地文件，全程不联网。


## 3. 唯一的补丁：本地化进程输出导致 `stop` 崩溃

### 症状

在简体中文 Windows 上执行停止服务：

```
AttributeError: 'NoneType' object has no attribute 'splitlines'
Exception in thread Thread-1 (_readerthread):
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xbb in position 2: invalid start byte
```

服务其实**已经停掉了**，但引擎以退出码 1 结束并打印 traceback，
`stop-workbench.bat` 于是把它当成失败并弹一个 `[exit code: 1]`。

### 根因

`listeners_on_port()` 用 `subprocess.run([...], text=True)` 调 `netstat` 来枚举端口占用者：

1. `text=True` 且未指定 `encoding` 时，CPython 走 `subprocess._text_encoding()`：
   **只要解释器处于 UTF-8 模式（`sys.flags.utf8_mode`）就返回 `"utf-8"`**，否则返回 `locale.getencoding()`（中文 Windows 上是 `cp936`）。已对照 `Lib/subprocess.py:381-386` 确认。
2. `netstat` / `taskkill` 的输出是**本地化**的。中文 Windows 上其表头是 GBK 字节
   （`0xbb 0xee` = "活"，正是报错里 `position 2` 的那个字节）。
3. GBK 字节按 UTF-8 解码失败 → 读线程抛 `UnicodeDecodeError` 并退出 →
   `result.stdout` 保持 `None` → 紧接着 `result.stdout.splitlines()` 抛 `AttributeError`。

这条路径只在"UTF-8 模式 **且** 拿到本地化输出"时触发。Python 3.15 起 UTF-8 模式默认开启，
所以这并非罕见组合，属上游的真实脆弱点。

### 补丁（三处，均只加 `errors="replace"`）

```diff
--- workbench.py (upstream 2.1.0)
+++ workbench.py (htmlfiddle)
@@ -1489,3 +1489,9 @@
                 ["netstat", "-ano", "-p", "tcp"],
-                capture_output=True, text=True, timeout=5,
+                # errors="replace" 是 HTML Fiddle 的下游补丁（见 UPSTREAM.md）：
+                # netstat/taskkill 的输出是本地化的（简体中文 Windows 上是 GBK），
+                # 而 Python 处于 UTF-8 模式时 subprocess 文本模式会用 UTF-8 解码，
+                # 读线程抛 UnicodeDecodeError 后 stdout 变成 None，下面的
+                # splitlines() 就会 AttributeError。解析只取 ASCII 列，替换掉
+                # 解不出的字节是安全且必要的。
+                capture_output=True, text=True, errors="replace", timeout=5,
             )
@@ -1509,3 +1515,3 @@
             ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
-            capture_output=True, text=True, timeout=5,
+            capture_output=True, text=True, errors="replace", timeout=5,  # 下游补丁，见 UPSTREAM.md
         )
@@ -1530,3 +1536,3 @@
                 ["taskkill", "/PID", str(pid), "/T", "/F"],
-                capture_output=True, text=True, timeout=5,
+                capture_output=True, text=True, errors="replace", timeout=5,  # 下游补丁，见 UPSTREAM.md
             )
```

为什么这样修是安全的：解析逻辑只看 `TCP` / `LISTENING` / 端口号 / PID，全是 ASCII 列；
替换掉解不出的本地化表头字节，不影响任何判定。`lsof`（macOS/Linux）同样处理，
那里输出一般也是 UTF-8，加上 `errors="replace"` 只是兜底。

### 顺带在启动器侧规避

`launcher.py` 调用引擎时只用 `PYTHONIOENCODING=utf-8`（让引擎写出的 JSON 是 UTF-8，
好让启动器正确读回中文报错），**刻意不用 `PYTHONUTF8=1`**：后者会把解释器切进 UTF-8 模式，
连带改变 subprocess 的解码选择。两个变量是正交的——

```
PYTHONIOENCODING=utf-8 → sys.stdout.encoding = utf-8,  utf8_mode = 0, _text_encoding() = cp936   ✅
PYTHONUTF8=1           → sys.stdout.encoding = utf-8,  utf8_mode = 1, _text_encoding() = utf-8   ⚠️
```

即使你在系统里全局设了 `PYTHONUTF8=1`，第 3 节的引擎补丁也能保证 `stop` 不崩
（已实测：在 `PYTHONUTF8=1` 下停止服务，退出码 0、无 traceback）。

## 4. 为什么找 Python 不能只用 `where`

这一节记录的是本项目自己的一个真实缺陷及其修法，不是上游问题。

### 症状

首次双击 `start-workbench.bat`，只看到：

```
[exit code: 9009]
```

没有任何解释。`9009` 是 cmd 的"命令未找到"。

### 根因

Windows 自带一组**零字节的 "App Execution Alias" 桩文件**，通常在：

```
C:\Users\<你>\AppData\Local\Microsoft\WindowsApps\python.exe
C:\Users\<你>\AppData\Local\Microsoft\WindowsApps\python3.exe
```

它们**在 PATH 上，会被 `where python` 找到**，但没有安装商店版 Python 时它们并不是解释器：
执行会打印 "Python was not found..." 并返回 **9009**。本机实测：

```
where python 的第一个命中: ...\WindowsApps\python.exe      ← 0 字节
直接执行它              : exit code 9009
持久化 PATH 中的顺序    : WindowsApps(索引 16) 早于 miniconda3(索引 17)
```

最初的 `.bat` 用 `where python >nul 2>nul && set "PY=python"` 判断"有没有 Python"——
`where` 命中了桩文件，于是它认定 Python 存在，接着执行它，得到 9009。

这个 bug 之所以没在开发自测中被发现，是因为 **conda init 会把 miniconda 目录注入到
交互式 shell 的 PATH 最前面**，于是我测试时的 `python` 一直是好的；
而双击 `.bat` 使用的是**持久化 PATH**，那里的顺序是相反的。

### 现在的做法：`scripts/find-python.bat`

不再相信"存在"，而是**真的去跑一遍**。候选按顺序：

1. `py -3`（Windows 的 py 启动器，仅当 `where py` 成功时尝试）；
2. `where python` / `where python3` 返回的**每一个**路径；
3. 常见安装位置兜底（`%USERPROFILE%\miniconda3`、`anaconda3`、`%LOCALAPPDATA%\Programs\Python\Python3xx`、`%ProgramFiles%\Python3xx` …）。

每个候选要过两道关：

- **按路径跳过**：路径里含 `WindowsApps` 直接丢弃（针对上面这个已知陷阱的快速路径）；
- **执行验证**：`call <候选> "<根>\scripts\launcher.py" --version`，退出码非 0 就丢弃。
  这一层能拦住其他任何不可用的解释器（装坏的、架构不对的、别的厂商的桩），
  也是 `launcher.py` 里那个 `sys.version_info < (3, 9)` 检查的用途——它让 `--version`
  成为一个有意义的"能不能用"探针。

两个细节：

- 用 `call` 而不是直接调用。候选可能是 `.bat` / `.cmd` 包装器（conda、pyenv-win 都会装这类 shim），
  批处理里不带 `call` 调用另一个批处理会**链式替换、控制流不再返回**，表现为整条命令静默无输出
  （这个问题在对抗性测试里被实测复现并修掉了）。
- 全部候选都失败时，`.bat` 打印明确的安装指引并以 **2** 退出，而不是把 9009 抛给用户。

### 对抗性验证（均为确定性构造，不依赖机器真实 PATH 顺序）

| 场景 | 构造方式 | 期望 | 结果 |
| --- | --- | --- | --- |
| 坏解释器排最前（`.bat` 桩，`exit /b 9009`） | 假目录置于 PATH 首位 | 被"执行验证"拒绝，回落到 miniconda | ✅ |
| 坏解释器排最前（真 `.exe` 但不是解释器） | 把 `where.exe` 改名为 `python.exe` | 同上 | ✅ |
| **可用**的 python 藏在 `WindowsApps` 路径下 | 目录名含 `WindowsApps` 的假 shim | 被"按路径跳过"，回落 miniconda | ✅ |
| 所有解释器都无法验证 | 临时改名 `launcher.py` | 友好报错 + 退出码 2（不再是 9009） | ✅ |

## 5. 若日后要跟随上游升级

1. 从新版 [alienzhou/html-workbench](https://github.com/alienzhou/html-workbench) 取
   `skill/html-workbench/scripts/workbench.py` 与 `skill/html-workbench/assets/workbench.html`，
   **整体覆盖**本仓库同路径文件（等价来源：更新 DSH 插件后再从其包内拷贝）。
2. 记录新提交 SHA，更新第 1 节的"取用提交"。
2. 重新套用第 3 节的补丁：把三处 `capture_output=True, text=True, timeout=5,` 改成
   `capture_output=True, text=True, errors="replace", timeout=5,`。
3. 若上游 `VENDOR_ASSETS` 的 `GRAPESJS_VERSION` 或 `sha256` 变了，重新下载并替换 `vendor/` 两个文件
   （哈希必须是新脚本里写的期望值，否则引擎会认为缓存无效并尝试联网下载）。
4. 校验：`python scripts/launcher.py --status`，以及打开一个文件后另存一次。

`launcher.py` 不依赖引擎内部实现，只使用其 CLI（`serve` / `open` / `health` / `stop`）与
`/api/health` 的能力声明，因此上游小版本升级一般不需要改动启动器。

## 6. 许可与归属

**结论先说：别照搬"上游是 MIT 所以我也 MIT"的写法，也别吓到不敢用——两个事实要一起看。**

- **事实 A — 上游仓库没有 LICENSE 文件。**
  GitHub API 对 `alienzhou/html-workbench` 返回 `license: null`，根目录与 `skill/`、
  `dsh-plugin/` 下都没有 LICENSE / COPYING。纯看仓库，这是"未声明许可"。
- **事实 B — 但作者本人在 npm 上以 MIT 发布了同一份代码。**

  ```
  npm: @vibe-x/dsh-html-workbench@0.3.0
    license     : MIT
    maintainers : alienzhou（上游作者本人）
    first publish: 2026-08-17
  ```

  包的产物就是本仓库 `scripts/workbench.py` 与 `assets/workbench.html` 的来源。
  也就是说，作者主动对外分发这份代码时，说的就是 MIT。

**本项目的判断：** 作者想以 MIT 传播的意图是明确的，缺 LICENSE 文件更像仓库层面的疏忽。
但 LICENSE 缺失是客观事实，且 GitHub ToS 对公开仓库授予他人的权利**仅限服务内**
（`D.5` 的 *"through the Service"*），不含下载与站外再分发。所以处理上取中间路线：
行为上按 MIT 对待上游文件（修改、再分发、保留声明），但**不在 LICENSE 里替作者宣称 MIT**，
只把两个事实原样摆出来。

- **GrapesJS 0.23.4：BSD-3-Clause**，Copyright (c) 2017-current, Artur Arseniev。
  完整文本见 `vendor/LICENSE-grapesjs.txt`，前端页面通过本地路由加载 `vendor/` 下的这两个文件。
- **本项目原创部分（启动器、入口脚本、文档、示例页）：MIT**，见根 `LICENSE`。

据此，根 `LICENSE` 的 MIT 授权**有意限定范围**，明确把 `scripts/workbench.py` 与
`assets/workbench.html` 排除在外。完整归因、逐文件哈希、以及"该怎么对待上游文件"的
建议见 **[NOTICE](NOTICE)**。

引擎与前端代码的著作权归原作者。若上游后续追加 LICENSE，以新 LICENSE 为准，
本文件与 NOTICE 会同步修订。
