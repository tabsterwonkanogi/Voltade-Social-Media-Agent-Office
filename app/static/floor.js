/* Voltade Social Media Office, the floor.
 *
 * Everything drawn here comes from /api/floor. A figure walks only when the
 * audit trail says work actually changed hands, and when the kill switch is
 * on the lamps go out and nobody moves. An office that looked busy while the
 * system was halted would be a lie told in pixels.
 */
(() => {
  const cv = document.getElementById('floor');
  const cx = cv.getContext('2d');
  const TW = 64, TH = 32;
  const cam = { x: 0, y: 0, z: 1 };

  const P = {
    masterKey: '#dccd8b', pricklyPear: '#a7993c', mozart: '#475480',
    sunburn: '#b57056', copperRed: '#7f3b25', edamame: '#aea181',
    wiltedBrown: '#a84f3d', purpleBasil: '#5a4651', dulcetViolet: '#5a384b',
    palmLeaf: '#37462b',
  };

  /* The cast. Shirt, hair, and one distinguishing detail each: enough to tell
     six people apart at thirty pixels tall, which is all the resolution a
     likeness gets here anyway. */
  const CAST = {
    michael: { shirt: P.purpleBasil, hair: '#3a2b22', tie: P.copperRed },
    jim:     { shirt: P.mozart,      hair: '#2f2620', tie: '#6c7ba6' },
    pam:     { shirt: P.sunburn,     hair: '#7a5433', pony: true },
    dwight:  { shirt: P.palmLeaf,    hair: '#2b2118', glasses: true, tie: P.masterKey },
    kelly:   { shirt: P.wiltedBrown, hair: '#1f1a17', pony: true },
    angela:  { shirt: P.pricklyPear, hair: '#c9ab6a', bun: true },
  };

  const DESKS = {
    michael: { x: 2.0, y: 1.2 },
    jim:     { x: 8.2, y: 2.8 },
    pam:     { x: 10.8, y: 2.8 },
    dwight:  { x: 8.2, y: 5.1 },
    angela:  { x: 10.8, y: 5.1 },
    kelly:   { x: 8.2, y: 7.4 },
  };
  const PLACES = {
    michael: { x: 5.2, y: 2.4 },
    queue:   { x: 13.4, y: 6.6 },
    out:     { x: 3.0, y: 12.4 },
    bin:     { x: 12.2, y: 8.6 },
  };
  const CORRIDOR = 6.8;
  const FLOOR_W = 16, FLOOR_H = 13;

  let data = null, seen = new Set(), walkers = [], selected = null, first = true;

  /* ---------------------------------------------------------- geometry */
  const iso = (x, y) => ({
    sx: cam.x + (x - y) * (TW / 2) * cam.z,
    sy: cam.y + (x + y) * (TH / 2) * cam.z,
  });
  const z = (n) => n * cam.z;

  const shade = (hex, f) => {
    const n = parseInt(hex.slice(1), 16);
    const c = (v) => Math.max(0, Math.min(255, Math.round(v * f)));
    return 'rgb(' + c((n >> 16) & 255) + ',' + c((n >> 8) & 255) + ',' + c(n & 255) + ')';
  };

  function tile(x, y, fill) {
    const p = iso(x, y);
    cx.beginPath();
    cx.moveTo(p.sx, p.sy);
    cx.lineTo(p.sx + z(TW / 2), p.sy + z(TH / 2));
    cx.lineTo(p.sx, p.sy + z(TH));
    cx.lineTo(p.sx - z(TW / 2), p.sy + z(TH / 2));
    cx.closePath();
    cx.fillStyle = fill;
    cx.fill();
  }

  /* A solid standing on the floor. Light falls from the upper left, so the
     left face is always brighter than the right. That one rule is what makes
     flat shapes read as volume. */
  function box(x, y, w, d, h, colour, lift) {
    lift = lift || 0;
    const a = iso(x, y), b = iso(x + w, y), c = iso(x + w, y + d), e = iso(x, y + d);
    const up = (p, n) => ({ sx: p.sx, sy: p.sy - z(n) });
    const A = up(a, h + lift), B = up(b, h + lift);
    const C = up(c, h + lift), E = up(e, h + lift);
    const a0 = up(a, lift), e0 = up(e, lift), c0 = up(c, lift);

    cx.beginPath();
    cx.moveTo(A.sx, A.sy); cx.lineTo(B.sx, B.sy);
    cx.lineTo(C.sx, C.sy); cx.lineTo(E.sx, E.sy); cx.closePath();
    cx.fillStyle = shade(colour, 1.12); cx.fill();

    cx.beginPath();
    cx.moveTo(A.sx, A.sy); cx.lineTo(E.sx, E.sy);
    cx.lineTo(e0.sx, e0.sy); cx.lineTo(a0.sx, a0.sy); cx.closePath();
    cx.fillStyle = shade(colour, 0.92); cx.fill();

    cx.beginPath();
    cx.moveTo(E.sx, E.sy); cx.lineTo(C.sx, C.sy);
    cx.lineTo(c0.sx, c0.sy); cx.lineTo(e0.sx, e0.sy); cx.closePath();
    cx.fillStyle = shade(colour, 0.72); cx.fill();
  }

  /* ---------------------------------------------------------- the room */
  /* Each room carries its own colour, the way a floor plan does, so the eye
     can find the conference room without reading the label. */
  const ROOMS = [
    { x0: -1, x1: 6, y0: -1, y1: 5, floor: '#cdc0cb', wall: '#ded0da' },   // Michael
    { x0: 12, x1: 17, y0: -1, y1: 3, floor: '#c6cfc0', wall: '#d8dfd1' },  // break
    { x0: 11.5, x1: 17, y0: 9, y1: 14, floor: '#c6cad8', wall: '#d6dae5' }, // conference
  ];
  const roomAt = (x, y) =>
    ROOMS.find((r) => x >= r.x0 && x < r.x1 && y >= r.y0 && y < r.y1);

  function carpet(dark) {
    const base = dark ? '#3a332a' : '#c7ba98';
    const alt = dark ? '#413a30' : '#d0c5a6';
    for (let x = 0; x < FLOOR_W; x++) {
      for (let y = 0; y < FLOOR_H; y++) {
        const r = roomAt(x, y);
        if (r) {
          tile(x, y, dark ? '#463c33'
                          : ((x + y) % 2 ? r.floor : shade(r.floor, 1.04)));
        } else {
          tile(x, y, (x + y) % 2 ? base : alt);
        }
      }
    }
  }

  const wall = (x, y, w, d, dark, colour) =>
    box(x, y, w, d, 62, dark ? '#5a5043' : (colour || '#ece3cd'));

  function glass(x, y, w, d, dark) {
    box(x, y, w, d, 20, dark ? '#5a5043' : '#ece3cd');
    cx.globalAlpha = 0.45;
    box(x, y, w, d, 40, dark ? '#4f6a6a' : '#cfe0da', 20);
    cx.globalAlpha = 1;
  }

  function rooms(dark) {
    const m = ROOMS[0].wall, b = ROOMS[1].wall, c = ROOMS[2].wall;
    wall(-0.2, -0.2, 6.0, 0.16, dark, m);
    wall(-0.2, -0.2, 0.16, 5.0, dark, m);
    glass(5.6, -0.2, 0.16, 2.2, dark);
    glass(5.6, 3.2, 0.16, 1.8, dark);
    wall(-0.2, 4.8, 6.0, 0.16, dark, m);

    wall(12.4, -0.2, 3.8, 0.16, dark, b);
    wall(12.4, -0.2, 0.16, 3.0, dark, b);
    wall(12.4, 2.9, 3.8, 0.16, dark, b);

    wall(11.6, 9.4, 4.6, 0.16, dark, c);
    wall(11.6, 9.4, 0.16, 3.6, dark, c);
  }

  function deskUnit(d, dark) {
    const panel = dark ? '#4e463a' : P.edamame;
    box(d.x - 0.15, d.y - 0.85, 2.0, 0.14, 30, panel);
    box(d.x - 0.15, d.y - 0.85, 0.14, 2.0, 30, panel);

    const top = dark ? '#5b4b38' : '#c9ad82';
    box(d.x, d.y, 1.7, 1.05, 15, top);

    const beige = dark ? '#6b6356' : '#e4dcc6';
    box(d.x + 0.42, d.y + 0.12, 0.62, 0.55, 26, beige, 15);
    box(d.x + 0.46, d.y + 0.16, 0.5, 0.44, 2, dark ? '#2b3a36' : '#8fb7a6', 39);
    box(d.x + 0.35, d.y + 0.74, 0.75, 0.2, 3, beige, 15);

    if (!dark) box(d.x + 0.1, d.y + 0.5, 0.3, 0.26, 2, '#f7f2e4', 15);
    box(d.x + 1.3, d.y + 0.18, 0.14, 0.14, 18, dark ? '#6a5a33' : P.masterKey, 15);

    const chair = dark ? '#3e3a33' : '#7d7466';
    box(d.x + 0.5, d.y + 1.45, 0.55, 0.55, 5, chair);
    box(d.x + 0.55, d.y + 1.78, 0.45, 0.13, 20, chair, 5);
  }

  function props(dark) {
    const t = dark ? '#5b4b38' : '#c9ad82';
    box(PLACES.queue.x - 0.5, PLACES.queue.y - 0.4, 1.2, 0.9, 13, t);
    if (!dark) box(PLACES.queue.x - 0.35, PLACES.queue.y - 0.25, 0.9, 0.6, 3, '#f7f2e4', 13);
    label(PLACES.queue.x, PLACES.queue.y + 0.95, 'OUT TRAY', dark);

    box(PLACES.bin.x, PLACES.bin.y, 0.5, 0.5, 18, dark ? '#43483c' : '#8a8e77');
    label(PLACES.bin.x + 0.25, PLACES.bin.y + 0.85, 'REFUSED', dark);

    box(PLACES.out.x, PLACES.out.y, 1.3, 0.16, 50, dark ? '#5d4a33' : '#a9835a');
    label(PLACES.out.x + 0.65, PLACES.out.y + 0.6, 'PUBLISHED', dark);

    box(12.6, 10.6, 2.6, 1.3, 14, dark ? '#5b4b38' : '#c9ad82');
    box(13.2, -0.05, 0.7, 0.5, 40, dark ? '#3f4a52' : P.mozart);
  }

  function label(x, y, text, dark) {
    const p = iso(x, y);
    const fs = Math.max(8, z(9.5));
    cx.font = fs.toFixed(1) + 'px "Helvetica Neue", Helvetica, Arial, sans-serif';
    cx.fillStyle = dark ? 'rgba(240,231,214,.34)' : 'rgba(59,46,53,.40)';
    cx.textAlign = 'center';
    cx.fillText(text, p.sx, p.sy + z(4));
    cx.textAlign = 'left';
  }

  /* ---------------------------------------------------------- figures */
  function limb(x, y, w, h, colour) {
    cx.fillStyle = colour;
    cx.beginPath();
    cx.roundRect(x - w / 2, y, w, h, w / 2);
    cx.fill();
  }

  /* A small person with volume. A gradient across the torso and a lit side on
     the head do the work; at this size real geometry would read as noise. */
  function person(x, y, who, opts) {
    const look = CAST[who];
    const walking = opts.walking, dim = opts.dim, carry = opts.carry;
    const typing = opts.typing, t = opts.t || 0;
    const p = iso(x, y);
    const gy = p.sy + z(TH / 2);

    const stride = walking ? Math.sin(t / 110) : 0;
    const bob = walking ? Math.abs(Math.cos(t / 110)) * 1.4 : Math.sin(t / 900) * 0.5;
    const base = gy - z(bob);

    cx.globalAlpha = dim ? 0.45 : 1;

    cx.beginPath();
    cx.ellipse(p.sx, gy + z(1.5), z(9), z(3.6), 0, 0, Math.PI * 2);
    cx.fillStyle = 'rgba(59,46,53,.20)';
    cx.fill();

    const trouser = '#3f3a33';
    limb(p.sx - z(3.2), base - z(10) + z(stride * 1.6), z(4.4), z(10), trouser);
    limb(p.sx + z(3.2), base - z(10) - z(stride * 1.6), z(4.4), z(10), trouser);

    const tw = z(12.5), th = z(13);
    const g = cx.createLinearGradient(p.sx - tw / 2, 0, p.sx + tw / 2, 0);
    g.addColorStop(0, shade(look.shirt, 1.18));
    g.addColorStop(0.55, look.shirt);
    g.addColorStop(1, shade(look.shirt, 0.74));
    cx.fillStyle = g;
    cx.beginPath();
    cx.roundRect(p.sx - tw / 2, base - z(22), tw, th, [z(5), z(5), z(2), z(2)]);
    cx.fill();

    if (look.tie) {
      cx.fillStyle = '#f3ede0';
      cx.beginPath();
      cx.moveTo(p.sx - z(3.4), base - z(22));
      cx.lineTo(p.sx + z(3.4), base - z(22));
      cx.lineTo(p.sx, base - z(17.5));
      cx.closePath(); cx.fill();
      cx.fillStyle = look.tie;
      cx.fillRect(p.sx - z(1), base - z(20), z(2), z(7));
    }

    const armSw = walking ? stride * 1.4 : 0;
    limb(p.sx - tw / 2 - z(0.6), base - z(21) - z(armSw), z(3.6), z(10),
         shade(look.shirt, 0.86));
    limb(p.sx + tw / 2 + z(0.6), base - z(21) + z(armSw), z(3.6), z(10),
         shade(look.shirt, 1.06));

    if (typing) {
      const tick = Math.sin(t / 90) * z(1);
      cx.fillStyle = '#e8c9a8';
      cx.beginPath(); cx.arc(p.sx - z(4), base - z(11) + tick, z(1.7), 0, 7); cx.fill();
      cx.beginPath(); cx.arc(p.sx + z(4), base - z(11) - tick, z(1.7), 0, 7); cx.fill();
    }

    const hy = base - z(28);
    const hg = cx.createRadialGradient(p.sx - z(2), hy - z(2), z(0.5), p.sx, hy, z(6.4));
    hg.addColorStop(0, '#f6e0c6');
    hg.addColorStop(1, '#d9b691');
    cx.fillStyle = hg;
    cx.beginPath(); cx.arc(p.sx, hy, z(6), 0, Math.PI * 2); cx.fill();

    cx.fillStyle = look.hair;
    cx.beginPath();
    cx.arc(p.sx, hy - z(0.8), z(6.1), Math.PI * 1.02, Math.PI * 1.98);
    cx.fill();
    if (look.pony) {
      cx.beginPath();
      cx.ellipse(p.sx + z(6), hy + z(2), z(2.2), z(4.4), 0, 0, Math.PI * 2);
      cx.fill();
    }
    if (look.bun) {
      cx.beginPath(); cx.arc(p.sx, hy - z(6.4), z(2.6), 0, Math.PI * 2); cx.fill();
    }
    if (look.glasses) {
      cx.strokeStyle = 'rgba(40,30,25,.85)';
      cx.lineWidth = Math.max(0.7, z(0.7));
      cx.beginPath();
      cx.arc(p.sx - z(2.2), hy + z(0.6), z(1.9), 0, 7);
      cx.moveTo(p.sx + z(4.1), hy + z(0.6));
      cx.arc(p.sx + z(2.2), hy + z(0.6), z(1.9), 0, 7);
      cx.stroke();
    }

    if (carry) {
      cx.fillStyle = '#f7f2e4';
      cx.strokeStyle = 'rgba(59,46,53,.28)';
      cx.lineWidth = Math.max(0.6, z(0.6));
      cx.beginPath();
      cx.roundRect(p.sx + z(6), base - z(19), z(8), z(6.5), z(0.8));
      cx.fill(); cx.stroke();
    }

    cx.globalAlpha = 1;
    return { sx: p.sx, sy: gy };
  }

  function nameplate(x, y, name, state, colour) {
    const p = iso(x, y);
    const fs = Math.max(10, z(11.5));
    const display = 'px "Typist", Cutive, "Courier New", Georgia, serif';
    const body = 'px "Helvetica Neue", Helvetica, Arial, sans-serif';
    const label = name.charAt(0).toUpperCase() + name.slice(1);

    cx.font = fs.toFixed(1) + display;
    const w1 = cx.measureText(label).width;
    const sub = state ? '  ' + state : '';
    cx.font = (fs * 0.72).toFixed(1) + body;
    const w2 = sub ? cx.measureText(sub).width : 0;

    const w = w1 + w2 + fs * 1.5, h = fs * 1.6;
    const bx = p.sx - w / 2, by = p.sy - z(46) - h;

    cx.fillStyle = 'rgba(246,240,225,.95)';
    cx.strokeStyle = 'rgba(59,46,53,.20)';
    cx.lineWidth = Math.max(0.7, z(0.8));
    cx.beginPath(); cx.roundRect(bx, by, w, h, z(3)); cx.fill(); cx.stroke();
    cx.fillStyle = colour;
    cx.fillRect(bx, by, Math.max(1.5, z(3)), h);

    cx.textAlign = 'left';
    cx.fillStyle = '#3b2e35';
    cx.font = fs.toFixed(1) + display;
    cx.fillText(label, bx + fs * 0.75, by + h * 0.72);
    if (sub) {
      cx.font = (fs * 0.72).toFixed(1) + body;
      cx.fillStyle = 'rgba(59,46,53,.6)';
      cx.fillText(sub, bx + fs * 0.75 + w1, by + h * 0.72);
    }
  }

  /* ---------------------------------------------------------- walking */
  function path(from, to) {
    const a = DESKS[from] ? { x: DESKS[from].x + 0.8, y: DESKS[from].y + 2.1 }
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
      w.p += dt / 1000;
      while (w.p >= 1 && w.leg < w.legs.length - 2) { w.leg++; w.p -= 1; }
      if (w.leg >= w.legs.length - 2 && w.p >= 1) w.done = true;
    }
    walkers = walkers.filter((w) => !w.done);
  }
  const walkerAt = (name) => walkers.find((w) => w.who === name);
  function walkerPos(w) {
    const a = w.legs[w.leg], b = w.legs[w.leg + 1] || a;
    return { x: a.x + (b.x - a.x) * w.p, y: a.y + (b.y - a.y) * w.p };
  }

  /* ---------------------------------------------------------- drawing */
  let hit = [];

  function draw(t) {
    const loaded = !!data;
    const dark = !loaded || data.killed;
    cx.clearRect(0, 0, cv.width, cv.height);
    carpet(dark);
    rooms(dark);
    for (const name in DESKS) deskUnit(DESKS[name], dark);
    props(dark);
    label(2.9, 0.4, 'MICHAEL', dark);
    label(14.2, 1.4, 'BREAK ROOM', dark);
    label(13.8, 12.3, 'CONFERENCE', dark);

    hit = [];
    const order = Object.keys(DESKS).sort(
      (a, b) => (DESKS[a].x + DESKS[a].y) - (DESKS[b].x + DESKS[b].y));

    const plates = [];
    for (const name of order) {
      const d = DESKS[name];
      const st = loaded ? data.agents.find((a) => a.name === name) : null;
      const w = walkerAt(name);
      const pos = w ? walkerPos(w) : { x: d.x + 0.8, y: d.y + 1.6 };
      const working = st && st.state === 'working';
      const base = person(pos.x, pos.y, name, {
        walking: !!w,
        typing: !w && working,
        dim: st ? (st.state === 'blocked' || st.state === 'stopped') : true,
        carry: !!w,
        t: t,
      });
      hit.push({ name: name, sx: base.sx, sy: base.sy });

      let state = '';
      if (st) {
        if (w) state = w.what;
        else if (st.state === 'working') state = 'working';
        else if (st.state === 'blocked') state = 'blocked';
        else if (st.state === 'stopped') state = 'stopped';
      }
      plates.push([pos.x, pos.y, name, state, CAST[name].shirt]);
    }
    for (const a of plates) nameplate(a[0], a[1], a[2], a[3], a[4]);

    if (dark) {
      cx.fillStyle = loaded ? 'rgba(35,29,24,.42)' : 'rgba(35,29,24,.30)';
      cx.fillRect(0, 0, cv.width, cv.height);
      const fs = Math.max(13, z(15));
      cx.font = fs.toFixed(1) + 'px "Typist", Cutive, Georgia, serif';
      cx.fillStyle = loaded ? '#d9907a' : '#a89a86';
      cx.textAlign = 'center';
      cx.fillText(loaded ? 'Everyone is stopped. The kill switch is on.'
                         : 'Reading the floor', cv.width / 2, z(30) + 20);
      cx.textAlign = 'left';
    }
  }

  /* ---------------------------------------------------------- panel */
  const panel = document.getElementById('panel');
  const $ = (id) => document.getElementById(id);

  function openPanel(name) {
    selected = name;
    panel.hidden = false;
    const st = data && data.agents.find((a) => a.name === name);
    $('p-name').textContent = name.charAt(0).toUpperCase() + name.slice(1);
    $('p-name').style.color = CAST[name].shirt;
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
    if (st.state === 'working' && st.working_on) {
      extra = ' for ' + Math.max(1, Math.round(st.working_on.seconds)) + 's';
    }
    $('p-status').innerHTML =
      '<span class="pill ' + bits[1] + '">' + bits[0] + extra + '</span>' +
      '<span class="pill">' + (st.autonomy === 'auto' ? 'just do it' : 'ask me') + '</span>';
    $('p-today').innerHTML =
      '<div><b>' + st.today.runs + '</b><span>runs</span></div>' +
      '<div><b>' + st.today.ok + '</b><span>finished</span></div>' +
      '<div><b>' + st.today.errors + '</b><span>errors</span></div>' +
      '<div><b>' + (st.today.tokens / 1000).toFixed(1) + 'k</b><span>tokens</span></div>';
    $('p-last').textContent = st.today.last || 'Nothing finished today.';
  }

  async function loadChat(name) {
    const r = await fetch('/api/agent/' + name + '/chat');
    if (!r.ok) return;
    const j = await r.json();
    const boxEl = $('p-chat');
    boxEl.innerHTML = j.messages.length ? '' : '<p class="sub">No instructions yet.</p>';
    for (const m of j.messages) {
      const d = document.createElement('div');
      d.className = 'msg ' + m.role;
      d.textContent = m.text;
      boxEl.appendChild(d);
    }
    boxEl.scrollTop = boxEl.scrollHeight;
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
    const r = await fetch('/api/agent/' + selected + '/chat', { method: 'POST', body: body });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      $('p-note').textContent = j.error || 'That did not go through.';
      return;
    }
    $('p-msg').value = '';
    loadChat(selected);
  };

  /* ---------------------------------------------------------- camera */
  function frameFloor() {
    const pad = 26;
    const worldW = (FLOOR_W + FLOOR_H) * (TW / 2);
    const worldH = (FLOOR_W + FLOOR_H) * (TH / 2) + 80;
    cam.z = Math.max(0.35, Math.min(2.4,
      Math.min((cv.width - pad * 2) / worldW, (cv.height - pad * 2) / worldH)));
    cam.x = cv.width / 2 + (FLOOR_H - FLOOR_W) * (TW / 4) * cam.z;
    const drawnH = (FLOOR_W + FLOOR_H) * (TH / 2) * cam.z;
    cam.y = (cv.height - drawnH) / 2 + z(26);
  }

  /* The floor is a wide diamond, so fitting it to the width leaves a band of
     empty carpet above and below. Shrink the element to what is actually
     drawn rather than framing the room inside a larger empty one. */
  function fitHeight() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const drawn = ((FLOOR_W + FLOOR_H) * (TH / 2) * cam.z + z(120)) / dpr;
    const want = Math.max(260, Math.min(600, Math.round(drawn)));
    if (Math.abs(parseFloat(cv.style.height || 0) - want) > 2) {
      cv.style.height = want + 'px';
      return true;
    }
    return false;
  }

  function resize() {
    const r = cv.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.round(r.width * dpr);
    cv.height = Math.round(r.height * dpr);
    frameFloor();
    if (fitHeight()) {                    // one settle pass, never a loop
      const r2 = cv.getBoundingClientRect();
      cv.width = Math.round(r2.width * dpr);
      cv.height = Math.round(r2.height * dpr);
      frameFloor();
    }
  }
  resize();
  new ResizeObserver(() => resize()).observe(cv);

  const toCanvas = (clientX, clientY) => {
    const r = cv.getBoundingClientRect();
    return { x: (clientX - r.left) * (cv.width / r.width),
             y: (clientY - r.top) * (cv.height / r.height) };
  };

  let drag = null, moved = 0, pinch = null;
  const pointers = new Map();

  function zoomAt(px, py, factor) {
    const before = cam.z;
    cam.z = Math.min(3.5, Math.max(0.3, cam.z * factor));
    cam.x = px - (px - cam.x) * (cam.z / before);
    cam.y = py - (py - cam.y) * (cam.z / before);
  }
  function spread() {
    const vals = [...pointers.values()];
    const a = vals[0], b = vals[1];
    return { d: Math.hypot(a.x - b.x, a.y - b.y),
             cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 };
  }

  cv.addEventListener('pointerdown', (e) => {
    cv.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, toCanvas(e.clientX, e.clientY));
    if (pointers.size === 1) { drag = toCanvas(e.clientX, e.clientY); moved = 0; }
    if (pointers.size === 2) { drag = null; pinch = spread(); }
  });
  cv.addEventListener('pointermove', (e) => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, toCanvas(e.clientX, e.clientY));
    if (pointers.size === 2 && pinch) {
      const now = spread();
      if (now.d > 0 && pinch.d > 0) zoomAt(now.cx, now.cy, now.d / pinch.d);
      cam.x += now.cx - pinch.cx; cam.y += now.cy - pinch.cy;
      pinch = now; moved = 99;
      return;
    }
    if (!drag) return;
    const p = toCanvas(e.clientX, e.clientY);
    cam.x += p.x - drag.x; cam.y += p.y - drag.y;
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

  cv.addEventListener('click', (e) => {
    if (moved > 8) return;                 // that was a drag, not a tap
    const r = cv.getBoundingClientRect();
    const mx = (e.clientX - r.left) * (cv.width / r.width);
    const my = (e.clientY - r.top) * (cv.height / r.height);
    // A thumb is about 40 CSS pixels. The figures are smaller than that when
    // zoomed out, so the target is sized in screen terms, not world terms.
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
        if (!first) spawn(ev);             // never replay history on first load
      }
      first = false;
      if (selected) {
        renderStatus(data.agents.find((a) => a.name === selected));
        loadChat(selected);
      }
    } catch (err) { /* keep drawing the last known state */ }
  }

  let last = performance.now();
  function frame(now) {
    const dt = Math.min(60, now - last); last = now;
    stepWalkers(dt);
    draw(now);
    requestAnimationFrame(frame);
  }

  poll();
  setInterval(poll, 5000);
  requestAnimationFrame(frame);
})();
