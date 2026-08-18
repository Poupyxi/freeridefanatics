(function(){
  var mainContent = document.querySelector('main');
  if(mainContent && !mainContent.id) mainContent.id = 'main-content';

  function safe(name, fn){
    try { fn(); } catch(err) { console.error('[site.js] ' + name + ' failed:', err); }
  }

  // Header shadow on scroll
  safe('header-scroll', function(){
    var header = document.querySelector('header');
    if(!header) return;
    window.addEventListener('scroll', function(){
      header.classList.toggle('scrolled', window.scrollY > 8);
    }, {passive:true});
  });

  // Mobile nav toggle
  safe('mobile-nav', function(){
    var toggle = document.querySelector('.nav-toggle');
    var navLinks = document.querySelector('nav.links');
    if(!toggle || !navLinks) return;
    function setMenu(open){
      navLinks.classList.toggle('open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? 'Close navigation menu' : 'Open navigation menu');
    }
    toggle.addEventListener('click', function(){ setMenu(!navLinks.classList.contains('open')); });
    navLinks.querySelectorAll('a').forEach(function(a){
      a.addEventListener('click', function(){ setMenu(false); });
    });
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape' && navLinks.classList.contains('open')){
        setMenu(false);
        toggle.focus();
      }
    });
  });

  // Scroll-reveal
  safe('scroll-reveal', function(){
    var revealEls = document.querySelectorAll('.reveal');
    if(!revealEls.length) return;
    if('IntersectionObserver' in window){
      var io = new IntersectionObserver(function(entries){
        entries.forEach(function(entry){
          if(entry.isIntersecting){
            entry.target.classList.add('in-view');
            io.unobserve(entry.target);
          }
        });
      }, {threshold:0.12});
      revealEls.forEach(function(el){ io.observe(el); });
    } else {
      revealEls.forEach(function(el){ el.classList.add('in-view'); });
    }
  });

  // FAQ accordion
  safe('faq-accordion', function(){
    document.querySelectorAll('.faq-item').forEach(function(item){
      var q = item.querySelector('.faq-q');
      var a = item.querySelector('.faq-a');
      if(!q || !a) return;
      function setOpen(open){
        item.classList.toggle('open', open);
        q.setAttribute('aria-expanded', open ? 'true' : 'false');
        a.hidden = !open;
        a.style.maxHeight = open ? a.scrollHeight + 'px' : null;
      }
      q.addEventListener('click', function(){
        var isOpen = item.classList.contains('open');
        document.querySelectorAll('.faq-item.open').forEach(function(openItem){
          if(openItem !== item){
            var openQ = openItem.querySelector('.faq-q');
            var openA = openItem.querySelector('.faq-a');
            openItem.classList.remove('open');
            if(openQ) openQ.setAttribute('aria-expanded', 'false');
            if(openA){ openA.hidden = true; openA.style.maxHeight = null; }
          }
        });
        setOpen(!isOpen);
      });
    });
  });

  // Best Equipment marquee — continuous slow scroll, pauses on hover, draggable.
  // The track holds two copies of the card set; when one full set has scrolled
  // past, the offset wraps back seamlessly.
  safe('carousel', function(){
    document.querySelectorAll('[data-marquee]').forEach(function(marquee){
      var track = marquee.querySelector('.carousel-track');
      if(!track) return;
      var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      var SPEED = 28; // px per second
      var x = 0;
      var half = 0;
      var paused = false;
      var dragging = false;
      var lastTime = null;

      function measure(){ half = track.scrollWidth / 2; }
      measure();
      window.addEventListener('resize', measure);

      function tick(now){
        if(lastTime === null) lastTime = now;
        var dt = Math.min((now - lastTime) / 1000, 0.1);
        lastTime = now;
        if(!paused && !dragging && !reducedMotion){ x -= SPEED * dt; }
        if(half > 0){
          while(x <= -half) x += half;
          while(x > 0) x -= half;
        }
        track.style.transform = 'translateX(' + x + 'px)';
        requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);

      marquee.addEventListener('mouseenter', function(){ paused = true; });
      marquee.addEventListener('mouseleave', function(){ paused = false; });

      // Drag to browse (pointer events cover touch + mouse)
      var startX = 0, startTrackX = 0, moved = 0;
      function dragMove(e){
        if(!dragging) return;
        var d = e.clientX - startX;
        if(Math.abs(d) > moved) moved = Math.abs(d);
        x = startTrackX + d;
      }
      function dragEnd(){
        dragging = false;
        window.removeEventListener('pointermove', dragMove);
        window.removeEventListener('pointerup', dragEnd);
      }
      track.addEventListener('pointerdown', function(e){
        dragging = true;
        startX = e.clientX;
        startTrackX = x;
        moved = 0;
        window.addEventListener('pointermove', dragMove);
        window.addEventListener('pointerup', dragEnd);
      });
      // A real drag shouldn't trigger the link under the pointer on release
      track.addEventListener('click', function(e){
        if(moved > 8){
          e.preventDefault();
          e.stopPropagation();
          moved = 0;
        }
      }, true);
    });
  });

  // Rider grid filters (riders.html only)
  safe('rider-filters', function(){
    var grid = document.querySelector('[data-rider-grid]');
    if(!grid) return;
    var cards = Array.prototype.slice.call(grid.querySelectorAll('.rider-card'));
    var filterBtns = Array.prototype.slice.call(document.querySelectorAll('[data-filter]'));
    var searchInput = document.querySelector('[data-search]');
    var activeFilter = 'all';

    function applyFilters(){
      var term = (searchInput && searchInput.value || '').trim().toLowerCase();
      cards.forEach(function(card){
        var cat = card.getAttribute('data-category');
        var haystack = card.getAttribute('data-search') || '';
        var matchesFilter = activeFilter === 'all' || cat === activeFilter;
        var matchesSearch = !term || haystack.indexOf(term) !== -1;
        card.style.display = (matchesFilter && matchesSearch) ? '' : 'none';
      });
    }

    var filterHashes = {'all':'grid', 'Men Elite':'men', 'Women Elite':'women'};

    filterBtns.forEach(function(btn){
      btn.addEventListener('click', function(){
        filterBtns.forEach(function(b){ b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
        activeFilter = btn.getAttribute('data-filter');
        applyFilters();
        var nextHash = filterHashes[activeFilter] || 'grid';
        window.history.replaceState(null, '', window.location.pathname + '#' + nextHash);
      });
    });

    if(searchInput){
      searchInput.addEventListener('input', applyFilters);
    }

    // Filters use fragments so crawlers see one canonical directory URL.
    // Legacy query-string links remain supported until their 301 redirects
    // have been fully processed by search engines.
    var params = new URLSearchParams(window.location.search);
    var hashFilters = {'#grid':'all', '#men':'Men Elite', '#women':'Women Elite'};
    function activateLocationFilter(urlFilter){
      if(!urlFilter) return;
      var match = filterBtns.find(function(b){
        return b.getAttribute('data-filter') === urlFilter;
      });
      if(match){ match.click(); }
    }
    activateLocationFilter(params.get('filter') || hashFilters[window.location.hash]);
    window.addEventListener('hashchange', function(){
      activateLocationFilter(hashFilters[window.location.hash]);
    });
  });

  // Standings page: pick a group (Men / Women / Teams) and a competition.
  // Every table is rendered; only the matching one is shown.
  safe('standings', function(){
    var blocks = Array.prototype.slice.call(document.querySelectorAll('[data-standings]'));
    if(!blocks.length) return;
    var groupBar = document.querySelector('[data-standings-filters]');
    var compBar = document.querySelector('[data-standings-comp-filters]');
    var searchInput = document.querySelector('[data-standings-search]');

    function activeOf(bar, attr){
      if(!bar) return null;
      var btn = bar.querySelector('.filter-btn.active') || bar.querySelector('.filter-btn');
      return btn && btn.getAttribute(attr);
    }

    function render(){
      var group = activeOf(groupBar, 'data-standings-group');
      var comp = activeOf(compBar, 'data-standings-comp');
      var term = (searchInput && searchInput.value || '').trim().toLowerCase();
      blocks.forEach(function(b){
        var okGroup = !group || b.getAttribute('data-standings') === group;
        var okComp = !comp || b.getAttribute('data-competition') === comp;
        var isShown = okGroup && okComp;
        b.classList.toggle('is-shown', isShown);
        var rows = Array.prototype.slice.call(b.querySelectorAll('[data-standing-row]'));
        var shown = 0;
        rows.forEach(function(row){
          var match = !term || (row.getAttribute('data-search') || '').indexOf(term) !== -1;
          row.hidden = !match;
          if(match) shown += 1;
        });
        var empty = b.querySelector('.standings-empty');
        var scroll = b.querySelector('.standings-scroll');
        if(empty) empty.hidden = shown !== 0;
        if(scroll) scroll.hidden = shown === 0;
      });
    }

    [[groupBar, 'data-standings-group'], [compBar, 'data-standings-comp']].forEach(function(pair){
      var bar = pair[0];
      if(!bar) return;
      bar.querySelectorAll('.filter-btn').forEach(function(btn){
        btn.addEventListener('click', function(){
          bar.querySelectorAll('.filter-btn').forEach(function(b){
            b.classList.remove('active');
            if(b.hasAttribute('aria-selected')) b.setAttribute('aria-selected', 'false');
          });
          btn.classList.add('active');
          if(btn.hasAttribute('aria-selected')) btn.setAttribute('aria-selected', 'true');
          render();
        });
      });
    });

    if(searchInput) searchInput.addEventListener('input', render);

    if(groupBar){
      groupBar.addEventListener('keydown', function(e){
        if(e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
        var tabs = Array.prototype.slice.call(groupBar.querySelectorAll('[role="tab"]'));
        var current = tabs.indexOf(document.activeElement);
        if(current < 0) return;
        e.preventDefault();
        var direction = e.key === 'ArrowRight' ? 1 : -1;
        var next = tabs[(current + direction + tabs.length) % tabs.length];
        next.focus();
        next.click();
      });
    }

    blocks.forEach(function(block){
      var scroller = block.querySelector('.standings-scroll');
      var hint = block.querySelector('.standings-swipe');
      if(!scroller || !hint) return;
      function updateHint(){
        hint.classList.toggle('is-complete',
          scroller.scrollLeft + scroller.clientWidth >= scroller.scrollWidth - 4);
      }
      scroller.addEventListener('scroll', updateHint, {passive:true});
      updateHint();
    });

    render();
  });

  // Results: narrow the table to one competition (rider pages)
  safe('competition-filters', function(){
    var bar = document.querySelector('[data-competition-filters]');
    var table = document.querySelector('[data-results-table]');
    if(!bar || !table) return;
    var btns = Array.prototype.slice.call(bar.querySelectorAll('[data-competition-filter]'));
    var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr'));

    function apply(want){
      rows.forEach(function(row){
        row.style.display = (row.getAttribute('data-competition') === want) ? '' : 'none';
      });
    }

    btns.forEach(function(btn){
      btn.addEventListener('click', function(){
        btns.forEach(function(b){ b.classList.remove('active'); });
        btn.classList.add('active');
        apply(btn.getAttribute('data-competition-filter'));
      });
    });

    // The markup ships every row; without this the table would show all
    // competitions while a single chip claims to be selected.
    var initial = bar.querySelector('.filter-btn.active') || btns[0];
    if(initial) apply(initial.getAttribute('data-competition-filter'));
  });

  // Frame reveal — the outline draws itself, turns into a pencil sketch, then
  // resolves into the photo. Held until the composition is scrolled into view
  // so nobody misses it, and replayable afterwards.
  safe('frame-reveal', function(){
    var nodes = Array.prototype.slice.call(document.querySelectorAll('[data-frame-reveal]'));
    if(!nodes.length) return;
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    var SEQUENCE_MS = 5800;

    nodes.forEach(function(node){
      var draw = node.querySelector('.bb-draw');
      var panel = node.closest('.bike-build');
      if(!draw || !panel) return;

      var baseSrc = draw.getAttribute('src');
      var runs = 0;
      var doneTimer = null;
      node.classList.add('armed');

      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'bb-replay';
      btn.textContent = '↻ Replay';
      panel.appendChild(btn);

      function play(){
        runs += 1;
        clearTimeout(doneTimer);
        node.classList.remove('playing');
        panel.classList.remove('reveal-done');
        void node.offsetWidth;  // reflow, so re-adding the class restarts the CSS animations
        // Reloading the SVG restarts the stroke-dashoffset animation it carries
        // internally; without this the outline would only ever draw once.
        draw.setAttribute('src', baseSrc.split('?')[0] + '?r=' + runs);
        node.classList.add('playing');
        doneTimer = setTimeout(function(){ panel.classList.add('reveal-done'); }, SEQUENCE_MS);
      }

      btn.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        play();
      });

      if(!('IntersectionObserver' in window)){ play(); return; }
      var io = new IntersectionObserver(function(entries){
        entries.forEach(function(entry){
          if(!entry.isIntersecting) return;
          io.unobserve(node);
          play();
        });
      }, { threshold: 0.35 });
      io.observe(node);
    });
  });

  // Newsletter signup. The form posts over fetch so the reader never leaves the
  // page, and every outcome lands in the status line. Without JS the form still
  // submits natively to the same endpoint, so nothing is lost.
  document.querySelectorAll('form[data-newsletter]').forEach(function(form){
    var status = form.parentNode.querySelector('[data-newsletter-status]');
    var button = form.querySelector('button[type="submit"]');
    var email  = form.querySelector('input[type="email"]');
    var trap   = form.querySelector('.nl-trap input');
    var idle   = button ? button.textContent : 'Subscribe';

    function say(message, state){
      if (!status) return;
      status.textContent = message;
      status.className = 'cta-status' + (state ? ' is-' + state : '');
    }

    form.addEventListener('submit', function(e){
      e.preventDefault();
      if (trap && trap.value) return;            // bot: accept silently, send nothing
      if (!email || !email.value.trim()) { say('Enter your email address.', 'error'); email && email.focus(); return; }
      if (!email.checkValidity())        { say('That email address looks off.', 'error'); email.focus(); return; }
      if (form.dataset.sending === '1') return;  // double click, double signup

      form.dataset.sending = '1';
      button.disabled = true;
      button.textContent = 'Sending…';
      say('Signing you up…');

      fetch(form.action, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          email: email.value.trim(),
          source: window.location.pathname,
          submitted_at: new Date().toISOString()
        })
      }).then(function(res){
        if (!res.ok) throw new Error(res.status);
        form.reset();
        form.hidden = true;
        say('You are in. The next setup sheet lands the morning after the round.', 'done');
      }).catch(function(){
        // Never pretend it worked — that is the whole point of this rewrite.
        say('That did not go through. Try again in a moment.', 'error');
      }).then(function(){
        form.dataset.sending = '';
        button.disabled = false;
        button.textContent = idle;
      });
    });

    // Clear a stale error as soon as the reader starts fixing it
    email && email.addEventListener('input', function(){
      if (status && status.classList.contains('is-error')) say('');
    });
  });

  // The public Brevo form endpoint accepts a regular HTML POST. Targeting a
  // hidden iframe keeps the reader on RidersFanatics and keeps the API key on
  // Brevo's side. Brevo then handles the signup and confirmation email.
  safe('brevo-newsletter', function(){
    document.querySelectorAll('form[data-brevo-newsletter]').forEach(function(form){
      var status = form.parentNode.querySelector('[data-brevo-newsletter-status]');
      var responseFrame = form.parentNode.querySelector('iframe[name="brevo-newsletter-response"]');
      var button = form.querySelector('button[type="submit"]');
      var email = form.querySelector('input[type="email"]');
      var trap = form.querySelector('.nl-trap input');
      var idle = button ? button.textContent : 'Join the newsletter';
      var waiting = false;

      function say(message, state){
        if (!status) return;
        status.textContent = message;
        status.className = 'cta-status' + (state ? ' is-' + state : '');
      }

      form.addEventListener('submit', function(event){
        if (trap && trap.value) {
          event.preventDefault();
          form.reset();
          return;
        }
        if (!email || !email.checkValidity()) {
          event.preventDefault();
          say('Enter a valid email address.', 'error');
          email && email.focus();
          return;
        }
        if (waiting) {
          event.preventDefault();
          return;
        }
        waiting = true;
        button.disabled = true;
        button.textContent = 'Sending…';
        say('Securely sending your request to Brevo…');
      });

      responseFrame && responseFrame.addEventListener('load', function(){
        if (!waiting) return;
        waiting = false;
        form.reset();
        button.disabled = false;
        button.textContent = idle;
        say('You are subscribed. Check your inbox for our welcome email.', 'done');
      });

      email && email.addEventListener('input', function(){
        if (status && status.classList.contains('is-error')) say('');
      });
    });
  });

  // Contact form progressive enhancement. Native POST remains available when
  // JavaScript is disabled; with JavaScript the visitor stays on the page and
  // receives an honest success or failure message from the server.
  safe('contact-form', function(){
    document.querySelectorAll('form[data-contact]').forEach(function(form){
      var status = form.querySelector('[data-contact-status]');
      var button = form.querySelector('button[type="submit"]');
      var started = form.querySelector('input[name="form_started"]');
      var idle = button ? button.textContent : 'Send message';

      if(started) started.value = String(Math.floor(Date.now() / 1000));

      function say(message, state){
        if(!status) return;
        status.textContent = message;
        status.className = 'contact-status' + (state ? ' is-' + state : '');
      }

      var params = new URLSearchParams(window.location.search);
      if(params.get('sent') === '1') say('Message sent. Thank you — we will review it as soon as possible.', 'done');
      if(params.get('error') === '1') say('The message could not be sent. Please email contact@ridersfanatics.com instead.', 'error');

      form.addEventListener('submit', function(e){
        if(!window.fetch || !window.FormData) return;
        e.preventDefault();
        if(!form.checkValidity()){
          form.reportValidity();
          say('Please complete the required fields.', 'error');
          return;
        }
        if(form.dataset.sending === '1') return;

        form.dataset.sending = '1';
        button.disabled = true;
        button.textContent = 'Sending…';
        say('Sending your message…');

        fetch(form.action, {
          method: 'POST',
          headers: {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
          body: new FormData(form),
          credentials: 'same-origin'
        }).then(function(res){
          return res.json().catch(function(){ return {}; }).then(function(data){
            if(!res.ok || !data.ok) throw new Error(data.message || String(res.status));
            return data;
          });
        }).then(function(){
          form.reset();
          if(started) started.value = String(Math.floor(Date.now() / 1000));
          say('Message sent. Thank you — we will review it as soon as possible.', 'done');
        }).catch(function(){
          say('The message could not be sent. Please try again or email contact@ridersfanatics.com.', 'error');
        }).then(function(){
          form.dataset.sending = '';
          button.disabled = false;
          button.textContent = idle;
        });
      });

      form.addEventListener('input', function(){
        if(status && status.classList.contains('is-error')) say('');
      });
    });
  });

  // "Random rider" CTA — the markup ships with a working href so the button
  // still goes somewhere without JS; here we make it land on a random rider,
  // and on a *different* one each time it is used.
  safe('random-rider', function(){
    document.querySelectorAll('[data-random-rider]').forEach(function(btn){
      var slugs = (btn.getAttribute('data-random-rider') || '').split(',').filter(Boolean);
      if(slugs.length < 2) return;
      var prefix = btn.getAttribute('data-rider-prefix') || 'riders/';
      var last = null;

      function roll(){
        var slug = slugs[Math.floor(Math.random() * slugs.length)];
        if(slugs.length > 1){
          // avoid repeating the previous pick — a repeat reads as a broken button
          while(slug === last){
            slug = slugs[Math.floor(Math.random() * slugs.length)];
          }
        }
        last = slug;
        return prefix + slug + '.html';
      }

      btn.setAttribute('href', roll());
      btn.addEventListener('click', function(e){
        // Let modifier-clicks and middle-clicks open the current href normally
        if(e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        window.location.href = roll();
      });
    });
  });

  // Simple equipment comparator. Products are selected on category pages and
  // stored locally in the visitor's browser; no account or server is required.
  safe('equipment-compare', function(){
    var buttons = Array.prototype.slice.call(document.querySelectorAll('[data-compare-product]'));
    var page = document.querySelector('[data-compare-page]');
    if(!buttons.length && !page) return;

    var STORAGE_KEY = 'rf_equipment_compare_v1';
    var MAX_ITEMS = 4;

    function readSelection(){
      try {
        var value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
        if(!Array.isArray(value)) return [];
        return value.filter(function(item){
          return item && typeof item.id === 'string' && typeof item.category === 'string' && typeof item.title === 'string';
        }).slice(0, MAX_ITEMS);
      } catch(err) { return []; }
    }

    function saveSelection(items){
      selection = items.slice(0, MAX_ITEMS);
      try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(selection)); } catch(err) {}
      updateButtons();
      updateTray();
      renderPage();
    }

    function make(tag, className, text){
      var node = document.createElement(tag);
      if(className) node.className = className;
      if(text !== undefined) node.textContent = text;
      return node;
    }

    var selection = readSelection();
    var tray = null;
    var trayCount = null;
    var trayStatus = null;
    var trayLink = null;

    function ensureTray(){
      if(!buttons.length || tray) return;
      tray = make('aside', 'compare-tray');
      tray.setAttribute('aria-live', 'polite');
      var copy = make('div', 'compare-tray-copy');
      trayCount = make('strong', '', '0 products selected');
      trayStatus = make('span', '', 'Select 2 to 4 products from this category.');
      copy.appendChild(trayCount);
      copy.appendChild(trayStatus);
      var actions = make('div', 'compare-tray-actions');
      var clear = make('button', 'compare-clear', 'Clear');
      clear.type = 'button';
      clear.addEventListener('click', function(){ saveSelection([]); });
      trayLink = make('a', 'btn btn-solid compare-open', 'Compare');
      trayLink.href = '/compare.html';
      trayLink.addEventListener('click', function(e){
        if(selection.length < 2) e.preventDefault();
      });
      actions.appendChild(clear);
      actions.appendChild(trayLink);
      tray.appendChild(copy);
      tray.appendChild(actions);
      document.body.appendChild(tray);
    }

    function updateButtons(){
      buttons.forEach(function(button){
        var product;
        try { product = JSON.parse(button.getAttribute('data-compare-product') || '{}'); } catch(err) { return; }
        var selected = selection.some(function(item){ return item.id === product.id; });
        button.classList.toggle('is-selected', selected);
        button.setAttribute('aria-pressed', selected ? 'true' : 'false');
        button.textContent = selected ? 'Selected' : 'Compare';
      });
    }

    function updateTray(message){
      ensureTray();
      if(!tray) return;
      tray.classList.toggle('is-visible', selection.length > 0);
      trayCount.textContent = selection.length + ' product' + (selection.length === 1 ? '' : 's') + ' selected';
      var categoryName = selection.length ? (selection[0].categoryLabel || selection[0].category || 'products') : 'products';
      trayStatus.textContent = message || (selection.length < 2 ? 'Select at least one more product.' : 'Ready to compare ' + categoryName.toLowerCase() + '.');
      var ready = selection.length >= 2;
      trayLink.classList.toggle('is-disabled', !ready);
      trayLink.setAttribute('aria-disabled', ready ? 'false' : 'true');
    }

    buttons.forEach(function(button){
      button.addEventListener('click', function(){
        var product;
        try { product = JSON.parse(button.getAttribute('data-compare-product') || '{}'); } catch(err) { return; }
        var index = selection.findIndex(function(item){ return item.id === product.id; });
        if(index !== -1){
          selection.splice(index, 1);
          saveSelection(selection);
          return;
        }
        if(selection.length && selection[0].category !== product.category){
          selection = [product];
          saveSelection(selection);
          updateTray('New category started. Select another ' + product.categoryLabel.toLowerCase() + '.');
          return;
        }
        if(selection.length >= MAX_ITEMS){
          updateTray('Maximum reached: remove one product before adding another.');
          return;
        }
        selection.push(product);
        saveSelection(selection);
      });
    });

    function addFact(card, label, value){
      var row = make('div', 'compare-fact');
      row.appendChild(make('span', '', label));
      row.appendChild(make('strong', '', value));
      card.appendChild(row);
    }

    function renderPage(){
      if(!page) return;
      while(page.firstChild) page.removeChild(page.firstChild);
      if(!selection.length){
        var empty = make('div', 'compare-empty');
        empty.appendChild(make('h2', '', 'No products selected yet.'));
        empty.appendChild(make('p', '', 'Open an equipment category and select between two and four products marked “Compare”.'));
        var browse = make('a', 'btn btn-solid', 'Browse equipment');
        browse.href = 'equipment.html';
        empty.appendChild(browse);
        page.appendChild(empty);
        return;
      }

      var heading = make('div', 'compare-page-head');
      var titleWrap = make('div');
      titleWrap.appendChild(make('div', 'label', selection[0].competition || 'Current competition'));
      titleWrap.appendChild(make('h2', '', (selection[0].categoryLabel || selection[0].category) + ' comparison'));
      heading.appendChild(titleWrap);
      var clearAll = make('button', 'compare-clear', 'Clear comparison');
      clearAll.type = 'button';
      clearAll.addEventListener('click', function(){ saveSelection([]); });
      heading.appendChild(clearAll);
      page.appendChild(heading);

      if(selection.length < 2){
        page.appendChild(make('p', 'compare-hint', 'Select at least one more product from the same category to complete the comparison.'));
      }

      var grid = make('div', 'compare-grid');
      selection.forEach(function(product){
        var card = make('article', 'compare-card');
        var remove = make('button', 'compare-remove', 'Remove');
        remove.type = 'button';
        remove.setAttribute('aria-label', 'Remove ' + product.title + ' from comparison');
        remove.addEventListener('click', function(){
          saveSelection(selection.filter(function(item){ return item.id !== product.id; }));
        });
        card.appendChild(remove);
        if(product.image && product.image.indexOf('/assets/img/equipment/') === 0){
          var image = document.createElement('img');
          image.src = product.image;
          image.alt = product.title;
          image.loading = 'lazy';
          card.appendChild(image);
        } else {
          card.appendChild(make('div', 'compare-placeholder', 'RF'));
        }
        card.appendChild(make('div', 'label', product.brand || product.categoryLabel));
        card.appendChild(make('h3', '', product.title));
        addFact(card, 'Tracked riders', String(product.riderCount || 0));
        addFact(card, 'Competition points', String(product.points || 0));
        addFact(card, 'Teams', (product.teams || []).join(', ') || '—');

        var riders = make('div', 'compare-riders');
        riders.appendChild(make('span', '', 'Riders'));
        var riderLinks = make('div');
        (product.riders || []).forEach(function(rider){
          if(!rider || typeof rider.url !== 'string' || rider.url.indexOf('/riders/') !== 0) return;
          var link = make('a', '', rider.name || 'Rider');
          link.href = rider.url;
          riderLinks.appendChild(link);
        });
        if(!riderLinks.childNodes.length) riderLinks.appendChild(make('em', '', 'No rider linked'));
        riders.appendChild(riderLinks);
        card.appendChild(riders);

        if(product.productUrl && /^https?:\/\//.test(product.productUrl)){
          var source = make('a', 'shop-btn compare-source', 'Product details');
          source.href = product.productUrl;
          source.target = '_blank';
          source.rel = 'noopener sponsored';
          card.appendChild(source);
        }
        grid.appendChild(card);
      });
      page.appendChild(grid);
    }

    updateButtons();
    updateTray();
    renderPage();
  });

  // Keep the latest race winners for the first visit of each local day. Every
  // following navigation or reload rotates both riders and their shared kit.
  safe('daily-promo-rotation', function(){
    var strip = document.querySelector('[data-promo-prefix]');
    if(!strip) return;
    var now = new Date();
    var today = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-');
    var storageKey = 'rf-promo-first-visit';
    try {
      if(localStorage.getItem(storageKey) !== today){
        localStorage.setItem(storageKey, today);
        return;
      }
    } catch(err) {
      return;
    }

    var prefix = strip.getAttribute('data-promo-prefix') || '';
    fetch(prefix + 'assets/data/promo-pool.json', {credentials:'same-origin'})
      .then(function(response){
        if(!response.ok) throw new Error('Promo pool unavailable');
        return response.json();
      })
      .then(function(data){
        var riders = Array.isArray(data.riders) ? data.riders : [];
        var women = riders.filter(function(rider){ return rider.gender === 'Women Elite'; });
        var men = riders.filter(function(rider){ return rider.gender === 'Men Elite'; });
        var womenCard = strip.querySelector('[data-promo-role="women"]');
        var menCard = strip.querySelector('[data-promo-role="men"]');
        var equipmentCard = strip.querySelector('[data-promo-role="equipment"]');
        if(!women.length || !men.length || !womenCard || !menCard || !equipmentCard) return;

        function choose(pool, excludedSlug){
          var choices = pool.filter(function(item){ return item.slug !== excludedSlug; });
          if(!choices.length) choices = pool;
          return choices[Math.floor(Math.random() * choices.length)];
        }
        function setMedia(card, source, fallback){
          var media = card.querySelector('.promo-card-media');
          if(!media) return;
          media.textContent = '';
          if(source){
            var image = document.createElement('img');
            image.src = source;
            image.alt = '';
            image.loading = 'lazy';
            image.width = 180;
            image.height = 180;
            media.appendChild(image);
          } else {
            var placeholder = document.createElement('span');
            placeholder.className = 'promo-initials';
            placeholder.setAttribute('aria-hidden', 'true');
            placeholder.textContent = fallback;
            media.appendChild(placeholder);
          }
        }
        function updateRider(card, rider, label){
          var words = rider.name.trim().split(/\s+/);
          var initials = (words[0] ? words[0][0] : '') + (words.length > 1 ? words[words.length - 1][0] : '');
          setMedia(card, rider.photo, initials.toUpperCase());
          card.querySelector('.direct-ad-disclosure').textContent = label;
          card.querySelector('strong').textContent = rider.name;
          card.querySelector('p').textContent = rider.team;
          var link = card.querySelector('a');
          link.href = rider.href;
          link.innerHTML = 'View profile <span aria-hidden="true">→</span>';
        }

        var woman = choose(women, womenCard.getAttribute('data-current-slug'));
        var man = choose(men, menCard.getAttribute('data-current-slug'));
        updateRider(womenCard, woman, 'Random Women');
        updateRider(menCard, man, 'Random Men');

        var womanProducts = {};
        (woman.equipment || []).forEach(function(item){ womanProducts[item.key] = item; });
        var common = (man.equipment || []).filter(function(item){ return womanProducts[item.key]; });
        var productPool = common.length ? common : (woman.equipment || []).concat(man.equipment || []);
        if(productPool.length){
          var product = productPool[Math.floor(Math.random() * productPool.length)];
          setMedia(equipmentCard, product.photo, '+');
          equipmentCard.querySelector('.direct-ad-disclosure').textContent = (common.length ? 'Common equipment · ' : 'Random equipment · ') + product.category;
          equipmentCard.querySelector('strong').textContent = [product.brand, product.model].filter(Boolean).join(' ');
          equipmentCard.querySelector('p').textContent = common.length ? 'Used by both selected riders.' : 'Used by one of the selected riders.';
          var equipmentLink = equipmentCard.querySelector('a');
          equipmentLink.href = product.href;
          equipmentLink.innerHTML = 'Explore category <span aria-hidden="true">→</span>';
        }
      })
      .catch(function(err){ console.error('[site.js] promo rotation failed:', err); });
  });
})();
