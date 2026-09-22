// The painter.
//
// ONE MODE 0 PIXEL IS TWICE AS WIDE AS IT IS TALL, so a tile that is 8
// pixels across and 16 down is SQUARE on the glass - 16 by 16 of whatever
// unit we draw in (CLAUDE.md 7.6 says the same thing to Blender: render at
// pixel aspect 2:1 or the art is framed for a shape the hardware never
// shows). Every number below is in those square units.
//
// AND THE PENS COME OFF THE SERVER ALREADY DECODED. The Mode 0 bit
// interleaving is written down in exactly two places in this project,
// tools/cpclib.py and Mode0Layout.cs, and a canvas that unpacked the bytes
// itself would be a third one in a language with no suite pointed at it.
//
// AND SO DO THE ENUMS. Every list a designer picks from - the entity kinds,
// the four flag bits, the pickups, the region kinds, and what p0 and p1 are
// called for each kind - comes from /api/vocabulary, which builds them out
// of the C# enums themselves. A canvas that spelled out EntityKind would be
// a second copy of the engine's own numbering, which is the same class of
// bug as two copies of a bit table (CLAUDE.md 6.3).
//
// A RECORD'S UNITS ARE NOT THE MAP'S. An entity is placed in world PIXELS
// with Y at the BASE of its hitbox, because that is what a designer drops on
// a floor (CLAUDE.md 8.6), so its marker fills the cell ABOVE the line it
// stands on. A region is in TILES, which is what its byte-wide width and
// height are for.

const TILE = 16;            // square units a tile occupies
const PW = 8, PH = 16;      // Mode 0 pixels in one
const SCREEN_TILES_X = 20;  // the play area, CLAUDE.md 8.3
const SCREEN_TILES_Y = 11;
const HUD_TILE_ROW = SCREEN_TILES_Y;    // the 12th tile row is the HUD's
const HUD_CELLS = 20;                   // ... and only its left 20 characters

const $ = (id) => document.getElementById(id);
const state = {
  project: null, tileset: null, atlas: null, vocab: null,
  tile: 0, tool: 'brush', zoom: 2, ops: [], drag: null, hover: null,
  selection: null,            // { kind: 'entity' | 'region', index }
  entityKind: 'Pickup', regionKind: 'Trigger',
};

// ---------------------------------------------------------------- transport

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    // THE API ANSWERS 401 AND DOES NOT REDIRECT (EditorAuth), so a signed-out
    // session arrives here as a status and not as a login page parsed as JSON.
    if (res.status === 401) {
      location.href = '/accounts/login?returnUrl=' + encodeURIComponent(location.pathname);
      throw new Error('signed out');
    }
    if (res.status === 403) throw new Error('this account is not approved yet');
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* not a problem doc */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

// ---------------------------------------------------------------- the atlas

/** One strip of every tile, drawn once: 16 x 16 square units each. */
function buildAtlas(tileset) {
  const pens = b64(tileset.pens);
  const count = tileset.tiles.length;
  const perTile = (PW / 2) * PH;
  const atlas = document.createElement('canvas');
  atlas.width = count * TILE;
  atlas.height = TILE;
  const ctx = atlas.getContext('2d');
  const image = ctx.createImageData(count * TILE, TILE);

  for (let t = 0; t < count; t++) {
    for (let y = 0; y < PH; y++) {
      for (let x = 0; x < PW; x += 2) {
        const byte = pens[t * perTile + y * (PW / 2) + x / 2];
        for (const [dx, pen] of [[0, byte >> 4], [1, byte & 15]]) {
          const [r, g, b] = tileset.palette[pen];
          // a Mode 0 pixel is two units wide
          for (let u = 0; u < 2; u++) {
            const at = ((y * image.width) + t * TILE + (x + dx) * 2 + u) * 4;
            image.data[at] = r; image.data[at + 1] = g;
            image.data[at + 2] = b; image.data[at + 3] = 255;
          }
        }
      }
    }
  }
  ctx.putImageData(image, 0, 0);
  return atlas;
}

// ---------------------------------------------------------------- drawing

