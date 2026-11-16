"""Per-instrument routing, with isolated worker, chart, cache and alert keys."""
from markets import Instrument

def install(scope):
    registry = scope["EXCHANGES"]
    bases = {key: type(value) for key,value in registry.items()}
    get = scope["http_get_json"]

    def register(item):
        if item.exchange not in bases:
            raise ValueError("Unsupported exchange")
        if item.quote != "USDT":
            raise ValueError("Only USDT quoted instruments are supported")
        if item.market not in ("spot","perpetual") or not item.instrument_id or not item.base:
            raise ValueError("Invalid instrument")
        route = "|".join((item.exchange,item.market_type,item.instrument_id))
        if route in registry:
            return registry[route]
        base = bases[item.exchange]
        class Routed(base):
            instrument = item
            key = route
            name = base.name + (" S" if item.market == "spot" else " P")
            def pair(self, symbol):
                return item.instrument_id
            def symbol_from_pair(self, pair):
                return item.base if pair == item.instrument_id else ""
            def ws_setup(self, symbols):
                if item.exchange == "binance":
                    host = "wss://fstream.binance.com/market" if item.market == "perpetual" else "wss://data-stream.binance.vision"
                    return host+"/stream?streams="+item.instrument_id.lower()+"@ticker", None
                url, sub = super().ws_setup(symbols)
                if item.exchange == "bitget" and item.market == "perpetual":
                    sub["args"][0]["instType"] = "USDT-FUTURES"
                return url,sub
            def ws_candidates(self, symbols):
                return [self.ws_setup(symbols)]
        adapter = Routed()
        if item.market == "perpetual":
            if item.exchange == "binance":
                adapter.REST_24H = "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={p}"
                adapter.KL = "https://fapi.binance.com/fapi/v1/klines?symbol={p}&interval={i}&limit={l}"
            elif item.exchange == "bitget":
                adapter.REST_T = "https://api.bitget.com/api/v2/mix/market/ticker?productType=USDT-FUTURES&symbol={p}"
                adapter.KL = "https://api.bitget.com/api/v2/mix/market/candles?productType=USDT-FUTURES&symbol={p}&granularity={i}&limit={l}"
                adapter.KL_INTERVALS = {"1m":"1m","5m":"5m","15m":"15m","1h":"1H","4h":"4H","1d":"1D"}
        registry[route] = adapter
        return adapter

    def restore(coin):
        """Old routes remain spot; explicit records never downgrade to spot."""
        if coin.get("instrument_id"):
            item = Instrument.from_dict(coin)
            adapter = register(item)
            return dict(coin, exchange=adapter.key, symbol=item.base)
        if coin.get("market", "spot") != "spot":
            raise ValueError("Missing native ID for a non-spot instrument")
        return {k:v for k,v in coin.items() if k not in ('market','market_type')}

    def export(coin):
        adapter = registry.get(coin.get("exchange"))
        item = getattr(adapter,"instrument",None)
        if item:
            return dict(item.to_dict(), symbol=item.base)
        # Legacy defaults remain usable offline until catalog resolution.
        return dict(coin, market="spot", market_type="SPOT")

    scope.update(register_instrument=register, restore_instrument=restore, export_instrument=export)
