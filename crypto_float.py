# -*- coding: utf-8 -*-
"""
Market Float Widget（多交易所现货／永续实验版）
- 桌面置顶无边框浮窗，可拖动、边框可拖拽缩放
- 多交易所：币安 / 欧易(OKX) / Bitget，WebSocket 优先、连不上自动降级 REST 轮询
- 添加自选：先选交易所，再搜标的；默认 BTC/ETH/SOL 读币安
- 标的数：下限 3 / 上限 10
- 价格变动闪烁、涨跌着色
- 价格报警（涨破/跌破 + 托盘通知 + 蜂鸣 + 行闪烁）
- 迷你 K 线（双击行打开，多周期，按该币种所属交易所拉取）
- 系统托盘常驻（关窗缩托盘，右键退出）
"""

import sys
import os
import json
import threading
import time
import ssl
import math
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
import urllib.request
from urllib.parse import urlsplit, unquote

from markets import discover, search, Instrument, instrument_label
from market_runtime import install

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QInputDialog, QMessageBox, QMenu, QGraphicsDropShadowEffect,
    QSystemTrayIcon, QButtonGroup, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QCursor, QIcon, QPixmap, QPen, QBrush

import websocket
import json as _json

# ---------------- 全局配置 ----------------
__version__ = "0.2.0-dev"
STALE_SECONDS = 30

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".crypto_float_config.json")
DEFAULT_COINS = [
    {"symbol": "BTC", "exchange": "binance"},
    {"symbol": "ETH", "exchange": "binance"},
    {"symbol": "SOL", "exchange": "binance"},
]
MIN_COINS = 3
MAX_COINS = 10

# 窗口尺寸约束
MIN_W, MAX_W = 320, 580
MIN_H, MAX_H = 250, 640
ROW_H = 46           # 单行高度
ROW_GAP = 4          # 行间距
LAYOUT_BASE = 110    # 标题+表头+页脚等固定高度

# 主题配色（暗色 / 亮色）
THEMES = {
    "dark": {
        "BG": "#161a28", "BG2": "#1e2436", "ROW": "#1a2030", "ROW_HOVER": "#222a40",
        "TEXT": "#e8ecf4", "TEXT_DIM": "#8b93a7", "UP": "#26a69a", "DOWN": "#ef5350",
        "ACCENT": "#5b8cff", "BORDER": "#2a3350",
        "LIVE": "#26a69a", "REST": "#f0a020", "DEAD": "#ef5350",
    },
    "light": {
        "BG": "#eef1f7", "BG2": "#ffffff", "ROW": "#ffffff", "ROW_HOVER": "#e4eaf4",
        "TEXT": "#1c2333", "TEXT_DIM": "#6b7280", "UP": "#0d9c7f", "DOWN": "#e0483e",
        "ACCENT": "#3f6fe8", "BORDER": "#d0d7e2",
        "LIVE": "#0d9c7f", "REST": "#d48806", "DEAD": "#e0483e",
    },
}
THEME = "dark"


def set_theme(name):
    """切换全局配色；此后所有读取 C_* 常量的地方都使用新主题"""
    global THEME, C_BG, C_BG2, C_ROW, C_ROW_HOVER, C_TEXT, C_TEXT_DIM
    global C_UP, C_DOWN, C_ACCENT, C_BORDER, C_LIVE, C_REST, C_DEAD
    THEME = name if name in THEMES else "dark"
    t = THEMES[THEME]
    C_BG, C_BG2, C_ROW, C_ROW_HOVER = t["BG"], t["BG2"], t["ROW"], t["ROW_HOVER"]
    C_TEXT, C_TEXT_DIM = t["TEXT"], t["TEXT_DIM"]
    C_UP, C_DOWN, C_ACCENT, C_BORDER = t["UP"], t["DOWN"], t["ACCENT"], t["BORDER"]
    C_LIVE, C_REST, C_DEAD = t["LIVE"], t["REST"], t["DEAD"]


set_theme("dark")


def menu_style():
    """右键菜单/托盘菜单样式（读取当前主题色）"""
    return f"""
        QMenu {{ background-color: {C_BG2}; color: {C_TEXT};
            border: 1px solid {C_BORDER}; padding: 4px; }}
        QMenu::item {{ padding: 6px 28px; border-radius: 4px; }}
        QMenu::item:selected {{ background-color: {C_ROW_HOVER}; }}
    """


# ---------------- 工具函数 ----------------
def load_config():
    defaults = {"coins": list(DEFAULT_COINS), "pos": None, "alarms": []}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as handle:
            cfg = json.load(handle)
        if not isinstance(cfg, dict):
            return defaults
        raw = cfg.get("coins", [{"symbol": x, "exchange": "binance"}
                                for x in cfg.get("symbols", []) if isinstance(x, str)])
        coins, seen = [], set()
        for coin in raw if isinstance(raw, list) else []:
            if not isinstance(coin, dict):
                continue
            try:
                coin = restore_instrument(coin)
            except (ValueError, TypeError, KeyError):
                continue
            ex, sym = coin.get("exchange"), coin.get("symbol")
            if ex not in EXCHANGES or not isinstance(sym, str):
                continue
            sym = sym.strip().upper()
            key = f"{ex}:{sym}"
            if re.fullmatch(r"[A-Z0-9]{1,24}", sym) and key not in seen:
                coins.append(dict(coin, exchange=ex, symbol=sym))
                seen.add(key)
        for coin in DEFAULT_COINS:
            if len(coins) >= MIN_COINS:
                break
            if coin not in coins:
                coins.append(dict(coin))
        cfg["coins"] = coins[:MAX_COINS]
        valid = {f"{c['exchange']}:{c['symbol']}" for c in cfg["coins"]}
        alarms = []
        for alarm in cfg.get("alarms", []) if isinstance(cfg.get("alarms"), list) else []:
            if isinstance(alarm, dict) and isinstance(alarm.get("instrument"), dict):
                try:
                    restored = restore_instrument(alarm["instrument"])
                    alarm = dict(alarm, exchange=restored["exchange"], symbol=restored["symbol"],
                                 key=f'{restored["exchange"]}:{restored["symbol"]}')
                except (ValueError, KeyError, TypeError):
                    continue
            if not isinstance(alarm, dict):
                continue
            try:
                price = float(alarm.get("price"))
            except (ValueError, TypeError):
                continue
            if (alarm.get("key") in valid and alarm.get("direction") in ("up", "down")
                    and math.isfinite(price) and price > 0):
                ex, sym = alarm["key"].split(":", 1)
                alarms.append(dict(alarm, exchange=ex, symbol=sym, price=price))
        cfg["alarms"] = alarms
        cfg["theme"] = cfg.get("theme") if cfg.get("theme") in THEMES else "dark"
        cfg["always_on_top"] = cfg.get("always_on_top", True) is not False
        return cfg
    except (OSError, ValueError, TypeError):
        return defaults


def save_config(cfg):
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    if "coins" in clean:
        clean["coins"] = [export_instrument(c) for c in clean["coins"]]
    if "alarms" in clean:
        clean["alarms"] = [dict(a, instrument=export_instrument(
            {"exchange": a.get("exchange"), "symbol": a.get("symbol")})) for a in clean["alarms"]]
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False,
                                         dir=os.path.dirname(CONFIG_PATH)) as handle:
            temporary = handle.name
            json.dump(clean, handle, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, CONFIG_PATH)
        return True
    except (OSError, ValueError, TypeError):
        return False
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def format_price(p):
    try:
        p = float(p)
    except Exception:
        return "--"
    if p >= 1000:
        return f"{p:,.2f}"
    elif p >= 1:
        return f"{p:,.2f}"
    elif p >= 0.01:
        return f"{p:,.4f}"
    else:
        return f"{p:,.8f}"


def websocket_proxy_options(url):
    """Use the same Windows HTTPS proxy and bypass rules as REST."""
    host = urlsplit(url).hostname
    proxy = urllib.request.getproxies().get("https")
    if not proxy or not host or urllib.request.proxy_bypass(host):
        return {}
    try:
        endpoint = urlsplit(proxy if "://" in proxy else f"http://{proxy}")
        if endpoint.scheme != "http" or not endpoint.hostname:
            return {}
        options = {"proxy_type": "http", "http_proxy_host": endpoint.hostname,
                   "http_proxy_port": endpoint.port or 80}
        if endpoint.username is not None:
            options["http_proxy_auth"] = (unquote(endpoint.username), unquote(endpoint.password or ""))
        return options
    except ValueError:
        return {}