function draw() {
  const p = state.project, ts = state.tileset;
  if (!p || !ts) return;
  const canvas = $('map');
  const z = state.zoom;
  canvas.width = p.width * TILE * z;
  canvas.height = p.height * TILE * z;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.setTransform(z, 0, 0, z, 0, 0);
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, p.width * TILE, p.height * TILE);

  for (let y = 0; y < p.height; y++)
    for (let x = 0; x < p.width; x++) {
      const tile = p.map[y * p.width + x];
      ctx.drawImage(state.atlas, tile * TILE, 0, TILE, TILE,
                    x * TILE, y * TILE, TILE, TILE);
    }

  // THE OVERLAY LAYER IS THE EDITOR'S AND THE ENGINE NEVER SEES IT: the
  // pair is composited into a new tile at export and the map cell becomes
  // a finished tile (CLAUDE.md 7.3). So it is drawn on top here, with a
  // corner mark saying that this cell is two tiles and not one.
  if ($('show-overlays').checked)
    for (const o of p.overlays) {
      ctx.globalAlpha = 0.85;
      ctx.drawImage(state.atlas, o.tile * TILE, 0, TILE, TILE,
                    o.x * TILE, o.y * TILE, TILE, TILE);
      ctx.globalAlpha = 1;
      ctx.fillStyle = '#f0a000';
      ctx.fillRect(o.x * TILE, o.y * TILE, 3, 3);
    }

  if ($('show-solid').checked) {
    ctx.fillStyle = 'rgba(255,60,60,.28)';
    for (let y = 0; y < p.height; y++)
      for (let x = 0; x < p.width; x++)
        if (ts.tiles[p.map[y * p.width + x]].flags)
          ctx.fillRect(x * TILE, y * TILE, TILE, TILE);
  }

  if ($('show-grid').checked) {
    ctx.strokeStyle = 'rgba(255,255,255,.08)';
    ctx.lineWidth = 1 / state.zoom;
    ctx.beginPath();
    for (let x = 0; x <= p.width; x++) {
      ctx.moveTo(x * TILE, 0); ctx.lineTo(x * TILE, p.height * TILE);
    }
    for (let y = 0; y <= p.height; y++) {
      ctx.moveTo(0, y * TILE); ctx.lineTo(p.width * TILE, y * TILE);
    }
    ctx.stroke();
  }

  if ($('show-regions').checked)
    p.regions.forEach((r, i) => {
      const on = state.selection?.kind === 'region' && state.selection.index === i;
      ctx.fillStyle = on ? 'rgba(124,255,160,.22)' : 'rgba(124,255,160,.10)';
      ctx.fillRect(r.x * TILE, r.y * TILE, r.width * TILE, r.height * TILE);
      ctx.strokeStyle = on ? '#fff' : 'rgba(124,255,160,.8)';
      ctx.lineWidth = (on ? 2 : 1) / state.zoom;
      ctx.strokeRect(r.x * TILE + .5, r.y * TILE + .5,
                     r.width * TILE - 1, r.height * TILE - 1);
      ctx.fillStyle = '#7cffa0';
      ctx.font = `${TILE * .6}px monospace`;
      ctx.fillText(r.kind, r.x * TILE + 3, r.y * TILE + TILE * .7);
    });

  if ($('show-entities').checked)
    p.entities.forEach((e, i) => {
      // Y ANCHORS THE BASE OF THE HITBOX, which is what a designer drops on
      // a floor (CLAUDE.md 8.6), so the marker hangs above the line.
      const x = e.x / PW * TILE, base = e.y / PH * TILE;
      const on = state.selection?.kind === 'entity' && state.selection.index === i;
      ctx.strokeStyle = on ? '#fff' : '#4cc2ff';
      ctx.lineWidth = (on ? 2 : 1) / state.zoom;
      ctx.strokeRect(x + .5, base - TILE + .5, TILE - 1, TILE - 1);
      // ... and the line it stands ON, which is the one a floor has to be at
      ctx.strokeStyle = on ? 'rgba(255,255,255,.7)' : 'rgba(76,194,255,.5)';
      ctx.beginPath();
      ctx.moveTo(x, base + .5); ctx.lineTo(x + TILE, base + .5);
      ctx.stroke();
      ctx.fillStyle = on ? '#fff' : '#4cc2ff';
      ctx.font = `${TILE * .7}px monospace`;
      ctx.fillText(e.kind[0], x + 3, base - 4);
    });

  // THE SCREEN IS 20x11 TILES OF PLAY AND ONE TILE ROW OF HUD, not the
  // 24 bottom lines docs/editor.md 2.1 asks for: R6 = 24 and 192 lines,
  // because the 64 words that leaves off-screen are what makes vertical
  // scrolling tear-free (CLAUDE.md 8.2, 8.3). And what actually ships is
  // smaller again - twenty CHARACTERS of the bottom row, which is the ten
  // left-hand tiles' lower half (7.8).
  if ($('show-screen').checked) {
    const x0 = 0, y0 = 0;
    ctx.strokeStyle = 'rgba(240,160,0,.9)';
    ctx.lineWidth = 2 / state.zoom;
    ctx.strokeRect(x0, y0, SCREEN_TILES_X * TILE, (SCREEN_TILES_Y + 1) * TILE);
    ctx.strokeStyle = 'rgba(240,160,0,.45)';
    ctx.lineWidth = 1 / state.zoom;
    ctx.strokeRect(x0, y0 + HUD_TILE_ROW * TILE, SCREEN_TILES_X * TILE, TILE);
    ctx.fillStyle = 'rgba(240,160,0,.22)';
    ctx.fillRect(x0, y0 + HUD_TILE_ROW * TILE + TILE / 2, HUD_CELLS / 2 * TILE, TILE / 2);
  }

  // A RECTANGLE IS EASIER TO GET RIGHT WHEN IT IS VISIBLE while it is being
  // dragged - both for the tile rect and for a new region.
  const drag = state.drag;
  if (drag && !drag.moving && (drag.tool === 'rect' || drag.tool === 'region')) {
    const x0 = Math.min(drag.from.x, drag.to.x), y0 = Math.min(drag.from.y, drag.to.y);
    const w = Math.abs(drag.to.x - drag.from.x) + 1, h = Math.abs(drag.to.y - drag.from.y) + 1;
    ctx.strokeStyle = drag.tool === 'region' ? '#7cffa0' : '#fff';
    ctx.lineWidth = 2 / state.zoom;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(x0 * TILE + .5, y0 * TILE + .5, w * TILE - 1, h * TILE - 1);
    ctx.setLineDash([]);
  }

  if (state.hover) {
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1 / state.zoom;
    ctx.strokeRect(state.hover.x * TILE + .5, state.hover.y * TILE + .5, TILE - 1, TILE - 1);
  }
}

