# Changelog

## 0.1.0 — pre-release repairs / 发布前修复

- Verify TLS certificates and hostnames for WebSocket connections.
- Correct OKX nested ticker channel parsing, use production public endpoint, and correct Bitget SPOT subscriptions.
- Add application text heartbeats and stale-quote watchdogs; a handshake alone no longer means live data.
- Report partial outages and failed REST rounds; fetch REST symbols concurrently.
- Check one-shot alerts on valid quote delivery and exclude stale prices; reject nonfinite/nonpositive targets.
- Validate symbols asynchronously so adding a watchlist item does not block the UI.
- Ignore obsolete K-line responses, validate candle prices and suppress updates after close.
- Normalize saved watchlists/alerts, save config atomically and notify on save failure.
- Restore persisted pin preference and avoid starting workers before connecting signals.
- Pin runtime/build requirements; use a tracked portable PyInstaller spec.
- Update English/Chinese documentation, privacy details and binary distribution requirements.

修复范围：证书验证、交易所适配、心跳与过期检测、部分断线提示、并发 REST、有效行情报警、异步添加币种、K 线请求顺序、配置校验及保存、置顶恢复、依赖固定、中英文安装和分发说明。