def http_get_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return _json.loads(resp.read())


# ---------------- 交易所抽象 ----------------
class Exchange:
    """每个交易所的接口适配：WS 订阅、消息解析、REST 校验/轮询、K 线"""
    key = ""
    name = ""
    badge = ""        # 品牌主色（作 badge 背景）
    badge_fg = "#161a28"  # badge 文字色

    def pair(self, symbol):
        return symbol.upper()

    def symbol_from_pair(self, pair):
        return pair

    def ws_setup(self, symbols):
        """返回 (ws_url, subscribe_msg_or_None)"""
        return ("", None)

    def ws_candidates(self, symbols):
        """返回可尝试的 [(ws_url, subscribe_msg_or_None), ...]，按优先级排列；
        前一个端点被网络阻断时自动尝试下一个"""
        return [self.ws_setup(symbols)]

    def parse_ws(self, raw):
        """返回 [(symbol, price, pct, chg), ...]"""
        return []

    def rest_ticker(self, symbol):
        """返回 (price_str, pct_str) 或 None（同时用于校验币种有效性）"""
        return None

    def fetch_klines(self, symbol, interval, limit=60):
        return []

    # 应用周期 -> 交易所周期
    KL_INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}


class BinanceExchange(Exchange):
    key = "binance"
    name = "Binance"
    badge = "#f0b90b"
    badge_fg = "#161a28"
    REST_24H = "https://api.binance.com/api/v3/ticker/24hr?symbol={p}"
    KL = "https://api.binance.com/api/v3/klines?symbol={p}&interval={i}&limit={l}"

    def pair(self, symbol):
        s = symbol.upper()
        return s + "USDT" if not s.endswith("USDT") else s

    def symbol_from_pair(self, pair):
        return pair[:-4] if pair.endswith("USDT") else pair

    def ws_setup(self, symbols):
        streams = "/".join(f"{s.lower()}usdt@ticker" for s in symbols)
        # data-stream.binance.vision 为币安官方纯行情推送端点，无需 API Key，
        # 在部分网络下比 stream.binance.com 更易连通
        return (f"wss://data-stream.binance.vision/stream?streams={streams}", None)

    def ws_candidates(self, symbols):
        streams = "/".join(f"{s.lower()}usdt@ticker" for s in symbols)
        return [
            (f"wss://data-stream.binance.vision/stream?streams={streams}", None),
            (f"wss://stream.binance.com:443/stream?streams={streams}", None),
        ]

    def parse_ws(self, raw):
        try:
            obj = json.loads(raw)
            data = obj.get("data") or obj
            if data.get("e") == "24hrTicker":
                return [(self.symbol_from_pair(data.get("s", "")),
                         data.get("c", ""), data.get("P", "0"), data.get("p", "0"))]
        except Exception:
            return []
        return []

    def rest_ticker(self, symbol):
        try:
            d = http_get_json(self.REST_24H.format(p=self.pair(symbol)), timeout=6)
            return (d.get("lastPrice", ""), d.get("priceChangePercent", "0"))
        except Exception:
            return None

    def fetch_klines(self, symbol, interval, limit=60):
        try:
            return http_get_json(self.KL.format(p=self.pair(symbol),
                                                 i=self.KL_INTERVALS.get(interval, interval),
                                                 l=limit), timeout=8)
        except Exception:
            return []


class OKXExchange(Exchange):
    key = "okx"
    name = "OKX"
    badge = "#2dbd9e"
    badge_fg = "#0a0e1a"
    REST_T = "https://www.okx.com/api/v5/market/ticker?instId={p}"
    KL = "https://www.okx.com/api/v5/market/candles?instId={p}&bar={i}&limit={l}"
    KL_INTERVALS = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}

    def pair(self, symbol):
        s = symbol.upper()
        return s + "-USDT" if not s.endswith("-USDT") else s

    def symbol_from_pair(self, pair):
        return pair.split("-")[0] if "-" in pair else pair

    def ws_setup(self, symbols):
        args = [{"channel": "tickers", "instId": self.pair(s)} for s in symbols]
        return ("wss://ws.okx.com/ws/v5/public",
                {"op": "subscribe", "args": args})

    def ws_candidates(self, symbols):
        args = [{"channel": "tickers", "instId": self.pair(s)} for s in symbols]
        sub = {"op": "subscribe", "args": args}
        return [
            ("wss://ws.okx.com/ws/v5/public", sub),
            
        ]

    def parse_ws(self, raw):
        try:
            obj = json.loads(raw)
            if (obj.get("arg") or {}).get("channel", obj.get("channel")) == "tickers" and obj.get("data"):
                out = []
                for d in obj["data"]:
                    last = d.get("last", "")
                    o24 = d.get("open24h", "")
                    try:
                        pct = f"{(float(last) - float(o24)) / float(o24) * 100:.4f}" if o24 else "0"
                    except Exception:
                        pct = "0"
                    out.append((self.symbol_from_pair(d.get("instId", "")), last, pct, "0"))
                return out
        except Exception:
            return []
        return []

    def rest_ticker(self, symbol):
        try:
            d = http_get_json(self.REST_T.format(p=self.pair(symbol)), timeout=6)
            if d.get("code") == "0" and d.get("data"):
                t = d["data"][0]
                last = t.get("last", "")
                o24 = t.get("open24h", "")
                try:
                    pct = f"{(float(last) - float(o24)) / float(o24) * 100:.4f}" if o24 else "0"
                except Exception:
                    pct = "0"
                return (last, pct)
        except Exception:
            return None

    def fetch_klines(self, symbol, interval, limit=60):
        try:
            d = http_get_json(self.KL.format(p=self.pair(symbol),
                                             i=self.KL_INTERVALS.get(interval, interval),
                                             l=limit), timeout=8)
            arr = d.get("data", []) if isinstance(d, dict) else d
            arr = sorted(arr, key=lambda x: int(x[0]))  # 由旧到新
            return arr
        except Exception:
            return []


class BitgetExchange(Exchange):
    key = "bitget"
    name = "Bitget"
    badge = "#00f0d4"
    badge_fg = "#0a0e1a"
    REST_T = "https://api.bitget.com/api/v2/spot/market/tickers?symbol={p}"
    KL = "https://api.bitget.com/api/v2/spot/market/candles?symbol={p}&granularity={i}&limit={l}"
    KL_INTERVALS = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "4h": "4h", "1d": "1day"}

    def pair(self, symbol):
        s = symbol.upper()
        return s + "USDT" if not s.endswith("USDT") else s

    def symbol_from_pair(self, pair):
        return pair[:-4] if pair.endswith("USDT") else pair

    def ws_setup(self, symbols):
        args = [{"instType": "SPOT", "channel": "ticker", "instId": self.pair(s)} for s in symbols]
        return ("wss://ws.bitget.com/v2/ws/public",
                {"op": "subscribe", "args": args})

    def parse_ws(self, raw):
        try:
            obj = json.loads(raw)
            channel = (obj.get("arg") or {}).get("channel", obj.get("channel"))
            if channel in (None, "ticker") and not obj.get("event") and obj.get("data"):
                out = []
                data = obj["data"] if isinstance(obj["data"], list) else [obj["data"]]
                for d in data:
                    last = d.get("lastPr", "")
                    if not last:
                        continue
                    chg = d.get("change24h", "0")
                    try:
                        pct = f"{float(chg) * 100:.4f}"
                    except Exception:
                        pct = "0"
                    inst = d.get("instId") or d.get("symbol") or obj.get("arg", {}).get("instId", "")
                    out.append((self.symbol_from_pair(inst), last, pct, "0"))
                return out
        except Exception:
            return []
        return []

    def rest_ticker(self, symbol):
        try:
            d = http_get_json(self.REST_T.format(p=self.pair(symbol)), timeout=6)
            if d.get("code") == "00000" and d.get("data"):
                t = d["data"][0]
                last = t.get("lastPr", "")
                chg = t.get("change24h", "0")
                try:
                    pct = f"{float(chg) * 100:.4f}"
                except Exception:
                    pct = "0"
                return (last, pct)
        except Exception:
            return None

    def fetch_klines(self, symbol, interval, limit=60):
        try:
            d = http_get_json(self.KL.format(p=self.pair(symbol),
                                             i=self.KL_INTERVALS.get(interval, interval),
                                             l=limit), timeout=8)
            arr = d.get("data", []) if isinstance(d, dict) else d
            arr = sorted(arr, key=lambda x: int(x[0]))  # 由旧到新
            return arr
        except Exception:
            return []


