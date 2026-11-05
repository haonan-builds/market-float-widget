import json
import unittest
from unittest.mock import patch
from test_regressions import m

class MessageCompatibility(unittest.TestCase):
    def test_websocket_uses_system_https_proxy_and_honors_bypass(self):
        with patch.object(m.urllib.request, 'getproxies', return_value={'https': 'http://proxy.test:8080'}), patch.object(m.urllib.request, 'proxy_bypass', return_value=False) as bypass:
            self.assertEqual(m.websocket_proxy_options('wss://ws.okx.com/ws/v5/public'),
                             {'proxy_type': 'http', 'http_proxy_host': 'proxy.test', 'http_proxy_port': 8080})
            bypass.return_value = True
            self.assertEqual(m.websocket_proxy_options('wss://ws.okx.com/ws/v5/public'), {})

    def test_okx_original_top_level_channel(self):
        payload={'channel':'tickers','data':[{'instId':'BTC-USDT','last':'100','open24h':'80'}]}
        self.assertEqual(m.OKXExchange().parse_ws(json.dumps(payload))[0][:3],('BTC','100','25.0000'))

    def test_bitget_original_flat_message(self):
        payload={'data':[{'symbol':'BTCUSDT','lastPr':'100','change24h':'0.02'}]}
        self.assertEqual(m.BitgetExchange().parse_ws(json.dumps(payload))[0][:3],('BTC','100','2.0000'))

    def test_bitget_explicit_other_channel_rejected(self):
        payload={'arg':{'channel':'trade'},'data':[{'symbol':'BTCUSDT','lastPr':'100'}]}
        self.assertEqual(m.BitgetExchange().parse_ws(json.dumps(payload)),[])

    def test_bitget_control_message_rejected(self):
        self.assertEqual(m.BitgetExchange().parse_ws(json.dumps({'event':'subscribe','data':[{'lastPr':'100'}]})),[])

    def test_bitget_non_ticker_data_rejected(self):
        self.assertEqual(m.BitgetExchange().parse_ws(json.dumps({'data':[{'symbol':'BTCUSDT','price':'100'}]})),[])
