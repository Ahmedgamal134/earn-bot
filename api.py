from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
DB_PATH = 'profit_bot.db'

@app.route('/api/user/<int:user_id>', methods=['GET'])
def get_user_data(user_id):
    """جلب بيانات المستخدم للميني آب"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT points, total_earned FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
    ads = c.fetchone()
    
    c.execute("SELECT streak FROM daily_checkin WHERE user_id=? ORDER BY check_date DESC LIMIT 1", (user_id,))
    streak = c.fetchone()
    
    conn.close()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'user_id': user_id,
        'points': user[0],
        'total_earned': user[1],
        'ads_today': ads[0] if ads else 0,
        'max_ads': 400,
        'streak': streak[0] if streak else 0,
        'success': True
    })

@app.route('/api/watch_ad/<int:user_id>', methods=['POST'])
def watch_ad(user_id):
    """تسجيل مشاهدة إعلان من الميني آب"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    c.execute("SELECT ad_count FROM ads WHERE user_id=? AND ad_date=?", (user_id, today))
    result = c.fetchone()
    
    if result and result[0] >= 400:
        conn.close()
        return jsonify({'error': 'Daily limit reached', 'success': False}), 400
    
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
    
    return jsonify({
        'success': True,
        'new_points': new_points,
        'new_ads_today': new_ads,
        'max_ads': 400
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