EXCHANGES = {
    "binance": BinanceExchange(),
    "okx": OKXExchange(),
    "bitget": BitgetExchange(),
}
EXCHANGE_ORDER = ["binance", "okx", "bitget"]
install(globals())


def make_tray_icon():
    pix = QPixmap(64, 64)
    pix.fill(QColor(C_BG))
    p = QPainter(pix)
    p.setPen(QColor(C_ACCENT))
    p.setFont(QFont("Arial", 36, QFont.Bold))
    p.drawText(pix.rect(), Qt.AlignCenter, "$")
    p.end()
    return QIcon(pix)


# ---------------- 行情 Worker（每交易所一个，WS 优先 + REST 兜底）----------------
class MarketWorker(threading.Thread):
    def __init__(self, exchange, symbols, on_ticker, on_status):
        super().__init__(daemon=True)
        self.exchange = exchange
        self.symbols = list(symbols)
        self.on_ticker = on_ticker    # (symbol, price, pct, chg)
        self.on_status = on_status    # ("live"|"rest"|"down")
        self._ws = None
        self._stopping = False
        self._lock = threading.Lock()
        self._pending = None
        self._connected = False
        self._opened = False
        self._latest = {}
        self.mode = "ws"   # "ws" | "rest"

    def update_symbols(self, symbols):
        with self._lock:
            self._pending = list(symbols)
            try:
                if self._ws:
                    self._ws.close()
            except Exception:
                pass

    def stop(self):
        self._stopping = True
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass

    def run(self):
        while not self._stopping:
            with self._lock:
                if self._pending is not None:
                    self.symbols = self._pending
                    self._pending = None
                    self.mode = "ws"   # 切换后重试 WS
            syms = list(self.symbols)
            if not syms:
                time.sleep(1)
                continue

            if self.mode != "rest":
                connected = self._try_ws(syms)
                if not connected:
                    self.mode = "rest"
                    self.on_status("down")
                # 已连接过又断开 -> mode 仍为 ws，外层循环重连
            if self.mode == "rest":
                self._poll_rest(syms)
                # 轮询一段时间后回到外层重试 WS（否则会永久停在轮询）
                with self._lock:
                    if self._pending is None:
                        self.mode = "ws"
            if self._stopping:
                break
            time.sleep(1.5)

    def force_reconnect(self):
        """供刷新按钮调用：立即重连 WS 并重置为实时模式"""
        with self._lock:
            self._pending = list(self.symbols)
            self.mode = "ws"
            try:
                if self._ws:
                    self._ws.close()
            except Exception:
                pass

    def _try_ws(self, syms):
        """按优先级依次尝试 WS 端点，任一连通即返回 True"""
        for url, sub in self.exchange.ws_candidates(syms):
            if self._stopping:
                return False
            if not url:
                continue
            self._connected = False
            self._opened = False

            def on_open(ws, _sub=sub):
                self._opened = True
                self._latest = {}
                self.on_status("down")
                if _sub:
                    try:
                        ws.send(json.dumps(_sub))
                    except Exception:
                        pass

            def on_msg(ws, message):
                # 处理 OKX/Bitget 的文本 ping
                try:
                    if isinstance(message, str) and message.strip() == "ping":
                        ws.send("pong")
                        return
                except Exception:
                    pass
                if message == "pong":
                    return
                try:
                    obj = json.loads(message)
                    if obj.get("event") == "error":
                        self._connected = False
                        ws.close()
                        return
                except (ValueError, AttributeError):
                    return
                for t in self.exchange.parse_ws(message):
                    try:
                        price, pct = float(t[1]), float(t[2])
                        if not math.isfinite(price) or price <= 0 or not math.isfinite(pct):
                            continue
                    except (ValueError, TypeError):
                        continue
                    self._latest[t[0]] = time.monotonic()
                    self.on_ticker(*t)
                if all(time.monotonic() - self._latest.get(s, 0) < STALE_SECONDS for s in syms):
                    self._connected = True
                    self.on_status("live")

            def on_err(ws, e):
                self.on_status("down")

            def on_close(ws, code, msg):
                self.on_status("down")

            # 连接超时看门狗：9s 内未握手成功则强制中断，切换到下一个端点
            watchdog = threading.Timer(9.0, self._abort_pending)
            watchdog.daemon = True
            watchdog.start()
            monitor_done = threading.Event()
            monitor_thread = None
            def monitor():
                opened_at = time.monotonic()
                heartbeat_at = opened_at
                while not monitor_done.wait(2):
                    if self._stopping:
                        return
                    now = time.monotonic()
                    if now - opened_at > STALE_SECONDS and any(
                            now - self._latest.get(s, opened_at) > STALE_SECONDS for s in syms):
                        self._connected = False
                        self.on_status("down")
                        if self._ws:
                            self._ws.close()
                        return
                    if self._opened and self.exchange.key.split("|")[0] in ("okx", "bitget") and now - heartbeat_at >= 15:
                        try:
                            self._ws.send("ping")
                        except Exception:
                            return
                        heartbeat_at = now
            try:
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=on_open, on_message=on_msg,
                    on_error=on_err, on_close=on_close,
                )
                monitor_thread = threading.Thread(target=monitor, daemon=True)
                monitor_thread.start()
                # Always verify the exchange certificate and hostname.
                self._ws.run_forever(
                    ping_interval=15, ping_timeout=8,
                    sslopt={"cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True},
                    **websocket_proxy_options(url),
                )
            except Exception:
                pass
            finally:
                monitor_done.set()
                watchdog.cancel()
                if monitor_thread:
                    monitor_thread.join(timeout=1)
            if self._connected:
                return True
            # 该端点不通，继续尝试下一个
        return False

    def _abort_pending(self):
        """握手未成功则主动关闭当前 WS，避免卡在超长等待上"""
        if not self._opened:
            try:
                if self._ws:
                    self._ws.close()
            except Exception:
                pass

    def _poll_rest(self, syms):
        """REST 轮询 24 轮（每轮请求耗时 + 2.5s），之后重试 WS。"""
        for _ in range(24):
            if self._stopping:
                return
            with self._lock:
                if self._pending is not None:
                    self.symbols = self._pending
                    self._pending = None
                    return   # 外层重连
                cur = list(self.symbols)
            successful = 0
            with ThreadPoolExecutor(max_workers=MAX_COINS) as pool:
                results = list(pool.map(self.exchange.rest_ticker, cur))
            for symbol, result in zip(cur, results):
                if self._stopping:
                    return
                if result:
                    try:
                        price, pct = float(result[0]), float(result[1])
                        if math.isfinite(price) and price > 0 and math.isfinite(pct):
                            self.on_ticker(symbol, result[0], result[1], "0")
                            successful += 1
                    except (ValueError, TypeError):
                        pass
            self.on_status("rest" if successful == len(cur) else "down")
            # 分段睡眠 2.5s
            for _ in range(25):
                if self._stopping:
                    return
                time.sleep(0.1)


# ---------------- K 线蜡烛图 ----------------
class KlineChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.klines = []
        self.setMinimumHeight(140)
        self.restyle()

    def restyle(self):
        """主题切换后重刷样式与画面"""
        self.setStyleSheet(f"background-color: {C_ROW}; border-radius: 8px;")
        self.update()

    def set_klines(self, klines):
        self.klines = klines
        self.update()

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if not self.klines:
            painter.setPen(QColor(C_TEXT_DIM))
            painter.setFont(QFont("", 9))
            painter.drawText(self.rect(), Qt.AlignCenter, "加载中…")
            return

        ml, mr, mt, mb = 6, 56, 10, 8
        cw, ch = w - ml - mr, h - mt - mb
        highs = [float(k[2]) for k in self.klines]
        lows = [float(k[3]) for k in self.klines]
        pmax, pmin = max(highs), min(lows)
        prange = pmax - pmin
        if prange == 0:
            prange = max(abs(pmax) * 0.01, 0.0001)
        pmax += prange * 0.08
        pmin -= prange * 0.08
        prange = pmax - pmin

        n = len(self.klines)
        step = cw / n
        candle_w = max(2, step * 0.6)

        def y(p):
            return mt + ch - (p - pmin) / prange * ch

        painter.setPen(QPen(QColor(C_BORDER), 1, Qt.DashLine))
        for i in range(4):
            gy = int(mt + ch * i / 3)
            painter.drawLine(ml, gy, ml + cw, gy)

        painter.setPen(QColor(C_TEXT_DIM))
        painter.setFont(QFont("Consolas", 7))
        for i in range(4):
            price = pmax - prange * i / 3
            painter.drawText(ml + cw + 4, int(y(price)) + 4, format_price(price))

        for i, k in enumerate(self.klines):
            o, hi, lo, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
            x = ml + i * step + step / 2
            up = c >= o
            color = QColor(C_UP) if up else QColor(C_DOWN)
            painter.setPen(QPen(color, 1))
            painter.drawLine(QPoint(int(x), int(y(hi))), QPoint(int(x), int(y(lo))))
            body_top = y(max(o, c))
            body_bot = y(min(o, c))
            body_h = max(1, body_bot - body_top)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(int(x - candle_w / 2), int(body_top), int(candle_w), int(body_h))

        last = float(self.klines[-1][4])
        painter.setPen(QPen(QColor(C_ACCENT), 1, Qt.DashLine))
        painter.drawLine(ml, int(y(last)), ml + cw, int(y(last)))
        painter.setPen(QColor(C_ACCENT))
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.drawText(ml + cw + 4, int(y(last)) + 4, format_price(last))


class KlineWindow(QWidget):
    klines_ready = Signal(int, str, list)
    closed_signal = Signal(str)

    INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]

    def __init__(self, exchange, symbol):
        super().__init__()
        self.exchange = exchange
        self.symbol = symbol.upper()
        self.pair = exchange.pair(self.symbol)
        self.interval = "15m"
        self._request_id = 0
        self._closed = False
        self._drag = None
        self.setWindowTitle(f"{exchange.name} · {self.pair} · K-line")

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(380, 260)

        self._container = QWidget(self)
        self._container.setObjectName("kw")
        container = self._container
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(container)

        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        tb = QWidget()
        tb.setFixedHeight(34)
        hl = QHBoxLayout(tb)
        hl.setContentsMargins(12, 0, 8, 0)
        title = QLabel(f"📊 {self.exchange.name} · {self.pair}")
        self._title_lbl = title
        hl.addWidget(title)
        hl.addStretch()
        close = QPushButton("✕")
        close.setFixedSize(22, 22)
        close.setCursor(Qt.PointingHandCursor)
        self._close_btn = close
        close.clicked.connect(self.close)
        hl.addWidget(close)
        v.addWidget(tb)

        ib = QWidget()
        ib.setFixedHeight(28)
        il = QHBoxLayout(ib)
        il.setContentsMargins(10, 0, 10, 0)
        il.setSpacing(4)
        self.btn_group = QButtonGroup(self)
        self._iv_btns = []
        for iv in self.INTERVALS:
            b = QPushButton(iv)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(22)
            b.clicked.connect(lambda _, i=iv: self._change_interval(i))
            self.btn_group.addButton(b)
            self._iv_btns.append(b)
            il.addWidget(b)
            if iv == self.interval:
                b.setChecked(True)
        il.addStretch()
        v.addWidget(ib)

        self.chart = KlineChart()
        v.addWidget(self.chart)

        self.status = QLabel("加载中…")
        fl = QHBoxLayout()
        fl.setContentsMargins(12, 4, 12, 8)
        fl.addWidget(self.status)
        fl.addStretch()
        v.addLayout(fl)

        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(24)
        eff.setColor(QColor(0, 0, 0, 150))
        eff.setOffset(0, 3)
        container.setGraphicsEffect(eff)

        self.klines_ready.connect(self._on_klines)
        self.restyle()
        self._fetch()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._fetch)
        self.timer.start(30000)

    def _change_interval(self, iv):
        self.interval = iv
        self.chart.set_klines([])
        self.status.setText("加载中…")
        self._fetch()

    def _fetch(self):
        self.status.setText(f"刷新中… ({self.interval})")

        self._request_id += 1
        request_id, interval = self._request_id, self.interval
        def work():
            data = self.exchange.fetch_klines(self.symbol, interval, 60)
            self.klines_ready.emit(request_id, interval, data)
        threading.Thread(target=work, daemon=True).start()

    def _on_klines(self, request_id, interval, data):
        if self._closed or request_id != self._request_id or interval != self.interval:
            return
        try:
            data = [k for k in data if len(k) >= 5 and all(
                math.isfinite(float(v)) and float(v) > 0 for v in k[1:5])]
        except (ValueError, TypeError):
            data = []
        if not data:
            self.status.setText("加载失败（{0}）".format(self.exchange.name))
            return
        self.chart.set_klines(data)
        last = float(data[-1][4])
        self.status.setText(f"最新: {format_price(last)}  · {self.interval}  · {self.exchange.name}  · 30s 刷新")

    def restyle(self):
        """主题切换后重刷 K 线窗口所有样式"""
        self._container.setStyleSheet(f"""
            QWidget#kw {{
                background-color: {C_BG};
                border: 1px solid {C_BORDER};
                border-radius: 12px;
            }}
        """)
        self._title_lbl.setStyleSheet(f"color:{C_TEXT}; font-size:12px; font-weight:700;")
        self._close_btn.setStyleSheet(f"""
            QPushButton {{ background-color:{C_BG2}; color:{C_TEXT};
                border:1px solid {C_BORDER}; border-radius:5px; font-size:11px; }}
            QPushButton:hover {{ background-color:#c0392b; color:#fff; }}
        """)
        for b in self._iv_btns:
            b.setStyleSheet(f"""
                QPushButton {{ background-color:{C_BG2}; color:{C_TEXT_DIM};
                    border:1px solid {C_BORDER}; border-radius:4px;
                    padding:0 8px; font-size:10px; font-weight:600; }}
                QPushButton:checked {{ background-color:{C_ACCENT}; color:#fff; }}
            """)
        self.status.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
        self.chart.restyle()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag = None
        e.accept()

    def closeEvent(self, e):
        self._closed = True
        self._request_id += 1
        self.timer.stop()
        self.closed_signal.emit(f"{self.exchange.key}:{self.symbol}")
        e.accept()