// ---------------------------------------------------------------- editing

function push(op) { state.ops.push(op); }

function setTile(x, y, tile) {
  const p = state.project;
  if (x < 0 || y < 0 || x >= p.width || y >= p.height) return;
  if (p.map[y * p.width + x] === tile) return;
  p.map[y * p.width + x] = tile;
  push({ op: 'tile', x, y, tile });
}

function fill(x, y, tile) {
  const p = state.project, from = p.map[y * p.width + x];
  if (from === tile) return;
  const queue = [[x, y]];
  while (queue.length) {
    const [cx, cy] = queue.pop();
    if (cx < 0 || cy < 0 || cx >= p.width || cy >= p.height) continue;
    if (p.map[cy * p.width + cx] !== from) continue;
    setTile(cx, cy, tile);
    queue.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]);
  }
}

function apply(x, y, tool) {
  const p = state.project;
  // A CAPTURED POINTER KEEPS REPORTING WHEN IT LEAVES THE CANVAS, so a
  // drag off the edge would queue an op the server has to refuse - and a
  // refused batch is a reload for the designer.
  if (x < 0 || y < 0 || x >= p.width || y >= p.height) return;
  switch (tool) {
    case 'brush': setTile(x, y, state.tile); break;
    case 'fill': fill(x, y, state.tile); break;
    case 'pick': selectTile(p.map[y * p.width + x]); break;
    case 'overlay':
      p.overlays.push({ x, y, tile: state.tile });
      push({ op: 'overlay', x, y, tile: state.tile });
      break;
    case 'overlay-clear':
      p.overlays = p.overlays.filter((o) => o.x !== x || o.y !== y);
      push({ op: 'overlay-clear', x, y });
      break;
  }
}

// ---------------------------------------------------------------- records

