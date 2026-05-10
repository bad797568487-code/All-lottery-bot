Import os
import logging
import hashlib
import time
import json
import requests
import random
import sqlite3
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext, CallbackQueryHandler

# Bot configuration
BOT_TOKEN = "8794113449:AAHFoq024SBcp6qlFTClRHkrETDEUScO4KY"


# Channel configuration
CHANNEL_USERNAME = "Trx  Tree"
CHANNEL_LINK = "https://t.me/trxsignalbyminaohay"

# Multiple API endpoints
API_ENDPOINTS = {
    "ck": "https://ckygjf6r.com/api/webapi/",
    "777": "https://api.bigwinqaz.com/api/webapi/",
    "6": "https://6lotteryapi.com/api/webapi/"
}

# Colour Bet Types
COLOUR_BET_TYPES = {
    "RED": 10,      # selectType: 10
    "GREEN": 11,    # selectType: 11  
    "VIOLET": 12    # selectType: 12
}

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(name)

# Database setup
DB_NAME = "auto_bot.db"

def migrate_database():
    """Migrate database to add missing columns"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # First, make sure user_settings table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                bet_amount INTEGER DEFAULT 100,
                auto_login BOOLEAN DEFAULT 1,
                bet_sequence TEXT DEFAULT '100,300,700,1600,3200,7600,16000,32000',
                current_bet_index INTEGER DEFAULT 0,
                platform TEXT DEFAULT 'ck',
                auto_betting BOOLEAN DEFAULT 0,
                random_betting TEXT DEFAULT 'bot',
                profit_target INTEGER DEFAULT 0,
                loss_target INTEGER DEFAULT 0,
                language TEXT DEFAULT 'english',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check and add language column if missing
        cursor.execute("PRAGMA table_info(user_settings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'language' not in columns:
            print("🔧 Migrating database: Adding language column...")
            cursor.execute('ALTER TABLE user_settings ADD COLUMN language TEXT DEFAULT "english"')
            conn.commit()
            print("✅ Database migration completed: language column added")
        
        conn.close()
    except Exception as e:
        print(f"❌ Database migration error: {e}")

def init_database():
    """Initialize SQLite database with auto-update capability"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone TEXT,
                password TEXT,
                platform TEXT DEFAULT 'ck',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create user_settings table - language column added
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                bet_amount INTEGER DEFAULT 100,
                auto_login BOOLEAN DEFAULT 1,
                bet_sequence TEXT DEFAULT '100,300,700,1600,3200,7600,16000,32000',
                current_bet_index INTEGER DEFAULT 0,
                platform TEXT DEFAULT 'ck',
                auto_betting BOOLEAN DEFAULT 0,
                random_betting TEXT DEFAULT 'bot',
                profit_target INTEGER DEFAULT 0,
                loss_target INTEGER DEFAULT 0,

