let points = 0;
let lastAdTime = 0;

function updatePointsDisplay() {
  document.getElementById('points').innerText = `رصيدك: ${points} نقطة`;
}

async function playAd(spotId) {
  const now = Date.now();
  if (now - lastAdTime < 20000) {
    alert("انتظر 20 ثانية بين كل إعلان والتاني");
    return;
  }
  lastAdTime = now;

  try {
    const show = await window.initCdTma?.({ id: spotId });
    await show();
    points += 5; // كل إعلان = 5 نقاط
    updatePointsDisplay();
    console.log("تم تشغيل الإعلان بنجاح");
  } catch (e) {
    console.log("خطأ في تشغيل الإعلان", e);
  }
}