const records = (kind) =>
  kind === 'entity' ? state.project.entities : state.project.regions;

/** The cell an entity's marker fills — its base line is that cell's bottom. */
const entityCell = (e) => ({ x: Math.floor(e.x / PW), y: Math.floor(e.y / PH) - 1 });

function entityAt(cell) {
  const list = state.project.entities;
  for (let i = list.length - 1; i >= 0; i--) {
    const c = entityCell(list[i]);
    if (c.x === cell.x && c.y === cell.y) return i;
  }
  return -1;
}

function regionAt(cell) {
  const list = state.project.regions;
  for (let i = list.length - 1; i >= 0; i--) {
    const r = list[i];
    if (cell.x >= r.x && cell.x < r.x + r.width
        && cell.y >= r.y && cell.y < r.y + r.height) return i;
  }
  return -1;
}

function addRecord(kind, record) {
  const list = records(kind);
  list.push(record);
  push({ op: `${kind}-add`, [kind]: record });
  state.selection = { kind, index: list.length - 1 };
}

/**
 * Replace a record — COALESCED, so a drag across forty cells is one op and
 * not forty. Only the last op is folded into, which is what keeps the order
 * the server applies them in the same as the order they were made.
 */
function setRecord(kind, index, record) {
  records(kind)[index] = record;
  const op = `${kind}-set`;
  const last = state.ops[state.ops.length - 1];
  if (last && last.op === op && last.index === index) last[kind] = record;
  else push({ op, index, [kind]: record });
}

function removeSelected() {
  const sel = state.selection;
  if (!sel) return;
  records(sel.kind).splice(sel.index, 1);
  push({ op: `${sel.kind}-remove`, index: sel.index });
  state.selection = null;
}

function addEntityAt(cell) {
  const p = state.project, v = state.vocab;
  if (p.entities.length >= v.limits.maxEntities)
    return say(`the table holds ENT_MAX = ${v.limits.maxEntities} records, and the `
      + 'engine clears exactly that many');
  addRecord('entity', {
    kind: state.entityKind,
    x: cell.x * PW, y: (cell.y + 1) * PH,
    flags: v.defaultFlags[state.entityKind], p0: 0, p1: 0,
  });
}

function moveEntity(index, cell) {
  const p = state.project, e = p.entities[index];
  const x = clamp(cell.x, 0, p.width - 1) * PW;
  const y = (clamp(cell.y, 0, p.height - 1) + 1) * PH;
  if (e.x === x && e.y === y) return;
  setRecord('entity', index, { ...e, x, y });
}

function addRegionAt(a, b) {
  const p = state.project;
  const x0 = clamp(Math.min(a.x, b.x), 0, p.width - 1);
  const y0 = clamp(Math.min(a.y, b.y), 0, p.height - 1);
  const x1 = clamp(Math.max(a.x, b.x), 0, p.width - 1);
  const y1 = clamp(Math.max(a.y, b.y), 0, p.height - 1);
  addRecord('region', {
    kind: state.regionKind,
    x: x0, y: y0, width: x1 - x0 + 1, height: y1 - y0 + 1,
  });
}

function moveRegion(index, origin, cell) {
  const p = state.project, r = p.regions[index];
  const x = clamp(origin.x + cell.x - state.drag.from.x, 0, p.width - origin.width);
  const y = clamp(origin.y + cell.y - state.drag.from.y, 0, p.height - origin.height);
  if (r.x === x && r.y === y) return;
  setRecord('region', index, { ...origin, x, y });
}

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

function cellAt(event) {
  const rect = $('map').getBoundingClientRect();
  return {
    x: Math.floor((event.clientX - rect.left) / (TILE * state.zoom)),
    y: Math.floor((event.clientY - rect.top) / (TILE * state.zoom)),
  };
}

// ---------------------------------------------------------------- panels

