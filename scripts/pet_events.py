#!/usr/bin/env python3
"""蜡笔小新桌宠 — 事件接入层（TeleAgent 适配版）

把 TeleAgent 的 teleagent.db part 表增量数据投影成桌宠能懂的状态。

数据源：teleagent.db 的 part 表，含 type（reasoning/tool/text/step-start/step-finish）
和 tool 名字、state.status，按 rowid 增量读取，并跟踪运行中工具的原行更新。

设计原则：
1. 隐私投影在第一线——只取结构字段（type、tool 名、session_id、时间戳），
   正文、命令、工具输出不投影；气泡仅使用工具描述、文件名和搜索关键词。
2. 多会话并行时按紧急度仲裁：failed > waiting > working > review > thinking > done > idle。
3. 没有会话结束事件，每个状态带 TTL，超时自动衰减回 idle。
"""

import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Optional

# ============================================================
# 状态优先级与 TTL
# ============================================================

PRIORITY = {
    "failed": 60, "waiting": 50, "working": 40,
    "review": 30, "thinking": 20, "done": 10, "idle": 0,
}

# 状态存活时长（秒）。TeleAgent 会话由 session-status.json 的 running 兜底，
# 这里放宽到"基本不清"的级别，避免长工具/长输出期间气泡消失：
# 只有会话真正结束后（session-status 无 running）才会被 sweep 清理。
TTL = {
    "thinking": 1800, "working": 3600, "review": 1800,
    "waiting": 7200, "done": 8, "failed": 30,
}

DECAY_TO = {k: "idle" for k in TTL}

# 系统内部会话标题前缀（技能进化/扫描 internal、记忆日志等），
# 这类会话不是用户主动打开的对话，气泡一律不显示、不参与状态仲裁。
# 用 startswith 匹配；[skill- 前缀覆盖所有 skill-evolution / skill-scanner / skill-xxx 系统会话。
SYS_TITLE_PREFIXES = ("[skill-", "_SYS_")

# ============================================================
# 工具分类
# ============================================================

# 只读工具 → "review"；写/执行工具 → "working"；等你 → "waiting"
TOOL_CLASS = {
    # 读
    "read": "review", "grep": "review", "glob": "review",
    "webfetch": "review", "online_search": "review",
    "todoread": "review", "image_understanding": "review",
    "memory_get": "review", "memory_search": "review",
    "playwright_browser_snapshot": "review", "browser_mcp_browser_text": "review",
    "playwright_browser_read_table": "review",
    # 写 / 执行
    "write": "working", "edit": "working", "multiedit": "working",
    "powershell": "working", "todowrite": "working",
    "task": "working",
    "imagegen": "working", "imagegenwithref": "working",
    "report_final_files": "working",
    "skill": "thinking",
    "skill_manage": "working",
    "teleai_claw_scan": "working",
    "playwright_browser_navigate": "working", "playwright_browser_click": "working",
    "playwright_browser_type": "working",
    "browser_mcp_browser_open": "working", "browser_mcp_browser_click": "working",
    "browser_mcp_browser_fill": "working", "browser_mcp_browser_screenshot": "working",
    "telecom-email_emails_find": "review", "telecom-email_email_send": "working",
    "telecom-email_email_respond": "working",
    # 等你
    "question": "waiting",
}

