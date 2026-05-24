# Crypto Pullback V1

Radical reset after stopping TradeBot2 RTB.

This bot is intentionally narrow:

- Binance spot dry-run only
- BTC/USDT and ETH/USDT only
- 15m timeframe
- Long-only
- Pullback/reclaim entries, not breakout chasing
- No live keys

Run on Hetzner:

```bash
cd /opt/trading/crypto-pullback
docker compose up -d
docker compose logs -f freqtrade
```

Web UI via SSH tunnel:

```bash
ssh -L 8082:localhost:8082 root@91.99.99.158
```

Then open `http://localhost:8082`.

