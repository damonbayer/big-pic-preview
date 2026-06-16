import confetti from 'canvas-confetti';

// Confetti for finished editions. The body carries `data-celebrate` only when a
// finished game has a winner, so this is a no-op on live pages. One pop fires on
// load (skipped under reduced-motion), and the winner's card re-pops on click —
// with a short cooldown so it can't be spammed.
const shouldCelebrate = document.body.dataset.celebrate !== undefined;

if (shouldCelebrate) {
  const COLORS = ['#f2c94c', '#1f9e68', '#f4efe1', '#4fd79a', '#c79a25'];
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let last = 0;
  function celebrate() {
    const now = Date.now();
    if (now - last < 600) return; // cooldown
    last = now;

    // Burst from the winner's card if it's on screen, else from up high.
    const card = document.querySelector('.score-card.leading');
    const r = card?.getBoundingClientRect();
    const origin = r
      ? { x: (r.left + r.width / 2) / window.innerWidth, y: (r.top + r.height / 2) / window.innerHeight }
      : { x: 0.5, y: 0.33 };

    confetti({
      particleCount: 110,
      spread: 360, // radial pop, matching the old all-directions burst
      startVelocity: 38,
      ticks: 140,
      origin,
      colors: COLORS,
    });
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
