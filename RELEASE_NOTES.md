# Market Float Widget v0.1.0-rc.1

Windows x64 候选版。行情浮窗支持 Binance、OKX、Bitget 的 USDT 现货报价、交易所自选、迷你 K 线和价格提醒。

- WebSocket 使用 Windows 配置的 HTTP CONNECT 代理，保持 TLS 证书与主机名验证。
- 兼容 OKX 和 Bitget 不同格式的行情消息，并在连接失败时尝试 REST 轮询。
- 兼容修复版已通过用户 Windows 实机的三家实时行情、K 线切换及重启配置保存。RC 保持相同应用源码。
- Windows RC 以单文件 EXE 构建。干净 Windows 验收及公开分发材料的状态见 [发布清单](RELEASE_CHECKLIST.md)。

Windows x64 candidate for the floating Binance, OKX and Bitget USDT spot watchlist. Includes exchange-specific candlestick charts, price alerts, system proxy support and REST fallback. The compatibility build passed user testing for live quotes, chart switching and persistence. The RC uses the same application source.

Original project source remains under [MIT](LICENSE). The planned combined binary distribution is GPL-3.0-only. See [distribution](DISTRIBUTION.md).

首次 GitHub 公开以源码仓库为范围。EXE 的公开分发另按 [发布检查清单](RELEASE_CHECKLIST.md) 验收。
