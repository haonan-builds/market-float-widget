import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('widget', ROOT / 'crypto_float.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = m.QApplication.instance() or m.QApplication([])

    def test_okx_nested_channel(self):
        result = m.OKXExchange().parse_ws(json.dumps({'arg': {'channel': 'tickers'},
            'data': [{'instId': 'BTC-USDT', 'last': '100', 'open24h': '80'}]}))
        self.assertEqual(result, [('BTC', '100', '25.0000', '0')])

    def test_bitget_spot_subscription(self):
        url, sub = m.BitgetExchange().ws_setup(['BTC'])
        self.assertEqual(sub['args'][0]['instType'], 'SPOT')
        self.assertEqual(sub['args'][0]['instId'], 'BTCUSDT')

    def test_binance_and_bitget_quotes(self):
        self.assertEqual(m.BinanceExchange().parse_ws(json.dumps({'data': {
            'e': '24hrTicker', 's': 'BTCUSDT', 'c': '100', 'P': '2'}}))[0][:3], ('BTC', '100', '2'))
        self.assertEqual(m.BitgetExchange().parse_ws(json.dumps({'arg': {'channel': 'ticker'}, 'data': [{
            'instId': 'BTCUSDT', 'lastPr': '100', 'change24h': '0.02'}]}))[0][:3], ('BTC', '100', '2.0000'))

    def test_invalid_config_recovery(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps({'coins': [None, {'exchange': 'bad', 'symbol': 'BTC'}],
                                        'alarms': [{'price': 'nan'}]}))
            with patch.object(m, 'CONFIG_PATH', str(path)):
                cfg = m.load_config()
            self.assertEqual(len(cfg['coins']), 3)
            self.assertEqual(cfg['alarms'], [])

    def test_config_atomic_save(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / 'config.json'
            with patch.object(m, 'CONFIG_PATH', str(path)):
                self.assertTrue(m.save_config({'coins': [], '_secret': 'skip'}))
                self.assertNotIn('_secret', json.loads(path.read_text()))
                self.assertFalse(m.save_config({'price': float('nan')}))
                self.assertEqual(json.loads(path.read_text()), {'coins': []})

    def test_handshake_is_not_live_and_tls_is_verified(self):
        modes = []
        worker = m.MarketWorker(m.OKXExchange(), ['BTC'], lambda *x: None, modes.append)
        class FakeSocket:
            def __init__(self, url, **callbacks):
                self.callbacks = callbacks
            def send(self, data):
                pass
            def close(self):
                pass
            def run_forever(sock, **options):
                self.assertEqual(options['sslopt']['cert_reqs'], m.ssl.CERT_REQUIRED)
                self.assertTrue(options['sslopt']['check_hostname'])
                sock.callbacks['on_open'](sock)
                self.assertNotIn('live', modes)
                sock.callbacks['on_message'](sock, json.dumps({'arg': {'channel': 'tickers'},
                    'data': [{'instId': 'BTC-USDT', 'last': '100', 'open24h': '80'}]}))
        with patch.object(m.websocket, 'WebSocketApp', FakeSocket):
            worker._try_ws(['BTC'])
        self.assertIn('live', modes)

    def make_window(self):
        with patch.object(m, 'load_config', return_value={'coins': list(m.DEFAULT_COINS),
                'alarms': [], 'always_on_top': False}), patch.object(m.MarketWorker, 'start'):
            window = m.CryptoFloat()
        self.addCleanup(window.tray.hide)
        self.addCleanup(window.deleteLater)
        return window

    def test_pin_restored(self):
        window = self.make_window()
        self.assertFalse(window.windowFlags() & m.Qt.WindowStaysOnTopHint)

    def test_partial_and_stale_status(self):
        window = self.make_window()
        for row in window.rows.values():
            row.last_update = time.monotonic()
        window._on_status('binance', 'live')
        self.assertIn('实时', window.status_label.text())
        window._add_row('okx', 'BTC', persist=False)
        window.workers['okx'] = object()
        window._render_status()
        self.assertIn('部分', window.status_label.text())
        for row in window.rows.values():
            row.last_update = time.monotonic() - 60
        window._render_status()
        self.assertIn('无有效行情', window.status_label.text())

    def test_alert_on_quote_and_no_stale_alert(self):
        window = self.make_window()
        alarm = {'key': 'binance:BTC', 'symbol': 'BTC', 'exchange': 'binance',
                 'price': 100, 'direction': 'up'}
        window.alarms = [alarm]
        row = window.rows['binance:BTC']
        row.last_price, row.last_update = 200, time.monotonic() - 60
        with patch.object(window, '_on_alarm_triggered') as fired, patch.object(window, '_persist'):
            window._check_alarms()
            fired.assert_not_called()
            window._on_ticker('binance', 'BTC', '101', '1', '0')
            fired.assert_called_once()
            self.assertEqual(window.alarms, [])

    def test_old_kline_response_ignored(self):
        with patch.object(m.KlineWindow, '_fetch'):
            window = m.KlineWindow(m.BinanceExchange(), 'BTC')
        window._request_id = 2
        window.interval = '1h'
        candles = [['1', '10', '12', '9', '11']]
        window._on_klines(1, '15m', candles)
        self.assertEqual(window.chart.klines, [])
        window._on_klines(2, '1h', candles)
        self.assertEqual(window.chart.klines, candles)
        window.close()
        window.deleteLater()

    def test_invalid_quote_does_not_refresh_or_trigger(self):
        window = self.make_window()
        row = window.rows['binance:BTC']
        window._on_ticker('binance', 'BTC', '100', '1', '0')
        old = row.last_update
        for value in ('nan', 'inf', '-1', 'garbage'):
            window._on_ticker('binance', 'BTC', value, '1', '0')
        self.assertEqual(row.last_price, 100)
        self.assertEqual(row.last_update, old)

    def test_add_remove_persist_and_restore(self):
        window = self.make_window()
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            with patch.object(m, 'CONFIG_PATH', str(Path(directory)/'config.json')), \
                    patch.object(window, '_sync_workers'):
                window._finish_add_coin('okx', 'BTC', True)
                self.assertIn('okx:BTC', window.rows)
                self.assertIn({'exchange': 'okx', 'symbol': 'BTC'}, m.load_config()['coins'])
                window._remove_coin('okx:BTC')
                self.assertNotIn('okx:BTC', window.rows)
                self.assertNotIn({'exchange': 'okx', 'symbol': 'BTC'}, m.load_config()['coins'])

    def test_minimum_and_maximum_watchlist(self):
        window = self.make_window()
        with patch.object(m.QMessageBox, 'information'):
            window._remove_coin('binance:BTC')
        self.assertEqual(len(window.rows), 3)
        with patch.object(window, '_persist'), patch.object(window, '_sync_workers'):
            for symbol in ('A','B','C','D','E','F','G','H'):
                window._finish_add_coin('binance', symbol, True)
        self.assertEqual(len(window.rows), 10)

    def test_theme_pin_tray_and_resize_methods(self):
        window = self.make_window()
        with patch.object(window, '_persist'):
            window._toggle_theme()
            self.assertEqual(m.THEME, 'light')
            window._toggle_theme()
            self.assertEqual(m.THEME, 'dark')
            window._toggle_pin()
            self.assertTrue(window.windowFlags() & m.Qt.WindowStaysOnTopHint)
            window.show()
            window._on_close()
            self.assertFalse(window.isVisible())
            window._show_window()
            self.assertTrue(window.isVisible())
        window._resize_start_geom = m.QRect(100, 100, 380, 300)
        window._resize_start_global = m.QPoint(480, 400)
        window._resize_mode = 'rb'
        window._apply_resize(m.QPoint(5000,5000))
        self.assertEqual(window.width(), m.MAX_W)
        self.assertEqual(window.height(), m.MAX_H)

    def test_fallback_entered_after_ws_failure(self):
        worker = m.MarketWorker(m.OKXExchange(), ['BTC'], lambda *x: None, lambda x: None)
        def poll(symbols):
            self.assertEqual(symbols, ['BTC'])
            worker.stop()
        with patch.object(worker, '_try_ws', return_value=False), patch.object(worker, '_poll_rest', side_effect=poll) as rest:
            worker.run()
        rest.assert_called_once()

    def test_rest_success_and_failure_states(self):
        for result, expected in [(('100','2'),'rest'), (None,'down')]:
            modes, quotes = [], []
            worker = m.MarketWorker(m.OKXExchange(), ['BTC'], lambda *x: quotes.append(x), modes.append)
            def done(_):
                worker._stopping = True
            with patch.object(worker.exchange, 'rest_ticker', return_value=result), patch.object(m.time, 'sleep', side_effect=done):
                worker._poll_rest(['BTC'])
            self.assertEqual(modes[-1], expected)
            self.assertEqual(bool(quotes), bool(result))

    def test_reconnect_updates_symbols(self):
        worker=m.MarketWorker(m.OKXExchange(), ['BTC'], lambda *x: None, lambda x: None)
        worker.update_symbols(['BTC','ETH'])
        self.assertEqual(worker._pending,['BTC','ETH'])
        worker.mode='rest'
        worker.force_reconnect()
        self.assertEqual(worker.mode,'ws')

    def test_bitget_symbol_from_arg(self):
        result=m.BitgetExchange().parse_ws(json.dumps({'arg': {'channel':'ticker','instId':'BTCUSDT'},
            'data':[{'lastPr':'100','change24h':'0.02'}]}))
        self.assertEqual(result[0][:3],('BTC','100','2.0000'))

    def test_alarm_down_once_and_notification_dispatch(self):
        window=self.make_window()
        window.alarms=[{'key':'binance:BTC','symbol':'BTC','exchange':'binance','price':100,'direction':'down'}]
        with patch.object(window.tray,'showMessage') as notify, patch.object(m.QApplication,'beep') as beep, patch.object(window,'_persist'):
            window._on_ticker('binance','BTC','99','-1','0')
            window._on_ticker('binance','BTC','98','-2','0')
            notify.assert_called_once()
            beep.assert_called_once()
        self.assertEqual(window.alarms,[])

    def test_valid_config_normalization_and_cap(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path=Path(directory)/'config.json'
            path.write_text(json.dumps({'coins':[{'exchange':'binance','symbol':f'COIN{i}'} for i in range(20)],
                'alarms':[{'key':'binance:COIN0','direction':'up','price':50},
                          {'key':'binance:COIN1','direction':'up','price':float('inf')}]}))
            with patch.object(m,'CONFIG_PATH',str(path)):
                config=m.load_config()
        self.assertEqual(len(config['coins']),10)
        self.assertEqual(len(config['alarms']),1)

    def test_handshake_without_quotes_tries_next_endpoint(self):
        worker=m.MarketWorker(m.BinanceExchange(), ['BTC'], lambda *x: None, lambda x: None)
        urls=[]
        class Socket:
            def __init__(self,url,**callbacks):
                urls.append(url)
                self.callbacks=callbacks
            def send(self,data):pass
            def close(self):pass
            def run_forever(self,**options):self.callbacks['on_open'](self)
        with patch.object(m.websocket,'WebSocketApp',Socket):
            self.assertFalse(worker._try_ws(['BTC']))
        self.assertEqual(len(urls),2)

    def test_watchdog_stale_connection_enters_fallback(self):
        worker=m.MarketWorker(m.OKXExchange(), ['BTC'], lambda *x: None, lambda x: None)
        import threading
        done=threading.Event()
        class Socket:
            def __init__(self,url,**callbacks):self.callbacks=callbacks
            def send(self,data):pass
            def close(self):done.set()
            def run_forever(self,**options):
                self.callbacks['on_open'](self)
                done.wait(4)
        with patch.object(m.websocket,'WebSocketApp',Socket), patch.object(m,'STALE_SECONDS',0.01):
            self.assertFalse(worker._try_ws(['BTC']))
        self.assertTrue(done.is_set())

    def test_exchange_candle_adapters(self):
        candles=[['2','10','12','9','11'],['1','9','11','8','10']]
        for exchange in (m.OKXExchange(),m.BitgetExchange()):
            with patch.object(m,'http_get_json',return_value={'data':candles}):
                self.assertEqual(exchange.fetch_klines('BTC','1h')[0][0],'1')
        with patch.object(m,'http_get_json',return_value=list(reversed(candles))):
            self.assertEqual(m.BinanceExchange().fetch_klines('BTC','1h')[0][0],'1')

    def test_kline_switch_clears_previous_period(self):
        with patch.object(m.KlineWindow,'_fetch'):
            window=m.KlineWindow(m.BinanceExchange(),'BTC')
            window.chart.set_klines([['1','10','12','9','11']])
            window._change_interval('1h')
            self.assertEqual(window.chart.klines,[])
            self.assertEqual(window.interval,'1h')
        window.close();window.deleteLater()

    def test_chart_symbol_windows_and_reopen(self):
        window=self.make_window()
        with patch.object(m.KlineWindow,'_fetch'):
            window._open_kline(m.EXCHANGES['binance'],'BTC')
            window._open_kline(m.EXCHANGES['binance'],'BTC')
            window._open_kline(m.EXCHANGES['binance'],'ETH')
            self.assertEqual(len(window.kline_windows),2)
            self.assertEqual(window.kline_windows['binance:ETH'].symbol,'ETH')
            window.kline_windows['binance:BTC'].close()
            self.assertNotIn('binance:BTC',window.kline_windows)
            window._open_kline(m.EXCHANGES['binance'],'BTC')
            self.assertFalse(window.kline_windows['binance:BTC']._closed)
            for chart in list(window.kline_windows.values()):chart.close();chart.deleteLater()


if __name__ == '__main__':
    unittest.main()
