"""账号池与任务存储（JSON 落盘，原子写）。"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid

_LOCK = threading.Lock()

# 决定账号生死的核心 cookie（与 engine.ESSENTIAL_COOKIES 保持一致）
ESSENTIAL_COOKIES = ("hatch_sess", "hatch_gw", "hatch_vml",
                     "hatch_native_auth_device")


def _is_pos(v) -> bool:
    try:
        return int(v) > 0
    except (TypeError, ValueError):
        return False


# hatch_vml 固定约 2 天，且不因使用而延长 —— 它就是决定账号寿命的那条 cookie。
# 实测对照：生成前后 synced_at 变了、也捞到新 cookie，但 4 条核心 cookie 的
# expires 一动不动。所以拿不到 hatch_vml 的 expires 时，按「导入时间 + 2 天」估算，
# 而不是退回到 hatch_native_auth_device 的 30 天（那个不决定生死，会误导用户）。
VML_TTL = 2 * 86400
QUOTA_CACHE_TTL_SECONDS = 15 * 60
_TOKEN_UNITS = {"": 1, "K": 10**3, "M": 10**6, "B": 10**9, "T": 10**12}


def parse_token_amount(value) -> int | None:
    """Parse values such as ``2.7B tokens left`` without trusting display text."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    match = re.search(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*([KMBT]?)\b", str(value), re.I)
    if not match:
        return None
    number = float(match.group(1).replace(",", "."))
    return max(0, int(number * _TOKEN_UNITS[match.group(2).upper()]))


def quota_state(account: dict, *, now: int | None = None,
                ttl_seconds: int = QUOTA_CACHE_TTL_SECONDS) -> str:
    """Return ``eligible``, ``exhausted`` or ``unknown`` for media generation."""
    quota = account.get("quota") if isinstance(account, dict) else None
    if not isinstance(quota, dict) or not quota.get("found"):
        return "unknown"
    current = int(time.time()) if now is None else int(now)
    try:
        checked_at = int(quota.get("checked_at") or 0)
    except (TypeError, ValueError):
        checked_at = 0
    if checked_at <= 0 or current - checked_at > max(0, int(ttl_seconds)):
        return "unknown"
    if quota.get("runtime_exhausted"):
        return "exhausted"
    try:
        weekly_used = float(quota["weekly_used_pct"])
    except (KeyError, TypeError, ValueError):
        weekly_used = None
    if weekly_used is not None and weekly_used < 100:
        return "eligible"
    extra_left = parse_token_amount(quota.get("extra_left_value"))
    if extra_left is None:
        extra_left = parse_token_amount(quota.get("extra_left"))
    if extra_left is not None and extra_left > 0:
        return "eligible"
    extra_known = (
        "extra_pool_present" in quota
        or "extra_left_value" in quota
        or "extra_left" in quota
        or "extra_used_pct" in quota
    )
    if weekly_used is not None and weekly_used >= 100 and extra_known and extra_left == 0:
        return "exhausted"
    return "unknown"


def quota_refresh_needed(account: dict, *, now: int | None = None,
                         ttl_seconds: int = QUOTA_CACHE_TTL_SECONDS) -> bool:
    """Rate-limit refresh failures as well as successful quota reads."""
    current = int(time.time()) if now is None else int(now)
    if quota_state(account, now=current, ttl_seconds=ttl_seconds) != "unknown":
        return False
    try:
        attempted_at = int(account.get("quota_refresh_attempted_at") or 0)
    except (TypeError, ValueError):
        attempted_at = 0
    return attempted_at <= 0 or current - attempted_at > max(0, int(ttl_seconds))


def min_expiry(cookies_exp: dict | None) -> int | None:
    """核心 cookie 里最早过期的那个（通用兜底，不区分哪条决定寿命）。"""
    if not cookies_exp:
        return None
    vals = []
    for name in ESSENTIAL_COOKIES:
        v = cookies_exp.get(name)
        try:
            v = int(v)
        except (TypeError, ValueError):
            continue
        if v > 0:
            vals.append(v)
    if not vals:
        for v in cookies_exp.values():
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
            if v > 0:
                vals.append(v)
    return min(vals) if vals else None


