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

const TILE = 16;            // square units a tile occupies
const PW = 8, PH = 16;      // Mode 0 pixels in one
const SCREEN_TILES_X = 20;  // the play area, CLAUDE.md 8.3
const SCREEN_TILES_Y = 11;
const HUD_TILE_ROW = SCREEN_TILES_Y;    // the 12th tile row is the HUD's
const HUD_CELLS = 20;                   // ... and only its left 20 characters

const $ = (id) => document.getElementById(id);
const state = {
  project: null, tileset: null, atlas: null,
  tile: 0, tool: 'brush', zoom: 2, ops: [], drag: null, hover: null,
};

// ---------------------------------------------------------------- transport

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
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

  if ($('show-entities').checked)
    for (const e of p.entities) {
      // Y ANCHORS THE BASE OF THE HITBOX, which is what a designer drops on
      // a floor (CLAUDE.md 8.6), so the marker hangs above the line.
      const x = e.x / PW * TILE, base = e.y / PH * TILE;
      ctx.strokeStyle = '#4cc2ff';
      ctx.lineWidth = 1 / state.zoom;
      ctx.strokeRect(x + .5, base - TILE + .5, TILE - 1, TILE - 1);
      ctx.fillStyle = '#4cc2ff';
      ctx.font = `${TILE * .7}px monospace`;
      ctx.fillText(e.kind[0], x + 3, base - 4);
    }

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
  buildPalette();
  draw();
  $('status').textContent =
    `${project.name} — ${project.width}x${project.height} tiles, `
    + `${state.tileset.tiles.length} in the sheet, v${project.version}`;
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
$('validate').onclick = () => validate().catch((e) => say(String(e.message)));
$('export').onclick = () => exportLevel().catch((e) => say(String(e.message)));

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
map.onpointerdown = (e) => {
  if (!state.project) return;
  map.setPointerCapture(e.pointerId);
  const cell = cellAt(e);
  state.drag = { tool: state.tool, from: cell };
  if (state.tool !== 'rect') apply(cell.x, cell.y, state.tool);
  draw();
};
map.onpointermove = (e) => {
  if (!state.project) return;
  const cell = cellAt(e);
  state.hover = cell;
  const inside = cell.x >= 0 && cell.y >= 0
    && cell.x < state.project.width && cell.y < state.project.height;
  $('status').textContent = inside
    ? `(${cell.x},${cell.y})  ${state.tileset.tiles[
        state.project.map[cell.y * state.project.width + cell.x]].name}`
      + `   v${state.project.version}${state.ops.length ? ` +${state.ops.length}` : ''}`
    : '';
  if (state.drag && state.drag.tool === 'brush') apply(cell.x, cell.y, 'brush');
  draw();
};
map.onpointerup = (e) => {
  if (state.drag?.tool === 'rect') {
    const a = state.drag.from, b = cellAt(e);
    for (let y = Math.min(a.y, b.y); y <= Math.max(a.y, b.y); y++)
      for (let x = Math.min(a.x, b.x); x <= Math.max(a.x, b.x); x++) setTile(x, y, state.tile);
  }
  state.drag = null;
  draw();
};
map.onpointerleave = () => { state.hover = null; draw(); };

addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  const keys = { b: 'brush', r: 'rect', f: 'fill', i: 'pick', o: 'overlay', x: 'overlay-clear' };
  if (keys[e.key]) $(`tools`).querySelector(`[data-tool="${keys[e.key]}"]`).click();
  if (e.key === 's' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); save(); }
});

refreshProjects().then((list) => list.length && open(list[0].id))
  .catch((e) => say(String(e.message)));
