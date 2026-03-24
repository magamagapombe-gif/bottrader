import os
import json
import time
import uuid
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
import requests

import MetaTrader5 as mt5
import numpy as np

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG  — stored locally, never sent to backend except status blobs
# ══════════════════════════════════════════════════════════════════════════════
CONFIG_FILE   = os.path.join(os.path.expanduser("~"), ".supereye", "config.json")
CAMPAIGN_FILE = os.path.join(os.path.expanduser("~"), ".supereye", "campaign.json")
HISTORY_FILE  = os.path.join(os.path.expanduser("~"), ".supereye", "history.json")
BACKEND_URL   = "https://supereye-api.onrender.com"   # replace after Render deploy

os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)


def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(c: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(c, f, indent=2)

# ══════════════════════════════════════════════════════════════════════════════
#  BACKEND CLIENT
# ══════════════════════════════════════════════════════════════════════════════
class BackendClient:
    def __init__(self, token: str):
        self.token     = token
        self.user_id   = None
        self.username  = None
        self.role      = None
        self._session  = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def validate(self) -> dict:
        try:
            r = self._session.post(
                f"{BACKEND_URL}/validate-token",
                json={"token": self.token},
                timeout=15
            )
            data = r.json()
            if data.get("valid"):
                self.user_id  = data.get("user_id")
                self.username = data.get("username")
                self.role     = data.get("role")
            return data
        except Exception as e:
            return {"valid": False, "reason": f"Network error: {e}"}

    def push_status(self, payload: dict) -> Optional[str]:
        """Push status, returns pending command string or None."""
        try:
            payload["token"] = self.token
            r = self._session.post(
                f"{BACKEND_URL}/status-update",
                json=payload,
                timeout=10
            )
            data = r.json()
            return data.get("command")
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
#  PAIR CONFIG
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class PairConfig:
    symbol:             str
    label:              str
    magic:              int
    lot_base:           float
    lot_max:            float
    sl_pips:            int
    sl_distance:        float
    profit_trigger:     float
    stage_pips:         int
    max_spread_pts:     int
    budget_guard:       float
    drawdown_limit:     float
    compound_every:     float
    loss_streak_max:    int
    loss_pause_secs:    int
    pip_value:          float
    is_24_7:            bool
    trade_hour_start:   int
    trade_hour_end:     int
    limit_offset:       float = 20.0
    limit_timeout_secs: int   = 20
    grid_size:          int   = 3

GOLD_CONFIG = PairConfig(
    symbol="XAUUSD", label="GOLD (XAUUSD)", magic=20250301,
    lot_base=0.01, lot_max=0.04, sl_pips=15, sl_distance=2.00,
    profit_trigger=1.20, stage_pips=5, max_spread_pts=150,
    budget_guard=10.0, drawdown_limit=0.20, compound_every=2.0,
    loss_streak_max=3, loss_pause_secs=180, pip_value=0.10,
    is_24_7=False, trade_hour_start=8, trade_hour_end=20,
    limit_offset=0.80, limit_timeout_secs=45,
)
BTC_CONFIG = PairConfig(
    symbol="BTCUSD", label="BITCOIN (BTCUSD)", magic=20250302,
    lot_base=0.01, lot_max=0.01, sl_pips=300, sl_distance=500.0,
    profit_trigger=1.20, stage_pips=20, max_spread_pts=2500,
    budget_guard=10.0, drawdown_limit=0.20, compound_every=999.0,
    loss_streak_max=3, loss_pause_secs=180, pip_value=1.00,
    is_24_7=True, trade_hour_start=0, trade_hour_end=24,
    limit_offset=20.0, limit_timeout_secs=20,
)

_FILLING_FOK = 1
_FILLING_IOC = 2


# ══════════════════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════════════════
class SuperEyeGUI:
    def __init__(self, root: tk.Tk, engine_ref):
        self.root   = root
        self.engine = engine_ref
        root.title("SuperEye Trading Bot")
        root.geometry("480x560")
        root.resizable(False, False)
        root.configure(bg="#0f1117")
        self._build()

    def _build(self):
        BG   = "#0f1117"
        CARD = "#1a1d27"
        ACC  = "#00c896"
        TXT  = "#e2e8f0"
        MUT  = "#64748b"
        RED  = "#ef4444"

        self.root.configure(bg=BG)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Card.TFrame",   background=CARD)
        style.configure("BG.TFrame",     background=BG)
        style.configure("Green.TButton", background=ACC,  foreground="#000", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Red.TButton",   background=RED,  foreground="#fff", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Title.TLabel",  background=CARD, foreground=TXT,   font=("Segoe UI", 11, "bold"))
        style.configure("Val.TLabel",    background=CARD, foreground=ACC,   font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel",    background=CARD, foreground=MUT,   font=("Segoe UI", 9))
        style.configure("Muted.TLabel",  background=BG,   foreground=MUT,   font=("Segoe UI", 9))
        style.configure("Log.TLabel",    background=BG,   foreground=TXT,   font=("Consolas", 9))

        # Header
        hdr = ttk.Frame(self.root, style="BG.TFrame")
        hdr.pack(fill="x", padx=16, pady=(16, 0))
        tk.Label(hdr, text="SuperEye", bg=BG, fg=TXT,
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        self.status_dot = tk.Label(hdr, text="●", bg=BG, fg=RED,
                                   font=("Segoe UI", 14))
        self.status_dot.pack(side="left", padx=(8, 0), pady=(4, 0))
        self.status_lbl = tk.Label(hdr, text="Stopped", bg=BG, fg=MUT,
                                   font=("Segoe UI", 10))
        self.status_lbl.pack(side="left", padx=(4, 0), pady=(6, 0))
        self.user_lbl = tk.Label(hdr, text="", bg=BG, fg=MUT,
                                 font=("Segoe UI", 9))
        self.user_lbl.pack(side="right", pady=(6, 0))

        # Stats row
        stats = ttk.Frame(self.root, style="BG.TFrame")
        stats.pack(fill="x", padx=16, pady=12)
        self._balance_val, self._balance_lbl = self._stat_card(stats, "Balance", "$0.00")
        self._session_val, self._session_lbl = self._stat_card(stats, "Session P&L", "$0.00")
        self._cycle_val,   self._cycle_lbl   = self._stat_card(stats, "Cycle", "0")

        # Campaign progress
        camp = ttk.Frame(self.root, style="Card.TFrame")
        camp.pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(camp, text="Campaign progress", bg=CARD, fg=MUT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(8, 2))
        self.prog_bar = ttk.Progressbar(camp, length=440, mode="determinate")
        self.prog_bar.pack(padx=12, pady=(0, 4))
        self.prog_lbl = tk.Label(camp, text="$0.00 / $0.00  (0%)", bg=CARD,
                                 fg=MUT, font=("Segoe UI", 9))
        self.prog_lbl.pack(anchor="w", padx=12, pady=(0, 8))

        # Config row
        cfg_frame = ttk.Frame(self.root, style="Card.TFrame")
        cfg_frame.pack(fill="x", padx=16, pady=(0, 8))
        inner = ttk.Frame(cfg_frame, style="Card.TFrame")
        inner.pack(fill="x", padx=12, pady=10)

        tk.Label(inner, text="Pair", bg=CARD, fg=MUT,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self.pair_var = tk.StringVar(value="GOLD")
        pair_cb = ttk.Combobox(inner, textvariable=self.pair_var,
                               values=["GOLD", "BITCOIN"], width=10, state="readonly")
        pair_cb.grid(row=1, column=0, sticky="w", padx=(0, 16))

        tk.Label(inner, text="Grid", bg=CARD, fg=MUT,
                 font=("Segoe UI", 9)).grid(row=0, column=1, sticky="w")
        self.grid_var = tk.StringVar(value="3")
        grid_cb = ttk.Combobox(inner, textvariable=self.grid_var,
                               values=["3", "4", "6"], width=6, state="readonly")
        grid_cb.grid(row=1, column=1, sticky="w", padx=(0, 16))

        tk.Label(inner, text="Capital ($)", bg=CARD, fg=MUT,
                 font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w")
        self.capital_var = tk.StringVar(value="10")
        tk.Entry(inner, textvariable=self.capital_var, width=8,
                 bg="#262a36", fg=TXT, insertbackground=TXT,
                 relief="flat").grid(row=1, column=2, padx=(0, 16))

        tk.Label(inner, text="Goal ($)", bg=CARD, fg=MUT,
                 font=("Segoe UI", 9)).grid(row=0, column=3, sticky="w")
        self.goal_var = tk.StringVar(value="6")
        tk.Entry(inner, textvariable=self.goal_var, width=8,
                 bg="#262a36", fg=TXT, insertbackground=TXT,
                 relief="flat").grid(row=1, column=3)

        # Buttons
        btn_frame = ttk.Frame(self.root, style="BG.TFrame")
        btn_frame.pack(fill="x", padx=16, pady=(0, 8))
        self.start_btn = ttk.Button(btn_frame, text="Start Bot",
                                    style="Green.TButton",
                                    command=self._on_start)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.stop_btn = ttk.Button(btn_frame, text="Stop after cycle",
                                   style="Red.TButton",
                                   command=self._on_stop, state="disabled")
        self.stop_btn.pack(side="left", expand=True, fill="x")

        # Log
        log_frame = ttk.Frame(self.root, style="BG.TFrame")
        log_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        tk.Label(log_frame, text="Log", bg=BG, fg=MUT,
                 font=("Segoe UI", 9)).pack(anchor="w")
        self.log_box = tk.Text(log_frame, bg=CARD, fg=TXT,
                               font=("Consolas", 9), relief="flat",
                               state="disabled", wrap="word", height=10)
        self.log_box.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(log_frame, command=self.log_box.yview)
        sb.pack(side="right", fill="y")
        self.log_box.configure(yscrollcommand=sb.set)

    def _stat_card(self, parent, label, initial):
        CARD = "#1a1d27"; ACC = "#00c896"; MUT = "#64748b"
        f = ttk.Frame(parent, style="Card.TFrame")
        f.pack(side="left", expand=True, fill="x", padx=(0, 8))
        tk.Label(f, text=label, bg=CARD, fg=MUT,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(8, 0))
        val = tk.Label(f, text=initial, bg=CARD, fg=ACC,
                       font=("Segoe UI", 16, "bold"))
        val.pack(anchor="w", padx=10, pady=(0, 8))
        return val, f

    def log(self, msg: str):
        def _do():
            self.log_box.configure(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_box.insert("end", f"[{ts}] {msg}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.root.after(0, _do)

    def set_running(self, running: bool):
        def _do():
            ACC = "#00c896"; RED = "#ef4444"; MUT = "#64748b"
            if running:
                self.status_dot.configure(fg=ACC)
                self.status_lbl.configure(text="Running")
                self.start_btn.configure(state="disabled")
                self.stop_btn.configure(state="normal")
            else:
                self.status_dot.configure(fg=RED)
                self.status_lbl.configure(text="Stopped")
                self.start_btn.configure(state="normal")
                self.stop_btn.configure(state="disabled")
        self.root.after(0, _do)

    def update_stats(self, balance: float, session_profit: float,
                     cycle: int, campaign_earned: float, campaign_goal: float):
        def _do():
            ACC = "#00c896"; RED = "#ef4444"
            self._balance_val.configure(text=f"${balance:.2f}")
            color = ACC if session_profit >= 0 else RED
            self._session_val.configure(
                text=f"${session_profit:+.2f}", fg=color)
            self._cycle_val.configure(text=str(cycle))
            pct = min(100, (campaign_earned / campaign_goal * 100)
                      if campaign_goal > 0 else 0)
            self.prog_bar["value"] = pct
            self.prog_lbl.configure(
                text=f"${campaign_earned:.2f} / ${campaign_goal:.2f}  ({pct:.1f}%)")
        self.root.after(0, _do)

    def set_username(self, name: str):
        self.root.after(0, lambda: self.user_lbl.configure(text=f"User: {name}"))

    def _on_start(self):
        self.engine.request_start(
            pair=self.pair_var.get(),
            grid_size=int(self.grid_var.get()),
            capital=float(self.capital_var.get()),
            goal=float(self.goal_var.get()),
        )

    def _on_stop(self):
        self.engine.request_stop()


# ══════════════════════════════════════════════════════════════════════════════
#  SETUP DIALOG  (first run)
# ══════════════════════════════════════════════════════════════════════════════
class SetupDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("SuperEye — First time setup")
        self.geometry("400x340")
        self.resizable(False, False)
        self.configure(bg="#0f1117")
        self.result = None
        self._build()
        self.grab_set()
        self.wait_window()

    def _build(self):
        BG = "#0f1117"; CARD = "#1a1d27"; TXT = "#e2e8f0"; MUT = "#64748b"; ACC = "#00c896"

        tk.Label(self, text="SuperEye Setup", bg=BG, fg=TXT,
                 font=("Segoe UI", 14, "bold")).pack(pady=(20, 4))
        tk.Label(self, text="Enter your access token and Exness MT5 details",
                 bg=BG, fg=MUT, font=("Segoe UI", 9)).pack(pady=(0, 16))

        fields_frame = tk.Frame(self, bg=CARD, bd=0)
        fields_frame.pack(padx=24, fill="x")

        self._entries = {}
        fields = [
            ("Access Token",   "token",    False),
            ("MT5 Account #",  "account",  False),
            ("MT5 Password",   "password", True),
            ("MT5 Server",     "server",   False),
        ]
        for label, key, is_pass in fields:
            tk.Label(fields_frame, text=label, bg=CARD, fg=MUT,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(8, 0))
            e = tk.Entry(fields_frame, bg="#262a36", fg=TXT, insertbackground=TXT,
                         relief="flat", font=("Segoe UI", 10),
                         show="*" if is_pass else "")
            e.pack(fill="x", padx=12, pady=(2, 0))
            self._entries[key] = e

        # Pre-fill server default
        self._entries["server"].insert(0, "Exness-MT5Trial9")

        self.err_lbl = tk.Label(self, text="", bg=BG, fg="#ef4444",
                                font=("Segoe UI", 9))
        self.err_lbl.pack(pady=(8, 0))

        tk.Button(self, text="Connect", bg=ACC, fg="#000",
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  padx=20, pady=8, command=self._submit).pack(pady=12)

    def _submit(self):
        vals = {k: e.get().strip() for k, e in self._entries.items()}
        if not all(vals.values()):
            self.err_lbl.configure(text="All fields are required.")
            return
        try:
            int(vals["account"])
        except ValueError:
            self.err_lbl.configure(text="Account number must be numeric.")
            return
        self.result = vals
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  TRADING ENGINE  (runs in background thread)
# ══════════════════════════════════════════════════════════════════════════════
class TradingEngine:
    def __init__(self, gui: SuperEyeGUI, client: BackendClient, config: dict):
        self.gui            = gui
        self.client         = client
        self.config         = config
        self._stop_flag     = False
        self._running       = False
        self._thread        = None
        self._status_thread = None
        self._cfg: Optional[PairConfig] = None
        self._session_profit = 0.0
        self._cycle          = 0
        self._campaign       = {}

    def request_start(self, pair: str, grid_size: int,
                      capital: float, goal: float):
        if self._running:
            return
        self._stop_flag = False
        self._thread = threading.Thread(
            target=self._run,
            args=(pair, grid_size, capital, goal),
            daemon=True
        )
        self._thread.start()

    def request_stop(self):
        self._stop_flag = True
        self.gui.log("Stop requested — will stop after current cycle.")

    def _log(self, msg: str):
        self.gui.log(msg)

    # ── status pusher ─────────────────────────────────────────────────────────
    def _start_status_pusher(self):
        def pusher():
            while self._running:
                time.sleep(60)
                if not self._running:
                    break
                payload = {
                    "balance":          self._get_balance(),
                    "session_profit":   self._session_profit,
                    "pair":             self._cfg.symbol if self._cfg else "",
                    "grid_size":        self._cfg.grid_size if self._cfg else 0,
                    "cycle":            self._cycle,
                    "loss_streak":      0,
                    "is_running":       self._running,
                    "campaign_goal":    self._campaign.get("goal", 0),
                    "campaign_earned":  self._campaign.get("total_earned", 0),
                }
                cmd = self.client.push_status(payload)
                if cmd == "stop":
                    self._log("Remote stop command received — finishing cycle.")
                    self._stop_flag = True
        self._status_thread = threading.Thread(target=pusher, daemon=True)
        self._status_thread.start()

    def _get_balance(self) -> float:
        try:
            return mt5.account_info().balance
        except Exception:
            return 0.0

    # ── main run ──────────────────────────────────────────────────────────────
    def _run(self, pair: str, grid_size: int, capital: float, goal: float):
        self._running = True
        self.gui.set_running(True)
        self._log(f"Starting {pair} | grid={grid_size} | capital=${capital} | goal=${goal}")

        try:
            cfg = GOLD_CONFIG if pair == "GOLD" else BTC_CONFIG
            cfg.grid_size      = grid_size
            cfg.profit_trigger = round(1.20 * (grid_size / 3), 2)
            self._cfg = cfg
            self._apply_capital(cfg, capital)

            # Connect MT5
            if not self._connect_mt5(cfg, capital, goal):
                return

            # Load/create campaign
            self._campaign = self._load_or_new_campaign(pair, capital, goal)
            profit_target  = self._session_target(self._campaign)
            self._log(f"Session target: ${profit_target:.2f}")

            self._start_status_pusher()
            self._run_engine(cfg, profit_target, capital)

        except Exception as e:
            self._log(f"Engine error: {e}")
        finally:
            self._running = False
            self.gui.set_running(False)
            try:
                mt5.shutdown()
            except Exception:
                pass
            self._log("Bot stopped.")

    def _connect_mt5(self, cfg: PairConfig, capital: float, goal: float) -> bool:
        account  = int(self.config["account"])
        password = self.config["password"]
        server   = self.config["server"]

        for attempt in range(12):
            if mt5.initialize():
                break
            self._log(f"MT5 init attempt {attempt+1}/12 failed — retrying...")
            time.sleep(5)
        else:
            self._log("MT5 failed to initialize after 12 attempts.")
            return False

        if not mt5.login(account, password=password, server=server):
            self._log(f"MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False

        terminal = mt5.terminal_info()
        if terminal and not terminal.trade_allowed:
            self._log("AutoTrading is DISABLED in MT5. Enable it and restart.")
            mt5.shutdown()
            return False

        self._log(f"Connected to MT5 | {server} | account {account}")
        cfg.symbol = self._resolve_symbol(cfg.symbol)
        return True

    def _resolve_symbol(self, base: str) -> str:
        for sym in [base, base+"m", base+"c", base+".r"]:
            if mt5.symbol_select(sym, True):
                info = mt5.symbol_info(sym)
                if info:
                    return sym
        syms = [s.name for s in (mt5.symbols_get() or []) if base[:3] in s.name]
        if syms:
            mt5.symbol_select(syms[0], True)
            return syms[0]
        raise RuntimeError(f"Symbol {base} not found")

    def _apply_capital(self, cfg: PairConfig, capital: float):
        raw = round(capital / 1000, 2)
        cfg.lot_base = max(cfg.lot_base, min(raw, cfg.lot_max))
        if cfg.lot_max > cfg.lot_base:
            cfg.lot_max = min(cfg.lot_base * 2, cfg.lot_max)
        else:
            cfg.lot_max = cfg.lot_base
        cfg.compound_every = round(capital * 0.30, 2)
        cfg.budget_guard   = round(capital * 0.80, 2)

    # ── campaign helpers ──────────────────────────────────────────────────────
    def _load_or_new_campaign(self, pair: str, capital: float, goal: float) -> dict:
        if os.path.exists(CAMPAIGN_FILE):
            try:
                with open(CAMPAIGN_FILE) as f:
                    c = json.load(f)
                if not c.get("completed"):
                    self._log(f"Resuming campaign — earned ${c['total_earned']:.2f} of ${c['goal']:.2f}")
                    return c
            except Exception:
                pass
        c = {
            "pair": pair, "capital": capital, "goal": goal,
            "grid_size": self._cfg.grid_size if self._cfg else 3,
            "total_earned": 0.0, "sessions": [], "completed": False,
            "started": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self._save_campaign(c)
        return c

    def _save_campaign(self, c: dict):
        with open(CAMPAIGN_FILE, "w") as f:
            json.dump(c, f, indent=2)

    def _session_target(self, c: dict) -> float:
        remaining = c["goal"] - c["total_earned"]
        return round(min(remaining, c["goal"] * 2), 4)

    def _record_session(self, profit: float, cycles: int):
        c = self._campaign
        c["total_earned"] = round(c["total_earned"] + profit, 4)
        c["sessions"].append({
            "date":   datetime.now().strftime("%Y-%m-%d %H:%M"),
            "profit": round(profit, 4),
            "cycles": cycles,
        })
        if c["total_earned"] >= c["goal"]:
            c["completed"] = True
        self._save_campaign(c)
        self._append_history(profit, cycles)

    def _append_history(self, profit: float, cycles: int):
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE) as f:
                    history = json.load(f)
            except Exception:
                pass
        history.append({
            "date":    datetime.now().strftime("%Y-%m-%d %H:%M"),
            "pair":    self._cfg.symbol if self._cfg else "",
            "profit":  round(profit, 4),
            "cycles":  cycles,
            "balance": self._get_balance(),
        })
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)

    # ── trading engine (core loop) ────────────────────────────────────────────
    def _run_engine(self, cfg: PairConfig, profit_target: float, capital: float):
        session_profit    = 0.0
        cycle             = 0
        loss_streak       = 0
        prev_tickets      = set()
        ticket_open_times = {}
        individual_closes = 0
        grid_open_time    = time.time()
        closed_tickets    = set()
        last_ui_update    = 0.0

        self._wait_for_market(cfg)
        orphans = mt5.positions_get(symbol=cfg.symbol, magic=cfg.magic) or []
        for p in orphans:
            self._close_position(cfg, p.ticket)
            time.sleep(0.2)

        current_lot = self._calc_lot(cfg, session_profit)
        direction   = self._wait_for_direction(cfg)
        self._open_staged_grid(cfg, direction, current_lot)
        grid_open_time = time.time()

        try:
            while True:
                # ── stop flag check (after cycle) ─────────────────────────────
                if self._stop_flag:
                    self._log("Stop flag set — closing positions and stopping.")
                    break

                # ── session target hit ─────────────────────────────────────────
                if session_profit >= profit_target:
                    self._close_all(cfg)
                    self._record_session(session_profit, cycle)
                    self._log(f"Target hit! Session profit: ${session_profit:.2f}")
                    break

                # ── market check ───────────────────────────────────────────────
                if not self._market_available(cfg):
                    self._close_all(cfg)
                    prev_tickets = set(); ticket_open_times = {}; closed_tickets = set()
                    self._wait_for_market(cfg)
                    current_lot = self._calc_lot(cfg, session_profit)
                    direction   = self._wait_for_direction(cfg)
                    self._open_staged_grid(cfg, direction, current_lot)
                    grid_open_time = time.time(); individual_closes = 0
                    continue

                if self._drawdown_exceeded(cfg):
                    self._log("DRAWDOWN LIMIT HIT — emergency stop")
                    self._close_all(cfg)
                    break

                floating = self._total_pnl(cfg)
                if floating < -cfg.budget_guard:
                    time.sleep(30)
                    continue

                # ── loss streak ────────────────────────────────────────────────
                if loss_streak >= cfg.loss_streak_max:
                    self._close_all(cfg)
                    prev_tickets = set(); ticket_open_times = {}; closed_tickets = set()
                    loss_streak = 0
                    current_lot = self._calc_lot(cfg, session_profit)
                    direction   = self._wait_for_direction(cfg)
                    self._open_staged_grid(cfg, direction, current_lot)
                    grid_open_time = time.time(); individual_closes = 0
                    continue

                # ── scan positions ─────────────────────────────────────────────
                positions       = mt5.positions_get(symbol=cfg.symbol, magic=cfg.magic) or []
                current_tickets = {p.ticket for p in positions}
                cycle          += 1
                self._cycle     = cycle

                now_ts   = time.time()
                vanished = prev_tickets - current_tickets
                real_sl  = {t for t in vanished
                            if now_ts - ticket_open_times.get(t, now_ts) >= 15}
                if real_sl:
                    loss_streak += len(real_sl)
                for t in current_tickets - prev_tickets:
                    ticket_open_times[t] = now_ts
                for t in vanished:
                    ticket_open_times.pop(t, None)
                prev_tickets = current_tickets

                # ── profit logic ───────────────────────────────────────────────
                _esc_scale      = min(cfg.grid_size / 3, 1.5)
                COLLECTIVE      = cfg.profit_trigger
                DOUBLE_COMBINED = round(0.80 * _esc_scale, 2)
                DOUBLE_MIN_LEG  = round(0.20 * _esc_scale, 2)
                BLEED_STOP      = -(capital * 0.80)
                ESCALATION      = [round(v * _esc_scale, 2) for v in [0.55, 0.65, 0.75]]

                live = []
                for p in positions:
                    if p.ticket in closed_tickets:
                        continue
                    chk = mt5.positions_get(ticket=p.ticket)
                    if chk:
                        live.append(chk[0])

                if live:
                    total_profit = sum(p.profit for p in live)
                    session_profit_snap = session_profit

                    if total_profit <= BLEED_STOP:
                        for p in live:
                            session_profit += self._close_position(cfg, p.ticket)
                        loss_streak += 1
                        current_lot  = max(cfg.lot_base, self._calc_lot(cfg, max(session_profit, 0)))
                        direction    = self._wait_for_direction(cfg)
                        individual_closes = 0
                        prev_tickets = set(); ticket_open_times = {}; closed_tickets = set()
                        self._open_staged_grid(cfg, direction, current_lot)
                        grid_open_time = time.time()

                    elif total_profit >= COLLECTIVE:
                        for p in live:
                            session_profit += self._close_position(cfg, p.ticket)
                        loss_streak = 0
                        prev_tickets = set(); ticket_open_times = {}; closed_tickets = set()
                        current_lot  = max(cfg.lot_base, self._calc_lot(cfg, max(session_profit, 0)))
                        time.sleep(2)
                        direction = self._wait_for_direction(cfg)
                        individual_closes = 0
                        self._open_limit_grid(cfg, direction, current_lot, count=cfg.grid_size)
                        grid_open_time = time.time()

                    else:
                        indiv_fired = False
                        threshold   = ESCALATION[min(individual_closes, len(ESCALATION)-1)]
                        for p in live:
                            if p.ticket in closed_tickets:
                                continue
                            if p.profit >= threshold:
                                same_dir = mt5.ORDER_TYPE_BUY if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_SELL
                                captured = self._close_position(cfg, p.ticket)
                                session_profit += captured
                                closed_tickets.add(p.ticket)
                                indiv_fired     = True
                                if captured >= 0:
                                    loss_streak = 0
                                individual_closes += 1
                                threshold = ESCALATION[min(individual_closes, len(ESCALATION)-1)]
                                current_lot = max(cfg.lot_base, self._calc_lot(cfg, max(session_profit, 0)))
                                time.sleep(0.3)
                                reopen_dir = self._get_trend_direction(cfg)
                                if reopen_dir is None:
                                    reopen_dir = same_dir
                                self._open_position(cfg, reopen_dir, current_lot)

                        remaining = [p for p in live if p.ticket not in closed_tickets]
                        if not indiv_fired and len(remaining) >= 2:
                            best = None; best_val = DOUBLE_COMBINED
                            for i in range(len(remaining)):
                                for j in range(i+1, len(remaining)):
                                    pi, pj = remaining[i], remaining[j]
                                    if pi.profit < DOUBLE_MIN_LEG or pj.profit < DOUBLE_MIN_LEG:
                                        continue
                                    if pi.profit + pj.profit >= best_val:
                                        best     = (pi, pj)
                                        best_val = pi.profit + pj.profit
                            if best:
                                ddirs = []
                                for p in best:
                                    sd = mt5.ORDER_TYPE_BUY if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_SELL
                                    session_profit += self._close_position(cfg, p.ticket)
                                    closed_tickets.add(p.ticket)
                                    current_lot = max(cfg.lot_base, self._calc_lot(cfg, max(session_profit, 0)))
                                    ddirs.append(sd)
                                    if session_profit >= 0:
                                        loss_streak = 0
                                    time.sleep(0.3)
                                reopen_dir = self._get_trend_direction(cfg)
                                if reopen_dir is None:
                                    reopen_dir = max(set(ddirs), key=ddirs.count)
                                self._open_limit_grid(cfg, reopen_dir, current_lot, count=2)

                # ── refill ─────────────────────────────────────────────────────
                positions_now = mt5.positions_get(symbol=cfg.symbol, magic=cfg.magic) or []
                shortfall     = cfg.grid_size - len(positions_now)
                if shortfall > 0 and loss_streak < cfg.loss_streak_max:
                    sv = sum(p.profit for p in positions_now)
                    if sv >= -1.00 or shortfall < 2:
                        spread = self._get_spread(cfg.symbol)
                        if spread <= cfg.max_spread_pts:
                            refill_dir = self._wait_for_direction(cfg)
                            for _ in range(shortfall):
                                self._open_position(cfg, refill_dir, current_lot)
                                time.sleep(0.3)

                # ── UI update every 5s ─────────────────────────────────────────
                if time.time() - last_ui_update > 5:
                    bal = self._get_balance()
                    self.gui.update_stats(
                        bal, session_profit, cycle,
                        self._campaign.get("total_earned", 0),
                        self._campaign.get("goal", 0),
                    )
                    last_ui_update = time.time()

                self._session_profit = session_profit
                time.sleep(0.2)

        finally:
            self._close_all(cfg)
            self._record_session(session_profit, cycle)
            self.gui.update_stats(
                self._get_balance(), session_profit, cycle,
                self._campaign.get("total_earned", 0),
                self._campaign.get("goal", 0),
            )

    # ── MT5 helpers ───────────────────────────────────────────────────────────
    def _calc_lot(self, cfg, profit):
        steps = max(0, int(profit // cfg.compound_every))
        return round(min(cfg.lot_base + steps * 0.01, cfg.lot_max), 2)

    def _get_spread(self, symbol):
        tick  = mt5.symbol_info_tick(symbol)
        point = mt5.symbol_info(symbol).point
        return round((tick.ask - tick.bid) / point)

    def _get_price(self, symbol, order_type):
        tick = mt5.symbol_info_tick(symbol)
        return tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

    def _get_filling(self, symbol):
        filling = mt5.symbol_info(symbol).filling_mode
        if filling & _FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        elif filling & _FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def _total_pnl(self, cfg):
        return sum(p.profit for p in (mt5.positions_get(symbol=cfg.symbol, magic=cfg.magic) or []))

    def _drawdown_exceeded(self, cfg):
        bal = self._get_balance()
        if bal <= 0:
            return False
        return abs(min(self._total_pnl(cfg), 0)) / bal >= cfg.drawdown_limit

    def _open_position(self, cfg, order_type, lot):
        spread = self._get_spread(cfg.symbol)
        if spread > cfg.max_spread_pts:
            return None
        info    = mt5.symbol_info(cfg.symbol)
        digits  = info.digits
        price   = self._get_price(cfg.symbol, order_type)
        filling = self._get_filling(cfg.symbol)
        result  = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": cfg.symbol,
            "volume": float(lot), "type": order_type,
            "price": float(price), "deviation": 30,
            "magic": cfg.magic, "comment": "supereye",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling,
        })
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return None
        ticket = result.order
        sl = round(price - cfg.sl_distance, digits) if order_type == mt5.ORDER_TYPE_BUY \
             else round(price + cfg.sl_distance, digits)
        for _ in range(3):
            time.sleep(0.2)
            pos = mt5.positions_get(ticket=ticket)
            if not pos:
                continue
            sl_res = mt5.order_send({
                "action": mt5.TRADE_ACTION_SLTP, "symbol": cfg.symbol,
                "position": ticket, "sl": float(sl), "tp": 0.0,
            })
            if sl_res and sl_res.retcode == mt5.TRADE_RETCODE_DONE:
                break
        return ticket

    def _close_position(self, cfg, ticket):
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return 0.0
        p          = positions[0]
        close_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price      = self._get_price(cfg.symbol, close_type)
        result     = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": cfg.symbol,
            "volume": float(p.volume), "type": close_type,
            "position": ticket, "price": float(price),
            "deviation": 30, "magic": cfg.magic, "comment": "supereye_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._get_filling(cfg.symbol),
        })
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return 0.0
        realized = p.profit
        time.sleep(0.15)
        deals = mt5.history_deals_get(position=ticket)
        if deals:
            realized = sum(d.profit + d.commission + d.swap for d in deals)
        return realized

    def _close_all(self, cfg):
        for p in (mt5.positions_get(symbol=cfg.symbol, magic=cfg.magic) or []):
            self._close_position(cfg, p.ticket)

    def _open_staged_grid(self, cfg, direction, lot):
        if not self._wait_spread(cfg):
            return []
        tickets = []
        for _ in range(cfg.grid_size):
            t = self._open_position(cfg, direction, lot)
            if t:
                tickets.append(t)
            else:
                time.sleep(5)
            time.sleep(0.2)
        self._log(f"Grid open — {len(tickets)}/{cfg.grid_size} positions")
        return tickets

    def _open_limit_grid(self, cfg, direction, lot, count=-1):
        if count == -1:
            count = cfg.grid_size
        if self._is_strong_trend(cfg, direction):
            return self._open_staged_grid(cfg, direction, lot)
        spread = self._get_spread(cfg.symbol)
        if spread > cfg.max_spread_pts:
            return self._open_staged_grid(cfg, direction, lot)
        info    = mt5.symbol_info(cfg.symbol)
        digits  = info.digits
        tick    = mt5.symbol_info_tick(cfg.symbol)
        filling = self._get_filling(cfg.symbol)
        if direction == mt5.ORDER_TYPE_BUY:
            lp   = round(tick.ask - cfg.limit_offset, digits)
            sl   = round(lp - cfg.sl_distance, digits)
            ltype = mt5.ORDER_TYPE_BUY_LIMIT
        else:
            lp   = round(tick.bid + cfg.limit_offset, digits)
            sl   = round(lp + cfg.sl_distance, digits)
            ltype = mt5.ORDER_TYPE_SELL_LIMIT
        pending = []
        for _ in range(count):
            r = mt5.order_send({
                "action": mt5.TRADE_ACTION_PENDING, "symbol": cfg.symbol,
                "volume": float(lot), "type": ltype,
                "price": round(float(lp), digits), "sl": round(float(sl), digits),
                "tp": 0.0, "deviation": 10, "magic": cfg.magic,
                "comment": "supereye_limit", "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            })
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                pending.append(r.order)
            time.sleep(0.2)
        if not pending:
            return self._open_staged_grid(cfg, direction, lot)
        deadline = time.time() + cfg.limit_timeout_secs
        filled   = []
        while time.time() < deadline and pending:
            still = []
            for t in pending:
                pos = mt5.positions_get(ticket=t)
                if pos:
                    filled.append(t)
                elif mt5.orders_get(ticket=t):
                    still.append(t)
            pending = still
            if pending:
                time.sleep(1.0)
        for t in pending:
            mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE, "order": t,
                "symbol": cfg.symbol, "magic": cfg.magic,
            })
            mkt = self._open_position(cfg, direction, lot)
            if mkt:
                filled.append(mkt)
        return filled

    def _is_strong_trend(self, cfg, direction):
        rates = mt5.copy_rates_from_pos(cfg.symbol, mt5.TIMEFRAME_M5, 0, 4)
        if rates is None or len(rates) < 3:
            return False
        for c in rates[-3:-1]:
            rng      = max(c["high"] - c["low"], 1e-8)
            body_pct = abs(c["close"] - c["open"]) / rng
            if direction == mt5.ORDER_TYPE_SELL and not (c["close"] < c["open"] and body_pct > 0.60):
                return False
            if direction == mt5.ORDER_TYPE_BUY  and not (c["close"] > c["open"] and body_pct > 0.60):
                return False
        return True

    def _wait_spread(self, cfg, timeout=120):
        spread = self._get_spread(cfg.symbol)
        if spread <= cfg.max_spread_pts:
            return True
        self._log(f"Spread {spread}pts — waiting...")
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(10)
            if self._get_spread(cfg.symbol) <= cfg.max_spread_pts:
                return True
        self._log("Spread timeout — skipping")
        return False

    def _calc_ema(self, values, period):
        k   = 2.0 / (period + 1)
        ema = np.zeros(len(values))
        ema[period-1] = np.mean(values[:period])
        for i in range(period, len(values)):
            ema[i] = values[i] * k + ema[i-1] * (1-k)
        return ema

    def _get_trend_direction(self, cfg):
        rates = mt5.copy_rates_from_pos(cfg.symbol, mt5.TIMEFRAME_M5, 0, 55)
        if rates is None or len(rates) < 52:
            if rates and len(rates) >= 2:
                c = rates[-2]
                return mt5.ORDER_TYPE_BUY if c["close"] > c["open"] else mt5.ORDER_TYPE_SELL
            return mt5.ORDER_TYPE_BUY
        closes = np.array([c["close"] for c in rates])
        opens  = np.array([c["open"]  for c in rates])
        highs  = np.array([c["high"]  for c in rates])
        lows   = np.array([c["low"]   for c in rates])
        e8  = self._calc_ema(closes, 8)[-2]
        e21 = self._calc_ema(closes, 21)[-2]
        e50 = self._calc_ema(closes, 50)[-2]
        bull = e8 > e21 > e50
        bear = e8 < e21 < e50
        BUY  = mt5.ORDER_TYPE_BUY
        SELL = mt5.ORDER_TYPE_SELL

        def score(direction):
            bc = int(np.sum(closes[-4:-1] > opens[-4:-1]))
            sc = int(np.sum(closes[-4:-1] < opens[-4:-1]))
            s2 = (bc >= 2) if direction == BUY else (sc >= 2)
            bodies = np.abs(closes[-3:-1] - opens[-3:-1])
            ranges = np.where(highs[-3:-1]-lows[-3:-1] < 1e-8, 1e-8, highs[-3:-1]-lows[-3:-1])
            s3 = float(np.mean(bodies/ranges)) >= 0.40
            lr = max(highs[-2]-lows[-2], 1e-8)
            lb = abs(closes[-2]-opens[-2])/lr
            if direction == BUY:
                s4 = not (closes[-2] < opens[-2] and lb > 0.50)
            else:
                s4 = not (closes[-2] > opens[-2] and lb > 0.50)
            return int(s2)+int(s3)+int(s4)

        bs = score(BUY);  bt = bs + (1 if bull else 0)
        ss = score(SELL); st = ss + (1 if bear else 0)
        buy_ok  = bt >= 3 and bull
        sell_ok = st >= 3 and bear
        if bs == 3 and not bull and not sell_ok:
            buy_ok = True
        if ss == 3 and not bear and not buy_ok:
            sell_ok = True
        if buy_ok and sell_ok:
            return BUY if bt >= st else SELL
        if buy_ok:
            return BUY
        if sell_ok:
            return SELL
        return None

    def _wait_for_direction(self, cfg):
        while True:
            rates = mt5.copy_rates_from_pos(cfg.symbol, mt5.TIMEFRAME_M5, 0, 55)
            d = self._get_trend_direction(cfg)
            if d is not None:
                return d
            nxt = (int(rates[-1]["time"]) + 300) if rates and len(rates) > 0 else time.time()+30
            wait = max(10, nxt - time.time() + 2)
            self._log(f"Waiting for signal — next M5 in {wait:.0f}s")
            time.sleep(wait)

    def _gold_market_open(self):
        now  = datetime.now(timezone.utc)
        wday = now.weekday()
        if wday == 5: return False
        if wday == 6: return now.hour >= 22
        if wday == 4: return now.hour < 21
        return True

    def _market_available(self, cfg):
        if cfg.is_24_7:
            return True
        if not self._gold_market_open():
            return False
        now  = datetime.now(timezone.utc)
        if now.weekday() >= 5:
            return False
        return cfg.trade_hour_start <= now.hour < cfg.trade_hour_end

    def _wait_for_market(self, cfg):
        if self._market_available(cfg):
            return
        self._log(f"{cfg.label} market closed — waiting...")
        while not self._market_available(cfg):
            time.sleep(60)
        self._log("Market open — starting.")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    root = tk.Tk()
    root.withdraw()  # hide until setup done

    config = load_config()

    # First-run setup
    if not config.get("token") or not config.get("account"):
        dlg = SetupDialog(root)
        if not dlg.result:
            root.destroy()
            return
        config.update(dlg.result)
        save_config(config)

    # Validate token against backend
    client = BackendClient(config["token"])

    # Show a loading message
    loading = tk.Toplevel(root)
    loading.title("Connecting...")
    loading.geometry("300x100")
    loading.configure(bg="#0f1117")
    tk.Label(loading, text="Validating access token...",
             bg="#0f1117", fg="#e2e8f0",
             font=("Segoe UI", 11)).pack(expand=True)
    loading.update()

    result = client.validate()
    loading.destroy()

    if not result.get("valid"):
        reason = result.get("reason", "Unknown error")
        messagebox.showerror(
            "Access Denied",
            f"Your access token is invalid or has been revoked.\n\nReason: {reason}\n\n"
            "Please contact your administrator."
        )
        root.destroy()
        return

    # Build and show GUI
    engine = TradingEngine.__new__(TradingEngine)
    gui    = SuperEyeGUI(root, engine)
    TradingEngine.__init__(engine, gui, client, config)

    gui.set_username(client.username or "")
    gui.log(f"Welcome, {client.username}! Token validated.")
    gui.log(f"Role: {client.role}")
    gui.log("Configure your settings and click Start Bot.")

    root.deiconify()
    root.mainloop()

if __name__ == "__main__":
    main()
