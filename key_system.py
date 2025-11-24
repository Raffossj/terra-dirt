import os
import asyncpg
from datetime import datetime, timedelta
import secrets
import hashlib

class KeySystem:
    def __init__(self):
        self.db_url = os.environ.get('DATABASE_URL')
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable not set")
        self.pool = None
    
    async def init(self):
        if not self.db_url:
            raise ValueError("DATABASE_URL is not configured")
        self.pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=10)
        if self.pool is None:
            raise RuntimeError("Failed to create database pool")
        await self.init_database()
    
    async def close(self):
        if self.pool:
            await self.pool.close()
    
    async def init_database(self):
        async with self.pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS scripts (
                    id SERIAL PRIMARY KEY,
                    script_name VARCHAR(255) UNIQUE NOT NULL,
                    script_id VARCHAR(32) UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS keys (
                    id SERIAL PRIMARY KEY,
                    key_code VARCHAR(64) UNIQUE NOT NULL,
                    script_id VARCHAR(32) NOT NULL,
                    discord_id BIGINT,
                    hwid_hash VARCHAR(64),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    redeemed_at TIMESTAMP,
                    max_uses INTEGER DEFAULT -1,
                    current_uses INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    note TEXT,
                    CONSTRAINT fk_script FOREIGN KEY (script_id) REFERENCES scripts(script_id) ON DELETE CASCADE
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS key_validations (
                    id SERIAL PRIMARY KEY,
                    key_code VARCHAR(64) NOT NULL,
                    discord_id BIGINT,
                    hwid_hash VARCHAR(64),
                    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN NOT NULL,
                    error_code VARCHAR(50)
                )
            ''')
    
    def generate_key(self, length=32):
        return secrets.token_hex(length // 2).upper()
    
    def hash_hwid(self, hwid):
        if hwid:
            return hashlib.sha256(hwid.encode()).hexdigest()
        return None
    
    async def create_script(self, script_name, description=''):
        script_id = secrets.token_hex(16).upper()
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO scripts (script_name, script_id, description)
                    VALUES ($1, $2, $3)
                ''', script_name, script_id, description)
                
                return {'success': True, 'script_id': script_id, 'script_name': script_name}
        except asyncpg.UniqueViolationError:
            return {'success': False, 'error': 'Script name already exists'}
    
    async def create_key(self, script_id, discord_id=None, days=None, max_uses=-1, note=''):
        async with self.pool.acquire() as conn:
            script = await conn.fetchrow('SELECT id FROM scripts WHERE script_id = $1', script_id)
            if not script:
                return {'success': False, 'error': 'Script not found'}
            
            key_code = self.generate_key()
            expires_at = None
            if days and days > 0:
                expires_at = datetime.now() + timedelta(days=days)
            
            try:
                await conn.execute('''
                    INSERT INTO keys (key_code, script_id, discord_id, expires_at, max_uses, note)
                    VALUES ($1, $2, $3, $4, $5, $6)
                ''', key_code, script_id, discord_id, expires_at, max_uses, note)
                
                return {
                    'success': True,
                    'key': key_code,
                    'script_id': script_id,
                    'expires_at': expires_at,
                    'max_uses': max_uses
                }
            except Exception as e:
                return {'success': False, 'error': str(e)}
    
    async def redeem_key(self, key_code, discord_id):
        async with self.pool.acquire() as conn:
            key_data = await conn.fetchrow('SELECT * FROM keys WHERE key_code = $1', key_code)
            
            if not key_data:
                return {'success': False, 'error': 'Invalid key'}
            
            if not key_data['is_active']:
                return {'success': False, 'error': 'Key is inactive'}
            
            if key_data['discord_id'] and key_data['discord_id'] != discord_id:
                return {'success': False, 'error': 'Key is bound to another Discord account'}
            
            if key_data['expires_at'] and datetime.now() > key_data['expires_at']:
                return {'success': False, 'error': 'Key has expired'}
            
            if not key_data['discord_id']:
                await conn.execute('''
                    UPDATE keys
                    SET discord_id = $1, redeemed_at = CURRENT_TIMESTAMP
                    WHERE key_code = $2
                ''', discord_id, key_code)
            
            return {'success': True, 'message': 'Key redeemed successfully'}
    
    async def validate_key(self, key_code, discord_id=None, hwid=None):
        async with self.pool.acquire() as conn:
            key_data = await conn.fetchrow('''
                SELECT k.*, s.script_name
                FROM keys k
                JOIN scripts s ON k.script_id = s.script_id
                WHERE k.key_code = $1
            ''', key_code)
            
            if not key_data:
                await self._log_validation(conn, key_code, discord_id, hwid, False, 'KEY_NOT_FOUND')
                return {'valid': False, 'code': 'KEY_NOT_FOUND', 'message': 'Invalid key'}
            
            if not key_data['is_active']:
                await self._log_validation(conn, key_code, discord_id, hwid, False, 'KEY_INACTIVE')
                return {'valid': False, 'code': 'KEY_INACTIVE', 'message': 'Key is inactive'}
            
            if key_data['expires_at'] and datetime.now() > key_data['expires_at']:
                await self._log_validation(conn, key_code, discord_id, hwid, False, 'KEY_EXPIRED')
                return {'valid': False, 'code': 'KEY_EXPIRED', 'message': 'Key has expired'}
            
            if discord_id and key_data['discord_id'] and key_data['discord_id'] != discord_id:
                await self._log_validation(conn, key_code, discord_id, hwid, False, 'DISCORD_ID_MISMATCH')
                return {'valid': False, 'code': 'DISCORD_ID_MISMATCH', 'message': 'Key bound to different Discord user'}
            
            if hwid:
                hwid_hash = self.hash_hwid(hwid)
                if key_data['hwid_hash'] is None:
                    await conn.execute('UPDATE keys SET hwid_hash = $1 WHERE key_code = $2', hwid_hash, key_code)
                elif key_data['hwid_hash'] != hwid_hash:
                    await self._log_validation(conn, key_code, discord_id, hwid, False, 'HWID_MISMATCH')
                    return {'valid': False, 'code': 'HWID_MISMATCH', 'message': 'Key bound to different HWID'}
            
            if key_data['max_uses'] > 0 and key_data['current_uses'] >= key_data['max_uses']:
                await self._log_validation(conn, key_code, discord_id, hwid, False, 'MAX_USES_EXCEEDED')
                return {'valid': False, 'code': 'MAX_USES_EXCEEDED', 'message': 'Key usage limit exceeded'}
            
            await conn.execute('UPDATE keys SET current_uses = current_uses + 1 WHERE key_code = $1', key_code)
            await self._log_validation(conn, key_code, discord_id, hwid, True, 'KEY_VALID')
            
            response = {
                'valid': True,
                'code': 'KEY_VALID',
                'message': 'Key is valid',
                'data': {
                    'script_name': key_data['script_name'],
                    'discord_id': key_data['discord_id'],
                    'expires_at': key_data['expires_at'].isoformat() if key_data['expires_at'] else None,
                    'current_uses': key_data['current_uses'] + 1,
                    'max_uses': key_data['max_uses']
                }
            }
            
            return response
    
    async def _log_validation(self, conn, key_code, discord_id, hwid, success, error_code):
        hwid_hash = self.hash_hwid(hwid) if hwid else None
        await conn.execute('''
            INSERT INTO key_validations (key_code, discord_id, hwid_hash, success, error_code)
            VALUES ($1, $2, $3, $4, $5)
        ''', key_code, discord_id, hwid_hash, success, error_code)
    
    async def get_user_keys(self, discord_id):
        async with self.pool.acquire() as conn:
            keys = await conn.fetch('''
                SELECT k.*, s.script_name
                FROM keys k
                JOIN scripts s ON k.script_id = s.script_id
                WHERE k.discord_id = $1
                ORDER BY k.created_at DESC
            ''', discord_id)
            
            return [dict(key) for key in keys]
    
    async def get_all_keys(self):
        async with self.pool.acquire() as conn:
            keys = await conn.fetch('''
                SELECT k.*, s.script_name
                FROM keys k
                JOIN scripts s ON k.script_id = s.script_id
                ORDER BY k.created_at DESC
            ''')
            
            return [dict(key) for key in keys]
    
    async def delete_key(self, key_code):
        async with self.pool.acquire() as conn:
            result = await conn.execute('DELETE FROM keys WHERE key_code = $1', key_code)
            return {'success': result == 'DELETE 1'}
    
    async def reset_hwid(self, key_code):
        async with self.pool.acquire() as conn:
            result = await conn.execute('UPDATE keys SET hwid_hash = NULL WHERE key_code = $1', key_code)
            return {'success': result == 'UPDATE 1'}
    
    async def get_all_scripts(self):
        async with self.pool.acquire() as conn:
            scripts = await conn.fetch('SELECT * FROM scripts ORDER BY created_at DESC')
            return [dict(script) for script in scripts]
    
    async def get_script_by_id(self, script_id):
        async with self.pool.acquire() as conn:
            script = await conn.fetchrow('SELECT * FROM scripts WHERE script_id = $1', script_id)
            return dict(script) if script else None
    
    async def get_key_info(self, key_code):
        async with self.pool.acquire() as conn:
            key_data = await conn.fetchrow('''
                SELECT k.*, s.script_name
                FROM keys k
                JOIN scripts s ON k.script_id = s.script_id
                WHERE k.key_code = $1
            ''', key_code)
            
            return dict(key_data) if key_data else None
