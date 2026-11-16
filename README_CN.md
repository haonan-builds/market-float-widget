# Market Float Widget — v0.2.0-dev

轻量置顶行情浮窗的实验源码版本。

## 支持市场

Binance 现货、加密货币 USDT 永续和 TradFi 永续。Bitget 现货及 USDT 永续，保留原始 RWA 元数据。保留 OKX 现货，OKX SWAP 待实网验证，暂不开放。

按交易所、现货／永续和关键词搜索官方目录。Base／原生 ID 精确匹配优先于 Base 前缀，MU 不再跨越 XLMUSDT 的报价币边界命中，必须明确选择结果。

提供最新成交报价、对应市场 REST 回退、重连／过期状态、迷你 K 线、隔离的价格提醒，以及主题、置顶、移动缩放、托盘和配置保存。

SOXLUSDT、MUUSDT 是交易所提供的永续衍生品报价，不是 ETF／股票现货行情，不代表持有证券。Binance TradFi 和 Bitget RWA 分别建模；行情链路新鲜不代表基础股票市场正在开市。

## 源码运行

使用 Windows x64 和 Python 3.12，在仓库根目录执行：

    py -3.12 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe crypto_float.py

## 配置

文件位于 ~/.crypto_float_config.json。实验请使用独立 Windows 测试用户，并备份已有配置。旧 exchange/symbol 默认按现货读取，后台查询官方 ID 并迁移关联提醒。目录失败时保留旧现货记录。显式记录保存市场、原生 ID 和元数据；旧程序不保证能读取迁移后的配置。

## 状态

准备前已有 48 项测试通过；用户确认 P1 搜索 GUI 5/5 Passed。已有 Binance／Bitget SOXL、MU 打包版行情和真实 REST 回退证据。整体验收尚有恢复、时段行为和 GUI 项，详见 [验收](docs/ACCEPTANCE.md)。
Windows 二进制发行仍为 NO-GO，本次仅准备源码更新。

## 授权与历史

项目自有源码、文档和已授权图片使用 MIT，Copyright (c) 2026 Haonan build。PySide6、Shiboken6、Qt 等依赖各自适用 LGPL／GPL 或其他条款，根目录 MIT 不单独授权组合 EXE。详见 [分发说明](DISTRIBUTION.md)。

旧 PyQt5 RC1 文档、spec 与截图作为历史材料保留于 docs/history 和 docs/screenshots，不能作为当前功能或二进制合规证明。

[English](README.md) · [构建](BUILD.md) · [变更](CHANGELOG.md)