# ---------------- 单行行情 ----------------
class CoinRow(QWidget):
    show_kline = Signal(object, str)   # exchange, symbol

    def __init__(self, exchange, symbol, parent=None):
        super().__init__(parent)
        self.exchange = exchange
        self.symbol = symbol.upper()
        self.pair = exchange.pair(self.symbol)
        self.last_price = None
        self.last_update = 0
        self._flash_color = None
        self._flash_until = 0
        self._last_pct = None

        self.setFixedHeight(ROW_H)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("row")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(6)

        item = getattr(self.exchange, "instrument", None)
        label = self.symbol
        if item:
            label += " S" if item.market == "spot" else " P"
            if item.category in ("equity_derivative", "rwa_derivative"):
                label += " ETF" if item.category == "equity_derivative" else " RWA"
        self.sym_label = QLabel(label)
        if item:
            self.sym_label.setToolTip(f"{item.instrument_id} · {item.market_type} · Last Price · 合约报价，不是 ETF 现货；无新数据时标记过期")
        self.sym_label.setMinimumWidth(48)

        self.ex_label = QLabel(self.exchange.name)
        self.ex_label.setAlignment(Qt.AlignCenter)
        self.ex_label.setStyleSheet(
            f"color:{self.exchange.badge_fg}; font-size:9px; font-weight:800;"
            f"background-color:{self.exchange.badge}; border-radius:3px;"
            f"padding:2px 6px;")
        self.ex_label.setFixedHeight(16)
        self.ex_label.setMinimumWidth(44)

        self.alarm_label = QLabel("")
        self.alarm_label.setVisible(False)

        self.price_label = QLabel("--")
        self.price_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.pct_label = QLabel("--")
        self.pct_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        lay.addWidget(self.sym_label)
        lay.addWidget(self.ex_label)
        lay.addWidget(self.alarm_label)
        lay.addStretch()
        lay.addWidget(self.price_label)
        lay.addSpacing(8)
        lay.addWidget(self.pct_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(60)
        self.restyle()

    def restyle(self):
        """主题切换后重刷行样式"""
        self.setStyleSheet(f"""
            QWidget#row {{
                background-color: {C_ROW};
                border: none;
                border-radius: 8px;
            }}
            QWidget#row:hover {{
                background-color: {C_ROW_HOVER};
            }}
        """)
        self.sym_label.setStyleSheet(f"color:{C_TEXT}; font-weight:600; font-size:13px;")
        self.price_label.setStyleSheet(f"color:{C_TEXT}; font-family:'Consolas','Courier New'; font-size:13px;")
        self.alarm_label.setStyleSheet(f"color:{C_ACCENT}; font-size:11px;")
        if self._last_pct is None:
            self.pct_label.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:12px; font-weight:600;")
        else:
            color = C_UP if self._last_pct >= 0 else C_DOWN
            self.pct_label.setStyleSheet(f"color:{color}; font-size:12px; font-weight:700;")

    def set_data(self, price, pct):
        try:
            p = float(price)
            percentage = float(pct)
            if not math.isfinite(p) or p <= 0 or not math.isfinite(percentage):
                return False
        except Exception:
            return False
        if p is not None and self.last_price is not None:
            if p > self.last_price:
                self._flash_color = C_UP
                self._flash_until = time.time() + 0.5
            elif p < self.last_price:
                self._flash_color = C_DOWN
                self._flash_until = time.time() + 0.5
        if p is not None and math.isfinite(p) and p > 0:
            self.last_price = p
            self.last_update = time.monotonic()
        self.price_label.setText(format_price(price))
        try:
            f = float(pct)
        except Exception:
            f = 0.0
        self._last_pct = f
        arrow = "▲" if f >= 0 else "▼"
        color = C_UP if f >= 0 else C_DOWN
        self.pct_label.setText(f"{arrow} {abs(f):.2f}%")
        self.pct_label.setStyleSheet(f"color:{color}; font-size:12px; font-weight:700;")
        return True

    def set_alarm_indicator(self, active):
        self.alarm_label.setText("🔔" if active else "")
        self.alarm_label.setVisible(active)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.show_kline.emit(self.exchange, self.symbol)
            e.accept()

    def paintEvent(self, e):
        if self._flash_color and time.time() < self._flash_until:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            col = QColor(self._flash_color)
            col.setAlpha(55)
            painter.setBrush(col)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 8, 8)
        super().paintEvent(e)


