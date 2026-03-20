"""
Telegram authentication utilities.
"""
import hmac
import hashlib
from datetime import datetime


def verify_telegram_auth(auth_data: dict, bot_token: str) -> bool:
    """
    Verify Telegram Login Widget authentication data.
    
    Args:
        auth_data: Dict with Telegram auth data (id, first_name, username, etc.)
        bot_token: Telegram bot token
        
    Returns:
        True if signature is valid
    """
    if not auth_data or not bot_token:
        return False
    
    # Required fields
    required_fields = ['id', 'hash']
    if not all(f in auth_data for f in required_fields):
        return False
    
    # Check auth_date (valid for 24 hours)
    auth_date = auth_data.get('auth_date')
    if auth_date:
        auth_timestamp = int(auth_date)
        current_timestamp = int(datetime.now().timestamp())
        if current_timestamp - auth_timestamp > 86400:  # 24 hours
            return False
    
    # Get hash
    received_hash = auth_data.pop('hash', None)
    if not received_hash:
        return False
    
    # Create data check string
    data_check_items = []
    for key, value in sorted(auth_data.items()):
        data_check_items.append(f"{key}={value}")
    data_check_string = '\n'.join(data_check_items)
    
    # Calculate secret key
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    
    # Calculate hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Compare hashes
    return hmac.compare_digest(calculated_hash, received_hash)


def parse_telegram_init_data(init_data: str) -> dict:
    """
    Parse Telegram WebApp initData string.
    
    Args:
        init_data: Query string like "user=...&auth_date=...&hash=..."
        
    Returns:
        Dict with parsed data
    """
    from urllib.parse import parse_qs
    import json
    
    result = {}
    parsed = parse_qs(init_data)
    
    for key, value in parsed.items():
        if value:
            if key == 'user' and value[0]:
                try:
                    result[key] = json.loads(value[0])
                except json.JSONDecodeError:
                    result[key] = value[0]
            else:
                result[key] = value[0]
    
    return result
