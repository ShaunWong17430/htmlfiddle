# HTML Fiddle

<p align="center">
  <a href="./README.md">English</a> · <strong>简体中文</strong>
</p>

在本地浏览器里**可视化编辑 HTML 文件**：双击改文案、面板调样式、切 Preview 验交互，点 Save 写回磁盘上的源文件。

```
双击 start-workbench.bat  →  挑一个 .html  →  浏览器里直接改  →  Save
```

> 📄 网页版说明（含运行架构图，可离线双击打开）：**[docs/index.html](docs/index.html)**
> 架构图由 archify 生成，规格在 `docs/architecture.json`。

---

## ⚠️ 这不是上游官方项目

HTML Fiddle 是 **[alienzhou/html-workbench](https://github.com/alienzhou/html-workbench)**
（提交 `8418087`）的**下游衍生版本**，由 [ShaunWong17430](https://github.com/ShaunWong17430) 维护。

上游的设计目标是"DeepSeek Harness 的一等插件"——编辑器嵌在 DSH 右侧栏里，由 Agent 驱动。
本项目做的事相反：**把插件壳摘掉**，让同一套编辑器在没有 DSH、没有 Node、没有 npm 的机器上
独立跑起来，靠双击一个 `.bat` 启动。

- 上游问题、功能建议请去[上游仓库](https://github.com/alienzhou/html-workbench)提；
- 启动器、入口脚本、Python 探测、独立运行相关的问题请在[本项目](https://github.com/ShaunWong17430/htmlfiddle/issues)提。

血缘与逐文件哈希见 **[UPSTREAM.md](UPSTREAM.md)**，许可与归因见 **[NOTICE](NOTICE)**。

### 它与 DSH 插件的关系

两者**完全独立、可以并存**：

| | DSH 插件 | HTML Fiddle |
| --- | --- | --- |
| 默认端口 | `4317` | `4318`（可用 `--port` 改） |
| 界面位置 | DSH 右侧栏面板 | 你自己的浏览器标签页 |
| 启动方式 | DSH 载入插件时自动 | 双击 `start-workbench.bat` |
| 选中文案 → 喂给 AI | 生成 chip 塞进聊天输入框 | 生成选区 Markdown 并**复制到剪贴板** |
| 文件来源 | 自动跟踪 agent 刚写出的 html | 你挑的文件 / 拖拽的文件 |

端口刻意错开，所以 `stop-workbench.bat` 不会误杀 DSH 拉起的那个服务
（已实测：停止本项目服务后，DSH 的 4317 依然健康）。

上游前端本来就内建了"不在 iframe 里就退回剪贴板"的降级逻辑，所以脱离 DSH 后
**唯一失去**的能力是"选中文案直接变成聊天框里的 chip"，替代方案是剪贴板。
其余功能（编辑、保存、预览、样式面板、外部改动自动刷新）都来自引擎，独立运行时一模一样。

---

## 快速开始

**方式一：双击**

双击 `start-workbench.bat`，会用菜单列出最近打开的文件；选序号，或按 `n` 新建一个。

**方式二：拖拽**

把任意 `.html` 文件拖到 `start-workbench.bat` 上，直接打开它（文件可以在任何目录，不限于 `pages/`）。

**方式三：命令行**

```bat
start-workbench.bat "D:\work\report.html"        :: 打开指定文件
start-workbench.bat --new landing                 :: 在 pages\ 下新建 landing.html 并打开
start-workbench.bat --list                        :: 只看最近文件
start-workbench.bat --status                      :: 体检：服务状态 + 离线资源是否就位
stop-workbench.bat                                :: 停止后台服务
```

关掉浏览器**不会**停止服务（方便反复打开），要停就运行 `stop-workbench.bat`。

macOS / Linux 用 `start-workbench.command`（首次可能需要 `chmod +x`）。

---

## 目录结构

```
htmlfiddle/
├─ start-workbench.bat      Windows 入口（双击 / 拖拽）
├─ stop-workbench.bat       停止后台服务
├─ start-workbench.command  macOS / Linux 入口
├─ scripts/
│  ├─ launcher.py           ★ 本项目原创：挑文件、拉起服务、开浏览器、记录最近文件
│  ├─ find-python.bat       ★ 本项目原创：解释器探测（逐个"真的跑一遍"，跳过商店桩文件）
│  └─ workbench.py          ↑ 上游引擎（alienzhou/html-workbench，一处兼容性补丁，见 UPSTREAM.md）
├─ assets/
│  └─ workbench.html        ↑ 上游编辑器前端（GrapesJS，未改动）
├─ vendor/                  GrapesJS 0.23.4 离线资源（BSD-3-Clause，哈希与引擎硬编码值一致）
├─ pages/                   新建文件的默认目录（含示例页 example.html）
├─ logs/                    运行日志（不入库）
├─ state/                   最近文件记录 / 调用引擎时的中转文件（不入库）
├─ docs/                    网页版说明 index.html + 架构图 architecture.html
├─ LICENSE                  MIT —— 只覆盖本项目原创部分
├─ NOTICE                   第三方组件归因与许可状态
└─ UPSTREAM.md              上游来源、哈希、补丁与升级步骤
```

启动器只调用引擎的 CLI（`serve` / `open` / `health` / `stop`），不碰它的内部实现。

---

## 运行要求与离线能力

- **Python ≥ 3.9**（与引擎要求一致，只用标准库）。本机已有 3.13，开箱可用。
  入口脚本会自己找解释器：`py -3` → PATH 上的每个 `python`/`python3` → 常见安装目录
  （miniconda / anaconda / Program Files 下的 Python），并且**逐个实际执行验证**，
  所以不会被"存在但不可用"的解释器骗到。详见 UPSTREAM.md 第 4 节。
- **首次运行不需要联网**：GrapesJS 已放进 `vendor/`，且哈希与引擎里写死的期望值逐字节一致，
  引擎校验通过就直接使用本地文件。用 `--status` 可以确认：

  ```
  GrapesJS 资源（离线缓存）：
    grapes.min.js        1124 KB  已就位
    grapes.min.css         60 KB  已就位
  ```

- 若目标机器**没有** Python：推荐把 Windows 版 embeddable Python 放进 `runtime/`，
  然后让 `.bat` 优先调用它。**单文件 exe 本项目没做**，原因是启动器以子进程方式调用
  `scripts/workbench.py`，用 PyInstaller 冻结后 `sys.executable` 不再指向 Python，
  需要额外做 argv 分发改造——不是"打包一下就完事"，所以没有提供，以免给你一个坏掉的 exe。

---

## 数据安全与边界

- 服务**只监听 `127.0.0.1`**，不对局域网暴露。但请注意：它没有任何鉴权，
  **本机上任何程序都能通过 `http://127.0.0.1:4318` 读写你打开的那个 html 文件**。
  所以别把端口转发出去，也别在不可信的多用户机器上长期挂着。
- 引擎可以打开**任意路径**的 `.html`（不是只能打开 `pages/` 下的）。
- 保存带 `revision` 校验：如果文件在你编辑期间被别的程序改过，保存会被**拒绝**而不是覆盖。
  已实测：

  ```
  PUT /api/document（陈旧 baseRevision）
  → 409 REVISION_CONFLICT / 磁盘文件已被外部修改，未覆盖最新版。
  ```

- 只接受 `.html` 文件（引擎限制）。
- 保存时引擎会往文件 `<head>` 里插入一个 `<style data-grapesjs-overrides>` 块，用于承载
  样式面板产生的覆盖样式——这是上游既有行为，属该工具的正常工作方式。

---

## 故障排查

先跑体检：

```bat
start-workbench.bat --status
```

| 现象 | 处理 |
| --- | --- |
| 双击后只看到 `[exit code: 9009]` | 这是"Python 没被正确找到"的旧表现，已修复。若仍出现，说明 Windows 商店的零字节 `python.exe` 桩文件在 PATH 里排在真解释器前面，且自动兜底也没找到——装一个真 Python 即可（见下条）。诊断：`where python` 的第一个结果若指向 `...\AppData\Local\Microsoft\WindowsApps\`，就是它 |
| 提示 `No usable Python 3.9+ found` | 机器上确实没有可用的 Python 3.9+。装 Python 并勾选 "Add python.exe to PATH"，或装 Miniconda。入口脚本已明确跳过商店桩文件并给出这条指引 |
| 提示端口被占用 | 用别的端口：`start-workbench.bat --port 4399 "D:\x\a.html"` |
| 浏览器打开是空白/报错 | 看 `logs\workbench-<端口>.log`；确认 `--status` 里引擎脚本与前端页面都"存在" |
| 报 `VENDOR_DOWNLOAD_FAILED` | `vendor/` 被删或哈希不符（引擎会逐字节校验）。重新放回两个文件即可，或让它联网重下 |
| 服务停不掉 | 先 `stop-workbench.bat`；若端口被别的程序占着，用 `--port` 换个端口，或手动结束该进程 |
| 想直接不用启动器 | `python scripts\workbench.py open "D:\x\a.html" --vendor-cache vendor --log-dir logs`，等价 |

杀毒软件/防火墙可能对"启动本地服务并打开浏览器"告警，选择允许即可（仅回环地址）。

---

## 许可

**这个仓库不是单一许可证，别整体当作 MIT 用。**

| 部分 | 许可 | 说明 |
| --- | --- | --- |
| 本项目原创代码（启动器、入口脚本、文档、示例页） | **MIT** | 见 [LICENSE](LICENSE) |
| `scripts/workbench.py`、`assets/workbench.html` | **上游仓库无 LICENSE 文件；但作者本人在 npm 以 MIT 发布了同一份代码** | 来自 alienzhou/html-workbench。两个事实冲突，本项目不替作者宣称 MIT，按 MIT 行为对待并保留全部归因 |
| `vendor/grapes.min.js`、`vendor/grapes.min.css` | **BSD-3-Clause** | GrapesJS 0.23.4，见 [vendor/LICENSE-grapesjs.txt](vendor/LICENSE-grapesjs.txt) |

完整归因、逐文件 SHA-256、以及"上游文件该怎么对待"的说明见 **[NOTICE](NOTICE)**。

技术血缘、补丁 diff 与跟随上游升级的步骤见 **[UPSTREAM.md](UPSTREAM.md)**。
