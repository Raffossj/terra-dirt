from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, timedelta
import hashlib
import threading
import requests

app = Flask(__name__)

DISCORD_CHANNEL_ID = 1442158195824001116

def get_db_connection():
    """Get direct database connection"""
    db_url = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(db_url)
    return conn

def hash_hwid(hwid):
    if hwid:
        return hashlib.sha256(hwid.encode()).hexdigest()
    return None

def validate_key_sync(key_code, discord_id=None, hwid=None):
    """Synchronous key validation - FAST"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get key data
        cur.execute('''
            SELECT k.*, s.script_name
            FROM keys k
            LEFT JOIN scripts s ON k.script_id = s.script_id
            WHERE k.key_code = %s
        ''', (key_code,))
        
        key_data = cur.fetchone()
        
        if not key_data:
            cur.close()
            conn.close()
            return {'valid': False, 'code': 'KEY_NOT_FOUND', 'message': 'Invalid key'}
        
        # Check if inactive
        if not key_data['is_active']:
            cur.close()
            conn.close()
            return {'valid': False, 'code': 'KEY_INACTIVE', 'message': 'Key is inactive'}
        
        # Check if expired
        if key_data['expires_at'] and datetime.now() > key_data['expires_at']:
            cur.close()
            conn.close()
            return {'valid': False, 'code': 'KEY_EXPIRED', 'message': 'Key has expired'}
        
        # Check Discord ID binding
        if discord_id and key_data['discord_id'] and key_data['discord_id'] != discord_id:
            cur.close()
            conn.close()
            return {'valid': False, 'code': 'DISCORD_ID_MISMATCH', 'message': 'Key bound to different user'}
        
        # Check HWID
        if hwid:
            hwid_hash = hash_hwid(hwid)
            if key_data['hwid_hash'] is None:
                # Bind HWID on first use
                cur.execute('UPDATE keys SET hwid_hash = %s WHERE key_code = %s', (hwid_hash, key_code))
            elif key_data['hwid_hash'] != hwid_hash:
                cur.close()
                conn.close()
                return {'valid': False, 'code': 'HWID_MISMATCH', 'message': 'Key bound to different device'}
        
        # Check max uses
        if key_data['max_uses'] > 0 and key_data['current_uses'] >= key_data['max_uses']:
            cur.close()
            conn.close()
            return {'valid': False, 'code': 'MAX_USES_EXCEEDED', 'message': 'Key usage limit exceeded'}
        
        # Increment usage
        cur.execute('UPDATE keys SET current_uses = current_uses + 1 WHERE key_code = %s', (key_code,))
        
        # Log validation
        cur.execute('''
            INSERT INTO key_validations (key_code, discord_id, hwid_hash, success, error_code)
            VALUES (%s, %s, %s, %s, %s)
        ''', (key_code, discord_id, hash_hwid(hwid) if hwid else None, True, None))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {'valid': True, 'code': 'KEY_VALID', 'message': 'Key is valid'}
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return {'valid': False, 'code': 'ERROR', 'message': str(e)}

def send_discord_notification_async(key_code, valid, user_id=None, error_code=None):
    """Send Discord notification in background (non-blocking)"""
    def send():
        try:
            bot_token = os.environ.get('DISCORD_BOT_TOKEN')
            if not bot_token:
                return
            
            headers = {
                'Authorization': f'Bot {bot_token}',
                'Content-Type': 'application/json'
            }
            
            if valid:
                embed = {
                    "title": "✅ Key Validation Successful",
                    "description": "A key was successfully validated",
                    "color": 65280,
                    "fields": [
                        {"name": "Key (masked)", "value": f"`{key_code[:8]}...{key_code[-4:]}`", "inline": True},
                        {"name": "User ID", "value": str(user_id) if user_id else "Unknown", "inline": True},
                    ]
                }
            else:
                embed = {
                    "title": "❌ Key Validation Failed",
                    "description": "A key validation attempt failed",
                    "color": 16711680,
                    "fields": [
                        {"name": "Key (masked)", "value": f"`{key_code[:8]}...{key_code[-4:]}`", "inline": True},
                        {"name": "Reason", "value": error_code or "Unknown error", "inline": True},
                    ]
                }
            
            data = {"embeds": [embed]}
            url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
            
            requests.post(url, json=data, headers=headers, timeout=5)
        except:
            pass  # Silently fail Discord notifications
    
    # Send in background thread
    thread = threading.Thread(target=send, daemon=True)
    thread.start()

@app.route('/validate', methods=['POST'])
def validate():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'valid': False, 'code': 'NO_DATA', 'message': 'No data provided'}), 400
        
        key_code = data.get('key', '').strip()
        discord_id = data.get('discord_id')
        hwid = data.get('hwid', '').strip()
        
        print(f"🔍 Validating: {key_code[:8]}... | User: {discord_id}")
        
        if not key_code:
            return jsonify({'valid': False, 'code': 'MISSING_KEY', 'message': 'Key is required'}), 400
        
        # Validate synchronously (FAST)
        result = validate_key_sync(key_code, discord_id, hwid)
        
        print(f"✅ Result: {result['code']}")
        
        # Send Discord notification in background (non-blocking)
        if result.get('valid'):
            send_discord_notification_async(key_code, True, discord_id)
        else:
            send_discord_notification_async(key_code, False, discord_id, result.get('code'))
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'valid': False, 'code': 'ERROR', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Terra Hub Key Validator'})

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting Terra Hub Key Validation Server")
    print("=" * 60)
    print(f"🌐 Server: http://0.0.0.0:5000")
    print(f"📢 Discord Channel: {DISCORD_CHANNEL_ID}")
    print(f"✅ Ready to validate keys!\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
