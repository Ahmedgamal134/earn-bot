from flask import Flask, jsonify, request, send_from_directory
import sqlite3
from datetime import datetime
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

DB_PATH = 'profit_bot.db'
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [1103784347]  # حط معرفك هنا

# =========== دوال الإشعارات ===========
def send_telegram_notification(user_id, action, details):
    """إرسال إشعار للمشرفين عن نشاط المستخدم"""
    
    # جلب معلومات المستخدم
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT first_name, points FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if not user:
        return
    
    name, points = user
    
    # أيقونة النشاط
    icons = {
        'watch_ad': '📺',
        'daily_checkin': '✅',
        'wheel_spin': '🎡',
        'withdraw_request': '💳'
    }
    icon = icons.get(action, '🔔')
    
    # تجهيز الرسالة
    message = f"{icon} **نشاط جديد في الموقع**\n\n"
    message += f"👤 **المستخدم:** {name}\n"
    message += f"🆔 **المعرف:** `{user_id}`\n"
    message += f"⚡ **الإجراء:** {action}\n"
    message += f"📝 **التفاصيل:** {details}\n"
    message += f"💰 **الرصيد:** {points}\n"
    message += f"🕐 **الوقت:** {datetime.now().strftime('%H:%M:%S')}"
    
    # إرسال لكل مشرف
    for admin in ADMIN_IDS:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': admin,
                'text': message,
                'parse_mode': 'Markdown'
            }
            requests.post(url, json=data)
        except:
            pass

# =========== API Endpoints ===========
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/admin.html')
def serve_admin():
    return send_from_directory('.', 'admin.html')

@app.route('/api/user/<int:user_id>', methods=['GET'])
def get_user_data(user_id):
    """جلب بيانات المستخدم"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("SELECT points, total_earned FROM users WHERE user_id=?", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
        ads = c.fetchone()
        
        c.execute("SELECT streak FROM daily_checkin WHERE user_id=? ORDER BY check_date DESC LIMIT 1", (user_id,))
        streak = c.fetchone()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'points': user[0],
            'total_earned': user[1],
            'ads_today': ads[0] if ads else 0,
            'max_ads': 400,
            'streak': streak[0] if streak else 0
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/watch_ad/<int:user_id>', methods=['POST'])
def watch_ad(user_id):
    """تسجيل مشاهدة إعلان"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
        result = c.fetchone()
        
        if result and result[0] >= 400:
            conn.close()
            return jsonify({'success': False, 'error': 'Daily limit reached'}), 400
        
        if not result:
            c.execute("INSERT INTO ads (user_id, ad_date, ad_count) VALUES (?, ?, ?)", (user_id, today, 1))
        else:
            c.execute("UPDATE ads SET ad_count = ad_count + 1 WHERE user_id=? AND ad_date=?", (user_id, today))
        
        c.execute("UPDATE users SET points = points + 1, total_earned = total_earned + 1 WHERE user_id=?", (user_id,))
        
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        new_points = c.fetchone()[0]
        
        c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
        new_ads = c.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        # إرسال إشعار للمشرف
        send_telegram_notification(user_id, 'watch_ad', f'شاهد إعلان - إجمالي اليوم: {new_ads}')
        
        return jsonify({
            'success': True,
            'new_points': new_points,
            'new_ads_today': new_ads,
            'max_ads': 400
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/daily_checkin/<int:user_id>', methods=['POST'])
def daily_checkin(user_id):
    """تسجيل دخول يومي"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        c.execute("SELECT * FROM daily_checkin WHERE user_id=? AND check_date=?", (user_id, today))
        if c.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Already checked in'}), 400
        
        c.execute("SELECT streak FROM daily_checkin WHERE user_id=? ORDER BY check_date DESC LIMIT 1", (user_id,))
        last = c.fetchone()
        
        streak = (last[0] + 1) if last else 1
        
        c.execute("INSERT INTO daily_checkin (user_id, check_date, streak) VALUES (?, ?, ?)", (user_id, today, streak))
        c.execute("UPDATE users SET points = points + 5, total_earned = total_earned + 5 WHERE user_id=?", (user_id,))
        
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        new_points = c.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        # إرسال إشعار للمشرف
        send_telegram_notification(user_id, 'daily_checkin', f'سلسلة: {streak} أيام')
        
        return jsonify({
            'success': True,
            'new_points': new_points,
            'streak': streak
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wheel_spin/<int:user_id>', methods=['POST'])
def wheel_spin(user_id):
    """دوران عجلة الحظ"""
    try:
        data = request.json
        prize = data.get('prize', 0)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("UPDATE users SET points = points + ? WHERE user_id=?", (prize, user_id))
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        new_points = c.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        # إرسال إشعار للمشرف
        send_telegram_notification(user_id, 'wheel_spin', f'ربح {prize} نقطة')
        
        return jsonify({
            'success': True,
            'new_points': new_points
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/notify', methods=['POST'])
def receive_notification():
    """استقبال إشعارات من الموقع"""
    try:
        data = request.json
        action = data.get('action')
        user_id = data.get('user_id')
        details = data.get('details', '')
        
        send_telegram_notification(user_id, action, details)
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
