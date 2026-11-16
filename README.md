# Market Float Widget — v0.2.0-dev

Experimental source of a lightweight always-on-top market widget.

## Supported markets

Binance Spot, Crypto USDT-M Perpetual and TradFi Perpetual. Bitget Spot and USDT-M Futures with native RWA metadata. OKX Spot retained; OKX SWAP disabled pending network validation.

Select exchange, Spot/Perpetual and a keyword in the official instrument catalog. Exact base/native-ID matching precedes base prefixes. MU cannot match XLMUSDT across the quote boundary. Explicit selection is required.

WebSocket last-price quotes, market-specific REST fallback, reconnect/stale status, mini candles and isolated price alerts. Themes, pinning, movement/resizing, tray and configuration persistence remain available.

SOXLUSDT and MUUSDT are exchange-provided perpetual derivative quotes, not ETF/stock spot feeds or ownership of securities. Binance TradFi and Bitget RWA are distinct classifications. Feed freshness does not establish the underlying equity market's opening status.

## Run from source

Use Windows x64 and Python 3.12. Run these commands from the repository root:

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe crypto_float.py

## Configuration

The file is ~/.crypto_float_config.json. Use a separate Windows test user for experiments and back up existing configuration. Legacy exchange/symbol entries default to Spot and are resolved against official IDs in the background with attached alerts migrated. Catalog failures retain legacy Spot records. Explicit records preserve market, native ID and metadata. Older apps may not understand a migrated file.

## Status

48 tests passed before preparation; owner confirms P1 search GUI 5/5 Passed. Packaged Binance/Bitget SOXL and MU quotes and real REST fallback have prior evidence. Overall market-iteration acceptance still has pending recovery/session and GUI items: [acceptance](docs/ACCEPTANCE.md).
Windows Binary Release remains NO-GO. This source update grants no binary release approval.

## Licensing and history

Project-owned source, documentation and authorized images use MIT, Copyright (c) 2026 Haonan build. PySide6, Shiboken6, Qt and other dependencies retain their own LGPL/GPL or other terms. Root MIT does not independently license the combined EXE. See [distribution](DISTRIBUTION.md).

Historical PyQt5 RC1 records/spec and screenshots are retained in docs/history and docs/screenshots; they do not establish current functionality or binary compliance.

[中文](README_CN.md) · [Build](BUILD.md) · [Changelog](CHANGELOG.md)
