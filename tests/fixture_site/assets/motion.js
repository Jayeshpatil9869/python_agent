/* Fixture motion helpers */
(function () {
  const preloader = document.getElementById('preloader');
  const pct = document.getElementById('preloader-pct');
  if (preloader && pct) {
    let n = 0;
    const id = setInterval(() => {
      n += 20;
      pct.textContent = Math.min(n, 100) + '%';
      if (n >= 100) {
        clearInterval(id);
        preloader.classList.add('exit');
        setTimeout(() => preloader.remove(), 400);
      }
    }, 80);
  }

  const cursor = document.getElementById('cursor');
  if (cursor) {
    document.body.classList.add('has-custom-cursor');
    document.addEventListener('mousemove', (e) => {
      cursor.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
    });
  }

  document.getElementById('menu-toggle')?.addEventListener('click', function () {
    const menu = document.getElementById('mobile-menu');
    if (!menu) return;
    const open = !menu.classList.contains('hidden');
    menu.classList.toggle('hidden', open);
    this.setAttribute('aria-expanded', open ? 'false' : 'true');
  });
})();
