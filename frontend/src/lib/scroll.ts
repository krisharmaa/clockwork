/** Smoothly scroll an element to the top of the view. If the browser did not animate it (background tab, reduced
 *  motion), jump there directly shortly afterwards. Returns a function that cancels the pending timers. */
export function scrollToId(id: string, delay = 80): () => void {
  const el = () => document.getElementById(id);
  const go = setTimeout(() => el()?.scrollIntoView({ behavior: 'smooth', block: 'start' }), delay);
  const ensure = setTimeout(() => {
    const top = el()?.getBoundingClientRect().top;
    if (top != null && (top < -40 || top > window.innerHeight * 0.5)) el()?.scrollIntoView({ behavior: 'auto', block: 'start' });
  }, delay + 900);
  return () => {
    clearTimeout(go);
    clearTimeout(ensure);
  };
}
