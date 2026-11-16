import unittest
from unittest.mock import patch
from test_markets import m
from markets import Instrument, search, instrument_label

def asset(base,exchange="bitget",market="perpetual",category="crypto",kind="perpetual",underlying=""):
    return Instrument(exchange,market,base+"USDT",base,"USDT",category,"normal",kind,underlying)

class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=m.QApplication.instance() or m.QApplication([])
    def setUp(self):
        self.items=[asset(s) for s in ("XLM","MUU","MU","BTC","ETH","SOXL")]
    def test_mu_not_cross_quote_boundary(self):
        self.assertEqual([x.base for x in search(self.items,"MU")],["MU"])
    def test_exact_native_id(self):
        self.assertEqual([x.base for x in search(self.items,"MUUSDT")],["MU"])
    def test_muu_distinct(self):
        self.assertEqual([x.base for x in search(self.items,"MUU")],["MUU"])
    def test_existing_assets(self):
        for base in ("XLM","BTC","ETH","SOXL"):
            with self.subTest(base=base):
                self.assertEqual([x.base for x in search(self.items,base)],[base])
    def test_short_fuzzy_is_prefix_only(self):
        self.assertEqual(search([asset("XLM")],"MU"),[])
        self.assertEqual(search(self.items,""),[])
        self.assertEqual([x.base for x in search([asset("MUU"),asset("MUC")],"MU")],["MUC","MUU"])
    def test_pair_input_and_quote_not_stripped_globally(self):
        self.assertEqual([x.base for x in search(self.items,"MU / USDT")],["MU"])
        self.assertEqual(search(self.items,"USDT"),[])
    def test_market_exchange_labels_identity(self):
        items=[asset("MU","binance",category="equity_derivative",kind="TRADIFI_PERPETUAL",underlying="EQUITY"),
               asset("MU",category="rwa_derivative"),asset("MU",market="spot")]
        labels=[instrument_label(i) for i in items]
        self.assertIn("Equity Perpetual",labels[0])
        self.assertIn("RWA Perpetual",labels[1])
        self.assertIn("Spot",labels[2])
        self.assertNotIn("Micron",labels[0]) # no guessed names
        self.assertEqual(len({i.key for i in items}),3)
    def test_no_default_or_cancel_or_empty_add(self):
        with patch.object(m,"load_config",return_value=dict(coins=list(m.DEFAULT_COINS),alarms=[])),patch.object(m.MarketWorker,"start"):
            w=m.CryptoFloat()
            try:
                count=len(w.rows)
                for choice,ok in [("— 请选择具体标的 —",True),("",False),("unrelated",True)]:
                    with patch.object(m.QInputDialog,"getItem",return_value=(choice,ok)):
                        w._show_catalog([asset("MU")],"")
                    self.assertEqual(len(w.rows),count)
                with patch.object(m.QMessageBox,"information") as msg:
                    w._show_catalog([],"")
                    msg.assert_called_once()
                self.assertEqual(len(w.rows),count)
            finally:
                for worker in w.workers.values():worker.stop()
                w.tray.hide();w.deleteLater()