# ---------------- 缩放手柄 ----------------
class ResizeGrip(QLabel):
    """右下角缩放手柄（纯视觉提示，鼠标事件穿透到父窗口统一处理）"""
    def __init__(self, parent):
        super().__init__("⇲", parent)
        self.setCursor(Qt.SizeFDiagCursor)
        self.restyle()
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def restyle(self):
        self.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:13px; padding:0 2px;")


# ---------------- 主浮窗 ----------------
class CryptoFloat(QWidget):
    ticker_signal = Signal(str, str, str, str, str)  # exchange_key, symbol, price, pct, chg
    status_signal = Signal(str, str)                   # exchange_key, mode
    migration_ready = Signal(object)
    catalog_ready = Signal(object, str)
    coin_validated = Signal(str, str, bool)
    refresh_done_signal = Signal(str)                  # 完成提示文案

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.coins = list(self.cfg.get("coins") or DEFAULT_COINS)
        self.alarms = list(self.cfg.get("alarms", []))
        set_theme(self.cfg.get("theme", "dark"))   # 恢复上次选择的主题
        self.rows = {}            # key "exchange:symbol" -> CoinRow
        self.workers = {}          # exchange_key -> MarketWorker
        self.kline_windows = {}
        self._drag_offset = None
        self.tray = None
        self._really_quitting = False
        self._resizing = False
        self._resize_mode = ""
        self._resize_start_global = None
        self._resize_start_geom = None
        self._tray_menu = None
        self._title_color = C_TEXT
        self._status_color = C_TEXT_DIM
        self.setWindowTitle(f"Market Float Widget v{__version__}")

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(MIN_W, MIN_H)
        self.setMaximumSize(MAX_W, MAX_H)
        self.setMouseTracking(True)   # hover 时切换边缘缩放光标

        self._build_ui()
        self._apply_shadow()
        self._build_tray()

        for c in self.coins:
            self._add_row(c["exchange"], c["symbol"], persist=False)

        self.ticker_signal.connect(self._on_ticker)
        self.status_signal.connect(self._on_status)
        self.refresh_done_signal.connect(self._on_refresh_done)

        self.alarm_timer = QTimer(self)
        self.alarm_timer.timeout.connect(self._check_alarms)
        self.alarm_timer.start(2000)
        self.coin_validated.connect(self._finish_add_coin)
        self.catalog_ready.connect(self._show_catalog)
        self.migration_ready.connect(self._apply_legacy_migration)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._render_status)
        self.status_timer.start(1000)
        self._sync_workers()
        if not self.cfg.get("always_on_top", True):
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.pin_btn.setText("置顶✓" if self.cfg.get("always_on_top", True) else "置顶")

        # 初始尺寸适配行数（至少 3 行）
        self.resize(self.width() if self.width() >= MIN_W else 380,
                    self._needed_height(len(self.rows)))

        # 恢复位置；换电脑/换分辨率后旧坐标可能落在屏幕外，做一次可见性校正
        pos = self.cfg.get("pos")
        if pos and len(pos) == 2:
            try:
                p = QPoint(*pos)
                scr = QApplication.primaryScreen().availableGeometry()
                p.setX(max(scr.left(), min(p.x(), scr.right() - self.width() + 1)))
                p.setY(max(scr.top(), min(p.y(), scr.bottom() - self.height() + 1)))
                self.move(p)
            except Exception:
                self.move(QPoint(60, 60))
        else:
            self.move(QPoint(60, 60))

    # ---------- UI ----------
    def _build_ui(self):
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet(f"""
            QWidget#container {{
                background-color: {C_BG};
                border: 1px solid {C_BORDER};
                border-radius: 14px;
            }}
        """)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.addWidget(self.container)

        v = QVBoxLayout(self.container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 标题栏
        title_bar = QWidget()
        title_bar.setFixedHeight(38)
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(14, 0, 10, 0)
        tb.setSpacing(6)

        self.title = QLabel("● 行情浮窗")
        self.title.setStyleSheet(f"color:{C_TEXT}; font-size:13px; font-weight:700;")
        tb.addWidget(self.title)
        tb.addStretch()

        self.pin_btn = QPushButton("置顶")
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setStyleSheet(self._btn_style(C_BG2))
        self.pin_btn.setFixedHeight(24)
        self.pin_btn.clicked.connect(self._toggle_pin)
        tb.addWidget(self.pin_btn)

        # 主题切换：暗色 ⇄ 亮色
        self.theme_btn = QPushButton("☀" if THEME == "light" else "🌙")
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setToolTip("切换到暗色主题" if THEME == "light" else "切换到亮色主题")
        self.theme_btn.setStyleSheet(self._btn_style(C_BG2))
        self.theme_btn.setFixedHeight(24)
        self.theme_btn.clicked.connect(self._toggle_theme)
        tb.addWidget(self.theme_btn)

        self.add_btn = QPushButton("＋ 自选")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setStyleSheet(self._btn_style(C_ACCENT, fg="#ffffff"))
        self.add_btn.setFixedHeight(24)
        self.add_btn.clicked.connect(self._on_add_coin)
        tb.addWidget(self.add_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet(self._btn_style("#c0392b", fg="#ffffff"))
        self.close_btn.clicked.connect(self._on_close)
        tb.addWidget(self.close_btn)

        v.addWidget(title_bar)

        # 表头
        header = QWidget()
        header.setFixedHeight(24)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 12, 0)
        hl.setSpacing(8)
        self._h_sym = QLabel("币种")
        self._h_sym.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        self._h_price = QLabel("价格 (USDT)")
        self._h_price.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._h_price.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        self._h_pct = QLabel("24H")
        self._h_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._h_pct.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        hl.addWidget(self._h_sym)
        hl.addStretch()
        hl.addWidget(self._h_price)
        hl.addSpacing(8)
        hl.addWidget(self._h_pct)
        v.addWidget(header)

        # 行情列表（可滚动）
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: {C_ROW}; width: 6px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {C_BORDER}; border-radius: 3px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(inner)
        self.list_layout.setContentsMargins(6, 0, 6, 4)
        self.list_layout.setSpacing(ROW_GAP)
        self.list_layout.addStretch()
        self.scroll.setWidget(inner)
        v.addWidget(self.scroll, 1)

        # 页脚
        footer_w = QWidget()
        footer_w.setFixedHeight(30)
        footer = QHBoxLayout(footer_w)
        footer.setContentsMargins(14, 4, 6, 6)
        footer.setSpacing(8)
        # 左下角刷新按钮：立即拉取最新行情并强制重连 WS
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setFixedSize(20, 18)
        self.refresh_btn.setToolTip("立即刷新行情并重连实时推送")
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_ACCENT};
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                font-size: 12px;
                font-weight: 700;
                padding: 0;
            }}
            QPushButton:hover {{ background-color: {C_ROW_HOVER}; color: {C_TEXT}; }}
            QPushButton:pressed {{ background-color: {C_ACCENT}; color: #ffffff; }}
            QPushButton:disabled {{ color: {C_TEXT_DIM}; }}
        """)
        self.refresh_btn.clicked.connect(self._on_refresh)
        footer.addWidget(self.refresh_btn)
        self.status_label = QLabel("连接中…")
        self.status_label.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        footer.addWidget(self.status_label)
        footer.addStretch()
        self.hint_label = QLabel("双击看K线 · 右键菜单")
        self.hint_label.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        footer.addWidget(self.hint_label)
        self.grip = ResizeGrip(self.container)
        footer.addWidget(self.grip)
        v.addWidget(footer_w)

        # 递归开启鼠标跟踪，使 hover 事件冒泡到主窗口以切换缩放光标
        self.container.setMouseTracking(True)
        for _w in self.container.findChildren(QWidget):
            _w.setMouseTracking(True)

    def _apply_shadow(self):
        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(30)
        eff.setColor(QColor(0, 0, 0, 160))
        eff.setOffset(0, 4)
        self.container.setGraphicsEffect(eff)

    def _btn_style(self, bg, fg=None):
        if fg is None:
            fg = C_TEXT
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {C_ROW_HOVER}; }}
        """

    def _needed_height(self, n):
        return max(MIN_H, min(MAX_H, LAYOUT_BASE + n * (ROW_H + ROW_GAP)))

    # ---------- 主题切换 ----------
    def _toggle_theme(self):
        set_theme("light" if THEME == "dark" else "dark")
        self.cfg["theme"] = THEME
        self._persist()
        self.restyle()

    def restyle(self):
        """主题切换后重刷主窗口、行情行、K 线窗口与托盘菜单"""
        self.container.setStyleSheet(f"""
            QWidget#container {{
                background-color: {C_BG};
                border: 1px solid {C_BORDER};
                border-radius: 14px;
            }}
        """)
        self.title.setStyleSheet(f"color:{self._title_color}; font-size:13px; font-weight:700;")
        self.pin_btn.setStyleSheet(self._btn_style(C_BG2))
        self.theme_btn.setText("☀" if THEME == "light" else "🌙")
        self.theme_btn.setToolTip("切换到暗色主题" if THEME == "light" else "切换到亮色主题")
        self.theme_btn.setStyleSheet(self._btn_style(C_BG2))
        self.add_btn.setStyleSheet(self._btn_style(C_ACCENT, fg="#ffffff"))
        self.close_btn.setStyleSheet(self._btn_style("#c0392b", fg="#ffffff"))
        for lbl in (self._h_sym, self._h_price, self._h_pct):
            lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background: {C_ROW}; width: 6px; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {C_BORDER}; border-radius: 3px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {C_ACCENT};
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                font-size: 12px;
                font-weight: 700;
                padding: 0;
            }}
            QPushButton:hover {{ background-color: {C_ROW_HOVER}; color: {C_TEXT}; }}
            QPushButton:pressed {{ background-color: {C_ACCENT}; color: #ffffff; }}
            QPushButton:disabled {{ color: {C_TEXT_DIM}; }}
        """)
        self.status_label.setStyleSheet(f"color:{self._status_color}; font-size:11px; font-weight:600;")
        self.hint_label.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        self.grip.restyle()
        for row in self.rows.values():
            row.restyle()
        for w in self.kline_windows.values():
            w.restyle()
        if self._tray_menu is not None:
            self._tray_menu.setStyleSheet(menu_style())
        if self.tray is not None:
            self.tray.setIcon(make_tray_icon())

    # ---------- 系统托盘 ----------
    def _build_tray(self):
        self.tray = QSystemTrayIcon(make_tray_icon(), self)
        menu = QMenu()
        menu.setStyleSheet(menu_style())
        self._tray_menu = menu

        a_show = QAction("显示浮窗", self)
        a_show.triggered.connect(self._show_window)
        menu.addAction(a_show)

        a_add = QAction("添加自选…", self)
        a_add.triggered.connect(self._on_add_coin)
        menu.addAction(a_add)

        menu.addSeparator()

        a_alarms = QAction("查看报警", self)
        a_alarms.triggered.connect(self._show_alarms)
        menu.addAction(a_alarms)

        a_clear = QAction("清除所有报警", self)
        a_clear.triggered.connect(self._clear_alarms)
        menu.addAction(a_clear)

        menu.addSeparator()

        a_quit = QAction("退出", self)
        a_quit.triggered.connect(self._quit)
        menu.addAction(a_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------- 行管理 ----------
    def _row_key(self, exchange_key, symbol):
        return f"{exchange_key}:{symbol.upper()}"

    def _add_row(self, exchange_key, symbol, persist=True):
        ex = EXCHANGES.get(exchange_key)
        if not ex:
            return
        sym = symbol.upper()
        key = self._row_key(exchange_key, sym)
        if key in self.rows:
            return
        row = CoinRow(ex, sym)
        row.show_kline.connect(self._open_kline)
        row.setContextMenuPolicy(Qt.CustomContextMenu)
        row.customContextMenuRequested.connect(lambda _, k=key: self._row_menu(k))
        self.list_layout.insertWidget(self.list_layout.count() - 1, row)
        self.rows[key] = row
        if persist:
            if not any(c["exchange"] == exchange_key and c["symbol"] == sym for c in self.coins):
                self.coins.append({"exchange": exchange_key, "symbol": sym})
            self._persist()
        self._update_alarm_indicator(key)
        # 自适应高度（只增不减，不超过上限）
        need = self._needed_height(len(self.rows))
        if self.height() < need:
            self.resize(self.width(), need)

    def _row_menu(self, key):
        row = self.rows.get(key)
        if not row:
            return
        ex = row.exchange
        sym = row.symbol
        menu = QMenu(self)
        menu.setStyleSheet(menu_style())
        a_kline = QAction(f"📈 查看 K 线 ({ex.name})", self)
        a_kline.triggered.connect(lambda: self._open_kline(ex, sym))
        menu.addAction(a_kline)
        a_alarm = QAction("🔔 设置价格报警", self)
        a_alarm.triggered.connect(lambda: self._set_alarm(ex, sym, key))
        menu.addAction(a_alarm)
        menu.addSeparator()
        a_del = QAction("✕ 删除该标的", self)
        a_del.triggered.connect(lambda: self._remove_coin(key))
        menu.addAction(a_del)
        menu.exec(QCursor.pos())

    def _remove_coin(self, key):
        if len(self.rows) <= MIN_COINS:
            QMessageBox.information(self, "无法删除", f"至少保留 {MIN_COINS} 个标的。")
            return
        row = self.rows.pop(key, None)
        if row:
            ex_key, sym = key.split(":", 1)
            row.setParent(None)
            row.deleteLater()
            self.coins = [c for c in self.coins
                          if not (c["exchange"] == ex_key and c["symbol"] == sym)]
            self.alarms = [a for a in self.alarms if a.get("key") != key]
            self._persist()
            self._sync_workers()

    def _persist(self):
        self.cfg["coins"] = list(self.coins)
        self.cfg["alarms"] = list(self.alarms)
        self.cfg["pos"] = [self.pos().x(), self.pos().y()]
        if not save_config(self.cfg):
            self.tray.showMessage("配置保存失败", "请检查用户目录写入权限；本次设置未保存。",
                                  QSystemTrayIcon.Warning, 4000)

    def resolve_legacy_instruments(self):
        legacy = [dict(c) for c in self.coins if "|" not in c["exchange"]]
        if not legacy:
            return
        def resolve():
            found = []
            for exchange in {c["exchange"] for c in legacy}:
                try:
                    catalog = discover(exchange, "spot")
                except Exception:
                    continue  # Preserve offline legacy configuration without guessing IDs.
                for coin in legacy:
                    if coin["exchange"] == exchange:
                        matches = [i for i in catalog if i.base.upper() == coin["symbol"].upper()]
                        if len(matches) == 1:
                            found.append((coin, matches[0]))
            self.migration_ready.emit(found)
        threading.Thread(target=resolve, daemon=True).start()

    def _apply_legacy_migration(self, found):
        if self._really_quitting:
            return
        changed = False
        for old, item in found:
            old_key = self._row_key(old["exchange"], old["symbol"])
            if old_key not in self.rows:
                continue
            adapter = register_instrument(item)
            new_key = self._row_key(adapter.key, item.base)
            row = self.rows.pop(old_key)
            row.setParent(None)
            row.deleteLater()
            self.coins = [c for c in self.coins if not
                          (c["exchange"] == old["exchange"] and c["symbol"] == old["symbol"])]
            for alarm in self.alarms:
                if alarm["key"] == old_key:
                    alarm.update(key=new_key, exchange=adapter.key, symbol=item.base)
            if not any(c["exchange"] == adapter.key and c["symbol"] == item.base for c in self.coins):
                self.coins.append(dict(exchange=adapter.key, symbol=item.base))
            self._add_row(adapter.key, item.base, persist=False)
            changed = True
        if changed:
            self._persist()
            self._sync_workers()

    # ---------- 添加自选：先选交易所再搜标的 ----------
    def _on_add_coin(self):
        if not self.add_btn.isEnabled():
            return
        if len(self.rows) >= MAX_COINS:
            QMessageBox.information(self, "已达上限", f"最多同时展示 {MAX_COINS} 个标的，请先删除一些。")
            return
        names = ["Binance", "OKX", "Bitget"]
        name, ok = QInputDialog.getItem(self, "交易所", "选择交易所", names, 0, False)
        if not ok:
            return
        exchange = EXCHANGE_ORDER[names.index(name)]
        market, ok = QInputDialog.getItem(self, "市场", "选择市场", ["Spot", "Perpetual"], 0, False)
        if not ok:
            return
        if exchange == "okx" and market == "Perpetual":
            QMessageBox.information(self, "暂不可用", "OKX SWAP 尚未完成实网验证，本实验暂不开放。")
            return
        keyword, ok = QInputDialog.getText(self, "查找交易标的", "输入 BTC、ETH、SOXL 或原生合约 ID")
        if not ok or not keyword.strip():
            return
        self.add_btn.setEnabled(False)
        def lookup():
            try:
                matches = search(discover(exchange, market.lower()), keyword)
                self.catalog_ready.emit(matches, "")
            except Exception as error:
                self.catalog_ready.emit([], f"市场目录不可访问：{type(error).__name__}。请检查网络或地区限制。")
        threading.Thread(target=lookup, daemon=True).start()

    def _show_catalog(self, matches, error):
        self.add_btn.setEnabled(True)
        if self._really_quitting:
            return
        if error or not matches:
            QMessageBox.information(self, "无法添加", error or "该市场没有可用的 USDT 交易标的，可能未上市或已暂停。")
            return
        labels = [instrument_label(i) for i in matches]
        prompt = "— 请选择具体标的 —"
        chosen, ok = QInputDialog.getItem(self, "选择真实交易标的", "合约显示 Last Price，不代表基础 ETF 现货成交", [prompt] + labels, 0, False)
        if not ok or chosen not in labels or len(self.rows) >= MAX_COINS:
            return
        item = matches[labels.index(chosen)]
        adapter = register_instrument(item)
        legacy_duplicate = item.market == "spot" and self._row_key(item.exchange, item.base) in self.rows
        if self._row_key(adapter.key, item.base) in self.rows or legacy_duplicate:
            QMessageBox.information(self, "已存在", "该交易所和市场的标的已在自选中。")
            return
        self._add_row(adapter.key, item.base, persist=True)
        self._sync_workers()

    def _finish_add_coin(self, ex_key, sym, valid):
        self.add_btn.setEnabled(True)
        if self._really_quitting:
            return
        if not valid:
            QMessageBox.warning(self, "无法添加", "未取得有效行情，请检查符号、网络或交易所可用性。")
            return
        if len(self.rows) >= MAX_COINS:
            return
        self._add_row(ex_key, sym, persist=True)
        self._sync_workers()

    # ---------- Worker 同步 ----------
    def _symbols_by_exchange(self):
        groups = {k: [] for k in EXCHANGES}
        for c in self.coins:
            groups.setdefault(c["exchange"], []).append(c["symbol"].upper())
        return groups

    def _sync_workers(self):
        groups = self._symbols_by_exchange()
        for ex_key, syms in groups.items():
            if not syms:
                # 没有该交易所的币，停掉 worker
                w = self.workers.pop(ex_key, None)
                if w:
                    w.stop()
                continue
            if ex_key in self.workers:
                self.workers[ex_key].update_symbols(syms)
            else:
                w = MarketWorker(
                    EXCHANGES[ex_key], syms,
                    on_ticker=lambda s, p, pct, chg, ek=ex_key: self.ticker_signal.emit(ek, s, p, pct, chg),
                    on_status=lambda mode, ek=ex_key: self.status_signal.emit(ek, mode),
                )
                self.workers[ex_key] = w
                w.start()

    # ---------- K 线 ----------
    def _open_kline(self, exchange, symbol):
        key = f"{exchange.key}:{symbol.upper()}"
        if key in self.kline_windows:
            w = self.kline_windows[key]
            w.show()
            w.raise_()
            return
        w = KlineWindow(exchange, symbol.upper())
        w.closed_signal.connect(lambda k: self.kline_windows.pop(k, None))
        self.kline_windows[key] = w
        w.show()

    # ---------- 价格报警 ----------
    def _set_alarm(self, ex, sym, key):
        row = self.rows.get(key)
        current = row.last_price if row and row.last_price else 0
        direction, ok1 = QInputDialog.getItem(
            self, "价格报警", "选择触发条件:",
            ["涨破指定价格（≥ 目标价）", "跌破指定价格（≤ 目标价）"],
            0, False
        )
        if not ok1:
            return
        is_up = "涨破" in direction
        price_text, ok2 = QInputDialog.getText(
            self, "价格报警",
            f"输入目标价格 (当前: {format_price(current)}):",
            text=str(current) if current else ""
        )
        if not ok2 or not price_text.strip():
            return
        try:
            target = float(price_text.strip())
            if not math.isfinite(target) or target <= 0:
                raise ValueError("positive finite price required")
        except ValueError:
            QMessageBox.warning(self, "无效输入", "请输入有效的数字。")
            return
        self.alarms.append({
            "key": key, "exchange": ex.key, "symbol": sym, "pair": ex.pair(sym),
            "price": target, "direction": "up" if is_up else "down"
        })
        self._persist()
        self._update_alarm_indicator(key)
        self.tray.showMessage("报警已设置",
                              f"{ex.name} · {sym} {'涨破' if is_up else '跌破'} {format_price(target)}",
                              QSystemTrayIcon.Information, 3000)

    def _check_alarms(self):
        if not self.alarms:
            return
        triggered = []
        for alarm in self.alarms:
            row = self.rows.get(alarm["key"])
            if (not row or row.last_price is None or
                    time.monotonic() - row.last_update > STALE_SECONDS):
                continue
            price = row.last_price
            if alarm["direction"] == "up" and price >= alarm["price"]:
                triggered.append(alarm)
            elif alarm["direction"] == "down" and price <= alarm["price"]:
                triggered.append(alarm)
        for alarm in triggered:
            if alarm in self.alarms:
                self.alarms.remove(alarm)
                self._on_alarm_triggered(alarm)
                self._update_alarm_indicator(alarm["key"])
        if triggered:
            self._persist()

    def _on_alarm_triggered(self, alarm):
        sym = alarm["symbol"]
        d = "涨破" if alarm["direction"] == "up" else "跌破"
        ex = EXCHANGES.get(alarm["exchange"])
        ex_name = ex.name if ex else alarm["exchange"]
        msg = f"{ex_name} · {sym} 已{d} {format_price(alarm['price'])}"
        if self.tray:
            self.tray.showMessage("🔔 价格报警", msg, QSystemTrayIcon.Warning, 8000)
        QApplication.beep()
        row = self.rows.get(alarm["key"])
        if row:
            row._flash_color = C_ACCENT
            row._flash_until = time.time() + 2.0

    def _update_alarm_indicator(self, key):
        row = self.rows.get(key)
        if not row:
            return
        has = any(a.get("key") == key for a in self.alarms)
        row.set_alarm_indicator(has)

    def _show_alarms(self):
        if not self.alarms:
            QMessageBox.information(self, "价格报警", "当前没有设置报警。")
            return
        lines = []
        for a in self.alarms:
            d = "涨破" if a["direction"] == "up" else "跌破"
            ex = EXCHANGES.get(a["exchange"])
            lines.append(f"🔔 {ex.name if ex else a['exchange']} · {a['symbol']}  {d}  {format_price(a['price'])}")
        QMessageBox.information(self, "价格报警", "\n".join(lines))

    def _clear_alarms(self):
        if not self.alarms:
            return
        self.alarms.clear()
        self._persist()
        for key in self.rows:
            self._update_alarm_indicator(key)
        self.tray.showMessage("价格报警", "所有报警已清除", QSystemTrayIcon.Information, 2000)

    # ---------- 交互 ----------
    def _toggle_pin(self):
        flags = self.windowFlags()
        on_top = bool(flags & Qt.WindowStaysOnTopHint)
        self.cfg["always_on_top"] = not on_top
        if on_top:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        self.show()
        self._persist()
        self.pin_btn.setText("置顶✓" if not on_top else "置顶")

    def _on_close(self):
        self.hide()
        if not self.cfg.get("_tray_hinted"):
            self.tray.showMessage(
                "行情浮窗", "已最小化到托盘，双击图标恢复，右键退出。",
                QSystemTrayIcon.Information, 4000
            )
            self.cfg["_tray_hinted"] = True
            self._persist()

    def _quit(self):
        self._really_quitting = True
        self._persist()
        for w in list(self.workers.values()):
            w.stop()
        for w in list(self.kline_windows.values()):
            w.close()
        self.tray.hide()
        QApplication.quit()

    # ---------- 回调 ----------
    def _on_ticker(self, ex_key, symbol, price, pct, chg):
        key = self._row_key(ex_key, symbol)
        row = self.rows.get(key)
        if row:
            if row.set_data(price, pct):
                self._check_alarms()

    def _on_status(self, ex_key, mode):
        if not hasattr(self, "_ex_states"):
            self._ex_states = {}
        self._ex_states[ex_key] = mode
        self._render_status()

    def _render_status(self):
        states = []
        now = time.monotonic()
        for key in self.workers:
            rows = [r for r in self.rows.values() if r.exchange.key == key]
            fresh = bool(rows) and all(r.last_update and now - r.last_update <= STALE_SECONDS for r in rows)
            mode = getattr(self, "_ex_states", {}).get(key, "down") if fresh else "down"
            states.append(mode)
            label = {"live": "实时", "rest": "轮询", "down": "无有效行情"}[mode]
            for row in rows:
                row.setToolTip(f"{row.exchange.name}: {label}")
        if not states or all(x == "down" for x in states):
            text, color = "● 无有效行情 · 重连中", C_DEAD
        elif any(x == "down" for x in states):
            text, color = "● 部分行情不可用", C_REST
        elif any(x == "rest" for x in states):
            text, color = "● REST 轮询" if all(x == "rest" for x in states) else "● 实时 / 轮询", C_REST
        else:
            text, color = "● 实时连接", C_LIVE
        self._title_color = self._status_color = color
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{color}; font-size:11px; font-weight:600;")
        self.title.setText("● 行情浮窗")
        self.title.setStyleSheet(f"color:{color}; font-size:13px; font-weight:700;")

    # ---------- 手动刷新 ----------
    def _on_refresh(self):
        """点击刷新：先立即 REST 拉一次全量行情，再强制所有 WS 重连"""
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("…")
        self.status_label.setText("正在刷新…")
        self.status_label.setStyleSheet(f"color:{C_ACCENT}; font-size:11px; font-weight:600;")

        coins = [(c.get("exchange"), c.get("symbol")) for c in list(self.coins)]
        workers = list(self.workers.values())

        def work():
            ok, fail = 0, 0
            for ex_key, sym in coins:
                ex = EXCHANGES.get(ex_key)
                if not ex:
                    continue
                try:
                    r = ex.rest_ticker(sym)
                    if r:
                        self.ticker_signal.emit(ex_key, sym, r[0], r[1], "0")
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
            for w in workers:
                try:
                    w.force_reconnect()
                except Exception:
                    pass
            self.refresh_done_signal.emit(
                f"已刷新 {time.strftime('%H:%M:%S')}（{ok} 个标的）" if not fail
                else f"已刷新 {time.strftime('%H:%M:%S')}（{ok} 成功 / {fail} 失败）"
            )

        threading.Thread(target=work, daemon=True).start()

    def _on_refresh_done(self, text):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("↻")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{C_ACCENT}; font-size:11px; font-weight:600;")

    # ---------- 边框缩放 ----------
    def _edge_mode(self, pos):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        E = 14  # 命中带宽：覆盖透明边距(10) + container 可见边缘内侧(4)，让用户在可见边缘即可触发缩放
        left = x < E
        right = x > w - E
        top = y < E
        bottom = y > h - E
        mode = ""
        if left:
            mode += "l"
        if right:
            mode += "r"
        if top:
            mode += "t"
        if bottom:
            mode += "b"
        return mode

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            mode = self._edge_mode(e.position().toPoint())
            if mode:
                self._resizing = True
                self._resize_mode = mode
                self._resize_start_global = e.globalPosition().toPoint()
                self._resize_start_geom = QRect(self.geometry())
                e.accept()
                return
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._resizing and e.buttons() & Qt.LeftButton:
            self._apply_resize(e.globalPosition().toPoint())
            e.accept()
            return
        if self._drag_offset is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()
            return
        # 未按下按钮：根据边缘方向切换光标，直观提示可缩放方向
        if e.buttons() == Qt.NoButton:
            mode = self._edge_mode(e.position().toPoint())
            self.setCursor(self._cursor_for(mode))

    def _cursor_for(self, mode):
        if not mode:
            return Qt.ArrowCursor
        if mode in ("lt", "rb"):
            return Qt.SizeFDiagCursor
        if mode in ("rt", "lb"):
            return Qt.SizeBDiagCursor
        if "l" in mode or "r" in mode:
            return Qt.SizeHorCursor
        return Qt.SizeVerCursor

    def mouseReleaseEvent(self, e):
        if self._resizing:
            self._resizing = False
            self._resize_mode = ""
            self._persist()
            e.accept()
            return
        if self._drag_offset is not None:
            self._drag_offset = None
            self._persist()
            e.accept()

    def _apply_resize(self, global_pos):
        g = self._resize_start_geom
        dx = global_pos.x() - self._resize_start_global.x()
        dy = global_pos.y() - self._resize_start_global.y()
        new_x, new_y, new_w, new_h = g.x(), g.y(), g.width(), g.height()
        mode = self._resize_mode
        if "r" in mode:
            new_w = g.width() + dx
        if "b" in mode:
            new_h = g.height() + dy
        if "l" in mode:
            new_w = g.width() - dx
            new_x = g.x() + dx
        if "t" in mode:
            new_h = g.height() - dy
            new_y = g.y() + dy
        new_w = max(MIN_W, min(MAX_W, new_w))
        new_h = max(MIN_H, min(MAX_H, new_h))
        if "l" in mode:
            new_x = g.x() + (g.width() - new_w)
        if "t" in mode:
            new_y = g.y() + (g.height() - new_h)
        self.setGeometry(new_x, new_y, new_w, new_h)

    def closeEvent(self, e):
        if self._really_quitting:
            self._persist()
            for w in list(self.workers.values()):
                w.stop()
            e.accept()
        else:
            e.ignore()
            self._on_close()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    f = CryptoFloat()
    f.show()
    f.resolve_legacy_instruments()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