TOOL_LABEL = {
    "read": "读取文件", "grep": "搜索内容", "glob": "查找文件",
    "write": "写入文件", "edit": "编辑文件", "multiedit": "批量编辑",
    "powershell": "执行命令",
    "webfetch": "抓取网页", "online_search": "搜索资料",
    "todowrite": "规划任务", "todoread": "查看任务",
    "task": "调度子代理", "skill": "加载技能",
    "question": "等你确认",
    "imagegen": "生成图片", "imagegenwithref": "编辑图片",
    "image_understanding": "识别图片",
    "report_final_files": "整理交付",
    "skill": "加载技能",
    # 兜底通用名
    "skill_manage": "管理技能", "memory_get": "读取记忆",
    "memory_search": "搜索记忆", "teleai_claw_scan": "安全扫描",
    "session_status": "查看会话", "session_continue": "继续会话",
    "playwright_browser_navigate": "浏览器导航",
    "playwright_browser_click": "点击网页",
    "playwright_browser_snapshot": "截图网页",
    "playwright_browser_type": "输入文字",
    "playwright_browser_read_table": "读取表格",
    "amap-maps-streamablehttp_maps_geo": "地理编码",
    "amap-maps-streamablehttp_maps_text_search": "搜索地点",
    "amap-maps-streamablehttp_maps_weather": "查天气",
    "browser_mcp_browser_open": "打开网页",
    "browser_mcp_browser_click": "点击网页",
    "browser_mcp_browser_fill": "填写表单",
    "browser_mcp_browser_text": "读取网页",
    "browser_mcp_browser_screenshot": "截图网页",
    "telecom-email_emails_find": "搜索邮件",
    "telecom-email_email_send": "发送邮件",
    "telecom-email_email_respond": "回复邮件",
}

STATE_LABEL = {
    "thinking": "思考中", "working": "执行中", "review": "检查中",
    "waiting": "等你确认", "done": "已完成", "failed": "出错了", "idle": "",
}

STATE_ANIM = {
    "thinking": "thinking", "working": "running", "review": "review",
    "waiting": "waiting", "done": "idle", "failed": "failed", "idle": "idle",
}


def _fit_text(s, n=42):
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s[:n] + "…" if len(s) > n else s


def _extract_tool_summary(tool: str, inp: dict, meta: dict) -> str:
    """从工具 input 里提取有意义的中文摘要（气泡第二行内容）。

    隐私安全：只取 description（agent 写的中文描述）和文件名（不含路径），
    不取 command 正文、content 正文等敏感参数。
    """
    if not isinstance(inp, dict):
        inp = {}
    if not isinstance(meta, dict):
        meta = {}

    # 1) description 字段（powershell 等工具有中文描述）
    desc = inp.get("description") or meta.get("description") or ""
    if desc:
        return _fit_text(desc, 50)

    # 2) 文件路径 → 只取文件名
    fp = inp.get("filePath") or inp.get("path") or inp.get("file_path") or ""
    if fp:
        name = Path(fp).name if isinstance(fp, str) else str(fp)
        return _fit_text(name, 50)

    # 3) 搜索关键词
    pattern = inp.get("pattern") or inp.get("query") or inp.get("keywords") or ""
    if pattern:
        return f"搜索 {_fit_text(pattern, 30)}"

    # 4) grep 的 include 参数
    include = inp.get("include") or ""
    if include:
        return f"搜索 {_fit_text(include, 30)}"

    # 5) todo 任务
    if "todos" in inp:
        return "规划任务"

    # 6) skill 名称
    skill_name = inp.get("name") or ""
    if skill_name and tool == "skill":
        return f"加载技能 {_fit_text(skill_name, 30)}"

    return ""


def _ends_with_question(text) -> bool:
    if not isinstance(text, str):
        return False
    s = text.strip()
    if not s:
        return False
    s = re.sub(r"```.*?```", "", s, flags=re.S)
    s = re.sub(r"`[^`]*`", "", s).strip()
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if not lines:
        return False
    last = lines[-1]
    # 只认显式问号："吗/呢"结尾在中文收尾里极常见，不代表真的需要用户输入
    return bool(re.search(r"[?？]\s*$", last))


# ============================================================
# 多会话状态跟踪（与原版完全一致）
# ============================================================

