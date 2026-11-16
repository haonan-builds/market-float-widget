"""Official instrument catalog. No constructed instrument identifiers."""
from dataclasses import dataclass, field, asdict
import json
import urllib.request

@dataclass(frozen=True)
class Instrument:
    exchange: str
    market: str
    instrument_id: str
    base: str
    quote: str
    category: str
    status: str

    contract_type: str = ""
    underlying_type: str = ""
    metadata: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def market_type(self):
        if self.market == "spot":
            return "SPOT"
        return "TRADIFI_PERPETUAL" if self.contract_type == "TRADIFI_PERPETUAL" else "CRYPTO_PERPETUAL"

    def to_dict(self):
        return dict(asdict(self), market_type=self.market_type)

    @classmethod
    def from_dict(cls, value):
        return cls(**{k: v for k, v in value.items() if k in cls.__dataclass_fields__})

    @property
    def key(self):
        return self.exchange, self.market, self.instrument_id

URLS = {
    ("binance", "spot"): "https://api.binance.com/api/v3/exchangeInfo",
    ("binance", "perpetual"): "https://fapi.binance.com/fapi/v1/exchangeInfo",
    ("okx", "spot"): "https://www.okx.com/api/v5/public/instruments?instType=SPOT",
    ("okx", "perpetual"): "https://www.okx.com/api/v5/public/instruments?instType=SWAP",
    ("bitget", "spot"): "https://api.bitget.com/api/v2/spot/public/symbols",
    ("bitget", "perpetual"): "https://api.bitget.com/api/v2/mix/market/contracts?productType=USDT-FUTURES",
}

def parse_catalog(exchange, market, response):
    if exchange == "binance":
        rows = response["symbols"]
    else:
        expected = "0" if exchange == "okx" else "00000"
        if response.get("code") != expected:
            raise ValueError("Exchange rejected market discovery")
        rows = response["data"]
    result = []
    for row in rows:
        if exchange == "binance":
            ident, base, quote = row["symbol"], row["baseAsset"], row["quoteAsset"]
            status = row["status"]
            kind = row.get("contractType", "SPOT")
            if market == "perpetual" and kind not in ("PERPETUAL", "TRADIFI_PERPETUAL"):
                continue
            category = "equity_derivative" if row.get("underlyingType") == "EQUITY" else "crypto"
            active = status == "TRADING"
        elif exchange == "okx":
            ident, quote = row["instId"], row.get("quoteCcy") or row.get("settleCcy")
            base = row.get("baseCcy") or row.get("uly", "").split("-")[0]
            status = row["state"]
            category = "unclassified" if market == "perpetual" else "spot"
            active = status == "live"
            if market == "perpetual" and (row.get("settleCcy") != "USDT" or row.get("ctType") != "linear"):
                continue
        else:
            ident, base, quote = row["symbol"], row["baseCoin"], row["quoteCoin"]
            status = row.get("symbolStatus", row.get("status"))
            category = "rwa_derivative" if row.get("isRwa") == "YES" else "crypto"
            active = status in ("normal", "online")
            if market == "perpetual" and row.get("symbolType") != "perpetual":
                continue
        if active and quote == "USDT":
            result.append(Instrument(exchange, market, ident, base, quote, category, status, row.get("contractType", row.get("symbolType", "SPOT")), row.get("underlyingType", ""), dict(row)))
    return result

def discover(exchange, market):
    request = urllib.request.Request(URLS[exchange, market], headers={"User-Agent":"MarketFloatWidget"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return parse_catalog(exchange, market, json.load(response))

def _normalize(value):
    return "".join(c for c in value.upper() if c not in " /-_")

def search(instruments, keyword):
    """Search structured base assets; quote boundaries never participate."""
    query = _normalize(keyword.strip())
    if not query:
        return []
    exact_base = [item for item in instruments if _normalize(item.base) == query]
    exact_id = [item for item in instruments if _normalize(item.instrument_id) == query]
    if exact_base:
        matches = exact_base
    elif exact_id:
        matches = exact_id
    else:
        matches = [item for item in instruments if _normalize(item.base).startswith(query)]
    return sorted(matches, key=lambda item: (item.base.upper(), item.exchange,
                                             item.market_type, item.instrument_id))

def instrument_label(item):
    exchange = {"binance": "Binance", "okx": "OKX", "bitget": "Bitget"}[item.exchange]
    if item.market == "spot":
        market = "Spot"
    elif item.market_type == "TRADIFI_PERPETUAL":
        market = "Equity Perpetual" if item.underlying_type == "EQUITY" else "TradFi Perpetual"
    elif item.category == "rwa_derivative":
        market = "RWA Perpetual"
    else:
        market = "Crypto Perpetual"
    # Only names explicitly supplied as base-asset names are displayed.
    name = item.metadata.get("baseAssetName") or item.metadata.get("baseName")
    display = f"{item.base} / {item.quote}"
    if isinstance(name, str) and name.strip():
        display += " · " + name.strip()
    return f"{display} · {exchange} · {market} · {item.instrument_id}"