function selectTile(index) {
  state.tile = index;
  for (const c of document.querySelectorAll('#palette canvas'))
    c.classList.toggle('on', Number(c.dataset.index) === index);
  const tile = state.tileset.tiles[index];
  const bits = ['Solid', 'Platform', 'Hazard', 'Ladder', 'Water', 'Quicksand', 'Deadly'];
  $('tile-detail').innerHTML =
    `<strong>${index} ${tile.name}</strong>${tile.overlay ? ' · overlay' : ''}`
    + bits.map((name, bit) => `<label><input type="checkbox" data-bit="${1 << bit}"`
        + `${tile.flags & (1 << bit) ? ' checked' : ''}> ${name}</label>`).join('');
  for (const box of $('tile-detail').querySelectorAll('input')) {
    box.onchange = () => {
      const bit = Number(box.dataset.bit);
      tile.flags = box.checked ? tile.flags | bit : tile.flags & ~bit;
      push({ op: 'flags', name: tile.name, flags: tile.flags });
      draw();
    };
  }
}

function buildPalette() {
  const holder = $('palette');
  holder.textContent = '';
  state.tileset.tiles.forEach((tile, index) => {
    const c = document.createElement('canvas');
    c.width = TILE; c.height = TILE;
    c.dataset.index = index;
    c.title = `${index} ${tile.name}${tile.overlay ? ' (overlay)' : ''}`;
    c.classList.toggle('overlay', tile.overlay);
    c.getContext('2d').drawImage(state.atlas, index * TILE, 0, TILE, TILE, 0, 0, TILE, TILE);
    c.onclick = () => selectTile(index);
    holder.append(c);
  });
  selectTile(0);
}

// ---------------------------------------------------------------- inspector
//
// EVERY LIST IN HERE COMES OFF /api/vocabulary. The kinds, the four flag
// bits, the pickups and the labels for p0 and p1 are the server's own enums
// and its own table of what those two bytes mean per kind (CLAUDE.md 8.6),
// so this file names none of them.

const optionsOf = (list, chosen) =>
  list.map((n) => `<option${n === chosen ? ' selected' : ''}>${n}</option>`).join('');

/** ... and where the byte is an INDEX into one of those lists, it says so. */
const indexedOf = (list, chosen) => list.map((n, i) =>
  `<option value="${i}"${i === chosen ? ' selected' : ''}>${i} ${n}</option>`).join('');

const row = (label, html) => `<label>${label}<br>${html}</label>`;

const number = (id, value, max) =>
  `<input id="${id}" type="number" min="0" max="${max}" value="${value}">`;

/** A [Flags] enum travels by NAME, so byte 5 arrives as "Active, Touch". */
const flagNames = (flags) => String(flags ?? 'None').split(',').map((n) => n.trim());
const flagString = (names) => (names.length ? names.join(', ') : 'None');

// THE LIST IS NAMED BY THE SERVER, not chosen here: spec.options is a key
// in v.lists, so a byte that becomes an enum tomorrow needs no change in
// this file (see VocabularyView).
const paramField = (id, value, spec, v) => spec.options
  ? `<select id="${id}">${indexedOf(v.lists[spec.options], value)}</select>`
  : number(id, value, 255);

function placingHtml(v) {
  const pick = (id, list, chosen) =>
    `<select id="${id}">${optionsOf(list, chosen)}</select>`;
  return '<strong>placing</strong>'
    + row('entity', pick('f-new-entity', v.lists.EntityKind, state.entityKind))
    + row('region', pick('f-new-region', v.lists.RegionKind, state.regionKind));
}

function entityHtml(v, e, index) {
  const params = v.params[e.kind] ?? [{ label: 'p0' }, { label: 'p1' }];
  return `<div class="record"><strong>entity ${index}</strong>`
    + row('kind', `<select id="f-kind">${optionsOf(v.lists.EntityKind, e.kind)}</select>`)
    + row('tile column', number('f-x', e.x / PW, state.project.width - 1))
    // Y IS THE BASE OF THE HITBOX: the row here is the one whose TOP surface
    // the thing stands on, which is what make_city_map.py's entity() takes.
    + row('stands on the top of row', number('f-y', e.y / PH, state.project.height))
    + row(params[0].label, paramField('f-p0', e.p0, params[0], v))
    + row(params[1].label, paramField('f-p1', e.p1, params[1], v))
    + `<div class="bits">${v.lists.EntityFlags.map((n) =>
        `<label><input type="checkbox" data-flag="${n}"`
        + `${flagNames(e.flags).includes(n) ? ' checked' : ''}> ${n}</label>`).join('')}</div>`
    + '<button id="f-delete">delete</button></div>';
}