class SessionTracker:
    def __init__(self):
        self.sessions = {}
        self._orphan_sid = "_orphan"
        self.sys_sids = set()       # 系统内部会话 id（来自标题扫描，动态同步）
        self.completed_sids = set() # 已结束会话 id（来自 session-status，动态同步）
        self.active_sids = set()

    def set_sys_sids(self, sids):
        """同步系统内部会话集合；已在 sessions 里的系统会话由 sweep 立即清除。"""
        self.sys_sids = set(sids or ())

    def set_completed_sids(self, sids):
        """同步已结束会话集合；sweep 时对已结束会话延迟 15 秒清除气泡。"""
        self.completed_sids = set(sids or ())

    def _latest_sid(self):
        best, best_ts = None, -1.0
        for sid, s in self.sessions.items():
            if sid == self._orphan_sid:
                continue
            if s["ts"] > best_ts:
                best, best_ts = sid, s["ts"]
        return best

    def on_event(self, ev: dict):
        event = ev.get("event")
        if not event:
            return
        sid = ev.get("session_id") or self._latest_sid() or "_orphan"
        now = ev.get("ts", int(time.time() * 1000)) / 1000.0

        # 系统内部会话（[skill-evolution] internal、_SYS_*）不参与气泡与仲裁
        if sid in self.sys_sids:
            return

        # 无归属会话的事件：session_id 缺失且当前没有任何已知会话时直接丢弃。
        # 绝不凭空造 "_orphan" 幽灵会话——否则它会与随后出现的真实会话并存，
        # 误入多会话模式，任务刚启动就同时弹出两个"会话 xxxx"气泡。
        if sid == self._orphan_sid:
            return

        if event == "SessionEnd":
            self.sessions.pop(sid, None)
            return

        st = classify(event, ev)
        tool = ev.get("tool_name") or ""

        cur = self.sessions.get(sid)
        if st is None:
            # 心跳事件：会话还不存在时直接忽略，不能无中生有造"思考中"会话
            if cur is None:
                return
            cur["ts"] = now
            if tool:
                cur["tool"] = tool
                cur["label"] = TOOL_LABEL.get(tool, "")
            snip = ev.get("snippet")
            if snip:
                cur["snippet"] = snip
            return

        if cur is None:
            cur = {"state": st, "ts": now, "tool": tool,
                   "label": TOOL_LABEL.get(tool, "") if tool else "",
                   "count": 1 if event == "PreToolUse" else 0,
                   "snippet": ev.get("snippet", "")}
            self.sessions[sid] = cur
            return

        cur["state"] = st
        cur["ts"] = now
        if not tool:
            cur["tool"] = ""
            cur["label"] = ""
            cur["snippet"] = ""
        if event == "PreToolUse":
            cur["count"] += 1
        if tool:
            cur["tool"] = tool
            cur["label"] = TOOL_LABEL.get(tool, "")
        snip = ev.get("snippet")
        if snip:
            cur["snippet"] = snip

    def sweep(self, now: Optional[float] = None) -> bool:
        if now is None:
            now = time.time()
        changed = False
        for sid, s in list(self.sessions.items()):
            # 系统内部会话：一旦被识别，立即清除（不等 TTL）
            if sid in self.sys_sids:
                self.sessions.pop(sid, None)
                changed = True
                continue
            # 已结束会话（session-status=completed）：延迟 20 秒后清除气泡
            if sid in self.completed_sids:
                if now - s["ts"] > 20:
                    self.sessions.pop(sid, None)
                    changed = True
                continue
            age = now - s["ts"]
            if sid in self.active_sids and s["state"] in ("thinking", "working", "review", "waiting"):
                continue
            ttl = TTL.get(s["state"], 60)
            if sid == self._orphan_sid:
                ttl = min(ttl, 90)
            if age > ttl:
                self.sessions.pop(sid, None)
                changed = True
        return changed

    def resolve_tasks(self, titles=None):
        self.sweep()
        titles = titles or {}
        out = []
        for sid, s in sorted(self.sessions.items(), key=lambda kv: kv[1]["ts"], reverse=True):
            if sid in self.sys_sids or sid == self._orphan_sid:
                continue
            # 消息优先级：snippet > label(工具中文名) > STATE_LABEL(状态文案) > 空
            msg = s.get("snippet", "") or s.get("label", "") or STATE_LABEL.get(s["state"], "")
            out.append({
                "id": sid, "name": titles.get(sid) or f"会话 {sid[:8]}",
                "status": s["state"], "current": s.get("count", 0),
                "total": 0, "message": msg,
            })
        return out

    def resolve(self):
        self.sweep()
        if not self.sessions:
            return "idle", {"label": "", "sessions": 0, "tool": ""}
        best = None
        for sid, s in self.sessions.items():
            if sid in self.sys_sids:
                continue
            p = PRIORITY.get(s["state"], 0)
            cand = (p, s["ts"])
            if best is None or cand > best[0]:
                best = (cand, sid, s)
        _, sid, s = best
        state = s["state"]
        n = len(self.sessions)
        label = s.get("label", "") or STATE_LABEL.get(state, "")
        return state, {
            "label": label, "sessions": n, "tool": s.get("tool", ""),
            "steps": s.get("count", 0), "snippet": s.get("snippet", ""),
            "session_id": sid,
        }


