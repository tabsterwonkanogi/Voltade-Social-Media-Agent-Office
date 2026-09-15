/* The office floor.
 *
 * Everything drawn here comes from /api/floor. A figure walks only when the
 * audit trail says work actually changed hands, and when the kill switch is
 * on the lamps go out and nobody moves. An office that looks busy while the
 * system is halted would be a lie told in pixels.
 */
(() => {
  const cv = document.getElementById('floor');
  const cx = cv.getContext('2d');
  const TW = 64, TH = 32;                 // isometric tile at zoom 1
  /* The camera. A floor this dense is unreadable on a phone at fit-width,
     so it opens zoomed in on the desks and you drag to look around. */
  const cam = { x: 600, y: 58, z: 1 };

  const INK = '#2a0030';
  const COLOURS = {
    michael: '#7a2f80', jim: '#1d9e75', pam: '#d8451a',
    dwight: '#2f6fb5', kelly: '#c9517c', angela: '#b9791b',
  };

  /* Desks. Michael has a room; everyone else is in the open plan. */
  const DESKS = {
    michael: { x: 3.0, y: 1.6, face: 1, office: true },
    jim:     { x: 8.6, y: 2.4, face: -1 },
    pam:     { x: 11.6, y: 4.2, face: -1 },
    dwight:  { x: 8.6, y: 6.2, face: -1 },
    kelly:   { x: 11.6, y: 8.0, face: -1 },
    angela:  { x: 8.6, y: 10.0, face: -1 },
  };
  /* Where work goes when it leaves a desk. */
  const PLACES = {
    michael: { x: 4.4, y: 2.6 },
    queue:   { x: 6.2, y: 11.4 },
    out:     { x: 3.4, y: 12.6 },
    bin:     { x: 13.0, y: 11.0 },
  };
  const CORRIDOR = 6.9;                   // the aisle everyone walks down

  let data = null, seen = new Set(), walkers = [], selected = null, first = true;

  /* ---------------------------------------------------------- geometry */
  const iso = (x, y) => ({
    sx: cam.x + (x - y) * (TW / 2) * cam.z,
    sy: cam.y + (x + y) * (TH / 2) * cam.z,
  });
  const z = (n) => n * cam.z;             // scale a pixel measurement

  function tile(x, y, fill, stroke) {
    const p = iso(x, y);
    cx.beginPath();
    cx.moveTo(p.sx, p.sy);
    cx.lineTo(p.sx + z(TW / 2), p.sy + z(TH / 2));
    cx.lineTo(p.sx, p.sy + z(TH));
    cx.lineTo(p.sx - z(TW / 2), p.sy + z(TH / 2));
    cx.closePath();
    cx.fillStyle = fill;
    cx.fill();
    if (stroke) { cx.strokeStyle = stroke; cx.lineWidth = 1; cx.stroke(); }
  }

  /* A box standing on the floor, drawn in three faces. */
  function box(x, y, w, d, h, top, left, right) {
    const a = iso(x, y), b = iso(x + w, y), c = iso(x + w, y + d), e = iso(x, y + d);
    const lift = p => ({ sx: p.sx, sy: p.sy - z(h) });
    const A = lift(a), B = lift(b), C = lift(c), E = lift(e);
    cx.beginPath();                                    // top
    cx.moveTo(A.sx, A.sy); cx.lineTo(B.sx, B.sy);
    cx.lineTo(C.sx, C.sy); cx.lineTo(E.sx, E.sy); cx.closePath();
    cx.fillStyle = top; cx.fill();
    cx.beginPath();                                    // left face
    cx.moveTo(A.sx, A.sy); cx.lineTo(E.sx, E.sy);
    cx.lineTo(e.sx, e.sy); cx.lineTo(a.sx, a.sy); cx.closePath();
    cx.fillStyle = left; cx.fill();
    cx.beginPath();                                    // right face
    cx.moveTo(E.sx, E.sy); cx.lineTo(C.sx, C.sy);
    cx.lineTo(c.sx, c.sy); cx.lineTo(e.sx, e.sy); cx.closePath();
    cx.fillStyle = right; cx.fill();
  }

  const shade = (hex, f) => {
    const n = parseInt(hex.slice(1), 16);
    const r = Math.round(((n >> 16) & 255) * f), g = Math.round(((n >> 8) & 255) * f),
          b = Math.round((n & 255) * f);
    return `rgb(${r},${g},${b})`;
  };

  /* ---------------------------------------------------------- furniture */
  function carpet(dark) {
    for (let x = 0; x < 15; x++)
      for (let y = 0; y < 14; y++) {
        const inOffice = x < 6 && y < 5;
        const base = inOffice ? (dark ? '#3a3340' : '#7a6b80')
                              : (dark ? '#2f3a38' : '#61736e');
        tile(x, y, (x + y) % 2 ? base : shade(base, 1.07), 'rgba(0,0,0,.05)');
      }
  }

  function cubicle(d, dark) {
    const panel = dark ? '#5d5750' : '#cdc6b6';
    const panelSide = dark ? '#4a453f' : '#b4ad9e';
    box(d.x - 0.1, d.y - 0.9, 1.9, 0.12, 34, panel, panelSide, shade(panelSide, .9));
    box(d.x - 0.2, d.y - 0.9, 0.12, 1.9, 34, panel, panelSide, shade(panelSide, .9));
    const desk = dark ? '#6a5b48' : '#c3ab88';
    box(d.x, d.y, 1.6, 1.0, 16, desk, shade(desk, .82), shade(desk, .7));
    const crt = dark ? '#6f6a5e' : '#ded7c4';
    box(d.x + 0.35, d.y + 0.15, 0.55, 0.5, 30, crt, shade(crt, .85), shade(crt, .72));
    const glow = dark ? '#1b2a26' : '#8fd6c2';
    box(d.x + 0.38, d.y + 0.17, 0.45, 0.42, 31, glow, glow, glow);
    if (!dark) {                                   // paper, and a desk lamp
      box(d.x + 0.08, d.y + 0.62, 0.35, 0.28, 17, '#f4efe4', '#ded8cb', '#ccc6b8');
      box(d.x + 1.28, d.y + 0.2, 0.16, 0.16, 26, '#e8a33c', '#c5862c', '#a86f22');
    }
  }

  function office(dark) {
    const wall = dark ? '#4b4550' : '#e6dfe8';
    const side = dark ? '#3c3741' : '#cfc6d3';
    box(-0.2, -0.2, 6.2, 0.14, 72, wall, side, shade(side, .9));   // back wall
    box(-0.2, -0.2, 0.14, 5.2, 72, wall, side, shade(side, .9));   // left wall
    box(5.9, -0.2, 0.14, 2.3, 72, wall, side, shade(side, .9));    // partial, doorway
    box(5.9, 3.4, 0.14, 1.6, 72, wall, side, shade(side, .9));
    const desk = dark ? '#5e4a3c' : '#a98a63';
    box(2.7, 1.4, 2.0, 1.1, 18, desk, shade(desk, .8), shade(desk, .68));
    const crt = dark ? '#6f6a5e' : '#ded7c4';
    box(3.3, 1.55, 0.6, 0.5, 32, crt, shade(crt, .85), shade(crt, .72));
    const glow = dark ? '#1b2a26' : '#8fd6c2';
    box(3.33, 1.57, 0.5, 0.42, 33, glow, glow, glow);
    if (!dark) box(2.85, 2.0, 0.4, 0.3, 19, '#f4efe4', '#ded8cb', '#ccc6b8');
    label(2.9, 0.2, 'MICHAEL', dark);
  }

  function props(dark) {
    const t = dark ? '#4a453f' : '#b9b2a4';
    box(PLACES.queue.x - 0.4, PLACES.queue.y - 0.3, 1.0, 0.7, 14, t,
        shade(t, .82), shade(t, .7));
    if (!dark) box(PLACES.queue.x - 0.3, PLACES.queue.y - 0.2, 0.8, 0.5, 16,
                   '#f4efe4', '#ded8cb', '#ccc6b8');
    label(PLACES.queue.x - 0.5, PLACES.queue.y + 0.55, 'OUT TRAY', dark);
    const b = dark ? '#3f4a47' : '#7d8a86';
    box(PLACES.bin.x, PLACES.bin.y, 0.5, 0.5, 20, b, shade(b, .8), shade(b, .68));
    label(PLACES.bin.x - 0.1, PLACES.bin.y + 0.7, 'REFUSED', dark);
    box(PLACES.out.x, PLACES.out.y, 1.2, 0.14, 54,
        dark ? '#584c42' : '#a08a6d', dark ? '#473d35' : '#84714f',
        dark ? '#3c332c' : '#6e5e42');
    label(PLACES.out.x, PLACES.out.y + 0.5, 'PUBLISHED', dark);
  }

  function label(x, y, text, dark) {
    const p = iso(x, y);
    cx.font = '500 ' + Math.max(8, z(10)).toFixed(1) + 'px "JetBrains Mono", monospace';
    cx.fillStyle = dark ? 'rgba(255,255,255,.35)' : 'rgba(0,0,0,.38)';
    cx.textAlign = 'center';
    cx.fillText(text, p.sx, p.sy + z(4));
    cx.textAlign = 'left';
  }

  /* ---------------------------------------------------------- figures */
  function person(x, y, colour, opts = {}) {
    const p = iso(x, y);
    const { seated = false, dim = false, carry = null, t = 0 } = opts;
    const bob = seated ? 0 : Math.sin(t / 120) * 1.6;
    const base = { sx: p.sx, sy: p.sy + z(TH / 2 + bob) };
    cx.globalAlpha = dim ? 0.42 : 1;

    cx.beginPath();                                       // shadow
    cx.ellipse(base.sx, base.sy + z(2), z(9), z(4), 0, 0, Math.PI * 2);
    cx.fillStyle = 'rgba(0,0,0,.22)'; cx.fill();

    const h = z(seated ? 15 : 21);
    cx.fillStyle = shade(colour, .72);                    // legs / chair block
    cx.fillRect(base.sx - z(5), base.sy - h + z(9), z(10), h - z(9));
    cx.fillStyle = colour;                                // torso
    cx.beginPath();
    cx.roundRect(base.sx - z(6), base.sy - h - z(2), z(12), z(13), z(3));
    cx.fill();
    cx.fillStyle = '#f0d9c0';                             // head
    cx.beginPath();
    cx.arc(base.sx, base.sy - h - z(8), z(5.2), 0, Math.PI * 2);
    cx.fill();
    cx.fillStyle = shade(colour, .55);                    // hair
    cx.beginPath();
    cx.arc(base.sx, base.sy - h - z(9.5), z(5.2), Math.PI, 0);
    cx.fill();

    if (carry) {
      cx.fillStyle = '#f7f2e6';
      cx.fillRect(base.sx + z(5), base.sy - h + z(1), z(7), z(6));
      cx.strokeStyle = 'rgba(0,0,0,.25)';
      cx.strokeRect(base.sx + z(5), base.sy - h + z(1), z(7), z(6));
    }
    cx.globalAlpha = 1;
    return base;
  }

  function badge(x, y, text, colour) {
    const p = iso(x, y);
    const fs = Math.max(9, z(11));
    cx.font = '500 ' + fs.toFixed(1) + 'px "League Spartan", sans-serif';
    const w = cx.measureText(text).width + fs * 1.3;
    const hh = fs * 1.55, bx = p.sx - w / 2, by = p.sy - z(54);
    cx.fillStyle = 'rgba(20,10,24,.82)';
    cx.beginPath(); cx.roundRect(bx, by, w, hh, hh / 2); cx.fill();
    cx.fillStyle = colour;
    cx.beginPath();
    cx.arc(bx + fs * 0.62, by + hh / 2, fs * 0.27, 0, Math.PI * 2); cx.fill();
    cx.fillStyle = '#f3ebf4';
    cx.textAlign = 'left';
    cx.fillText(text, bx + fs * 1.05, by + hh * 0.72);
  }

  /* ---------------------------------------------------------- walking */
  function path(from, to) {
    const a = DESKS[from] ? { x: DESKS[from].x, y: DESKS[from].y + 1.4 }
                          : PLACES[from];
    const b = DESKS[to] ? PLACES.michael : PLACES[to];
    if (!a || !b) return null;
    return [a, { x: CORRIDOR, y: a.y }, { x: CORRIDOR, y: b.y }, b];
  }

  function spawn(ev) {
    const legs = path(ev.from, ev.to);
    if (!legs) return;
    walkers.push({ who: ev.from, legs: legs.concat(legs.slice().reverse()),
                   leg: 0, p: 0, what: ev.what });
  }

  function stepWalkers(dt) {
    for (const w of walkers) {
      w.p += dt / 900;
      while (w.p >= 1 && w.leg < w.legs.length - 2) { w.leg++; w.p -= 1; }
      if (w.leg >= w.legs.length - 2 && w.p >= 1) w.done = true;
    }
    walkers = walkers.filter(w => !w.done);
  }

  const walkerAt = name => walkers.find(w => w.who === name);

  function walkerPos(w) {
    const a = w.legs[w.leg], b = w.legs[w.leg + 1] || a;
    return { x: a.x + (b.x - a.x) * w.p, y: a.y + (b.y - a.y) * w.p };
  }

  /* ---------------------------------------------------------- drawing */
  let hit = [];

  function draw(t, dt) {
    // Unknown is not the same as stopped. Before the first poll answers we
    // dim the room, but we do not claim the kill switch is on, because we do
    // not know yet and saying so would be the same class of lie as a made-up
    // number on the analytics page.
    const loaded = !!data;
    const dark = !loaded || data.killed;
    cx.clearRect(0, 0, cv.width, cv.height);
    carpet(dark);
    office(dark);
    for (const [name, d] of Object.entries(DESKS)) if (!d.office) cubicle(d, dark);
    props(dark);

    hit = [];
    const order = Object.entries(DESKS).sort(
      (a, b) => (a[1].x + a[1].y) - (b[1].x + b[1].y));

    for (const [name, d] of order) {
      const st = data ? data.agents.find(a => a.name === name) : null;
      const w = walkerAt(name);
      const pos = w ? walkerPos(w) : { x: d.x + 0.55, y: d.y + 1.15 };
      const base = person(pos.x, pos.y, COLOURS[name], {
        seated: !w,
        dim: st ? (st.state === 'blocked' || st.state === 'stopped') : true,
        carry: w ? true : false,
        t,
      });
      hit.push({ name, sx: base.sx, sy: base.sy });

      let tag = name.charAt(0).toUpperCase() + name.slice(1);
      if (st) {
        if (st.state === 'working') tag += ' · working';
        else if (st.state === 'blocked') tag += ' · blocked';
        else if (st.state === 'stopped') tag += ' · stopped';
        else if (w) tag += ' · ' + w.what;
      }
      badge(pos.x, pos.y, tag, COLOURS[name]);
    }

    if (dark) {
      cx.fillStyle = 'rgba(10,4,14,.45)';
      cx.fillRect(0, 0, cv.width, cv.height);
      cx.font = '500 15px "League Spartan", sans-serif';
      cx.fillStyle = loaded ? '#f09595' : '#8b7890';
      cx.textAlign = 'center';
      cx.fillText(loaded ? 'Everyone is stopped. The kill switch is on.'
                         : 'Reading the floor', cv.width / 2, 40);
      cx.textAlign = 'left';
    }
  }

  /* ---------------------------------------------------------- panel */
  const panel = document.getElementById('panel');
  const $ = id => document.getElementById(id);

  function openPanel(name) {
    selected = name;
    panel.hidden = false;
    const st = data && data.agents.find(a => a.name === name);
    $('p-name').textContent = name.charAt(0).toUpperCase() + name.slice(1);
    $('p-name').style.color = COLOURS[name];
    $('p-role').textContent = st ? st.role : '';
    renderStatus(st);
    loadChat(name);
  }

  function renderStatus(st) {
    if (!st) return;
    const bits = {
      working: ['working', 'go'],
      idle: ['at their desk, nothing running', 'hold'],
      blocked: [st.blocked_by || 'blocked', 'stop'],
      stopped: ['stopped by the kill switch', 'stop'],
    }[st.state];
    let extra = '';
    if (st.state === 'working' && st.working_on)
      extra = ` for ${Math.max(1, Math.round(st.working_on.seconds))}s`;
    $('p-status').innerHTML =
      `<span class="pill ${bits[1]}">${bits[0]}${extra}</span>` +
      `<span class="pill">${st.autonomy === 'auto' ? 'just do it' : 'ask me'}</span>`;
    $('p-today').innerHTML = `
      <div><b>${st.today.runs}</b><span>runs</span></div>
      <div><b>${st.today.ok}</b><span>finished</span></div>
      <div><b>${st.today.errors}</b><span>errors</span></div>
      <div><b>${(st.today.tokens / 1000).toFixed(1)}k</b><span>tokens</span></div>`;
    $('p-last').textContent = st.today.last
      ? st.today.last
      : 'Nothing finished today.';
  }

  async function loadChat(name) {
    const r = await fetch(`/api/agent/${name}/chat`);
    if (!r.ok) return;
    const j = await r.json();
    const box = $('p-chat');
    box.innerHTML = j.messages.length ? '' :
      '<p class="sub">No instructions yet.</p>';
    for (const m of j.messages) {
      const d = document.createElement('div');
      d.className = 'msg ' + m.role;
      d.textContent = m.text;
      box.appendChild(d);
    }
    box.scrollTop = box.scrollHeight;
    $('p-note').textContent = j.killed
      ? 'Everyone is stopped. Release the kill switch in Settings to give orders.'
      : (j.busy ? 'Busy with something right now.' : '');
    $('p-send').disabled = j.killed || j.busy;
  }

  $('p-close').onclick = () => { panel.hidden = true; selected = null; };

  $('p-form').onsubmit = async (e) => {
    e.preventDefault();
    const msg = $('p-msg').value.trim();
    if (!msg || !selected) return;
    const body = new FormData();
    body.append('message', msg);
    const r = await fetch(`/api/agent/${selected}/chat`, { method: 'POST', body });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      $('p-note').textContent = j.error || 'That did not go through.';
      return;
    }
    $('p-msg').value = '';
    loadChat(selected);
  };

  /* ---------------------------------------------------------- camera */
  /* The canvas is a window onto the floor, not a fixed-ratio picture. Its
     backing store matches its CSS box, so a tall phone gets a tall view
     instead of a letterboxed strip with half the team cropped off. */
  function resize() {
    const r = cv.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.round(r.width * dpr);
    cv.height = Math.round(r.height * dpr);
    frameFloor(r.width, dpr);
  }

  /* Open on the whole office, the way you would walk into a room, then let
     the reader zoom in on whoever they care about. */
  const FLOOR_W = 15, FLOOR_H = 14;

  function frameFloor() {
    const pad = 28;
    const worldW = (FLOOR_W + FLOOR_H) * (TW / 2);
    const worldH = (FLOOR_W + FLOOR_H) * (TH / 2) + 90;   // 90 for wall height
    cam.z = Math.min((cv.width - pad * 2) / worldW,
                     (cv.height - pad * 2) / worldH);
    cam.z = Math.max(0.35, Math.min(2.4, cam.z));
    cam.x = cv.width / 2 + (FLOOR_H - FLOOR_W) * (TW / 4) * cam.z;
    // Centre the diamond vertically. Fit is limited by width, so a tall
    // phone would otherwise hang the whole office off the top edge.
    const drawnH = (FLOOR_W + FLOOR_H) * (TH / 2) * cam.z;
    cam.y = (cv.height - drawnH) / 2 + 30 * cam.z;
  }
  resize();
  new ResizeObserver(() => resize()).observe(cv);

  const toCanvas = (clientX, clientY) => {
    const r = cv.getBoundingClientRect();
    return { x: (clientX - r.left) * (cv.width / r.width),
             y: (clientY - r.top) * (cv.height / r.height) };
  };

  let drag = null, moved = 0;
  const pointers = new Map();
  let pinch = null;

  function zoomAt(px, py, factor) {
    const before = cam.z;
    cam.z = Math.min(3.5, Math.max(0.3, cam.z * factor));
    cam.x = px - (px - cam.x) * (cam.z / before);
    cam.y = py - (py - cam.y) * (cam.z / before);
  }

  cv.addEventListener('pointerdown', (e) => {
    cv.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, toCanvas(e.clientX, e.clientY));
    if (pointers.size === 1) { drag = toCanvas(e.clientX, e.clientY); moved = 0; }
    if (pointers.size === 2) { drag = null; pinch = spread(); }
  });

  function spread() {
    const [a, b] = [...pointers.values()];
    return { d: Math.hypot(a.x - b.x, a.y - b.y),
             cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 };
  }

  cv.addEventListener('pointermove', (e) => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, toCanvas(e.clientX, e.clientY));

    if (pointers.size === 2 && pinch) {
      const now = spread();
      if (now.d > 0 && pinch.d > 0) zoomAt(now.cx, now.cy, now.d / pinch.d);
      cam.x += now.cx - pinch.cx;
      cam.y += now.cy - pinch.cy;
      pinch = now;
      moved = 99;
      return;
    }
    if (!drag) return;
    const p = toCanvas(e.clientX, e.clientY);
    cam.x += p.x - drag.x;
    cam.y += p.y - drag.y;
    moved += Math.abs(p.x - drag.x) + Math.abs(p.y - drag.y);
    drag = p;
  });

  const endDrag = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (pointers.size === 0) drag = null;
  };
  cv.addEventListener('pointerup', endDrag);
  cv.addEventListener('pointercancel', endDrag);

  cv.addEventListener('wheel', (e) => {
    e.preventDefault();
    const p = toCanvas(e.clientX, e.clientY);
    zoomAt(p.x, p.y, e.deltaY < 0 ? 1.12 : 0.89);
  }, { passive: false });

  cv.addEventListener('dblclick', (e) => {
    const p = toCanvas(e.clientX, e.clientY);
    zoomAt(p.x, p.y, 1.6);
  });

  /* ---------------------------------------------------------- input */
  cv.addEventListener('click', (e) => {
    if (moved > 8) return;                // that was a drag, not a tap
    const r = cv.getBoundingClientRect();
    const mx = (e.clientX - r.left) * (cv.width / r.width);
    const my = (e.clientY - r.top) * (cv.height / r.height);
    // A thumb is about 40 CSS pixels wide. The figures are smaller than that
    // when the floor is zoomed out, so the target is sized in screen terms,
    // not world terms, or half the taps land on carpet.
    const dpr = cv.width / r.width;
    let best = null, bd = Math.max(z(40), 34 * dpr);
    for (const h of hit) {
      const d = Math.hypot(h.sx - mx, (h.sy - z(16)) - my);
      if (d < bd) { bd = d; best = h.name; }
    }
    if (best) openPanel(best);
  });

  /* ---------------------------------------------------------- loop */
  async function poll() {
    try {
      const r = await fetch('/api/floor');
      if (!r.ok) return;
      data = await r.json();
      for (const ev of data.walks) {
        if (seen.has(ev.id)) continue;
        seen.add(ev.id);
        if (!first) spawn(ev);        // never replay history on first load
      }
      first = false;
      if (selected) {
        renderStatus(data.agents.find(a => a.name === selected));
        loadChat(selected);
      }
    } catch (err) { /* keep drawing the last known state */ }
  }

  let last = performance.now();
  function frame(now) {
    const dt = Math.min(60, now - last); last = now;
    stepWalkers(dt);
    draw(now, dt);
    requestAnimationFrame(frame);
  }

  poll();
  setInterval(poll, 5000);
  requestAnimationFrame(frame);
})();
