import telebot
import sqlite3
from datetime import datetime, date
import os

# TOKEN مخفي - يجي من Railway Variables
TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
DB = "profit_bot.db"
MINI_APP_URL = "https://earn-mini-appuprailwayapp-production.up.railway.app/"
ADMIN_ID = 1103784347

def init_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, spins INTEGER DEFAULT 0, daily_checkin_date TEXT, invites INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, wallet_type TEXT, wallet_number TEXT, status TEXT DEFAULT 'قيد الانتظار')")
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT points,spins,daily_checkin_date,invites FROM users WHERE user_id=?",(user_id,))
    result = c.fetchone()
    if not result:
        c.execute("INSERT INTO users(user_id) VALUES (?)",(user_id,))
        conn.commit()
        result = (0,0,None,0)
    conn.close()
    return result

def update_points(user_id,amount):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET points = points + ? WHERE user_id = ?",(amount,user_id))
    conn.commit()
    conn.close()

def update_spins(user_id,amount):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET spins = spins + ? WHERE user_id = ?",(amount,user_id))
    conn.commit()
    conn.close()

def set_daily_checkin(user_id):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET daily_checkin_date = ? WHERE user_id = ?",(today,user_id))
    conn.commit()
    conn.close()

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    points,spins,daily_date,invites = get_user_stats(user_id)
    
    markup = telebot.types.InlineKeyboardMarkup()
    btn1 = telebot.types.InlineKeyboardButton("🚀 التطبيق",web_app=telebot.types.WebAppInfo(url=MINI_APP_URL))
    btn2 = telebot.types.InlineKeyboardButton("💰 الحساب",callback_data='stats')
    markup.add(btn1)
    markup.row(btn2)
    
    today_str = date.today().isoformat()
    daily_status = "✅ اليوم" if daily_date == today_str else "❌ متاح"
    
    bot.send_message(message.chat.id,f"""🎉 Earn Pro

💎 نقاطك: {points}
🎰 لفاتك: {spins}
📅 يومي: {daily_status}
👥 دعوات: {invites}

🚀 ابدأ الكسب!""",reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == 'stats':
        user_id = call.from_user.id
        points,spins,daily_date,invites = get_user_stats(user_id)
        today_str = date.today().isoformat()
        daily_status = "✅ اليوم" if daily_date == today_str else "❌ متاح"
        
        bot.edit_message_text(f"""📊 حسابك:

💎 النقاط: {points}
🎰 اللفات: {spins}
📅 اليومي: {daily_status}
👥 الدعوات: {invites}
💳 السحب: قيد الانتظار""",call.message.chat.id,call.message.message_id)

@bot.message_handler(func=lambda m: True)
def webapp_data(message):
    user_id = message.from_user.id
    data = message.text
    
    if data == 'watch_ad':
        update_points(user_id,5)
        update_spins(user_id,2)
        bot.reply_to(message,"✅ إعلان تم!
💎 +5 نقطة
🎰 +2 لفة مجانية")
    
    elif data.startswith('wheel_'):
        try:
            reward = int(data.split('_')[1])
            update_points(user_id,reward)
            bot.reply_to(message,f"🎉 فزت بـ {reward} نقطة! 🎰")
        except:
            pass
    
    elif data == 'daily_checkin':
        points,spins,daily_date,invites = get_user_stats(user_id)
        today_str = date.today().isoformat()
        if daily_date != today_str:
            set_daily_checkin(user_id)
            update_points(user_id,10)
            bot.reply_to(message,"✅ تسجيل يومي!
💎 +10 نقطة يومياً")
        else:
            bot.reply_to(message,"❌ سبق تسجيلك اليوم!")
    
    elif data == 'invite':
        update_points(user_id,15)
        bot.reply_to(message,"👥 دعوة مسجلة!
💎 +15 نقطة فوراً")
    
    elif data.startswith('withdraw_'):
        parts = data.split('_')
        if len(parts) >= 4:
            wallet_type = parts[1]
            wallet_num = parts[2]
            amount = int(parts[3])
            
            conn = sqlite3.connect(DB, check_same_thread=False)
            c = conn.cursor()
            c.execute("INSERT INTO withdrawals(user_id,amount,wallet_type,wallet_number) VALUES(?,?,?,?)",(user_id,amount,wallet_type,wallet_num))
            c.execute("UPDATE users SET points = points - ? WHERE user_id = ?",(amount,user_id))
            conn.commit()
            conn.close()
            
            bot.reply_to(message,f"""💳 طلب سحب جديد ✅

💰 المبلغ: {amount} نقطة
💳 الطريقة: {wallet_type}
📱 الحساب: {wallet_num}
⏳ الحالة: قيد الانتظار""")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT SUM(points) FROM users")
    total_points = c.fetchone()[0] or 0
    c.execute("SELECT * FROM withdrawals WHERE status='قيد الانتظار' ORDER BY id DESC LIMIT 5")
    pending = c.fetchall()
    conn.close()
    
    text = f"""👨‍💼 لوحة التحكم

👥 المستخدمين: {total_users}
💎 النقاط الكلية: {total_points}

📋 طلبات السحب المعلقة:
"""
    for w in pending:
        text += f"• {w[2]} نقطة - {w[3]}
"
    
    bot.reply_to(message,text)

if __name__ == '__main__':
    init_db()
    print("🚀 Earn Bot شغال!")
    bot.infinity_polling()
