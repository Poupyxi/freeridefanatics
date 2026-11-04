(function () {
  'use strict';

  var dialog;
  var previousFocus;

  function createDialog() {
    if (dialog) return dialog;
    dialog = document.createElement('div');
    dialog.className = 'equipment-lightbox';
    dialog.hidden = true;
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'equipment-lightbox-title');
    dialog.innerHTML = '<div class="equipment-lightbox-panel" role="document">' +
      '<button class="equipment-lightbox-close" type="button" aria-label="Close equipment image">×</button>' +
      '<img class="equipment-lightbox-image" alt="">' +
      '<h2 class="equipment-lightbox-title" id="equipment-lightbox-title"></h2>' +
      '<a class="equipment-lightbox-category" href="">View category</a>' +
      '</div>';
    document.body.appendChild(dialog);
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog || event.target.closest('.equipment-lightbox-close')) close();
    });
    return dialog;
  }

  function open(button) {
    var layer = createDialog();
    var image = layer.querySelector('.equipment-lightbox-image');
    var title = layer.querySelector('.equipment-lightbox-title');
    var category = layer.querySelector('.equipment-lightbox-category');
    var label = button.getAttribute('data-equipment-title') || 'Equipment';
    image.src = button.getAttribute('data-equipment-image');
    image.alt = label;
    title.textContent = label;
    category.href = button.getAttribute('data-equipment-category-url') || '#';
    category.hidden = !button.getAttribute('data-equipment-category-url');
    previousFocus = document.activeElement;
    layer.hidden = false;
    document.body.classList.add('equipment-lightbox-open');
    layer.querySelector('.equipment-lightbox-close').focus();
  }

  function close() {
    if (!dialog) return;
    dialog.hidden = true;
    document.body.classList.remove('equipment-lightbox-open');
    if (previousFocus && previousFocus.focus) previousFocus.focus();
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest('.equip-thumb-trigger');
    if (button) open(button);
    var card = event.target.closest('[data-equipment-card="true"]');
    if (card && !event.target.closest('a,button')) {
      var trigger = card.querySelector('.equip-thumb-trigger');
      if (trigger) open(trigger);
    }
  });
  document.addEventListener('keydown', function (event) {
    var card = event.target.closest('[data-equipment-card="true"]');
    if (card && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      var trigger = card.querySelector('.equip-thumb-trigger');
      if (trigger) open(trigger);
    }
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') close();
  });
}());