language TEXT DEFAULT 'english',  -- NEW: Language setting
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if language column exists, if not add it
        try:
            cursor.execute("SELECT language FROM user_settings LIMIT 1")
        except sqlite3.OperationalError:
            print("🔧 Adding language column to user_settings table...")
            cursor.execute('ALTER TABLE user_settings ADD COLUMN language TEXT DEFAULT "english"')
        
        # Create bet_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bet_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                platform TEXT,
                issue TEXT,
                bet_type TEXT,
                amount INTEGER,
                result TEXT,
                profit_loss INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create pending_bets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                platform TEXT,
                issue TEXT,
                bet_type TEXT,
                amount INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create bot_sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_sessions (
                user_id INTEGER PRIMARY KEY,
                is_running BOOLEAN DEFAULT 0,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_bets INTEGER DEFAULT 0,
                total_profit INTEGER DEFAULT 0,
                session_profit INTEGER DEFAULT 0,
                session_loss INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create bs_patterns table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bs_patterns (
                user_id INTEGER PRIMARY KEY,
                pattern TEXT DEFAULT '',
                current_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create channel_verification table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_verification (
                user_id INTEGER PRIMARY KEY,
                has_joined BOOLEAN DEFAULT 0,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create sl_patterns table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sl_patterns (
                user_id INTEGER PRIMARY KEY,
                pattern TEXT DEFAULT '1,2,3,4,5',
                current_sl INTEGER DEFAULT 1,
                current_index INTEGER DEFAULT 0,
                wait_loss_count INTEGER DEFAULT 0,
                bet_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create sl_bet_sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sl_bet_sessions (
                user_id INTEGER PRIMARY KEY,
                is_wait_mode BOOLEAN DEFAULT 0,
                wait_bet_type TEXT DEFAULT '',
                wait_issue TEXT DEFAULT '',
                wait_amount INTEGER DEFAULT 0,
                wait_total_profit INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )

''')
        
        # Create formula_patterns table for separate BS and Colour patterns
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS formula_patterns (
                user_id INTEGER PRIMARY KEY,
                bs_pattern TEXT DEFAULT '',
                colour_pattern TEXT DEFAULT '',
                bs_current_index INTEGER DEFAULT 0,
                colour_current_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

def save_channel_status(user_id, has_joined):
    """Save channel join status"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO channel_verification (user_id, has_joined, verified_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, has_joined))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving channel status: {e}")
        return False

def get_channel_status(user_id):
    """Get channel join status"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT has_joined FROM channel_verification WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return bool(result[0])
        return False
    except Exception as e:
        logger.error(f"Error getting channel status: {e}")
        return False

def save_user_credentials(user_id, phone, password, platform='ck'):
    """Save user credentials to database"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, phone, password, platform)
            VALUES (?, ?, ?, ?)
        ''', (user_id, phone, password, platform))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving user credentials: {e}")
        return False

def get_user_credentials(user_id):
    """Get user credentials from database"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT phone, password, platform FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {'phone': result[0], 'password': result[1], 'platform': result[2]}
        return None
    except Exception as e:
        logger.error(f"Error getting user credentials: {e}")
        return None

def save_user_setting(user_id, setting_key, setting_value):
    """Save user setting with error handling for missing columns"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Check if user exists in settings
        cursor.execute('SELECT user_id FROM user_settings WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO user_settings (user_id) VALUES (?)', (user_id,))
        
        # Update the setting with error handling
        try:
            cursor.execute(f'UPDATE user_settings SET {setting_key} = ? WHERE user_id = ?', 
                           (setting_value, user_id))
        except sqlite3.OperationalError as e:
            if "no such column" in str(e):
                print(f"🔧 Column {setting_key} not found, adding it...")

# Add missing column
                cursor.execute(f'ALTER TABLE user_settings ADD COLUMN {setting_key} TEXT')
                cursor.execute(f'UPDATE user_settings SET {setting_key} = ? WHERE user_id = ?', 
                               (setting_value, user_id))
            else:
                raise e
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving user setting {setting_key}: {e}")
        return False

def get_user_setting(user_id, setting_key, default=None):
    """Get user setting with error handling for missing columns"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute(f'SELECT {setting_key} FROM user_settings WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
        except sqlite3.OperationalError as e:
            if "no such column" in str(e):
                print(f"🔧 Column {setting_key} not found, returning default...")
                return default
            else:
                raise e
        
        conn.close()
        
        if result and result[0] is not None:
            return result[0]
        return default
    except Exception as e:
        logger.error(f"Error getting user setting {setting_key}: {e}")
        return default

def save_bot_session(user_id, is_running=False, total_bets=0, total_profit=0, session_profit=0, session_loss=0):
    """Save bot session data"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO bot_sessions 
            (user_id, is_running, total_bets, total_profit, session_profit, session_loss, last_activity)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, is_running, total_bets, total_profit, session_profit, session_loss))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving bot session: {e}")
        return False

def get_bot_session(user_id):
    """Get bot session data"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('SELECT is_running, total_bets, total_profit, session_profit, session_loss FROM bot_sessions WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'is_running': bool(result[0]),
                'total_bets': result[1] or 0,
                'total_profit': result[2] or 0,
                'session_profit': result[3] or 0,
                'session_loss': result[4] or 0
            }
        return {'is_running': False, 'total_bets': 0, 'total_profit': 0, 'session_profit': 0, 'session_loss': 0}
    except Exception as e:
        logger.error(f"Error getting bot session: {e}")
        return {'is_running': False, 'total_bets': 0, 'total_profit': 0, 'session_profit': 0, 'session_loss': 0}

def update_bot_stats(user_id, profit=0):
    """Update bot statistics"""
    try:
        session = get_bot_session(user_id)
        new_total_bets = session['total_bets'] + 1
        new_total_profit = session['total_profit'] + profit
        
        # Update session profit/loss
        new_session_profit = session['session_profit']
        new_session_loss = session['session_loss']
        
        if profit > 0:
            new_session_profit += profit
        else:
            new_session_loss += abs(profit)
        
        save_bot_session(user_id, True, new_total_bets, new_total_profit, new_session_profit, new_session_loss)
        return True
    except Exception as e:
        logger.error(f"Error updating bot stats: {e}")
        return False

def reset_session_stats(user_id):
    """Reset session statistics"""
    try:
        save_bot_session(user_id, True, 0, 0, 0, 0)
        return True
    except Exception as e:
        logger.error(f"Error resetting session stats: {e}")
        return False

def save_bet_history(user_id, platform, issue, bet_type, amount, result, profit_loss):
    """Save bet history"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO bet_history (user_id, platform, issue, bet_type, amount, result, profit_loss)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, platform, issue, bet_type, amount, result, profit_loss))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving bet history: {e}")
        return False

