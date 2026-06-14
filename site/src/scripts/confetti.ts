// Dependency-free confetti for finished editions. The body carries
// `data-celebrate` only when a finished game has a winner, so this is a no-op
// on live pages. One pop fires on load (skipped under reduced-motion), and the
// winner's card re-pops on click — with a short cooldown so it can't be spammed.
const shouldCelebrate = document.body.dataset.celebrate !== undefined;

if (shouldCelebrate) {
  const COLORS = ['#f2c94c', '#1f9e68', '#f4efe1', '#4fd79a', '#c79a25'];
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  interface Particle {
    x: number;
    y: number;
    vx: number;
    vy: number;
    rot: number;
    vrot: number;
    size: number;
    color: string;
    life: number;
  }

  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:60;';
  let ctx: CanvasRenderingContext2D | null = null;
  let particles: Particle[] = [];
  let running = false;

  // Resizing resets the canvas transform, so re-apply the DPR scale each time.
  function resize() {
    canvas.width = Math.floor(window.innerWidth * devicePixelRatio);
    canvas.height = Math.floor(window.innerHeight * devicePixelRatio);
    ctx?.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  }

  function ensureCanvas() {
    if (ctx) return;
    document.body.appendChild(canvas);
    ctx = canvas.getContext('2d');
    resize();
    window.addEventListener('resize', resize, { passive: true });
  }

  function frame() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    ctx!.clearRect(0, 0, w, h);
    for (const p of particles) {
      p.vy += 0.25; // gravity
      p.vx *= 0.99;
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.vrot;
      p.life -= 0.008;
      ctx!.save();
      ctx!.translate(p.x, p.y);
      ctx!.rotate(p.rot);
      ctx!.globalAlpha = Math.max(0, p.life);
      ctx!.fillStyle = p.color;
      ctx!.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.5);
      ctx!.restore();
    }
    particles = particles.filter((p) => p.life > 0 && p.y < h + 40);
    if (particles.length > 0) {
      requestAnimationFrame(frame);
    } else {
      running = false;
      ctx!.clearRect(0, 0, w, h);
    }
  }

  let last = 0;
  function celebrate() {
    const now = Date.now();
    if (now - last < 600) return; // cooldown
    last = now;
    ensureCanvas();

    // Burst from the winner's card if it's on screen, else from up high.
    const card = document.querySelector('.score-card.leading');
    const r = card?.getBoundingClientRect();
    const ox = r ? r.left + r.width / 2 : window.innerWidth / 2;
    const oy = r ? r.top + r.height / 2 : window.innerHeight / 3;

    for (let i = 0; i < 90; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 6 + Math.random() * 9;
      particles.push({
        x: ox,
        y: oy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 6,
        rot: Math.random() * Math.PI,
        vrot: (Math.random() - 0.5) * 0.3,
        size: 5 + Math.random() * 6,
        color: COLORS[(Math.random() * COLORS.length) | 0],
        life: 1,
      });
    }
    if (!running) {
      running = true;
      requestAnimationFrame(frame);
    }
  }

  // The winning card invites a click for an encore (allowed even under
  // reduced-motion, since it's user-initiated).
  const winnerCard = document.querySelector<HTMLElement>('.score-card.leading');
  if (winnerCard) {
    winnerCard.style.cursor = 'pointer';
    winnerCard.title = 'Pop the confetti';
    winnerCard.addEventListener('click', celebrate);
  }

  if (!reduceMotion) {
    setTimeout(celebrate, 400);
  }
}
