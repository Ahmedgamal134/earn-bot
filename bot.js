require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const mongoose = require('mongoose');
const express = require('express');

const app = express();

// اتصال بقاعدة البيانات
mongoose.connect(process.env.MONGO_URI, {
  useNewUrlParser: true,
  useUnifiedTopology: true
}).then(() => console.log("✅ Connected to MongoDB"))
  .catch(err => console.error("❌ MongoDB connection error:", err));

// إعداد البوت
const bot = new TelegramBot(process.env.TELEGRAM_TOKEN, { polling: true });

// أمر /start
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  const userName = msg.from.username || "مستخدم";
  const welcomeMessage = `👋 مرحبًا ${userName}!\nأهلاً بك في تطبيق عجلة الحظ 🎰\nاكسب النقاط ودعوة الأصدقاء 💰`;
  const options = {
    reply_markup: {
      keyboard: [
        [{ text: "🎮 فتح التطبيق" }],
        [{ text: "📢 دعوة صديق" }]
      ],
      resize_keyboard: true
    }
  };
  bot.sendMessage(chatId, welcomeMessage, options);
});

// أمر فتح التطبيق
bot.onText(/فتح التطبيق/, (msg) => {
  bot.sendMessage(msg.chat.id, "رابط التطبيق: https://earnminiap-65a.b.jrnm.app");
});

// أمر دعوة صديق
bot.onText(/دعوة صديق/, (msg) => {
  bot.sendMessage(msg.chat.id, "شارك الرابط مع أصدقائك لزيادة نقاطك 💎");
});

// تشغيل السيرفر
app.listen(3000, () => {
  console.log("🚀 Server running on port 3000");
});
