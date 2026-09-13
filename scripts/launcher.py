#!/usr/bin/env python3
"""HTML Fiddle — 本地可视化 HTML 编辑器的启动器（不依赖 DSH / Node）。

它负责"用户体验"这一层：挑文件、拉起后台服务、打开浏览器、记录最近文件、
停止服务。真正的编辑器引擎是 scripts/workbench.py（上游原样拷贝，未改动），
本脚本只调用它的 CLI，不重复实现任何编辑逻辑。

用法（通常由 start-workbench.bat 代为调用）：

    python scripts/launcher.py                       # 交互式挑文件
    python scripts/launcher.py D:\\x\\page.html       # 直接打开
    python scripts/launcher.py --new report.html     # 新建并打开
    python scripts/launcher.py --list                # 只列最近文件
    python scripts/launcher.py --status              # 看服务/资源状态
    python scripts/launcher.py --stop                # 停掉后台服务

只用 Python 标准库，要求 Python >= 3.9（与引擎要求一致）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

APP_NAME = "HTML Fiddle"
APP_VERSION = "1.0.0"

# 目录约定：本文件位于 <ROOT>/scripts/，引擎与资源都在同级目录。
ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "scripts" / "workbench.py"
ASSET = ROOT / "assets" / "workbench.html"
VENDOR = ROOT / "vendor"
LOGS = ROOT / "logs"
STATE = ROOT / "state" / "launcher.json"
SCRATCH = ROOT / "state" / "run"
PAGES = ROOT / "pages"

# 独立默认端口：刻意与 DSH 插件的 4317 分开，这样两者互不干扰，
# 也不会因为 stop 而误杀 DSH 拉起的那个服务。
DEFAULT_PORT = int(os.environ.get("HWF_PORT") or 4318)
MAX_RECENTS = 20

STARTER_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
           margin: 0; padding: 48px 24px; line-height: 1.6; color: #18181b; }}
    .card {{ max-width: 760px; margin: 0 auto; }}
    h1 {{ font-size: 32px; margin: 0 0 12px; }}
    p {{ color: #52525b; }}
    .accent {{ color: #2563eb; font-weight: 600; }}
  </style>
</head>
<body>
  <section class="card">
    <h1>{title}</h1>
    <p>在右侧「样式」面板里改颜色和排版，双击文字直接编辑，改完点 <span class="accent">Save</span> 写回磁盘。</p>
  </section>
</body>
</html>
"""


# ── 输出小工具 ──────────────────────────────────────────────────────────────

