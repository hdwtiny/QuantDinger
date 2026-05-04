-- Price Alerts Table Migration
-- Run this SQL to create the qd_price_alerts table

CREATE TABLE IF NOT EXISTS qd_price_alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL DEFAULT 1 REFERENCES qd_users(id) ON DELETE CASCADE,
    market VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    target_price DECIMAL(20,8) NOT NULL,
    direction VARCHAR(10) NOT NULL,           -- above: 价格高于目标时触发, below: 价格低于目标时触发
    notification_config TEXT DEFAULT '',       -- 通知配置 JSON
    is_active INTEGER DEFAULT 1,               -- 是否激活
    is_triggered INTEGER DEFAULT 0,            -- 是否已触发（每个监控价格只通知一次）
    triggered_at TIMESTAMP,                    -- 触发时间
    notes TEXT DEFAULT '',                     -- 备注
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, market, symbol, target_price, direction)
);

CREATE INDEX IF NOT EXISTS idx_price_alerts_user_id ON qd_price_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_price_alerts_active ON qd_price_alerts(is_active);
CREATE INDEX IF NOT EXISTS idx_price_alerts_symbol ON qd_price_alerts(market, symbol);

-- Add comments
COMMENT ON TABLE qd_price_alerts IS '价格预警表 - 存储用户设置的价格监控预警';
COMMENT ON COLUMN qd_price_alerts.market IS '市场类型: Crypto, USStock, Forex, Futures';
COMMENT ON COLUMN qd_price_alerts.symbol IS '交易对/股票代码: BTC/USDT, AAPL, EUR/USD';
COMMENT ON COLUMN qd_price_alerts.target_price IS '目标价格';
COMMENT ON COLUMN qd_price_alerts.direction IS '触发方向: above(价格高于目标), below(价格低于目标)';
COMMENT ON COLUMN qd_price_alerts.notification_config IS '通知配置JSON: {"channels": ["browser", "telegram", "email"]}';
COMMENT ON COLUMN qd_price_alerts.is_active IS '是否激活: 1=激活, 0=禁用';
COMMENT ON COLUMN qd_price_alerts.is_triggered IS '是否已触发: 1=已触发, 0=未触发(每个监控价格只通知一次)';
