(() => {
  const root = document.querySelector('[data-rider-feedback]');
  if (!root) return;
  const trigger = root.querySelector('.rider-feedback-trigger');
  const backdrop = root.querySelector('.rider-feedback-backdrop');
  const dialog = root.querySelector('.rider-feedback-dialog');
  const closeButton = root.querySelector('.rider-feedback-close');
  const iframe = root.querySelector('iframe');
  const delay = Math.max(0, Number(root.dataset.delay) || 3000);
  let previousFocus = null;

  const close = () => {
    dialog.hidden = true;
    backdrop.hidden = true;
    document.body.classList.remove('rider-feedback-open');
    (previousFocus || trigger).focus();
  };
  const open = () => {
    previousFocus = document.activeElement;
    if (!iframe.src) iframe.src = iframe.dataset.formUrl;
    backdrop.hidden = false;
    dialog.hidden = false;
    document.body.classList.add('rider-feedback-open');
    closeButton.focus();
  };

  window.setTimeout(() => { trigger.hidden = false; }, delay);
  trigger.addEventListener('click', open);
  closeButton.addEventListener('click', close);
  backdrop.addEventListener('click', close);
  document.addEventListener('keydown', (event) => {
    if (dialog.hidden) return;
    if (event.key === 'Escape') close();
    if (event.key === 'Tab') {
      const focusable = Array.from(dialog.querySelectorAll('button, a, iframe')).filter(el => !el.hidden);
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
})();
