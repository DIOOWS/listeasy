(() => {
  'use strict';
  const button = document.querySelector('[data-print-mechanic]');
  if (button) button.addEventListener('click', () => window.print());
})();