def account_expiry(cookies_exp: dict | None,
                   base_ts: int | None = None) -> int | None:
    """账号实际失效时间。

    优先级：
      1) hatch_vml 的真实 expires（最准）；
      2) 拿不到就用 base_ts(导入/同步时刻) + VML_TTL 估算 —— 因为寿命就是 2 天；
      3) 都没有再退回核心 cookie 最早过期。
    """
    ce = cookies_exp or {}
    vml = ce.get("hatch_vml")
    if _is_pos(vml):
        return int(vml)
    if base_ts:
        return int(base_ts) + VML_TTL
    return min_expiry(ce)


def _read(path: str, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return default


def _write(path: str, obj):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Store:
    def __init__(self, cfg):
        self.cfg = cfg
        self._last_accounts_mtime = 0
        self.accounts: list[dict] = _read(cfg.accounts_file, [])
        for a in self.accounts:
            ce = a.get("cookies_exp") or {}
            if _is_pos(ce.get("hatch_vml")):
                a["expires_at"] = int(ce["hatch_vml"])
        if os.path.isfile(cfg.accounts_file):
            self._last_accounts_mtime = os.path.getmtime(cfg.accounts_file)
        self.tasks: dict[str, dict] = _read(cfg.tasks_file, {})

    def _reload_if_changed(self):
        try:
            if not os.path.isfile(self.cfg.accounts_file):
                return
            mtime = os.path.getmtime(self.cfg.accounts_file)
            if mtime != getattr(self, "_last_accounts_mtime", 0):
                self.accounts = _read(self.cfg.accounts_file, [])
                for a in self.accounts:
                    ce = a.get("cookies_exp") or {}
                    if _is_pos(ce.get("hatch_vml")):
                        a["expires_at"] = int(ce["hatch_vml"])
                self._last_accounts_mtime = mtime
        except Exception:
            pass

    # ---------- 账号 ----------
    def add_account(self, cookies: dict, label: str = "",
                    cookies_exp: dict | None = None) -> dict:
        with _LOCK:
            aid = uuid.uuid4().hex[:12]
            exp = {k: int(v) for k, v in (cookies_exp or {}).items()
                   if _is_pos(v)}
            now = int(time.time())
            acc = {"id": aid, "label": label or aid, "cookies": cookies,
                   "cookies_exp": exp, "expires_at": account_expiry(exp, now),
                   "expiry_anchor": None,
                   "enabled": True, "created_at": now,
                   "last_used": None, "last_keepalive": None, "use_count": 0,
                   "ok": None, "note": "", "synced_at": None}
            self.accounts.append(acc)
            _write(self.cfg.accounts_file, self.accounts)
            return acc

    def list_accounts(self) -> list[dict]:
        self._reload_if_changed()
        out = []
        for a in self.accounts:
            item = {k: v for k, v in a.items() if k != "cookies"}
            ce = a.get("cookies_exp") or {}
            if _is_pos(ce.get("hatch_vml")):
                item["expires_at"] = int(ce["hatch_vml"])
            item["cookie_count"] = len(a.get("cookies", {}))
            item["essential_ok"] = all(
                a.get("cookies", {}).get(n) for n in ESSENTIAL_COOKIES)
            # 有效期是 hatch_vml 的实测 expires，还是按「2 天寿命」推算的
            item["expires_estimated"] = not _is_pos(ce.get("hatch_vml"))
            item["media_quota_status"] = quota_state(a)
            out.append(item)
        return out

    def delete_account(self, aid: str) -> bool:
        with _LOCK:
            n = len(self.accounts)
            self.accounts = [a for a in self.accounts if a["id"] != aid]
            _write(self.cfg.accounts_file, self.accounts)
            return len(self.accounts) != n

    def pick_account(self, preferred_id: str | None = None, rotate: bool = True,
                     force_rotate: bool = False, exclude_id: str | None = None,
                     exclude_ids: set[str] | list[str] | None = None,
                     record_use: bool = True, quota_aware: bool = False,
                     quota_ttl_seconds: int = QUOTA_CACHE_TTL_SECONDS) -> dict | None:
        """选择可用账号：优先复用当前已预热的健康账号（减少切号重连耗时），每满 15 次或遇错自动轮转。
        exclude_ids: 需要排除的账号 ID 集合（例如正在被其他并发线程占用的账号）。"""
        with _LOCK:
            self._reload_if_changed()
            live = [a for a in self.accounts if a.get("enabled", True) and a.get("cookies")]
            if not live:
                return None
            blocked = set(exclude_ids or [])
            if exclude_id:
                blocked.add(exclude_id)
            if blocked:
                available = [a for a in live if a["id"] not in blocked]
                if available:
                    live = available
                elif exclude_ids is not None:
                    # 并发模式下要求避开所有繁忙账号，但当前无剩余空闲账号
                    return None
                elif len(live) > 1:
                    live = [a for a in live if a["id"] != exclude_id] or live
            if quota_aware:
                live = [a for a in live if a.get("ok") is not False]
                eligible = [
                    a for a in live
                    if quota_state(a, ttl_seconds=quota_ttl_seconds) == "eligible"
                ]
                unknown = [
                    a for a in live
                    if quota_state(a, ttl_seconds=quota_ttl_seconds) == "unknown"
                ]
                live = eligible or unknown
                if not live:
                    return None
            if preferred_id and not force_rotate:
                for a in live:
                    if a["id"] == preferred_id and a.get("ok") is not False:
                        sticky_n = getattr(self, "_sticky_count", 0) if getattr(self, "_sticky_id", None) == preferred_id else 0
                        if not rotate or sticky_n < 15:
                            self._sticky_id = preferred_id
                            self._sticky_count = sticky_n + 1
                            if record_use:
                                a["last_used"] = time.time()
                                a["use_count"] = a.get("use_count", 0) + 1
                                _write(self.cfg.accounts_file, self.accounts)
                            return a
            healthy = [a for a in live if a.get("ok") is not False]
            candidates = healthy if healthy else live
            candidates.sort(key=lambda a: (a.get("last_used") or 0.0, a.get("use_count") or 0))
            acc = candidates[0]
            self._sticky_id = acc["id"]
            self._sticky_count = 1
            if record_use:
                acc["last_used"] = time.time()
                acc["use_count"] = acc.get("use_count", 0) + 1
                _write(self.cfg.accounts_file, self.accounts)
            return acc

    def media_capacity(self, *, ttl_seconds: int = QUOTA_CACHE_TTL_SECONDS) -> dict:
        """Return only aggregate quota state; never expose account identity or raw quota."""
        with _LOCK:
            self._reload_if_changed()
            live = [
                a for a in self.accounts
                if a.get("enabled", True) and a.get("cookies") and a.get("ok") is not False
            ]
            counts = {"eligible": 0, "unknown": 0, "exhausted": 0}
            for account in live:
                counts[quota_state(account, ttl_seconds=ttl_seconds)] += 1
            if counts["eligible"]:
                status = "ready"
            elif counts["unknown"]:
                status = "degraded"
            elif not live:
                status = "degraded"
            else:
                status = "exhausted"
            return {
                "status": status,
                **counts,
                "skipped": max(0, len(self.accounts) - len(live)),
            }

    def mark_quota_exhausted(self, aid: str, note: str = "") -> dict | None:
        """Cache a direct provider quota failure without marking the session unhealthy."""
        now = int(time.time())
        with _LOCK:
            for account in self.accounts:
                if account["id"] != aid:
                    continue
                quota = dict(account.get("quota") or {})
                quota.pop("raw", None)
                quota.update({
                    "found": True,
                    "checked_at": now,
                    "runtime_exhausted": True,
                    "weekly_used_pct": 100,
                    "extra_pool_present": True,
                    "extra_left_value": 0,
                })
                account["quota"] = quota
                account["quota_refresh_attempted_at"] = now
                account["ok"] = True
                if note:
                    account["note"] = note[:300]
                _write(self.cfg.accounts_file, self.accounts)
                return account
        return None

    def touch_keepalive(self, aid: str, ok: bool | None = True, note: str = ""):
        """ok=None 仅记录未确认的检测；保留上次账号状态、成功保活时间和有效期。"""
        with _LOCK:
            now_ts = int(time.time())
            for a in self.accounts:
                if a["id"] == aid:
                    if ok is not None:
                        a["ok"] = ok
                    if ok is True:
                        a["last_keepalive"] = now_ts
                        # ponytail: 只信实际 Cookie 到期时间或原导入锚点，不凭检测成功虚推 48h。
                        a["expires_at"] = account_expiry(
                            a.get("cookies_exp"), a.get("expiry_anchor") or a.get("created_at"))
                    if note:
                        a["note"] = note[:300]
                    a["checked_at"] = now_ts
            _write(self.cfg.accounts_file, self.accounts)

    def mark(self, aid: str, ok: bool, note: str = ""):
        with _LOCK:
            for a in self.accounts:
                if a["id"] == aid:
                    a["ok"] = ok
                    a["note"] = note[:300]
                    a["checked_at"] = int(time.time())
            _write(self.cfg.accounts_file, self.accounts)

    def get_account(self, aid: str) -> dict | None:
        self._reload_if_changed()
        for a in self.accounts:
            if a["id"] == aid:
                return a
        return None

    def update_account(self, aid: str, **kw) -> dict | None:
        """更新标签 / 启用状态 / cookies / 有效期等；值为 None 的字段跳过。

        传了 cookies_exp 会自动重算 expires_at，不用调用方自己算。
        估算锚点 expiry_anchor 的维护规则（避免有效期被反复虚推）：
          - 读到了 hatch_vml 的真实 expires  -> 清空锚点，直接用真值；
          - 读不到且锚点为空                -> 把锚点钉在当下（只钉一次）；
          - 补入全新会话 cookie（重登）      -> 调用方显式传 expiry_anchor=now 重置。
        """
        with _LOCK:
            for a in self.accounts:
                if a["id"] == aid:
                    for k, v in kw.items():
                        if v is not None:
                            a[k] = v
                    if "cookies_exp" in kw and kw["cookies_exp"] is not None:
                        ce = a["cookies_exp"]
                        if _is_pos(ce.get("hatch_vml")):
                            a["expiry_anchor"] = None
                        elif not a.get("expiry_anchor"):
                            a["expiry_anchor"] = int(time.time())
                        a["expires_at"] = account_expiry(
                            ce, a.get("expiry_anchor") or a.get("created_at"))
                    _write(self.cfg.accounts_file, self.accounts)
                    return a
        return None

    def stats(self) -> dict:
        now = int(time.time())
        total = len(self.accounts)
        enabled = sum(1 for a in self.accounts if a.get("enabled", True))
        bad = sum(1 for a in self.accounts
                  if a.get("enabled", True) and a.get("ok") is False)
        healthy = sum(1 for a in self.accounts
                      if a.get("enabled", True) and a.get("ok") is True)
        expiring = sum(1 for a in self.accounts
                       if a.get("enabled", True)
                       and a.get("expires_at")
                       and a["expires_at"] - now < 3 * 86400)
        expired = sum(1 for a in self.accounts
                      if a.get("enabled", True)
                      and a.get("expires_at") and a["expires_at"] <= now)
        return {"total": total, "enabled": enabled, "disabled": total - enabled,
                "healthy": healthy, "error": bad,
                "expiring": expiring, "expired": expired}

    # ---------- 任务 ----------
    def create_task(self, kind: str, prompt: str) -> dict:
        with _LOCK:
            tid = "task_" + uuid.uuid4().hex[:20]
            t = {"id": tid, "object": "task", "kind": kind, "prompt": prompt,
                 "status": "queued", "created_at": int(time.time()),
                 "updated_at": int(time.time()), "result": None, "error": None}
            self.tasks[tid] = t
            _write(self.cfg.tasks_file, self.tasks)
            return t

    def update_task(self, tid: str, **kw):
        with _LOCK:
            t = self.tasks.get(tid)
            if not t:
                return None
            t.update(kw)
            t["updated_at"] = int(time.time())
            _write(self.cfg.tasks_file, self.tasks)
            return t

    def get_task(self, tid: str) -> dict | None:
        return self.tasks.get(tid)

    def list_tasks(self, limit: int = 50) -> list[dict]:
        items = sorted(self.tasks.values(),
                       key=lambda t: t.get("created_at") or 0, reverse=True)
        return items[:limit]

    def delete_task(self, tid: str) -> bool:
        with _LOCK:
            if tid in self.tasks:
                del self.tasks[tid]
                _write(self.cfg.tasks_file, self.tasks)
                return True
            return False

    def clear_tasks(self, keep: int = 0) -> int:
        with _LOCK:
            items = sorted(self.tasks.values(),
                           key=lambda t: t.get("created_at") or 0, reverse=True)
            keep_ids = {t["id"] for t in items[:keep]}
            removed = len(self.tasks) - len(keep_ids)
            self.tasks = {k: v for k, v in self.tasks.items() if k in keep_ids}
            _write(self.cfg.tasks_file, self.tasks)
            return max(0, removed)
