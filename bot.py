import telebot
import sqlite3
from datetime import datetime, date
import os

TOKEN = "8617943344:AAGrxfAedccd1nd1pRCpq1l5AI92psPahMA"
bot = telebot.TeleBot(TOKEN)
DB = "profit_bot.db"
MINI_APP_URL = "https://earn-mini-appuprailwayapp-production.up.railway.app/"
ADMIN_ID = 1103784347

def init_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        points INTEGER DEFAULT 0,
        spins INTEGER DEFAULT 0,
        daily_checkin_date TEXT,
        invites INTEGER DEFAULT 0,
        completed_invites INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        wallet_type TEXT,
        wallet_number TEXT,
        status TEXT DEFAULT 'قيد الانتظار',
        request_date TEXT
    )''')
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT points, spins, daily_checkin_date, invites, completed_invites FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    if not result:
        c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        result = (0, 0, None, 0, 0)
    conn.close()
    return result

def update_points(user_id, points_delta):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points_delta, user_id))
    conn.commit()
    conn.close()

def update_spins(user_id, spins_delta):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET spins = spins + ? WHERE user_id = ?", (spins_delta, user_id))
    conn.commit()
    conn.close()

def set_daily_checkin(user_id):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET daily_checkin_date = ? WHERE user_id = ?", (today, user_id))
    conn.commit()
    conn.close()

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    points, spins, daily_date, invites, completed = get_user_stats(user_id)
    
    markup = telebot.types.InlineKeyboardMarkup()
    mini_btn = telebot.types.InlineKeyboardButton("🚀 فتح التطبيق الاحترافي", web_app=telebot.types.WebAppInfo(url=MINI_APP_URL))
    balance_btn = telebot.types.InlineKeyboardButton("💰 بيانات الحساب", callback_data='stats')
    markup.add(mini_btn)
    markup.row(balance_btn)
    
    welcome_text = f"""🎉 مرحباً بك في Earn Pro!

💎 نقاطك: {points}
🎰 لفاتك: {spins}
📅 تسجيل يومي: {'✅ اليوم' if daily_date == date.today().isoformat() else '❌ متاح'}
👥 دعواتك: {invites} | مكتملة: {completed}

🚀 اضغط لفتح التطبيق واكسب الملايين! 💰"""
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    data = call.data
    user_id = call.from_user.id
    
    if data == 'stats':
        points, spins, daily_date, invites, completed = get_user_stats(user_id)
        status = "✅ اليوم" if daily_date == date.today().isoformat() else "❌ متاح الآن"
        
        stats_text = f"""📊 بيانات حسابك الكاملة:

💎 **النقاط**: {points}
🎰 **اللفات**: {spins}
📅 **تسجيل يومي**: {status}
👥 **دعوات مرسلة**: {invites}
✅ **دعوات مكتملة**: {completed}
💳 **طلبات السحب**: قيد المراجعة"""
        
        bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: True)
def webapp_data(message):
    user_id = message.from_user.id
    data = message.text
    
    if data == 'watch_ad':
        update_points(user_id, 5)
        update_spins(user_id, 2)
        bot.reply_to(message, "✅ إعلان OnClicka تم!
💎 +5 نقطة
🎰 +2 لفة مجانية!")
    
    elif data.startswith('wheel_'):
        try:
            reward = int(data.split('_')[1])
            update_points(user_id, reward)
            bot.reply_to(message, f"🎉 عجلة الحظ!
💎 فزت بـ **{reward} نقطة** ✨")
        except:
            pass
    
    elif data == 'daily_checkin':
        if get_user_stats(user_id)[2] != date.today().isoformat():
            set_daily_checkin(user_id)
            update_points(user_id, 10)
            bot.reply_to(message, "✅ تسجيل يومي ناجح!
💎 +10 نقطة يومياً!")
        else:
            bot.reply_to(message, "❌ سجلت اليوم بالفعل! ⏳ جرب غداً")
    
    elif data == 'invite':
        points, spins, daily_date, invites, completed = get_user_stats(user_id)
        update_points(user_id, 15)
        bot.reply_to(message, f"👥 دعوة جديدة!
💎 +15 نقطة (ستحصل على +15 إضافية عند إكمال المهمة)
📊 إجمالي دعواتك: {invites + 1}")
    
    elif data.startswith('withdraw_'):
        parts = data.split('_', 3)
        if len(parts) == 4:
            wallet_type, wallet_number, amount = parts[1], parts[2], int(parts[3])
            
            conn = sqlite3.connect(DB, check_same_thread=False)
            c = conn.cursor()
            c.execute("""INSERT INTO withdrawals(user_id, amount, wallet_type, wallet_number, request_date) 
                        VALUES(?,?,?,?,?)""", (user_id, amount, wallet_type, wallet_number, datetime.now().isoformat()))
            c.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (amount, user_id))
            conn.commit()
            conn.close()
            
            bot.reply_to(message, f"💳 **طلب سحب جديد**

"
                                f"💰 المبلغ: {amount} نقطة
"
                                f"💳 الطريقة: {wallet_type.replace('orange','أورانج كاش').replace('vodafone','فودافون كاش').replace('etisalat','اتصالات كاش').replace('paypal','PayPal')}
"
                                f"📱 البيانات: `{wallet_number}`
"
                                f"⏳ الحالة: **قيد الانتظار**

"
                                f"✅ سيتم الموافقة قريباً!")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ ليس لديك صلاحيات الأدمن")
        return
    
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT SUM(points) FROM users")
    total_points = c.fetchone()[0] or 0
    c.execute("SELECT * FROM withdrawals WHERE status='قيد الانتظار' ORDER BY id DESC")
    pending_withdrawals = c.fetchall()
    conn.close()
    
    admin_text = f"👨‍💼 **لوحة التحكم**

"
    admin_text += f"👥 المستخدمين: {total_users}
"
    admin_text += f"💎 النقاط الإجمالية: {total_points}

"
    admin_text += f"📋 **طلبات السحب قيد الانتظار** ({len(pending_withdrawals)}):
"
    
    for withdrawal in pending_withdrawals[:10]:
        admin_text += f"• ID:{withdrawal[0]} | {withdrawal[3]} | {withdrawal[2]} نقطة
"
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🔄 تحديث", callback_data='admin_refresh'))
    bot.reply_to(message, admin_text, reply_markup=markup, parse_mode='Markdown')

if __name__ == '__main__':
    init_db()
    print("🚀 Earn Bot Pro - شغال على Railway!")
    print(f"🌐 Frontend: https://earn-mini-appuprailwayapp-production.up.railway.app/")
    print(f"🔧 Backend: earn-bot-production-0d7a.up.railway.app")
    bot.infinity_polling()