def classify(event: str, ev: dict) -> Optional[str]:
    if event == "ToolError":
        return "failed"
    if event == "Waiting":
        return "waiting"
    if event == "Stop":
        return "waiting" if ev.get("ends_with_question") else "done"
    if event == "PostToolUse":
        return None
    if event == "PreToolUse":
        if ev.get("tool_status") == "error":
            return "failed"
        tool = ev.get("tool_name") or ""
        return TOOL_CLASS.get(tool, "working")
    if event == "Reasoning":
        return "thinking"
    if event == "AssistantMessage":
        return "thinking"  # 流式文本/中途说明不是本轮完成信号
    if event == "UserPromptSubmit":
        return "thinking"
    return None


# ============================================================
# SQLite 增量读取（TeleAgent part 表）
# ============================================================

# 定位结果缓存（一次解析，全程复用）
_tele_paths_cache = None


def _resolve_teleagent_paths():
    """动态定位 TeleAgent 用户数据目录，跨机器/跨用户/跨版本可移植。

    优先级：
      0) TELEAGENT_DB 环境变量（直接指定 db 路径）
      1) 新版布局：~/.local/share/TeleAgent/teleagent.db（直接在根目录）
      2) 旧版布局：~/.local/share/TeleAgent/users/<id>/teleagent.db（扫描取最新）
      3) TELEAGENT_CONFIG_DIR 环境变量推导
    返回 (db_path, status_path)；均可能为 None。
    """
    global _tele_paths_cache
    if _tele_paths_cache is not None:
        return _tele_paths_cache

    home = Path.home()
    ta_root = home / ".local" / "share" / "TeleAgent"
    users_root = ta_root / "users"

    # 0) TELEAGENT_DB 环境变量
    env_db = os.environ.get("TELEAGENT_DB")
    if env_db and Path(env_db).exists():
        db = Path(env_db)
        st = db.parent / "state" / "session-status.json"
        if not st.exists():
            st = db.parent / "session-status.json"
        _tele_paths_cache = (db, st if st.exists() else None)
        return _tele_paths_cache

    # 1) 新版布局：teleagent.db 直接在根目录
    cand_db = ta_root / "teleagent.db"
    if cand_db.exists():
        cand_st = ta_root / "session-status.json"
        if not cand_st.exists():
            cand_st = ta_root / "state" / "session-status.json"
        _tele_paths_cache = (cand_db, cand_st if cand_st.exists() else None)
        return _tele_paths_cache

    # 2) 旧版布局：users/<id>/teleagent.db
    best_db, best_st, best_mtime = None, None, 0.0
    if users_root.exists():
        for d in users_root.iterdir():
            if not d.is_dir():
                continue
            cand = d / "teleagent.db"
            if cand.exists():
                m = cand.stat().st_mtime
                if m > best_mtime:
                    cand_st = d / "state" / "session-status.json"
                    best_db, best_st, best_mtime = cand, cand_st if cand_st.exists() else None, m

    # 3) TELEAGENT_CONFIG_DIR 推导
    if best_db is None:
        cfg_env = os.environ.get("TELEAGENT_CONFIG_DIR")
        if cfg_env:
            p = Path(cfg_env)
            if p.parent.name == "users" and p.name:
                cand = p / "teleagent.db"
                if cand.exists():
                    best_db = cand
                    cand_st = p / "state" / "session-status.json"
                    best_st = cand_st if cand_st.exists() else None

    _tele_paths_cache = (best_db, best_st)
    return _tele_paths_cache