function regionHtml(v, r, index) {
  return `<div class="record"><strong>region ${index}</strong>`
    + row('kind', `<select id="f-kind">${optionsOf(v.lists.RegionKind, r.kind)}</select>`)
    + row('tile column', number('f-x', r.x, state.project.width - 1))
    + row('tile row', number('f-y', r.y, state.project.height - 1))
    + row('tiles across', number('f-w', r.width, state.project.width))
    + row('tiles down', number('f-h', r.height, state.project.height))
    + '<button id="f-delete">delete</button></div>';
}

function inspector() {
  const box = $('inspector'), v = state.vocab, p = state.project;
  if (!v || !p) return;
  const sel = state.selection;
  box.innerHTML = placingHtml(v) + (!sel ? ''
    : sel.kind === 'entity' ? entityHtml(v, p.entities[sel.index], sel.index)
    : regionHtml(v, p.regions[sel.index], sel.index));

  $('f-new-entity').onchange = (e) => { state.entityKind = e.target.value; };
  $('f-new-region').onchange = (e) => { state.regionKind = e.target.value; };
  if (!sel) return;

  const read = () => sel.kind === 'entity'
    ? {
        kind: $('f-kind').value,
        x: Number($('f-x').value) * PW,
        y: Number($('f-y').value) * PH,
        flags: flagString(v.lists.EntityFlags.filter(
          (n) => box.querySelector(`[data-flag="${n}"]`).checked)),
        p0: Number($('f-p0').value), p1: Number($('f-p1').value),
      }
    : {
        kind: $('f-kind').value,
        x: Number($('f-x').value), y: Number($('f-y').value),
        width: Number($('f-w').value), height: Number($('f-h').value),
      };

  for (const input of box.querySelectorAll('.record input, .record select'))
    input.onchange = () => { setRecord(sel.kind, sel.index, read()); inspector(); draw(); };
  $('f-delete').onclick = () => { removeSelected(); inspector(); draw(); };
}

function say(text, html = false) {
  const report = $('report');
  if (html) report.innerHTML = text; else report.textContent = text;
}

// ---------------------------------------------------------------- loading

async function refreshProjects(select) {
  const list = await api('GET', '/api/projects');
  $('projects').innerHTML = '<option value="">— open —</option>'
    + list.map((p) => `<option value="${p.id}">${p.name}</option>`).join('');
  if (select) $('projects').value = select;
  return list;
}

async function open(id) {
  const project = await api('GET', `/api/projects/${id}`);
  project.map = b64(project.map);
  state.project = project;
  state.tileset = await api('GET', `/api/projects/${id}/tileset`);
  state.atlas = buildAtlas(state.tileset);
  state.ops = [];
  state.selection = null;
  buildPalette();
  inspector();
  draw();
  $('status').textContent =
    `${project.name} — ${project.width}x${project.height} tiles, `
    + `${state.tileset.tiles.length} in the sheet, ${project.entities.length} entities, `
    + `${project.regions.length} regions, v${project.version}`;
}

async function save() {
  if (!state.project || !state.ops.length) return say('nothing to save');
  const result = await api('PATCH', `/api/projects/${state.project.id}`,
                           { version: state.project.version, ops: state.ops });
  state.project.version = result.version;
  state.ops = [];
  say(`saved ${result.applied} edit(s), now v${result.version}`);
}

async function validate() {
  const findings = await api('GET', `/api/projects/${state.project.id}/validate`);
  say(findings.length
    ? findings.map((f) => `<span class="${f.severity.toLowerCase()}">`
        + `[${f.severity}] ${f.rule}: ${f.message}</span>`).join('\n')
    : 'nothing to report', true);
}

