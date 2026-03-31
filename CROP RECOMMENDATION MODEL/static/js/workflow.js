function initWorkflowReveal() {
  const cards = document.querySelectorAll(".reveal-workflow");
  if (!cards.length) return;

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.2 },
  );

  cards.forEach((card) => io.observe(card));
}

document.addEventListener("DOMContentLoaded", () => {
  initWorkflowReveal();
});