def _db_path() -> Path:
    """定位 teleagent.db（环境变量 > 多级探测 > 兜底新版根目录）。"""
    env = os.environ.get("TELEAGENT_DB")
    if env:
        return Path(env)
    db, _st = _resolve_teleagent_paths()
    if db is not None:
        return db
    # 兜底：新版根目录布局（即使不存在也返回，启动日志会打印 exists=False）
    return Path.home() / ".local" / "share" / "TeleAgent" / "teleagent.db"


def _status_path() -> Path:
    """定位 session-status.json（动态推导，兜底新版根目录）。"""
    if os.environ.get("TELEAGENT_DB"):
        parent = Path(os.environ["TELEAGENT_DB"]).parent
        nested = parent / "state" / "session-status.json"
        return nested if nested.exists() else parent / "session-status.json"
    _db, st = _resolve_teleagent_paths()
    if st is not None:
        return st
    # 兜底：尝试新版根目录、旧版 users 目录
    ta_root = Path.home() / ".local" / "share" / "TeleAgent"
    cand = ta_root / "session-status.json"
    if cand.exists():
        return cand
    users_root = ta_root / "users"
    if users_root.exists():
        for d in users_root.iterdir():
            for sub in [d / "state" / "session-status.json", d / "session-status.json"]:
                if sub.is_file():
                    return sub
    return ta_root / "session-status.json"


# 只读工具集合（小写匹配）
READ_TOOLS = {"read", "grep", "glob", "webfetch", "online_search", "todoread", "image_understanding"}
# step-finish reason=stop → 助手输出完一段话
STOP_REASONS = {"stop", "end_turn"}