// A FLOOR PLAN, NOT A FIELD OF TILES. A blank project is 2,048 cells of
// tile 0, and the scaffolding every level needs before it is a level -
// floors, a way down from each to the next, and enough records that the
// bake, the patrol and the door have something to do - is the same
// scaffolding every time. What it may use it takes off the FLAGS, so a
// project whose table has no floor in it is refused with the role it is
// missing named rather than handed a level of scenery (LevelGenerator).
async function generate() {
  if (!state.project) return say('open a project first');
  if (state.ops.length && !confirm(
      `${state.ops.length} unsaved edit(s) will be thrown away. Generate anyway?`))
    return;
  if (!confirm('This replaces the map, the overlays and every record. Go on?'))
    return;
  const made = await api('POST', `/api/projects/${state.project.id}/generate`,
                         { version: state.project.version });
  state.ops = [];
  say([`generated, now v${made.version}`,
       `  ${made.floors} floor(s), ${made.ladders} ladder(s), ${made.holes} hole(s)`,
       `  ${made.pickups} pickup(s), ${made.enemies} enem(ies), one door`,
       `  floor ${made.floorTile}, ladder ${made.ladderTile}, `
         + `background ${made.backgroundTile}`].join('\n'));
  await open(state.project.id);
}

async function exportLevel() {
  const result = await api('POST', `/api/projects/${state.project.id}/export`);
  if (!result.files.length) return validate();
  const lines = result.files.map((f) => `${f.name.padEnd(28)} ${f.length} bytes`);
  if (result.directory) lines.push('', `written to ${result.directory}`);
  lines.push('', `${result.pairs.filter((p) => p.baked).length} overlay pair(s) baked, `
    + `${result.pairs.filter((p) => !p.baked).length} dropped`);
  for (const pair of result.pairs)
    lines.push(`  ${String(pair.index).padStart(3)}  ${pair.name}`
      + (pair.baked ? '' : '   (dropped — the composite came out the overlay)'));
  say(lines.join('\n'));
  for (const file of result.files) {
    const a = document.createElement('a');
    a.href = 'data:application/octet-stream;base64,' + file.bytes;
    a.download = file.name;
    a.click();
  }
}

// ---------------------------------------------------------------- wiring

$('projects').onchange = (e) => e.target.value && open(e.target.value);
$('zoom').oninput = (e) => { state.zoom = Number(e.target.value); draw(); };
$('save').onclick = () => save().catch((e) => say(String(e.message)));
$('generate').onclick = () => generate().catch((e) => say(String(e.message)));
$('validate').onclick = () => validate().catch((e) => say(String(e.message)));
$('export').onclick = () => exportLevel().catch((e) => say(String(e.message)));

// THE ART PACKAGE HAS SIX LEVELS AND NINE TILE SHEETS (CLAUDE.md 7.3), and
// only one of them has a map. A new project can be started on any of them;
// its tile flags start EMPTY, because nothing in the package says what a
// tile does - that is data the editor owns.
async function loadAssets() {
  const levels = await api('GET', '/api/assets');
  $('new-level').innerHTML = levels
    .map((l) => `<option value="${l.level}">${l.level}</option>`).join('');
  const sheets = () => {
    const level = levels.find((l) => l.level === $('new-level').value);
    $('new-sheet').innerHTML = level.sheets
      .map((n) => `<option value="${n}">${n}</option>`).join('');
  };
  $('new-level').onchange = sheets;
  sheets();
  // AND THE SHAPES COME OFF THE VOCABULARY, not out of this file. The
  // engine took one shape at compile time and takes three at run time,
  // patched out of the level's own header (CLAUDE.md 8.3); a canvas that
  // spelled them out would be a second copy of EngineLimits.
  $('new-shape').innerHTML = state.vocab.limits.mapShapes
    .map((s) => `<option value="${s.width}">${s.width}x${s.height}</option>`)
    .join('');
}

$('new-make').onclick = async () => {
  const id = $('new-id').value.trim();
  if (!id) return say('a project needs an id: letters, digits, - and _');
  try {
    await api('POST', '/api/projects', {
      id, name: id, assetLevel: $('new-level').value, sheet: $('new-sheet').value,
      width: Number($('new-shape').value),
    });
  } catch (e) { return say(String(e.message)); }
  $('new-project').open = false;
  await refreshProjects(id);
  await open(id);
};

$('open-shipped').onclick = async () => {
  try {
    await api('POST', '/api/projects',
              { id: 'city', name: 'Level 1 — the City', seed: 'shipped' });
  } catch (e) {
    if (!String(e.message).includes('already')) return say(String(e.message));
  }
  await refreshProjects('city');
  await open('city');
};

