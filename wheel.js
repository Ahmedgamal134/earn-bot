function spinWheel() {
  if (points < 5) {
    alert("لا يوجد نقاط كافية، شاهد إعلان للحصول على 2 لفة مجانية");
    points += 10; // 2 لفة مجانية = 10 نقاط
    updatePointsDisplay();
    return;
  }
  points -= 5;
  const reward = Math.floor(Math.random() * 51); // من 0 إلى 50
  points += reward;
  updatePointsDisplay();
  alert(`العجلة وقفت عند: ${reward} نقطة`);
}
