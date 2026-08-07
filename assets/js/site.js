(function(){
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
    toggle.addEventListener('click', function(){
      navLinks.classList.toggle('open');
    });
    navLinks.querySelectorAll('a').forEach(function(a){
      a.addEventListener('click', function(){ navLinks.classList.remove('open'); });
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
      q.addEventListener('click', function(){
        var isOpen = item.classList.contains('open');
        document.querySelectorAll('.faq-item.open').forEach(function(openItem){
          if(openItem !== item){
            openItem.classList.remove('open');
            openItem.querySelector('.faq-a').style.maxHeight = null;
          }
        });
        if(isOpen){
          item.classList.remove('open');
          a.style.maxHeight = null;
        } else {
          item.classList.add('open');
          a.style.maxHeight = a.scrollHeight + 'px';
        }
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

    filterBtns.forEach(function(btn){
      btn.addEventListener('click', function(){
        filterBtns.forEach(function(b){ b.classList.remove('active'); });
        btn.classList.add('active');
        activeFilter = btn.getAttribute('data-filter');
        applyFilters();
      });
    });

    if(searchInput){
      searchInput.addEventListener('input', applyFilters);
    }

    // Support ?filter=Women+Elite links from the nav
    var params = new URLSearchParams(window.location.search);
    var urlFilter = params.get('filter');
    if(urlFilter){
      var match = filterBtns.find(function(b){
        return b.getAttribute('data-filter') === urlFilter;
      });
      if(match){ match.click(); }
    }
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
})();