for (const button of $('tools').querySelectorAll('button'))
  button.onclick = () => {
    state.tool = button.dataset.tool;
    for (const b of $('tools').querySelectorAll('button')) b.classList.toggle('on', b === button);
  };

for (const box of document.querySelectorAll('.layers input')) box.onchange = draw;

const map = $('map');
const onMap = (cell) => cell.x >= 0 && cell.y >= 0
  && cell.x < state.project.width && cell.y < state.project.height;

map.onpointerdown = (e) => {
  if (!state.project) return;
  const cell = cellAt(e);
  if (!onMap(cell)) return;
  map.setPointerCapture(e.pointerId);
  state.drag = { tool: state.tool, from: cell, to: cell };

  // THE TWO RECORD TOOLS PICK BEFORE THEY PLACE. A click on something that
  // is already there selects it and starts a move; a click on empty ground
  // makes a new one. A region drag from empty ground draws its rectangle.
  if (state.tool === 'entity') {
    const hit = entityAt(cell);
    if (hit >= 0) state.selection = { kind: 'entity', index: hit };
    else addEntityAt(cell);
    state.drag.moving = state.selection;
  } else if (state.tool === 'region') {
    const hit = regionAt(cell);
    if (hit >= 0) {
      state.selection = { kind: 'region', index: hit };
      state.drag.moving = state.selection;
      state.drag.origin = { ...state.project.regions[hit] };
    }
  } else if (state.tool !== 'rect') {
    apply(cell.x, cell.y, state.tool);
  }
  inspector();
  draw();
};
map.onpointermove = (e) => {
  if (!state.project) return;
  const cell = cellAt(e);
  state.hover = cell;
  $('status').textContent = onMap(cell)
    ? `(${cell.x},${cell.y})  ${state.tileset.tiles[
        state.project.map[cell.y * state.project.width + cell.x]].name}`
      + `   v${state.project.version}${state.ops.length ? ` +${state.ops.length}` : ''}`
    : '';
  const drag = state.drag;
  if (drag) {
    drag.to = cell;
    if (drag.tool === 'brush') apply(cell.x, cell.y, 'brush');
    else if (drag.tool === 'entity' && drag.moving) moveEntity(drag.moving.index, cell);
    else if (drag.tool === 'region' && drag.moving)
      moveRegion(drag.moving.index, drag.origin, cell);
  }
  draw();
};
map.onpointerup = (e) => {
  const drag = state.drag;
  state.drag = null;
  if (!drag) return draw();
  const b = cellAt(e);
  if (drag.tool === 'rect')
    for (let y = Math.min(drag.from.y, b.y); y <= Math.max(drag.from.y, b.y); y++)
      for (let x = Math.min(drag.from.x, b.x); x <= Math.max(drag.from.x, b.x); x++)
        setTile(x, y, state.tile);
  if (drag.tool === 'region' && !drag.moving) addRegionAt(drag.from, b);
  inspector();
  draw();
};
map.onpointerleave = () => { state.hover = null; draw(); };

addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  const keys = { b: 'brush', r: 'rect', f: 'fill', i: 'pick', o: 'overlay', x: 'overlay-clear',
                 e: 'entity', g: 'region' };
  if (keys[e.key]) $('tools').querySelector(`[data-tool="${keys[e.key]}"]`).click();
  if (e.key === 's' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); save(); }
  if (e.key === 'Escape') { state.selection = null; inspector(); draw(); }
  if ((e.key === 'Delete' || e.key === 'Backspace') && state.selection) {
    e.preventDefault();
    removeSelected();
    inspector();
    draw();
  }
});

/** Who is signed in, and a way out. Both roads end in the same cookie. */
async function whoami() {
  const me = await api('GET', '/accounts/me');
  $('whoami').innerHTML = me.signedIn
    ? `${me.email}${me.admin ? ' · <a href="/admin">accounts</a>' : ''}`
      + ' · <a href="/accounts/logout">sign out</a>'
    : '<a href="/accounts/login">sign in</a>';
}

whoami().catch(() => { /* the page itself is behind the same gate */ });

api('GET', '/api/vocabulary')
  .then((v) => { state.vocab = v; return loadAssets(); })
  .then(() => refreshProjects())
  .then((list) => list.length && open(list[0].id))
  .catch((e) => say(String(e.message)));