class TranscriptWatcher:
    """增量查询 teleagent.db 的 part 表，产出结构化事件。

    对外接口与原版完全一致（poll/is_fresh/poll_titles），
    主程序无需修改。
    """

    def __init__(self, base=None):
        self.db_path = _db_path()
        self.status_path = _status_path()
        self._last_ts = 0          # 已读到的最大 time_created
        self._last_rowid = 0
        self._pending_tools = {}
        self._status_snapshot = {}
        self._initialized = False
        self.titles = {}
        self._last_title_scan = 0.0
        self._sys_sids = set()      # 系统内部会话 id（气泡/仲裁一律排除）
        self._known_sids = set()    # 已探测过的会话 id（避免重复查标题）
        self._completed_cache = set()  # session-status=completed 的会话（5秒缓存）
        self._last_status_scan = 0.0
        self._conn = None
        self._db_warned = False     # 是否已打印过 db 未找到告警
        # 启动诊断：打印解析到的路径，方便排查
        import __main__ as _main
        _log = getattr(_main, "log", None)
        if _log:
            _log(f"db_path={self.db_path} exists={self.db_path.exists()}")
            _log(f"status_path={self.status_path} exists={self.status_path.exists()}")

    def _ensure_conn(self):
        """每次 poll 用新鲜连接，避免 WAL 读快照卡住看不到新数据。"""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        try:
            self._conn = sqlite3.connect(
                self.db_path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
        except Exception:
            self._conn = None
            if not self._db_warned:
                self._db_warned = True
                import __main__ as _main
                _log = getattr(_main, "log", None)
                if _log:
                    _log(f"WARN: teleagent.db 连接失败 ({self.db_path})，自动感知暂停——桌宠将仅响应任务文件驱动")

    def _init_baseline(self):
        """首次运行：把基线设为当前最新时间，不重放历史。"""
        try:
            self._ensure_conn()
            if self._conn is None:
                return
            cur = self._conn.cursor()
            cur.execute("SELECT COALESCE(MAX(rowid), 0), COALESCE(MAX(time_created), 0) FROM part")
            row = cur.fetchone()
            self._last_rowid, self._last_ts = row
        except Exception:
            return
        self._initialized = True

    def _active_sessions(self):
        """读 session-status.json，返回状态为 running 且非系统内部的 session_id 集合。"""
        try:
            if not self.status_path.exists():
                return None  # 无法判断时返回 None（不过滤）
            with open(self.status_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sids = {sid for sid, st in data.items() if st == "running"}
            # 排除系统内部会话（[skill-evolution] internal / _SYS_*）
            self._scan_titles()
            return sids - self._sys_sids
        except Exception:
            return None

    def is_fresh(self, max_age=90.0, now=None):
        """teleagent.db 是否在 max_age 秒内有新 part 写入。"""
        now = now or time.time()
        try:
            self._ensure_conn()
            if self._conn is None:
                return False
            cur = self._conn.cursor()
            cur.execute("SELECT MAX(time_created) FROM part")
            row = cur.fetchone()
            if not row or not row[0]:
                return False
            age_ms = now * 1000 - row[0]
            return age_ms < max_age * 1000
        except Exception:
            return False

    def has_active_session(self):
        """是否有 running 状态的会话（来自 session-status.json）。

        这是最可靠的"任务还在进行"信号：即使 DB 暂时没有新 part 写入
        （长工具执行/长输出期间），只要会话状态仍是 running，气泡就不该消失。
        """
        sids = self._active_sessions()
        return bool(sids)

    def _scan_status(self):
        """读 session-status.json，缓存 completed 会话集合（5 秒）。"""
        now = time.time()
        if now - self._last_status_scan < 5:
            return self._completed_cache
        self._last_status_scan = now
        try:
            if self.status_path.exists():
                with open(self.status_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._completed_cache = {sid for sid, st in data.items() if st == "completed"}
        except Exception:
            pass
        return self._completed_cache

    def completed_sids(self):
        """当前已结束（completed）的会话 id 集合。"""
        return self._scan_status()

    def poll(self, force=False):
        """增量读取 part 表新行，返回投影后的事件列表。"""
        if not self._initialized:
            self._init_baseline()
            return self._status_events() if self._initialized else []

        self._scan_titles()  # 确保 _sys_sids 已构建（内部 30 秒缓存）
        events = []
        try:
            self._ensure_conn()
            if self._conn is None:
                return []

            cur = self._conn.cursor()
            # rowid 游标保留同一毫秒提交的全部记录，也不受分页边界影响。
            # SQL 第一层只投影允许显示的字段，不读取消息/思考/命令/输出正文。
            cur.execute(
                self._projection_sql() + " WHERE p.rowid > ? ORDER BY p.rowid ASC LIMIT 500",
                (self._last_rowid,),
            )
            rows = cur.fetchall()
            pending_before = dict(self._pending_tools)
            for r in rows:
                ts = r["time_created"]
                self._last_ts = max(ts, self._last_ts)
                self._last_rowid = r["row_id"]
                try:
                    data = json.loads(r["data"]) if r["data"] else {}
                except Exception:
                    continue

                if not isinstance(data, dict):
                    continue
                # 用 part 表自己的 session_id，不再猜测
                sid = r["session_id"]
                # 跳过系统内部会话（[skill-evolution] internal、_SYS_* 等）
                if sid in self._sys_sids:
                    continue
                # 新会话：立即探测一次标题，命中系统前缀即拦截（等不及5秒扫描）
                if sid not in self._known_sids:
                    self._known_sids.add(sid)
                    if self._probe_sys_sid(sid):
                        self._sys_sids.add(sid)
                        continue
                ev = self._part_to_event(data, ts, sid, r["role"])
                if ev:
                    events.append(ev)
                if data.get("type") == "tool" and data.get("state", {}).get("status") in ("pending", "running"):
                    self._pending_tools[r["row_id"]] = data
            # TeleAgent 把完成/失败状态更新在原 part 行，不能只看新增行。
            for row_id, previous in pending_before.items():
                row = self._conn.execute(self._projection_sql() + " WHERE p.rowid=?", (row_id,)).fetchone()
                if row is None:
                    self._pending_tools.pop(row_id, None)
                    continue
                data = json.loads(row["data"])
                status = data.get("state", {}).get("status")
                if status in ("completed", "error"):
                    ev = self._part_to_event(data, row["time_updated"], row["session_id"], row["role"])
                    if ev:
                        ev["event"] = "ToolError" if status == "error" else "PostToolUse"
                        events.append(ev)
                    self._pending_tools.pop(row_id, None)
        except Exception:
            pass
        active_event_sids = {ev["session_id"] for ev in events}
        events.extend(ev for ev in self._status_events()
                      if ev["event"] != "Reasoning" or ev["session_id"] not in active_event_sids)
        return events

    @staticmethod
    def _projection_sql():
        return """SELECT p.rowid AS row_id, p.session_id, p.time_created, p.time_updated,
            json_extract(m.data, '$.role') AS role,
            json_object('type', json_extract(p.data, '$.type'),
                'tool', json_extract(p.data, '$.tool'), 'reason', json_extract(p.data, '$.reason'),
                'state', json_object('status', json_extract(p.data, '$.state.status'),
                    'input', json_object(
                        'description', json_extract(p.data, '$.state.input.description'),
                        'filePath', json_extract(p.data, '$.state.input.filePath'),
                        'path', json_extract(p.data, '$.state.input.path'),
                        'file_path', json_extract(p.data, '$.state.input.file_path'),
                        'pattern', json_extract(p.data, '$.state.input.pattern'),
                        'query', json_extract(p.data, '$.state.input.query'),
                        'keywords', json_extract(p.data, '$.state.input.keywords'),
                        'include', json_extract(p.data, '$.state.input.include'),
                        'name', json_extract(p.data, '$.state.input.name')))) AS data
            FROM part p LEFT JOIN message m ON m.id=p.message_id"""

    def _status_events(self):
        try:
            data = json.loads(self.status_path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                return []
        except (OSError, ValueError):
            return []
        result = []
        for sid, status in data.items():
            old = self._status_snapshot.get(sid)
            if status == old or sid in self._sys_sids:
                continue
            event = None
            if status == "running" and old != "running":
                event = "Reasoning"
            elif status in ("paused", "needs_intervention") and old is not None:
                event = "Waiting"
            elif status == "completed" and old in ("running", "paused", "needs_intervention"):
                event = "Stop"
            if event and not self._probe_sys_sid(sid):
                result.append({"event": event, "session_id": sid, "ts": int(time.time()*1000)})
        self._status_snapshot = data
        return result

    def _part_to_event(self, data: dict, ts: int, sid: str, role=None) -> Optional[dict]:
        """把一条 part 行投影成结构事件。"""
        ptype = data.get("type", "")

        ev = {
            "ts": ts,
            "session_id": sid,
            "tool_name": None,
            "notification_type": None,
        }

        if ptype == "reasoning":
            ev["event"] = "Reasoning"
            # 不显示 reasoning 正文（是模型内部英文思考，对用户无意义且不美观）
            # 只保留状态信号，气泡只显示"思考中"

        elif ptype == "tool":
            tool_name = data.get("tool", "")
            state = data.get("state", {})
            status = state.get("status", "") if isinstance(state, dict) else ""
            inp = state.get("input", {}) if isinstance(state, dict) else {}
            meta = state.get("metadata", {}) if isinstance(state, dict) else {}
            ev["tool_name"] = tool_name
            ev["tool_status"] = status

            # 所有 tool 类型都视为"工作中"
            ev["event"] = "PreToolUse"

            # 从 input 提取中文摘要作为气泡第二行内容
            ev["snippet"] = _extract_tool_summary(tool_name, inp, meta)

        elif ptype == "text":
            if role not in ("assistant", "user"):
                return None
            ev["event"] = "AssistantMessage" if role == "assistant" else "UserPromptSubmit"

        elif ptype == "step-finish":
            reason = data.get("reason", "")
            if reason in STOP_REASONS:
                ev["event"] = "Stop"
                ev["ends_with_question"] = False
            else:
                return None  # tool_calls reason 不产生独立事件
        else:
            return None

        return ev

    def _probe_sys_sid(self, sid):
        """单个会话即时探测：标题命中系统前缀则判定为系统内部会话。"""
        try:
            self._ensure_conn()
            if self._conn is None:
                return False
            cur = self._conn.cursor()
            cur.execute("SELECT title FROM session WHERE id=?", (sid,))
            row = cur.fetchone()
            title = (row["title"] or "") if row else ""
            return title.startswith(SYS_TITLE_PREFIXES)
        except Exception:
            return False

    def _scan_titles(self):
        """扫描 session 表：填充 titles（气泡命名）与 _sys_sids（系统会话），5 秒缓存。"""
        now = time.time()
        if now - self._last_title_scan < 5:
            return
        self._last_title_scan = now
        try:
            self._ensure_conn()
            if self._conn is None:
                return
            cur = self._conn.cursor()
            cur.execute("SELECT id, title FROM session ORDER BY time_updated DESC LIMIT 20")
            for r in cur.fetchall():
                sid = r["id"]
                title = r["title"] or ""
                if title.startswith(SYS_TITLE_PREFIXES):
                    self._sys_sids.add(sid)
                    self.titles.pop(sid, None)
                elif title:
                    self.titles[sid] = title
        except Exception:
            pass

    def poll_titles(self):
        """从 session 表读会话标题（气泡命名用），30 秒缓存。"""
        self._scan_titles()
        return self.titles

    def poll_todos(self, sid=None):
        """从 todo 表拉当前会话的任务列表（TodoWrite 写入的数据）。

        返回 [{"name","status","current","total","message"}] 格式，
        与 TaskBubble.update_task 签名对齐。
        status 映射：pending→pending, in_progress→running, completed→completed
        """
        try:
            self._ensure_conn()
            if self._conn is None:
                return []
            cur = self._conn.cursor()
            if sid:
                cur.execute(
                    "SELECT content, status, position FROM todo WHERE session_id=? ORDER BY position",
                    (sid,),
                )
            else:
                # 取最近活跃会话的 todo
                cur.execute(
                    "SELECT content, status, position FROM todo ORDER BY time_updated DESC LIMIT 10"
                )
            rows = cur.fetchall()
            if not rows:
                return []
            tasks = []
            total = len(rows)
            for i, r in enumerate(rows):
                content = r["content"] or ""
                status = r["status"] or "pending"
                # 映射 todo status → 桌宠 status
                if status == "in_progress":
                    pet_status = "running"
                elif status == "completed":
                    pet_status = "completed"
                else:
                    pet_status = "pending"
                tasks.append({
                    "id": f"todo_{i}",
                    "name": content[:40],
                    "status": pet_status,
                    "current": i + 1,
                    "total": total,
                    "message": "",
                })
            return tasks
        except Exception:
            return []
