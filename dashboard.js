const fs = require('fs');
const express = require('express');
const app = express();
const PORT = 3000;

app.get('/dashboard', (req, res) => {
  const data = JSON.parse(fs.readFileSync('users.json'));
  res.send(data);
});

app.listen(PORT, () => {
  console.log(`Dashboard شغال على http://localhost:${PORT}/dashboard`);
});
