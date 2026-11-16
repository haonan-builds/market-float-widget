import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import crypto_float as m
from markets import Instrument, parse_catalog, search

def item(ex="binance", market="perpetual", base="BTC", kind="PERPETUAL",category="crypto"):
    return Instrument(ex,market,base+"USDT",base,"USDT",category,"TRADING",kind)

class MarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=m.QApplication.instance() or m.QApplication([])
    def test_catalog_identity_and_categories(self):
        r=Path(__file__).resolve().parents[1]
        for ex in ("binance","bitget"):
            data=json.loads((r/(ex+"_perpetual.json")).read_text())
            matches=search(parse_catalog(ex,"perpetual",data),"SOXLUSDT")
            exact=next(i for i in matches if i.instrument_id=="SOXLUSDT")
            self.assertNotEqual(exact.category,"crypto")
            self.assertEqual(exact.market_type,"TRADIFI_PERPETUAL" if ex=="binance" else "CRYPTO_PERPETUAL")
    def test_routes_and_subscriptions(self):
        spot=m.register_instrument(item(market="spot",kind="SPOT"))
        perp=m.register_instrument(item())
        self.assertNotEqual(spot.key,perp.key)
        self.assertIn("fstream",perp.ws_setup(["BTC"])[0])
        self.assertIn("btcusdt@ticker",perp.ws_setup(["BTC"])[0])
        bg=m.register_instrument(item(ex="bitget"))
        self.assertEqual(bg.ws_setup(["BTC"])[1]["args"][0]["instType"],"USDT-FUTURES")
        self.assertIn("/mix/",bg.KL)
        self.assertIn("/fapi/",perp.KL)
    def test_quote_native_id_filter(self):
        ex=m.register_instrument(item())
        self.assertEqual(ex.symbol_from_pair("ETHUSDT"),"")
        self.assertEqual(ex.symbol_from_pair("BTCUSDT"),"BTC")
    def test_restart_and_alert_identity(self):
        ex=m.register_instrument(item())
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as d, patch.object(m,"CONFIG_PATH",str(Path(d)/"config.json")):
            cfg=dict(coins=[*m.DEFAULT_COINS,dict(exchange=ex.key,symbol="BTC")],
                alarms=[dict(key=ex.key+":BTC",exchange=ex.key,symbol="BTC",direction="up",price=1)],
                theme="light",pos=[11,22],always_on_top=False)
            self.assertTrue(m.save_config(cfg))
            raw=json.loads(Path(m.CONFIG_PATH).read_text())
            self.assertEqual(raw["coins"][-1]["exchange"],"binance")
            self.assertEqual(raw["coins"][-1]["instrument_id"],"BTCUSDT")
            restored=m.load_config()
            self.assertEqual(restored["alarms"][0]["key"],ex.key+":BTC")
            self.assertEqual(restored["coins"][-1]["exchange"],ex.key)
            self.assertEqual(restored["pos"],[11,22])
    def test_ui_quote_and_alarm_isolation(self):
        spot=m.register_instrument(item(market="spot",kind="SPOT"))
        perp=m.register_instrument(item())
        with patch.object(m,"load_config",return_value=dict(coins=list(m.DEFAULT_COINS),alarms=[])),patch.object(m.MarketWorker,"start"),patch.object(m,"save_config",return_value=True):
            w=m.CryptoFloat()
            try:
                w._add_row(spot.key,"BTC")
                w._add_row(perp.key,"BTC")
                w._on_ticker(spot.key,"BTC","100","0","0")
                w._on_ticker(perp.key,"BTC","200","0","0")
                self.assertEqual(w.rows[spot.key+":BTC"].last_price,100)
                self.assertEqual(w.rows[perp.key+":BTC"].last_price,200)
                w.alarms=[dict(key=perp.key+":BTC",exchange=perp.key,symbol="BTC",price=150,direction="up")]
                with patch.object(w,"_on_alarm_triggered") as trigger:
                    w._check_alarms()
                    trigger.assert_called_once()
            finally:
                for worker in w.workers.values():worker.stop()
                w.tray.hide();w.deleteLater()
    def test_no_unlisted_guess(self):
        self.assertEqual(search([],"SOXL"),[])
        with self.assertRaises(ValueError):parse_catalog("bitget","spot",{"code":"bad","data":[]})


    def test_incomplete_perpetual_never_downgrades(self):
        with self.assertRaises(ValueError):
            m.restore_instrument(dict(exchange="binance",symbol="BTC",market="perpetual"))
    def test_legacy_migration_preserves_alerts(self):
        with patch.object(m,"load_config",return_value=dict(coins=list(m.DEFAULT_COINS),alarms=[])),patch.object(m.MarketWorker,"start"),patch.object(m,"save_config",return_value=True):
            w=m.CryptoFloat()
            try:
                w.alarms=[dict(key="binance:BTC",exchange="binance",symbol="BTC",price=1,direction="up")]
                native=item(market="spot",kind="SPOT")
                w._apply_legacy_migration([(dict(exchange="binance",symbol="BTC"),native)])
                route=m.register_instrument(native).key
                self.assertNotIn("binance:BTC",w.rows)
                self.assertIn(route+":BTC",w.rows)
                self.assertEqual(w.alarms[0]["key"],route+":BTC")
            finally:
                for worker in w.workers.values():worker.stop()
                w.tray.hide();w.deleteLater()
    def test_catalog_choice_and_duplicate(self):
        with patch.object(m,"load_config",return_value=dict(coins=list(m.DEFAULT_COINS),alarms=[])),patch.object(m.MarketWorker,"start"),patch.object(m,"save_config",return_value=True):
            w=m.CryptoFloat()
            native=item(base="SOXL",kind="TRADIFI_PERPETUAL",category="equity_derivative")
            label=m.instrument_label(native)
            try:
                with patch.object(m.QInputDialog,"getItem",return_value=(label,True)):
                    w._show_catalog([native],"")
                    count=len(w.rows)
                    with patch.object(m.QMessageBox,"information") as msg:
                        w._show_catalog([native],"")
                        msg.assert_called_once()
                    self.assertEqual(len(w.rows),count)
            finally:
                for worker in w.workers.values():worker.stop()
                w.tray.hide();w.deleteLater()
