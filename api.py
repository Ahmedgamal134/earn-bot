from flask import Flask, jsonify, request
import sqlite3
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # عشان يسمح للميني آب يتصل بالـ API

DB_PATH = 'profit_bot.db'

@app.route('/api/user/<int:user_id>', methods=['GET'])
def get_user_data(user_id):
    """جلب بيانات المستخدم للميني آب"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # جلب بيانات المستخدم
        c.execute("SELECT points, total_earned FROM users WHERE user_id=?", (user_id,))
        user = c.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # جلب إعلانات اليوم
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
        ads = c.fetchone()
        
        # جلب سلسلة التسجيل
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
    """تسجيل مشاهدة إعلان من الميني آب"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # التحقق من حد الإعلانات
        c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
        result = c.fetchone()
        
        if result and result[0] >= 400:
            conn.close()
            return jsonify({'success': False, 'error': 'Daily limit reached'}), 400
        
        # تسجيل المشاهدة
        if not result:
            c.execute("INSERT INTO ads (user_id, ad_date, ad_count) VALUES (?, ?, ?)", (user_id, today, 1))
        else:
            c.execute("UPDATE ads SET ad_count = ad_count + 1 WHERE user_id=? AND ad_date=?", (user_id, today))
        
        # إضافة نقطة
        c.execute("UPDATE users SET points = points + 1, total_earned = total_earned + 1 WHERE user_id=?", (user_id,))
        
        # جلب البيانات الجديدة
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        new_points = c.fetchone()[0]
        
        c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
        new_ads = c.fetchone()[0]
        
        conn.commit()
        conn.close()
        
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
    """تسجيل دخول يومي من الميني آب"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # التحقق من التسجيل اليوم
        c.execute("SELECT * FROM daily_checkin WHERE user_id=? AND check_date=?", (user_id, today))
        if c.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Already checked in today'}), 400
        
        # جلب آخر تسجيل
        c.execute("SELECT streak FROM daily_checkin WHERE user_id=? ORDER BY check_date DESC LIMIT 1", (user_id,))
        last = c.fetchone()
        
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        if last:
            streak = last[0] + 1
        else:
            streak = 1
        
        # تسجيل الدخول
        c.execute("INSERT INTO daily_checkin (user_id, check_date, streak) VALUES (?, ?, ?)", (user_id, today, streak))
        
        # إضافة 5 نقاط
        c.execute("UPDATE users SET points = points + 5, total_earned = total_earned + 5 WHERE user_id=?", (user_id,))
        
        # مكافآت السلسلة
        bonus = 0
        if streak == 7:
            bonus = 20
            c.execute("UPDATE users SET points = points + ?, total_earned = total_earned + ? WHERE user_id=?", (bonus, bonus, user_id))
        elif streak == 30:
            bonus = 100
            c.execute("UPDATE users SET points = points + ?, total_earned = total_earned + ? WHERE user_id=?", (bonus, bonus, user_id))
        
        # جلب النقاط الجديدة
        c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        new_points = c.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'new_points': new_points,
            'streak': streak,
            'bonus': bonus
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
