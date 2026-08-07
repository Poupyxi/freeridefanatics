// Newsletter signup checks. The box shipped for months with
// onsubmit="return false" — it looked alive and threw every address away, so
// the one behaviour worth pinning down is that it never claims success it did
// not get. Run against a build made with NEWSLETTER_ENDPOINT set.
//
//   npm install jsdom && node tests/newsletter.test.js
const fs = require('fs');
const { JSDOM } = require('jsdom');
const path = require('path');
const ROOT = path.join(__dirname, '..');
const html = fs.readFileSync(ROOT + '/index.html', 'utf8');
const js   = fs.readFileSync(ROOT + '/assets/js/site.js', 'utf8');

let pass = 0, fail = 0;
const ok = (name, cond, extra) => { cond ? pass++ : fail++;
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : '  <- ' + extra}`); };

function boot(fetchImpl) {
  const dom = new JSDOM(html, { runScripts: 'outside-only', url: 'https://ridersfanatics.com/' });
  const w = dom.window;
  w.fetch = fetchImpl;
  w.eval(js);
  w.document.dispatchEvent(new w.Event('DOMContentLoaded', { bubbles: true }));
  const form = w.document.querySelector('form[data-newsletter]');
  return { w, form,
    email:  form.querySelector('input[type=email]'),
    trap:   form.querySelector('.nl-trap input'),
    button: form.querySelector('button[type=submit]'),
    status: w.document.querySelector('[data-newsletter-status]') };
}
const submit = (w, form) => form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
const tick = () => new Promise(r => setTimeout(r, 20));

(async () => {
  console.log('=== markup ===');
  {
    const { form, email, trap, status } = boot(async () => ({ ok: true }));
    ok('form présent', !!form);
    ok('email requis + type email', email.required && email.type === 'email');
    ok('label associé', !!form.querySelector('label[for=newsletter-email]'));
    ok('honeypot présent et hors tabulation', !!trap && trap.tabIndex === -1);
    ok('status est une live region', status.getAttribute('aria-live') === 'polite');
  }

  console.log('\n=== soumission valide ===');
  {
    let sent = null;
    const { w, form, email, status, button } = boot(async (url, opt) => { sent = { url, opt }; return { ok: true }; });
    email.value = '  Marc@Example.com  ';
    submit(w, form);
    ok('bouton désactivé pendant l\'envoi', button.disabled);
    await tick();
    ok('endpoint appelé', !!sent, 'aucun fetch');
    const body = JSON.parse(sent.opt.body);
    ok('email trimmé dans le payload', body.email === 'Marc@Example.com', body.email);
    ok('méthode POST + JSON', sent.opt.method === 'POST' && /json/.test(sent.opt.headers['Content-Type']));
    ok('source transmise', body.source === '/');
    ok('formulaire masqué après succès', form.hidden);
    ok('message de succès', status.classList.contains('is-done'), status.textContent);
    ok('bouton réactivé', !button.disabled);
  }

  console.log('\n=== échec réseau : ne doit JAMAIS annoncer un succès ===');
  {
    const { w, form, email, status, button } = boot(async () => { throw new Error('offline'); });
    email.value = 'marc@example.com';
    submit(w, form); await tick();
    ok('message d\'erreur', status.classList.contains('is-error'), status.textContent);
    ok('formulaire toujours visible', !form.hidden);
    ok('bouton réactivé pour réessayer', !button.disabled);
  }
  {
    const { w, form, email, status } = boot(async () => ({ ok: false, status: 500 }));
    email.value = 'marc@example.com';
    submit(w, form); await tick();
    ok('HTTP 500 traité comme une erreur', status.classList.contains('is-error'), status.textContent);
  }

  console.log('\n=== garde-fous ===');
  {
    let calls = 0;
    const { w, form, email, trap } = boot(async () => { calls++; return { ok: true }; });
    trap.value = 'http://spam.example';
    email.value = 'bot@example.com';
    submit(w, form); await tick();
    ok('honeypot rempli => aucun envoi', calls === 0, `${calls} appel(s)`);
  }
  {
    let calls = 0;
    const { w, form, email, status } = boot(async () => { calls++; return { ok: true }; });
    email.value = '';
    submit(w, form); await tick();
    ok('email vide => aucun envoi + erreur', calls === 0 && status.classList.contains('is-error'));
    email.value = 'pas-un-email';
    submit(w, form); await tick();
    ok('email invalide => aucun envoi', calls === 0, `${calls} appel(s)`);
  }
  {
    let calls = 0;
    const { w, form, email } = boot(() => { calls++; return new Promise(r => setTimeout(() => r({ ok: true }), 60)); });
    email.value = 'marc@example.com';
    submit(w, form); submit(w, form); submit(w, form);
    await new Promise(r => setTimeout(r, 120));
    ok('triple clic => une seule inscription', calls === 1, `${calls} appel(s)`);
  }

  console.log(`\n${pass} pass, ${fail} fail`);
  process.exit(fail ? 1 : 0);
})();
