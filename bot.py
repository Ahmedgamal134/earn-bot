import logging, sqlite3, os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS=[1103784347]
DB="profit_bot.db"

def init_db():
    conn=sqlite3.connect(DB)
    c=conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,points INTEGER DEFAULT 0,joined_date TEXT,referrer INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS checkin(user_id INTEGER, check_date TEXT, UNIQUE(user_id,check_date))""")
    c.execute("""CREATE TABLE IF NOT EXISTS ads(user_id INTEGER, ad_date TEXT, ad_count INTEGER DEFAULT 0, UNIQUE(user_id,ad_date))""")
    c.execute("""CREATE TABLE IF NOT EXISTS withdrawals(user_id INTEGER, wallet TEXT, points INTEGER, date TEXT)""")
    conn.commit()
    conn.close()

def get_points(user_id):
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT points FROM users WHERE user_id=?",(user_id,))
    r=c.fetchone();conn.close()
    return r[0] if r else 0

def add_points(user_id,amount):
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("UPDATE users SET points=points+? WHERE user_id=?",(amount,user_id))
    conn.commit();conn.close()

def can_checkin(user_id):
    today=datetime.now().strftime("%Y-%m-%d")
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT * FROM checkin WHERE user_id=? AND check_date=?",(user_id,today))
    r=c.fetchone();conn.close()
    return r is None

def add_checkin(user_id):
    today=datetime.now().strftime("%Y-%m-%d")
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("INSERT INTO checkin VALUES(?,?)",(user_id,today))
    conn.commit();conn.close()

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    ref=int(context.args[0]) if context.args else None
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id,username,first_name,joined_date,referrer) VALUES(?,?,?,?,?)",(user.id,user.username,user.first_name,datetime.now().strftime("%Y-%m-%d"),ref))
    conn.commit();conn.close()
    keyboard=[[InlineKeyboardButton("🚀 فتح التطبيق",web_app=WebAppInfo(url="https://earn-mini-appuprailwayapp-production.up.railway.app/"))]]
    keyboard.append([InlineKeyboardButton("💰 رصيدي",callback_data="balance")])
    await update.message.reply_text(f"🎉 أهلاً {user.first_name}\n💰 رصيدك: {get_points(user.id)} نقطة",reply_markup=InlineKeyboardMarkup(keyboard))

async def balance(update:Update,context:ContextTypes.DEFAULT_TYPE):
    query=update.callback_query;await query.answer()
    await query.edit_message_text(f"💰 رصيدك: {get_points(query.from_user.id)} نقطة")

async def webapp_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    data=update.message.web_app_data.data
    user_id=update.effective_user.id
    # مشاهدة إعلان
    if data=="watch_ad":
        add_points(user_id,5)
        await update.message.reply_text("📺 تمت مشاهدة الإعلان +5 نقاط")
    elif data=="checkin":
        if not can_checkin(user_id):
            await update.message.reply_text("🎁 سجلت اليوم بالفعل")
            return
        add_checkin(user_id)
        add_points(user_id,5)
        await update.message.reply_text("🎁 تسجيل يومي +5 نقاط")
    elif data.startswith("wheel_"):
        reward=int(data.split("_")[1])
        add_points(user_id,reward)
        await update.message.reply_text(f"🎡 ربحت {reward} نقاط")
    elif data=="refer":
        bot=await context.bot.get_me()
        await update.message.reply_text(f"👥 رابط الدعوة:\nhttps://t.me/{bot.username}?start={user_id}")
    elif data.startswith("withdraw_"):
        parts=data.split("_")
        wallet=parts[1];pts=int(parts[2])
        if pts<875:
            await update.message.reply_text("⚠️ الحد الأدنى للسحب 875 نقطة (~700ج)")
            return
        conn=sqlite3.connect(DB);c=conn.cursor()
        c.execute("INSERT INTO withdrawals VALUES(?,?,?,?)",(user_id,wallet,pts,datetime.now().strftime("%Y-%m-%d")))
        conn.commit();conn.close()
        await update.message.reply_text(f"💳 تم طلب السحب إلى {wallet} بمقدار {pts} نقطة")

async def stats(update:Update,context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    conn=sqlite3.connect(DB);c=conn.cursor()
    c.execute("SELECT COUNT(*) FROM users");users=c.fetchone()[0]
    c.execute("SELECT SUM(points) FROM users");points=c.fetchone()[0]
    conn.close()
    await update.message.reply_text(f"📊 الإحصائيات\n👥 المستخدمين: {users}\n💰 مجموع النقاط: {points}")

def main():
    if not TOKEN: print("❌ BOT TOKEN NOT FOUND");return
    init_db()
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("stats",stats))
    app.add_handler(CallbackQueryHandler(balance,pattern="balance"))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA,webapp_handler))
    print("✅ BOT RUNNING")
    app.run_polling()

if __name__=="__main__":
    main()