def get_bet_history(user_id, platform=None, limit=10):
    """Get user bet history"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        if platform:
            cursor.execute('''
                SELECT platform, issue, bet_type, amount, result, profit_loss, created_at 
                FROM bet_history 
                WHERE user_id = ? AND platform = ?
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, platform, limit))
        else:
            cursor.execute('''
                SELECT platform, issue, bet_type, amount, result, profit_loss, created_at 
                FROM bet_history 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Error getting bet history: {e}")
        return []

def get_current_bet_amount(user_id):
    """Get current bet amount based on sequence - FINAL FIXED"""
    try:
        bet_sequence = get_user_setting(user_id, 'bet_sequence', '100,300,700,1600,3200,7600,16000,32000')
        current_index = get_user_setting(user_id, 'current_bet_index', 0)
        
        amounts = [int(x.strip()) for x in bet_sequence.split(',')]
        
        print(f"🔧 DEBUG: get_current_bet_amount")
        print(f"🔧 DEBUG: Current Index: {current_index}")
        print(f"🔧 DEBUG: Sequence: {bet_sequence}")
        print(f"🔧 DEBUG: Amounts: {amounts}")
        
        # ✅ FIXED: Always check bounds
        if current_index < len(amounts):
            amount = amounts[current_index]
            current_step = current_index + 1
            print(f"🔧 DEBUG: Returning: {amount}K at index {current_index} (Step {current_step})")
            return amount
        else:
            # If index is out of bounds, reset to first amount
            amount = amounts[0] if amounts else 100
            save_user_setting(user_id, 'current_bet_index', 0)
            print(f"🔧 DEBUG: Index out of bounds, resetting to: {amount}K at index 0")
            return amount
    except Exception as e:
        logger.error(f"Error in get_current_bet_amount: {e}")
        return 100

def update_bet_sequence(user_id, result):
    """Update bet sequence based on result (WIN/LOSE) - FIXED VERSION"""
    try:
        current_index = get_user_setting(user_id, 'current_bet_index', 0)
        bet_sequence = get_user_setting(user_id, 'bet_sequence', '100,300,700,1600,3200,7600,16000,32000')
        amounts = [int(x.strip()) for x in bet_sequence.split(',')]
        
        print(f"🔧 DEBUG: update_bet_sequence START")
        print(f"🔧 DEBUG: Current Index: {current_index}, Result: {result}")
        print(f"🔧 DEBUG: Sequence: {bet_sequence}")
        print(f"🔧 DEBUG: Amounts: {amounts}")

if result == "WIN":
            new_index = 0  # Win ရင် အစပြန်စ
            print(f"🔧 DEBUG: WIN - Reset index to 0")
        else:
            # Loss ရင် နောက်တစ်ဆင့်သို့
            new_index = current_index + 1
            print(f"🔧 DEBUG: LOSE - Current index: {current_index} -> New index: {new_index}")
            
            # Sequence ဆုံးရင် အစပြန်စ
            if new_index >= len(amounts):
                new_index = 0
                print(f"🔧 DEBUG: LOSE - Sequence ended, reset to 0")
        
        # ✅ FIXED: Save the new index
        save_user_setting(user_id, 'current_bet_index', new_index)
        
        print(f"🔧 DEBUG: update_bet_sequence END")
        print(f"🔧 DEBUG: Index updated: {current_index} -> {new_index}")
        
        return new_index
        
    except Exception as e:
        logger.er
ဒိ code 
