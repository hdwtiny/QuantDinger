"""
Price Alert API Routes - 价格预警API路由

提供价格预警的RESTful API接口：
- 创建预警
- 获取预警列表
- 获取预警详情
- 更新预警
- 删除预警
"""

from flask import Blueprint, request, jsonify, g
import json
import traceback

from app.utils.logger import get_logger
from app.utils.auth import login_required
from app.services.price_alert_service import get_price_alert_service

logger = get_logger(__name__)

price_alert_bp = Blueprint('price_alert', __name__)


@price_alert_bp.route('/alerts', methods=['GET'])
@login_required
def get_alerts():
    """
    获取用户的价格预警列表
    
    请求参数:
        active_only: 是否只返回激活的预警 (默认: true)
    
    响应:
        {
            "code": 1,
            "msg": "success",
            "data": [
                {
                    "id": 1,
                    "market": "Crypto",
                    "symbol": "BTC/USDT",
                    "target_price": 45000.0,
                    "direction": "above",
                    "is_active": 1,
                    "is_triggered": 0,
                    "notes": "我的第一个预警",
                    "created_at": "2024-01-01 12:00:00"
                }
            ]
        }
    """
    try:
        user_id = g.user_id
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        service = get_price_alert_service()
        alerts = service.get_alerts(user_id, active_only)
        
        return jsonify({
            'code': 1,
            'msg': 'success',
            'data': alerts
        })
    
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'code': 0,
            'msg': f'Failed: {str(e)}',
            'data': None
        }), 500


@price_alert_bp.route('/alerts/<int:alert_id>', methods=['GET'])
@login_required
def get_alert(alert_id):
    """
    获取单个预警详情
    
    路径参数:
        alert_id: 预警ID
    
    响应:
        {
            "code": 1,
            "msg": "success",
            "data": {
                "id": 1,
                "market": "Crypto",
                "symbol": "BTC/USDT",
                "target_price": 45000.0,
                "direction": "above",
                "is_active": 1,
                "is_triggered": 0,
                "triggered_at": null,
                "notes": "我的第一个预警",
                "created_at": "2024-01-01 12:00:00",
                "updated_at": "2024-01-01 12:00:00"
            }
        }
    """
    try:
        user_id = g.user_id
        
        service = get_price_alert_service()
        alert = service.get_alert_by_id(user_id, alert_id)
        
        if not alert:
            return jsonify({
                'code': 0,
                'msg': 'Alert not found',
                'data': None
            }), 404
        
        return jsonify({
            'code': 1,
            'msg': 'success',
            'data': alert
        })
    
    except Exception as e:
        logger.error(f"Failed to get alert: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'code': 0,
            'msg': f'Failed: {str(e)}',
            'data': None
        }), 500


@price_alert_bp.route('/alerts', methods=['POST'])
@login_required
def create_alert():
    """
    创建价格预警
    
    请求体:
        {
            "market": "Crypto",           // 市场类型 (Crypto, USStock, Forex, Futures)
            "symbol": "BTC/USDT",         // 交易对/股票代码
            "target_price": 45000.0,      // 目标价格
            "direction": "above",          // 触发方向: 'above' (高于) 或 'below' (低于)
            "notification_config": "{...}", // 通知配置 JSON (可选)
            "notes": "我的预警备注"         // 备注 (可选)
        }
    
    响应:
        {
            "code": 1,
            "msg": "success",
            "data": null
        }
    """
    try:
        user_id = g.user_id
        data = request.get_json() or {}
        
        market = (data.get('market') or '').strip()
        symbol = (data.get('symbol') or '').strip()
        target_price = data.get('target_price')
        direction = (data.get('direction') or 'above').strip()
        notification_config = data.get('notification_config', '')
        notes = (data.get('notes') or '').strip()
        
        # 验证参数
        if not market:
            return jsonify({
                'code': 0,
                'msg': 'market is required',
                'data': None
            }), 400
        
        if not symbol:
            return jsonify({
                'code': 0,
                'msg': 'symbol is required',
                'data': None
            }), 400
        
        if target_price is None:
            return jsonify({
                'code': 0,
                'msg': 'target_price is required',
                'data': None
            }), 400
        
        try:
            target_price = float(target_price)
        except ValueError:
            return jsonify({
                'code': 0,
                'msg': 'target_price must be a number',
                'data': None
            }), 400
        
        if direction not in ('above', 'below'):
            return jsonify({
                'code': 0,
                'msg': 'direction must be "above" or "below"',
                'data': None
            }), 400
        
        # 创建预警
        service = get_price_alert_service()
        success = service.create_alert(
            user_id=user_id,
            market=market,
            symbol=symbol,
            target_price=target_price,
            direction=direction,
            notification_config=notification_config,
            notes=notes
        )
        
        if success:
            return jsonify({
                'code': 1,
                'msg': 'success',
                'data': None
            })
        else:
            return jsonify({
                'code': 0,
                'msg': 'Failed to create alert',
                'data': None
            }), 500
    
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'code': 0,
            'msg': f'Failed: {str(e)}',
            'data': None
        }), 500


