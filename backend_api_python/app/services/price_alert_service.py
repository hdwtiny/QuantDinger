"""
Price Alert Service - 价格预警服务

提供价格监测和预警通知功能：
1. 创建/更新/删除价格预警
2. 定期检查价格并触发通知（每个价格只通知一次）
3. 通过用户配置的通知渠道发送预警消息
"""

import time
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from app.utils.db import get_db_connection
from app.utils.logger import get_logger
from app.services.kline import KlineService
from app.services.signal_notifier import SignalNotifier
from app.services.user_service import get_user_service

logger = get_logger(__name__)


class PriceAlertService:
    """价格预警服务"""
    
    def __init__(self):
        self.kline_service = KlineService()
        self.notifier = SignalNotifier()
        import os
        # 从环境变量读取检查间隔，默认为10秒
        self.check_interval = int(os.getenv('PRICE_ALERT_CHECK_INTERVAL', '10'))
    
    def create_alert(self, user_id: int, market: str, symbol: str, target_price: float, 
                     direction: str = 'above', notification_config: Optional[str] = None, 
                     notes: str = '') -> bool:
        """
        创建价格预警
        
        Args:
            user_id: 用户ID
            market: 市场类型 (Crypto, USStock, Forex, Futures)
            symbol: 交易对/股票代码
            target_price: 目标价格
            direction: 触发方向 ('above': 高于目标价格时触发, 'below': 低于目标价格时触发)
            notification_config: 通知配置 JSON
            notes: 备注
        
        Returns:
            True if successful, False otherwise
        """
        try:
            direction = direction.lower()
            if direction not in ('above', 'below'):
                raise ValueError("direction must be 'above' or 'below'")
            
            alert_id = None
            
            with get_db_connection() as db:
                cur = db.cursor()
                # First try upsert
                cur.execute(
                    """
                    INSERT INTO qd_price_alerts 
                    (user_id, market, symbol, target_price, direction, notification_config, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), NOW())
                    ON CONFLICT(user_id, market, symbol, target_price, direction) DO UPDATE SET
                        notification_config = COALESCE(EXCLUDED.notification_config, qd_price_alerts.notification_config),
                        notes = COALESCE(EXCLUDED.notes, qd_price_alerts.notes),
                        is_active = 1,
                        is_triggered = 0,
                        updated_at = NOW()
                    """,
                    (user_id, market, symbol, target_price, direction, notification_config or '', notes)
                )
                
                # Try to get inserted ID
                if hasattr(cur, 'lastrowid'):
                    alert_id = cur.lastrowid
                elif hasattr(cur, 'last_insert_id'):
                    alert_id = cur.last_insert_id()
                else:
                    # Fallback: select most recent
                    cur.execute(
                        "SELECT id FROM qd_price_alerts WHERE user_id = ? AND market = ? AND symbol = ? AND target_price = ? AND direction = ? ORDER BY created_at DESC LIMIT 1",
                        (user_id, market, symbol, target_price, direction)
                    )
                    row = cur.fetchone()
                    if row:
                        alert_id = row['id'] if isinstance(row, dict) else row[0]
                
                db.commit()
                cur.close()
            
            logger.info(f"Created price alert: user_id={user_id}, market={market}, symbol={symbol}, target_price={target_price}, direction={direction}, alert_id={alert_id}")
            
            # 立即检查当前价格是否已满足条件
            if alert_id:
                self._check_single_alert(alert_id, user_id, market, symbol, target_price, direction, notification_config)
            
            return True
        except Exception as e:
            logger.error(f"Failed to create price alert: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def get_alerts(self, user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        获取用户的价格预警列表
        
        Args:
            user_id: 用户ID
            active_only: 是否只返回激活的预警
        
        Returns:
            预警列表
        """
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                if active_only:
                    cur.execute(
                        "SELECT * FROM qd_price_alerts WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC",
                        (user_id,)
                    )
                else:
                    cur.execute(
                        "SELECT * FROM qd_price_alerts WHERE user_id = ? ORDER BY created_at DESC",
                        (user_id,)
                    )
                rows = cur.fetchall() or []
                cur.close()
            
            return rows
        except Exception as e:
            logger.error(f"Failed to get price alerts: {e}")
            return []
    
    def get_alert_by_id(self, user_id: int, alert_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取预警详情
        
        Args:
            user_id: 用户ID
            alert_id: 预警ID
        
        Returns:
            预警详情或None
        """
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute(
                    "SELECT * FROM qd_price_alerts WHERE id = ? AND user_id = ?",
                    (alert_id, user_id)
                )
                row = cur.fetchone()
                cur.close()
            
            return row
        except Exception as e:
            logger.error(f"Failed to get price alert by id: {e}")
            return None
    
    def update_alert(self, user_id: int, alert_id: int, **kwargs) -> bool:
        """
        更新价格预警
        
        Args:
            user_id: 用户ID
            alert_id: 预警ID
            kwargs: 要更新的字段 (target_price, direction, notification_config, notes, is_active)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            update_fields = []
            params = []
            
            if 'target_price' in kwargs:
                update_fields.append("target_price = ?")
                params.append(kwargs['target_price'])
            
            if 'direction' in kwargs:
                direction = kwargs['direction'].lower()
                if direction not in ('above', 'below'):
                    raise ValueError("direction must be 'above' or 'below'")
                update_fields.append("direction = ?")
                params.append(direction)
            
            if 'notification_config' in kwargs:
                update_fields.append("notification_config = ?")
                params.append(kwargs['notification_config'])
            
            if 'notes' in kwargs:
                update_fields.append("notes = ?")
                params.append(kwargs['notes'])
            
            if 'is_active' in kwargs:
                update_fields.append("is_active = ?")
                params.append(kwargs['is_active'])
                # 如果重新激活，重置触发状态
                if kwargs['is_active']:
                    update_fields.append("is_triggered = 0")
                    update_fields.append("triggered_at = NULL")
            
            if not update_fields:
                return False
            
            update_fields.append("updated_at = NOW()")
            params.extend([alert_id, user_id])
            
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute(
                    f"UPDATE qd_price_alerts SET {', '.join(update_fields)} WHERE id = ? AND user_id = ?",
                    tuple(params)
                )
                db.commit()
                cur.close()
            
            logger.info(f"Updated price alert: alert_id={alert_id}, user_id={user_id}")
            
            # 如果重新激活了预警，立即检查
            if kwargs.get('is_active', False):
                alert = self.get_alert_by_id(user_id, alert_id)
                if alert:
                    self._check_single_alert(
                        alert_id=alert_id,
                        user_id=user_id,
                        market=alert.get('market'),
                        symbol=alert.get('symbol'),
                        target_price=alert.get('target_price'),
                        direction=alert.get('direction'),
                        notification_config=alert.get('notification_config', '')
                    )
            
            return True
        except Exception as e:
            logger.error(f"Failed to update price alert: {e}")
            return False
    
    def delete_alert(self, user_id: int, alert_id: int) -> bool:
        """
        删除价格预警
        
        Args:
            user_id: 用户ID
            alert_id: 预警ID
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute(
                    "DELETE FROM qd_price_alerts WHERE id = ? AND user_id = ?",
                    (alert_id, user_id)
                )
                db.commit()
                cur.close()
            
            logger.info(f"Deleted price alert: alert_id={alert_id}, user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete price alert: {e}")
            return False
    
    def check_and_trigger_alerts(self) -> int:
        """
        检查所有激活的预警并触发通知
        
        Returns:
            触发的预警数量
        """
        triggered_count = 0
        
        try:
            # 获取所有激活且未触发的预警
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute(
                    "SELECT * FROM qd_price_alerts WHERE is_active = 1 AND is_triggered = 0"
                )
                alerts = cur.fetchall() or []
                cur.close()
            
            if not alerts:
                return 0
            
            logger.info(f"Checking {len(alerts)} active price alerts...")
            
            # 逐个检查预警
            for alert in alerts:
                try:
                    alert_id = alert.get('id')
                    user_id = alert.get('user_id')
                    market = alert.get('market')
                    symbol = alert.get('symbol')
                    target_price = alert.get('target_price')
                    direction = alert.get('direction')
                    notification_config = alert.get('notification_config')
                    
                    if not all([market, symbol, target_price, direction]):
                        continue
                    
                    # 获取当前价格
                    price_data = self.kline_service.get_realtime_price(market, symbol)
                    current_price = price_data.get('price', 0)
                    
                    if current_price <= 0:
                        logger.debug(f"Cannot get price for {market}:{symbol}, skipping")
                        continue
                    
                    # 判断是否触发
                    should_trigger = False
                    if direction == 'above' and current_price >= target_price:
                        should_trigger = True
                    elif direction == 'below' and current_price <= target_price:
                        should_trigger = True
                    
                    if should_trigger:
                        # 发送通知
                        self._send_alert_notification(
                            user_id=user_id,
                            alert_id=alert_id,
                            market=market,
                            symbol=symbol,
                            target_price=target_price,
                            current_price=current_price,
                            direction=direction,
                            notification_config=notification_config
                        )
                        
                        # 标记为已触发
                        self._mark_as_triggered(alert_id)
                        triggered_count += 1
                    
                except Exception as e:
                    logger.error(f"Error checking alert {alert.get('id')}: {e}")
            
            if triggered_count > 0:
                logger.info(f"Triggered {triggered_count} price alert(s)")
            
            return triggered_count
        
        except Exception as e:
            logger.error(f"Failed to check price alerts: {e}")
            return 0
    
    def _send_alert_notification(self, user_id: int, alert_id: int, market: str, symbol: str,
                                 target_price: float, current_price: float, direction: str,
                                 notification_config: str):
        """
        发送价格预警通知
        
        Args:
            user_id: 用户ID
            alert_id: 预警ID
            market: 市场类型
            symbol: 交易对
            target_price: 目标价格
            current_price: 当前价格
            direction: 触发方向
            notification_config: 通知配置
        """
        try:
            # 直接从数据库获取用户通知设置
            user_notification_settings = ''
            try:
                with get_db_connection() as db:
                    cur = db.cursor()
                    cur.execute("SELECT notification_settings FROM qd_users WHERE id = ?", (user_id,))
                    row = cur.fetchone()
                    if row:
                        user_notification_settings = row['notification_settings'] if isinstance(row, dict) else row[0]
                    cur.close()
            except Exception as e:
                logger.warning(f"Failed to get user notification settings: {e}")
            
            logger.info(f"User notification settings: {user_notification_settings}")
            channels = ['browser']
            targets = {}
            
            if user_notification_settings:
                try:
                    settings = json.loads(user_notification_settings)
                    logger.info(f"Parsed settings: {settings}")
                    # 获取默认渠道
                    channels = settings.get('default_channels', ['browser'])
                    # 转换配置格式
                    if 'webhook_url' in settings:
                        targets['webhook'] = settings['webhook_url']
                        logger.info(f"Set webhook target: {targets['webhook']}")
                    if 'telegram_bot_token' in settings:
                        targets['telegram_bot_token'] = settings['telegram_bot_token']
                    if 'telegram_chat_id' in settings:
                        targets['telegram'] = settings['telegram_chat_id']
                except Exception as e:
                    logger.warning(f"Failed to parse user notification settings: {e}")
            
            # 合并用户配置和预警配置
            if notification_config:
                try:
                    config = json.loads(notification_config)
                    if 'channels' in config:
                        channels = config['channels']
                    if 'targets' in config:
                        targets.update(config['targets'])
                except Exception as e:
                    logger.warning(f"Failed to parse alert notification config: {e}")
            
            logger.info(f"Final channels: {channels}")
            logger.info(f"Final targets: {targets}")
            
            # 构建通知配置
            notification_config_full = json.dumps({
                'channels': channels,
                'targets': targets
            })
            
            # 获取一个存在的策略ID，或者使用第一个策略
            strategy_id = 0
            strategy_name = 'Price Alert'
            try:
                with get_db_connection() as db:
                    cur = db.cursor()
                    cur.execute("SELECT id, strategy_name FROM qd_strategies_trading WHERE user_id = ? LIMIT 1", (user_id,))
                    row = cur.fetchone()
                    if row:
                        strategy_id = row['id'] if isinstance(row, dict) else row[0]
                        if isinstance(row, dict) and 'strategy_name' in row:
                            strategy_name = row['strategy_name']
                        elif isinstance(row, tuple) and len(row) > 1:
                            strategy_name = row[1]
                    cur.close()
            except Exception:
                pass
            
            # 使用SignalNotifier发送通知
            # 将 Decimal 类型转换为 float 以避免 JSON 序列化错误
            from decimal import Decimal
            result = self.notifier.notify_signal(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                symbol=symbol,
                signal_type='price_alert',
                price=float(current_price),
                notification_config=notification_config_full,
                extra={
                    'alert_id': int(alert_id),
                    'target_price': float(target_price) if isinstance(target_price, Decimal) else target_price,
                    'direction': direction,
                    'market': market
                }
            )
            
            logger.info(f"Notification sent for alert {alert_id}: {result}")
            
        except Exception as e:
            logger.error(f"Failed to send notification for alert {alert_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _mark_as_triggered(self, alert_id: int):
        """
        标记预警为已触发
        
        Args:
            alert_id: 预警ID
        """
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute(
                    "UPDATE qd_price_alerts SET is_triggered = 1, triggered_at = NOW() WHERE id = ?",
                    (alert_id,)
                )
                db.commit()
                cur.close()
            
            logger.debug(f"Marked alert {alert_id} as triggered")
        except Exception as e:
            logger.error(f"Failed to mark alert {alert_id} as triggered: {e}")
    
    def _check_single_alert(self, alert_id: int, user_id: int, market: str, symbol: str,
                         target_price: float, direction: str, notification_config: str):
        """
        立即检查单个预警是否满足条件并触发通知
        
        Args:
            alert_id: 预警ID
            user_id: 用户ID
            market: 市场类型
            symbol: 交易对
            target_price: 目标价格
            direction: 触发方向
            notification_config: 通知配置
        """
        try:
            # 获取当前价格
            price_data = self.kline_service.get_realtime_price(market, symbol)
            current_price = price_data.get('price', 0)
            
            if current_price <= 0:
                logger.warning(f"Cannot get price for {market}:{symbol} when creating alert")
                return
            
            logger.info(f"Checking new alert immediately: {market}:{symbol}, {target_price} @ {current_price} (direction: {direction})")
            
            # 判断是否触发
            should_trigger = False
            if direction == 'above' and current_price >= target_price:
                should_trigger = True
                logger.info(f"Price is already above target, triggering now")
            elif direction == 'below' and current_price <= target_price:
                should_trigger = True
                logger.info(f"Price is already below target, triggering now")
            
            if should_trigger:
                # 发送通知
                self._send_alert_notification(
                    user_id=user_id,
                    alert_id=alert_id,
                    market=market,
                    symbol=symbol,
                    target_price=target_price,
                    current_price=current_price,
                    direction=direction,
                    notification_config=notification_config
                )
                
                # 标记为已触发
                self._mark_as_triggered(alert_id)
                logger.info(f"Alert {alert_id} triggered immediately on creation")
            
        except Exception as e:
            logger.error(f"Error checking single alert {alert_id}: {e}")
    
    def run_alert_monitor(self, interval: Optional[int] = None):
        """
        启动价格预警监控循环（后台运行）
        
        Args:
            interval: 检查间隔（秒），默认为30秒
        """
        check_interval = interval or self.check_interval
        
        logger.info(f"Starting price alert monitor with {check_interval}s interval...")
        
        while True:
            try:
                self.check_and_trigger_alerts()
            except Exception as e:
                logger.error(f"Error in alert monitor loop: {e}")
            
            time.sleep(check_interval)


# 全局实例
_price_alert_service = None


def get_price_alert_service() -> PriceAlertService:
    """获取价格预警服务实例（单例）"""
    global _price_alert_service
    if _price_alert_service is None:
        _price_alert_service = PriceAlertService()
    return _price_alert_service