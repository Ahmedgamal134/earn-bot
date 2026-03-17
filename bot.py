import telebot
import sqlite3
from datetime import datetime
import os

TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
DB = "profit_bot.db"
MINI_APP_URL = "https://earn-mini-appuprailwayapp-production.up.railway.app/"

def init_db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS daily_checkin (user_id INTEGER, check_date TEXT, UNIQUE(user_id, check_date))")
    conn.commit()
    conn.close()

def get_points(user_id):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def add_points(user_id, amount):
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, points) VALUES (?, 0)", (user_id,))
    c.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def can_checkin(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT 1 FROM daily_checkin WHERE user_id=? AND check_date=?", (user_id, today))
    result = c.fetchone()
    conn.close()
    return result is None

def do_checkin(user_id):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT INTO daily_checkin (user_id, check_date) VALUES (?, ?)", (user_id, today))
    conn.commit()
    conn.close()

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    points = get_points(user_id)
    
    markup = telebot.types.InlineKeyboardMarkup()
    btn1 = telebot.types.InlineKeyboardButton("🚀 Mini App", web_app=telebot.types.WebAppInfo(url=MINI_APP_URL))
    btn2 = telebot.types.InlineKeyboardButton("✅ Daily Check", callback_data='daily')
    btn3 = telebot.types.InlineKeyboardButton("💰 Balance", callback_data='balance')
    
    markup.add(btn1, btn2, btn3)
    bot.send_message(message.chat.id, "Welcome! Points: " + str(points), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == 'daily':
        if can_checkin(user_id):
            do_checkin(user_id)
            add_points(user_id, 5)
            points = get_points(user_id)
            bot.answer_callback_query(call.id, "Daily OK! +5 points")
            bot.edit_message_text("Daily check OK! +5 points. Total: " + str(points), call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "Already done today")
            bot.edit_message_text("Daily check already done today", call.message.chat.id, call.message.message_id)
    
    elif data == 'balance':
        points = get_points(user_id)
        bot.answer_callback_query(call.id)
        bot.edit_message_text("Your balance: " + str(points) + " points", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda message: True)
def handle_all(message):
    user_id = message.from_user.id
    data = message.text
    
    if "watch_ad" in data:
        add_points(user_id, 5)
        bot.reply_to(message, "Ad watched! +5 points")
    
    elif "wheel_" in data:
        try:
            reward = int(data.split("_")[1])
            add_points(user_id, reward)
            bot.reply_to(message, "Wheel win! +" + str(reward) + " points")
        except:
            pass

if __name__ == '__main__':
    if not TOKEN:
        print("No BOT_TOKEN")
    else:
        init_db()
        print("Bot starting...")
        bot.polling(none_stop=True)