@price_alert_bp.route('/alerts/<int:alert_id>', methods=['PUT'])
@login_required
def update_alert(alert_id):
    """
    更新价格预警
    
    路径参数:
        alert_id: 预警ID
    
    请求体:
        {
            "target_price": 46000.0,      // 目标价格 (可选)
            "direction": "below",          // 触发方向 (可选)
            "notification_config": "{...}", // 通知配置 (可选)
            "notes": "更新后的备注",        // 备注 (可选)
            "is_active": 1                 // 是否激活 (可选)
        }
    
    响应:
        {
            "code": 1,
            "msg": "success",
            "data": null
        }
    """
    try:
        user_id = g.user_id
        data = request.get_json() or {}
        
        # 构建更新参数
        update_params = {}
        
        if 'target_price' in data:
            try:
                update_params['target_price'] = float(data['target_price'])
            except ValueError:
                return jsonify({
                    'code': 0,
                    'msg': 'target_price must be a number',
                    'data': None
                }), 400
        
        if 'direction' in data:
            direction = data['direction'].strip()
            if direction not in ('above', 'below'):
                return jsonify({
                    'code': 0,
                    'msg': 'direction must be "above" or "below"',
                    'data': None
                }), 400
            update_params['direction'] = direction
        
        if 'notification_config' in data:
            update_params['notification_config'] = data['notification_config']
        
        if 'notes' in data:
            update_params['notes'] = data['notes']
        
        if 'is_active' in data:
            update_params['is_active'] = int(data['is_active'])
        
        if not update_params:
            return jsonify({
                'code': 0,
                'msg': 'No fields to update',
                'data': None
            }), 400
        
        # 更新预警
        service = get_price_alert_service()
        success = service.update_alert(user_id, alert_id, **update_params)
        
        if success:
            return jsonify({
                'code': 1,
                'msg': 'success',
                'data': None
            })
        else:
            return jsonify({
                'code': 0,
                'msg': 'Failed to update alert (alert not found or no changes)',
                'data': None
            }), 404
    
    except Exception as e:
        logger.error(f"Failed to update alert: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'code': 0,
            'msg': f'Failed: {str(e)}',
            'data': None
        }), 500


@price_alert_bp.route('/alerts/<int:alert_id>', methods=['DELETE'])
@login_required
def delete_alert(alert_id):
    """
    删除价格预警
    
    路径参数:
        alert_id: 预警ID
    
    响应:
        {
            "code": 1,
            "msg": "success",
            "data": null
        }
    """
    try:
        user_id = g.user_id
        
        service = get_price_alert_service()
        success = service.delete_alert(user_id, alert_id)
        
        if success:
            return jsonify({
                'code': 1,
                'msg': 'success',
                'data': None
            })
        else:
            return jsonify({
                'code': 0,
                'msg': 'Failed to delete alert (alert not found)',
                'data': None
            }), 404
    
    except Exception as e:
        logger.error(f"Failed to delete alert: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'code': 0,
            'msg': f'Failed: {str(e)}',
            'data': None
        }), 500


@price_alert_bp.route('/alerts/check', methods=['POST'])
@login_required
def check_alerts():
    """
    手动触发价格检查（测试用）
    
    响应:
        {
            "code": 1,
            "msg": "success",
            "data": {
                "triggered_count": 0
            }
        }
    """
    try:
        service = get_price_alert_service()
        triggered_count = service.check_and_trigger_alerts()
        
        return jsonify({
            'code': 1,
            'msg': 'success',
            'data': {
                'triggered_count': triggered_count
            }
        })
    
    except Exception as e:
        logger.error(f"Failed to check alerts: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'code': 0,
            'msg': f'Failed: {str(e)}',
            'data': None
        }), 500


# ==================== 公开API（无需登录，用于外部调用） ====================

@price_alert_bp.route('/api/alerts/public/create', methods=['POST'])
def create_alert_public():
    """
    公开API：创建价格预警（需要API Token验证）
    
    请求体:
        {
            "token": "your_api_token",     // API Token
            "market": "Crypto",            // 市场类型
            "symbol": "BTC/USDT",          // 交易对
            "target_price": 45000.0,       // 目标价格
            "direction": "above",          // 触发方向
            "notification_config": "{...}", // 通知配置
            "notes": "备注"                 // 备注
        }
    
    响应:
        {
            "code": 1,
            "msg": "success",
            "data": null
        }
    """
    try:
        data = request.get_json() or {}
        
        # 验证API Token
        token = (data.get('token') or '').strip()
        if not token:
            return jsonify({
                'code': 0,
                'msg': 'API token is required',
                'data': None
            }), 401
        
        # 从token获取用户（这里简化处理，实际应验证token并获取用户）
        # 实际实现中应该验证agent token
        user_id = 1  # 默认用户
        
        market = (data.get('market') or '').strip()
        symbol = (data.get('symbol') or '').strip()
        target_price = data.get('target_price')
        direction = (data.get('direction') or 'above').strip()
        notification_config = data.get('notification_config', '')
        notes = (data.get('notes') or '').strip()
        
        if not market or not symbol or target_price is None:
            return jsonify({
                'code': 0,
                'msg': 'market, symbol, and target_price are required',
                'data': None
            }), 400
        
        try:
            target_price = float(target_price)
        except ValueError:
            return jsonify({
                'code': 0,
                'msg': 'target_price must be a number',
                'data': None
            }), 400
        
        if direction not in ('above', 'below'):
            return jsonify({
                'code': 0,
                'msg': 'direction must be "above" or "below"',
                'data': None
            }), 400
        
        service = get_price_alert_service()
        success = service.create_alert(
            user_id=user_id,
            market=market,
            symbol=symbol,
            target_price=target_price,
            direction=direction,
            notification_config=notification_config,
            notes=notes
        )
        
        if success:
            return jsonify({
                'code': 1,
                'msg': 'success',
                'data': None
            })
        else:
            return jsonify({
                'code': 0,
                'msg': 'Failed to create alert',
                'data': None
            }), 500
    
    except Exception as e:
        logger.error(f"Failed to create alert via public API: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'code': 0,
            'msg': f'Failed: {str(e)}',
            'data': None
        }), 500