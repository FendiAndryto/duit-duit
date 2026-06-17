import sqlite3
import os
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'slayer.db')

def get_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema and performs daily reset if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            quota INTEGER,
            expired_date TEXT
        )
    ''')
    
    # Create api_keys table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_string TEXT UNIQUE,
            usage_today INTEGER DEFAULT 0,
            last_used TEXT,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Create metadata table to track daily resets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Check for daily reset
    today_str = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT value FROM system_meta WHERE key = "last_reset_date"')
    row = cursor.fetchone()
    
    if not row or row['value'] != today_str:
        # Reset usage_today
        cursor.execute('UPDATE api_keys SET usage_today = 0')
        # Update last_reset_date
        cursor.execute('''
            INSERT INTO system_meta (key, value) 
            VALUES ("last_reset_date", ?)
            ON CONFLICT(key) DO UPDATE SET value = ?
        ''', (today_str, today_str))
        
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    """Hashes a password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# --- User Management ---

def verify_user(username: str, password: str) -> dict:
    """Verifies user credentials and returns user data if valid, else None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    
    if user and user['password_hash'] == hash_password(password):
        return dict(user)
    return None

def create_user(username: str, password: str, quota: int, expired_date: str = None) -> bool:
    """Creates a new user. Returns True if successful, False if username exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, quota, expired_date)
            VALUES (?, ?, ?, ?)
        ''', (username, hash_password(password), quota, expired_date))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def deduct_quota(user_id: int) -> bool:
    """Deducts 1 from the user's quota. Returns True if successful."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET quota = quota - 1 WHERE id = ? AND quota > 0', (user_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

# --- API Key Management (Smart Rotator) ---

def get_available_key() -> dict:
    """Gets an available API key that hasn't exceeded the daily limit (20)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Find active key with usage < 20, ordered by oldest last_used (or nulls first)
    cursor.execute('''
        SELECT id, key_string, usage_today, last_used 
        FROM api_keys 
        WHERE is_active = 1 AND usage_today < 20
        ORDER BY last_used ASC NULLS FIRST
        LIMIT 1
    ''')
    key = cursor.fetchone()
    conn.close()
    
    return dict(key) if key else None

def add_api_key(key_string: str) -> bool:
    """Adds a new API key. Returns True if successful, False if exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO api_keys (key_string) VALUES (?)', (key_string,))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def update_key_success(key_id: int):
    """Increments usage and updates last_used on successful API call."""
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    cursor.execute('''
        UPDATE api_keys 
        SET usage_today = usage_today + 1, last_used = ?
        WHERE id = ?
    ''', (now_str, key_id))
    conn.commit()
    conn.close()

def update_key_exhausted(key_id: int):
    """Marks key as exhausted for the day (e.g., sets usage to 20 temporarily)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE api_keys SET usage_today = 20 WHERE id = ?', (key_id,))
    conn.commit()
    conn.close()

def get_all_keys() -> list:
    """Returns all api keys for admin dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM api_keys')
    keys = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return keys

# Initialize the DB whenever this module is loaded
init_db()