def configure_output() -> None:
    """让中文在"非控制台"场景下也说得清楚。

    写向真正的 Windows 控制台时，Python 走 WriteConsoleW，中文本来就正确，
    这里不动它。但当 stdout 是管道/文件时，Python 会用系统的 locale 编码
    （简体中文 Windows 上是 cp936），下游按 UTF-8 解码就会变成乱码。
    统一成 UTF-8，行为才可预测。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError, ValueError):
            pass


def info(message: str) -> None:
    print(message)


def warn(message: str) -> None:
    print(message, file=sys.stderr)


def banner() -> None:
    info(f"{APP_NAME} v{APP_VERSION} — 本地可视化 HTML 编辑器")
    info("=" * 58)


# ── 最近文件 ────────────────────────────────────────────────────────────────

def _key(path: Path) -> str:
    """用于去重的规范化键。Windows 上大小写不敏感。"""
    return os.path.normcase(str(path))


def load_state() -> dict:
    try:
        payload = json.loads(STATE.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("recents", [])
            return payload
    except (OSError, ValueError):
        pass
    return {"recents": []}


def save_state(payload: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as caught:
        warn(f"（提示：最近文件记录写入失败：{caught}）")


def recents() -> list[str]:
    state = load_state()
    items = [item for item in state.get("recents", []) if isinstance(item, str)]
    return items[:MAX_RECENTS]


def remember(target: Path) -> None:
    state = load_state()
    items = [item for item in state.get("recents", []) if isinstance(item, str)]
    wanted = _key(target)
    items = [item for item in items if _key(Path(item)) != wanted]
    items.insert(0, str(target))
    state["recents"] = items[:MAX_RECENTS]
    save_state(state)


def candidates() -> list[Path]:
    """最近的、仍然存在的文件，顺序保持。"""
    seen: set[str] = set()
    result: list[Path] = []
    for raw in recents():
        path = Path(raw)
        if _key(path) in seen:
            continue
        seen.add(_key(path))
        if path.is_file():
            result.append(path)
    return result


def pages_html() -> list[Path]:
    if not PAGES.is_dir():
        return []
    found = [item for item in PAGES.glob("*.html") if item.is_file()]
    return sorted(found, key=lambda item: item.stat().st_mtime, reverse=True)


def describe(path: Path) -> str:
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
        size = path.stat().st_size
        size_text = f"{size / 1024:.0f} KB" if size >= 1024 else f"{size} B"
        return f"{stamp}  {size_text:>8}"
    except OSError:
        return "(不可读)"


# ── 交互式挑选 ──────────────────────────────────────────────────────────────

def make_starter(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    title = target.stem.replace("-", " ").replace("_", " ").strip() or "未命名页面"
    target.write_text(STARTER_TEMPLATE.format(title=title), encoding="utf-8")


def prompt_new_name() -> Path | None:
    raw = input("新文件名（直接回车取消）: ").strip()
    if not raw:
        return None
    name = raw if raw.lower().endswith(".html") else f"{raw}.html"
    target = (PAGES / name).resolve()
    if target.exists():
        info(f"文件已存在，直接打开：{target}")
    else:
        make_starter(target)
        info(f"已创建模板：{target}")
    return target


def interactive_pick() -> Path | None:
    items = candidates()
    known = {_key(item) for item in items}
    extras = [item for item in pages_html() if _key(item) not in known]
    menu = items + extras

    info("未指定文件。可选项：")
    info("")
    for index, path in enumerate(menu, start=1):
        info(f"  [{index:>2}] {path}")
        info(f"       {describe(path)}")
    info("")
    info("  [ n] 新建一个 HTML 文件")
    info("  [ q] 退出")
    info("")

    while True:
        try:
            answer = input("请输入序号，或直接粘贴 .html 绝对路径: ").strip()
        except (EOFError, KeyboardInterrupt):
            info("")
            return None
        if not answer:
            continue
        lowered = answer.lower()
        if lowered in {"q", "quit", "exit"}:
            return None
        if lowered in {"n", "new"}:
            picked = prompt_new_name()
            if picked is not None:
                return picked
            continue
        if answer.isdigit():
            index = int(answer)
            if 1 <= index <= len(menu):
                return menu[index - 1]
            warn(f"序号超出范围（1-{len(menu)}）。")
            continue
        candidate = Path(answer.strip('"').strip("'")).expanduser()
        return candidate


def resolve_target(requested: str | None, new_name: str | None, interactive: bool) -> Path | None:
    if new_name:
        name = new_name if new_name.lower().endswith(".html") else f"{new_name}.html"
        target = (PAGES / name).resolve()
        if not target.exists():
            make_starter(target)
            info(f"已创建模板：{target}")
        return target

    if requested:
        target = Path(requested.strip('"').strip("'")).expanduser()
        if not target.is_absolute():
            target = (Path.cwd() / target).resolve()
        if target.is_dir():
            found = sorted(target.glob("*.html"))
            if len(found) == 1:
                return found[0]
            if not found:
                warn(f"目录里没有 .html 文件：{target}")
                return None
            info(f"目录里有 {len(found)} 个 HTML，请指定具体文件：")
            for item in found:
                info(f"  {item}")
            return None
        if target.suffix.lower() != ".html":
            warn(f"只支持 .html 文件，收到：{target}")
            return None
        if not target.exists():
            if not interactive:
                warn(f"文件不存在：{target}\n（非交互模式不会自动创建，请先建好文件或加 --new）")
                return None
            try:
                answer = input(f"文件不存在：{target}\n创建骨架模板并打开？[y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                info("")
                return None
            if answer not in {"y", "yes"}:
                return None
            make_starter(target)
            info(f"已创建模板：{target}")
        return target

    if not interactive:
        warn("未指定文件，且当前不是交互式终端。用法：start-workbench.bat \"D:\\path\\page.html\"")
        return None
    return interactive_pick()


# ── 调用引擎 ────────────────────────────────────────────────────────────────

def run_engine(args: list[str], timeout: float = 60.0) -> tuple[int, str, str]:
    """调用 workbench.py 并取回它的输出。

    刻意用临时文件而不是管道：既避免管道缓冲区死锁，也让启动器在
    stdout 被重定向/关闭（例如 pythonw、某些双击场景）时依然可用。
    中转文件放在项目自己的 state/run 下，而不是系统临时目录：系统临时目录
    在受限环境里可能"能写不能删"，清理时抛 PermissionError 会直接崩掉启动器。

    同时给引擎强制 UTF-8：否则它写 JSON（含中文报错信息）时会用系统 locale
    编码，读回来就是乱码。这里只用 PYTHONIOENCODING 而**不用 PYTHONUTF8**：
    后者会把解释器切进 UTF-8 模式，连带让 subprocess 的文本模式按 UTF-8 解码
    子进程输出，而中文 Windows 上无控制台的 netstat/taskkill 会吐 GBK 表头，
    解码即崩（详见 UPSTREAM.md 记录的引擎补丁）。PYTHONIOENCODING 只管子进程
    自己的 stdin/stdout/stderr，正好是我要的效果，不牵连其他编码判断。
    """
    if not ENGINE.is_file():
        return 127, "", f"找不到引擎：{ENGINE}"
    try:
        SCRATCH.mkdir(parents=True, exist_ok=True)
    except OSError as caught:
        return 126, "", f"无法创建中转目录 {SCRATCH}：{caught}"

    stamp = f"{os.getpid()}-{int(time.time() * 1000)}"
    out_path = SCRATCH / f"{stamp}.out"
    err_path = SCRATCH / f"{stamp}.err"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    command = [sys.executable, str(ENGINE), *args]
    try:
        with out_path.open("wb") as out, err_path.open("wb") as err:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                timeout=timeout,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
        code = completed.returncode
    except subprocess.TimeoutExpired:
        code = 124
    except OSError as caught:
        for leftover in (out_path, err_path):
            _quiet_unlink(leftover)
        return 126, "", f"无法启动引擎：{caught}"

    stdout = out_path.read_text(encoding="utf-8", errors="replace") if out_path.exists() else ""
    stderr = err_path.read_text(encoding="utf-8", errors="replace") if err_path.exists() else ""
    if code == 124:
        stderr = f"引擎调用超时（{timeout:.0f}s）：{' '.join(args)}"
    for leftover in (out_path, err_path):
        _quiet_unlink(leftover)
    return code, stdout, stderr


def _quiet_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass  # 删不掉不影响功能，下次调用会覆盖同名文件


def parse_json_line(text: str) -> dict | None:
    for line in reversed([item for item in text.splitlines() if item.strip()]):
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def engine_error(stderr: str, fallback: str) -> str:
    payload = parse_json_line(stderr)
    if payload and payload.get("message"):
        return str(payload["message"])
    stripped = stderr.strip()
    return stripped or fallback


def start_service(target: Path, port: int, wait: float) -> str | None:
    """拉起（或复用）后台服务，返回编辑器 URL。"""
    code, stdout, stderr = run_engine([
        "open", str(target),
        "--port", str(port),
        "--editor-root", str(target.parent),
        "--vendor-cache", str(VENDOR),
        "--log-dir", str(LOGS),
        "--wait", str(wait),
    ])
    payload = parse_json_line(stdout)
    if code == 0 and payload and payload.get("url"):
        return str(payload["url"])
    reason = engine_error(stderr, f"引擎返回码 {code}")
    warn(f"启动失败：{reason}")
    if "PORT_IN_USE" in stderr or "端口" in reason:
        warn(f"提示：端口 {port} 被别的程序占用，可用 --port 换一个，例如 --port 4399")
    warn(f"日志目录：{LOGS}")
    return None


def open_browser(url: str) -> None:
    try:
        if os.name == "nt":
            os.startfile(url)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as caught:
        warn(f"（提示：自动打开浏览器失败：{caught}）")


# ── 子命令 ──────────────────────────────────────────────────────────────────

def cmd_status(port: int) -> int:
    banner()
    _code, stdout, _stderr = run_engine(["health", "--port", str(port)], timeout=20)
    payload = parse_json_line(stdout)
    if payload and payload.get("ok"):
        info(f"引擎状态 ：运行中（端口 {port}）")
        info(f"  服务版本：{payload.get('version')}")
        info(f"  编辑根  ：{payload.get('editorRoot')}")
        info(f"  能力集  ：{', '.join(payload.get('capabilities') or [])}")
    else:
        info(f"引擎状态 ：未运行（端口 {port} 空闲）")
    info("")
    info(f"项目根目录：{ROOT}")
    for label, path in (("引擎脚本", ENGINE), ("前端页面", ASSET)):
        info(f"  {label}：{'存在' if path.is_file() else '缺失 !!'}  {path}")
    info("  GrapesJS 资源（离线缓存）：")
    for name in ("grapes.min.js", "grapes.min.css"):
        item = VENDOR / name
        if item.is_file():
            info(f"    {name:<16} {item.stat().st_size / 1024:>8.0f} KB  已就位")
        else:
            info(f"    {name:<16} 缺失 !!  首次启动将尝试联网下载")
    recent = candidates()
    info(f"  最近文件：{len(recent)} 条有效记录")
    # --status 是体检报告，不是断言：服务没跑也是一种正常状态，退出码保持 0，
    # 免得 .bat 把它当失败弹一个 "[exit code: 3]" 出来。
    return 0


def cmd_stop(port: int) -> int:
    banner()
    code, stdout, stderr = run_engine(["stop", "--port", str(port)], timeout=30)
    payload = parse_json_line(stdout)
    if code == 0 and payload:
        if payload.get("stopped"):
            info(f"已停止端口 {port} 上的服务。")
        else:
            info(f"端口 {port} 上没有正在运行的服务（无需停止）。")
        return 0
    warn(f"停止失败：{engine_error(stderr, f'引擎返回码 {code}')}")
    return 1


def cmd_list() -> int:
    banner()
    recent = candidates()
    if not recent:
        info("还没有最近打开的记录。用 --new 新建，或直接传入 .html 路径。")
        return 0
    info("最近打开：")
    for index, path in enumerate(recent, start=1):
        info(f"  [{index:>2}] {path}")
        info(f"       {describe(path)}")
    return 0


def cmd_open(target: Path | None, port: int, wait: float, browser: bool, print_url: bool) -> int:
    banner()
    if target is None:
        return 0
    info(f"目标文件：{target}")
    url = start_service(target, port, wait)
    if url is None:
        return 1
    remember(target)
    info("")
    info(f"编辑器地址：{url}")
    info("（服务已在后台运行，关掉浏览器不会停止它；需要时运行 stop-workbench.bat）")
    if browser:
        open_browser(url)
    elif print_url:
        info("（--no-browser：未自动打开浏览器，请手动访问上面的地址）")
    return 0


# ── 入口 ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    # Exit non-zero on an interpreter we cannot support. The entry points use
    # `launcher.py --version` as their "is this Python actually usable?" probe,
    # so this check is what makes that probe meaningful (cf. scripts/find-python.bat).
    if sys.version_info < (3, 9):
        print(f"{APP_NAME} 需要 Python 3.9 或更高版本，当前为 {sys.version.split()[0]}。", file=sys.stderr)
        return 2
    configure_output()
    raw = list(sys.argv[1:] if argv is None else argv)
    # 允许 `start-workbench.bat stop` 这种顺手写法。
    if raw and raw[0] in {"stop", "status", "list"}:
        raw[0] = f"--{raw[0]}"

    parser = argparse.ArgumentParser(
        prog="start-workbench",
        description=f"{APP_NAME} — 在本地浏览器里可视化编辑 HTML 文件。",
        add_help=True,
    )
    parser.add_argument("file", nargs="?", help="要编辑的 .html 文件路径（可省略，省略则进入挑选菜单）")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"本地服务端口（默认 {DEFAULT_PORT}）")
    parser.add_argument("--new", metavar="NAME", help="在 pages/ 下新建一个 HTML 文件并打开")
    parser.add_argument("--wait", type=float, default=12.0, help="等待服务就绪的秒数（默认 12）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器，只在终端打印地址")
    parser.add_argument("--print-url", action="store_true", help="打印地址（默认行为，保留作显式声明）")
    parser.add_argument("--list", action="store_true", help="列出最近打开的文件后退出")
    parser.add_argument("--status", action="store_true", help="查看服务与离线资源状态后退出")
    parser.add_argument("--stop", action="store_true", help="停止指定端口上的后台服务")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    args = parser.parse_args(raw)

    if args.list:
        return cmd_list()
    if args.status:
        return cmd_status(args.port)
    if args.stop:
        return cmd_stop(args.port)

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    target = resolve_target(args.file, args.new, interactive)
    return cmd_open(target, args.port, args.wait, not args.no_browser, args.print_url)


if __name__ == "__main__":
    raise SystemExit(main())
