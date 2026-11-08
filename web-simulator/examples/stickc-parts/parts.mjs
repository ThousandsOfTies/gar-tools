import '/gar-components/m5stickc-plus2.mjs';
for (const [index, device] of [...document.querySelectorAll('gar-stickc-plus2')].entries()) {
  let count = index * 10;
  const canvas = device.querySelector('canvas'), context = canvas.getContext('2d');
  const draw = () => {
    context.fillStyle = '#081310'; context.fillRect(0,0,canvas.width,canvas.height);
    context.fillStyle = index ? '#ecbc68' : '#81cba0'; context.font = '16px monospace';
    context.fillText(`${canvas.width} x ${canvas.height}`, 10, 26);
    context.font = '38px monospace'; context.fillText(String(count), 14, 85);
  };
  device.addEventListener('gar-button', ({detail}) => {
    device.parentElement.querySelector('pre').textContent = JSON.stringify(detail);
    if (detail.phase !== 'up') return;
    count = detail.button === 'C' ? 0 : count + (detail.button === 'A' ? 1 : -1); draw();
  });
  draw();
}
