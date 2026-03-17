import telebot
import sqlite3
from datetime import datetime, date
import os


TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
DB = "profit_bot.db"
MINI_APP_URL = "https://earn-mini-appuprailwayapp-production.up.railway.app/"
ADMIN_ID = 1103784347

def init_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, spins INTEGER DEFAULT 0, daily_checkin_date TEXT, invites INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, wallet_type TEXT, wallet_number TEXT, status TEXT DEFAULT 'ظ‚ظٹط¯ ط§ظ„ط§ظ†طھط¸ط§ط±')")
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
    btn1 = telebot.types.InlineKeyboardButton("ط§ظ„طھط·ط¨ظٹظ‚",web_app=telebot.types.WebAppInfo(url=MINI_APP_URL))
    btn2 = telebot.types.InlineKeyboardButton("ط§ظ„ط­ط³ط§ط¨",callback_data='stats')
    markup.add(btn1)
    markup.row(btn2)

    today_str = date.today().isoformat()
    daily_status = "ط§ظ„ظٹظˆظ…" if daily_date == today_str else "ظ…طھط§ط­"

    text = "Earn Pro"
    text = text + "\n\n"
    text = text + "ظ†ظ‚ط§ط·ظƒ: " + str(points)
    text = text + "\n"
    text = text + "ظ„ظپط§طھظƒ: " + str(spins)
    text = text + "\n"
    text = text + "ظٹظˆظ…ظٹ: " + daily_status
    text = text + "\n"
    text = text + "ط¯ط¹ظˆط§طھ: " + str(invites)
    text = text + "\n\nط§ط¨ط¯ط£ ط§ظ„ظƒط³ط¨!"

    bot.send_message(message.chat.id,text,reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == 'stats':
        user_id = call.from_user.id
        points,spins,daily_date,invites = get_user_stats(user_id)
        today_str = date.today().isoformat()
        daily_status = "ط§ظ„ظٹظˆظ…" if daily_date == today_str else "ظ…طھط§ط­"

        text = "ط­ط³ط§ط¨ظƒ:"
        text = text + "\n\n"
        text = text + "ط§ظ„ظ†ظ‚ط§ط·: " + str(points)
        text = text + "\n"
        text = text + "ط§ظ„ظ„ظپط§طھ: " + str(spins)
        text = text + "\n"
        text = text + "ط§ظ„ظٹظˆظ…ظٹ: " + daily_status
        text = text + "\n"
        text = text + "ط§ظ„ط¯ط¹ظˆط§طھ: " + str(invites)
        text = text + "\n"
        text = text + "ط§ظ„ط³ط­ط¨: ظ‚ظٹط¯ ط§ظ„ط§ظ†طھط¸ط§ط±"

        bot.edit_message_text(text,call.message.chat.id,call.message.message_id)

@bot.message_handler(func=lambda m: True)
def webapp_data(message):
    user_id = message.from_user.id
    data = message.text

    if data == 'watch_ad':
        update_points(user_id,5)
        update_spins(user_id,2)
        bot.reply_to(message,"ط§ط¹ظ„ط§ظ† طھظ…! +5 ظ†ظ‚ط·ط© +2 ظ„ظپط©")

    elif data.startswith('wheel_'):
        reward = int(data.split('_')[1])
        update_points(user_id,reward)
        bot.reply_to(message,"ط¹ط¬ظ„ط© ط§ظ„ط­ط¸! ظپط²طھ ط¨ظ€ " + str(reward) + " ظ†ظ‚ط·ط©!")

    elif data == 'daily_checkin':
        points,spins,daily_date,invites = get_user_stats(user_id)
        today_str = date.today().isoformat()
        if daily_date != today_str:
            set_daily_checkin(user_id)
            update_points(user_id,10)
            bot.reply_to(message,"طھط³ط¬ظٹظ„ ظٹظˆظ…ظٹ! +10 ظ†ظ‚ط·ط©")
        else:
            bot.reply_to(message,"ط³ط¬ظ„طھ ط§ظ„ظٹظˆظ… ط¨ط§ظ„ظپط¹ظ„!")

    elif data == 'invite':
        update_points(user_id,15)
        bot.reply_to(message,"ط¯ط¹ظˆط© ظ…ط³ط¬ظ„ط©! +15 ظ†ظ‚ط·ط©")

    elif data.startswith('withdraw_'):
        parts = data.split('_')
        wallet_type = parts[1]
        wallet_num = parts[2]
        amount = int(parts[3])

        conn = sqlite3.connect(DB, check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO withdrawals(user_id,amount,wallet_type,wallet_number) VALUES(?,?,?,?)",(user_id,amount,wallet_type,wallet_num))
        c.execute("UPDATE users SET points = points - ? WHERE user_id = ?",(amount,user_id))
        conn.commit()
        conn.close()

        text = "ط·ظ„ط¨ ط³ط­ط¨:\n\n"
        text = text + "ط§ظ„ظ…ط¨ظ„ط؛: " + str(amount) + " ظ†ظ‚ط·ط©\n"
        text = text + "ط§ظ„ط·ط±ظٹظ‚ط©: " + wallet_type + "\n"
        text = text + "ط§ظ„ط­ط³ط§ط¨: " + wallet_num + "\n"
        text = text + "ظ‚ظٹط¯ ط§ظ„ط§ظ†طھط¸ط§ط±"
        bot.reply_to(message,text)

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
    c.execute("SELECT * FROM withdrawals WHERE status='ظ‚ظٹط¯ ط§ظ„ط§ظ†طھط¸ط§ط±' ORDER BY id DESC LIMIT 5")
    pending = c.fetchall()
    conn.close()

    text = "ظ„ظˆط­ط© ط§ظ„طھط­ظƒظ…\n\n"
    text = text + "ط§ظ„ظ…ط³طھط®ط¯ظ…ظٹظ†: " + str(total_users) + "\n"
    text = text + "ط§ظ„ظ†ظ‚ط§ط·: " + str(total_points) + "\n\n"
    text = text + "ط·ظ„ط¨ط§طھ ط§ظ„ط³ط­ط¨:\n"
    for w in pending:
        text = text + "- " + str(w[2]) + " " + w[3] + "\n"

    bot.reply_to(message,text)

if __name__ == '__main__':
    init_db()
    print("ط§ظ„ط¨ظˆطھ ط´ط؛ط§ظ„!")
    bot.infinity_polling()
