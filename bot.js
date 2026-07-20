require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const express = require('express');
const app = express();

// التوكن من متغير البيئة
const token = process.env.BOT_TOKEN;
const bot = new TelegramBot(token, { polling: true });

let users = [];
try {
  users = JSON.parse(fs.readFileSync('users.json'));
} catch (e) {
  users = [];
}

function saveUsers() {
  fs.writeFileSync('users.json', JSON.stringify(users, null, 2));
}

// أمر البداية
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;

  if (!users.find(u => u.id === chatId)) {
    users.push({ id: chatId, points: 0, invites: 0 });
    saveUsers();
  }

  bot.sendMessage(chatId, "🔥 أهلاً بيك في البوت الربحي! افتح التطبيق من هنا:", {
    reply_markup: {
      inline_keyboard: [
        [
          { 
            text: "فتح التطبيق", 
            web_app: { url: "https://ahmedgamal134.github.io/earn-bot/" } 
          }
        ]
      ]
    }
  });
});

// تشغيل الـ Dashboard
const PORT = process.env.PORT || 3000;
app.get('/dashboard', (req, res) => {
  const data = JSON.parse(fs.readFileSync('users.json'));
  res.send(data);
});

app.listen(PORT, () => {
  console.log(`Dashboard شغال على المنفذ ${PORT}`);
});
