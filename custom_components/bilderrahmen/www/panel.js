/*
 * Bilderrahmen – grafischer Layout-Editor für Home Assistant.
 * Reines Web-Component ohne Build-Schritt. Die Vorschau wird vom Server
 * gezeichnet (identisch mit dem Rahmen), der Editor legt Griffe darüber.
 */
const W = 800, H = 480, SNAP = 6, GRID = 4;

const css = `
:host { display:block; height:100%; background:var(--primary-background-color); color:var(--primary-text-color);
  font-family:var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif); --accent:var(--primary-color);
  --panel-bg:var(--card-background-color, #fff); --line:var(--divider-color, #e0e0e0); --muted:var(--secondary-text-color, #666); }
* { box-sizing:border-box; }
.app { display:grid; grid-template-rows:56px 1fr; height:100%; }
header { display:flex; align-items:center; gap:12px; padding:0 16px; background:var(--app-header-background-color, var(--primary-color));
  color:var(--app-header-text-color, #fff); box-shadow:0 1px 0 rgba(0,0,0,.08); }
header h1 { font-size:20px; font-weight:500; margin:0 8px 0 0; white-space:nowrap; }
header .spacer { flex:1; }
header .status { font-size:13px; opacity:.85; white-space:nowrap; }
.iconbtn { background:none; border:0; color:inherit; width:40px; height:40px; border-radius:50%; cursor:pointer;
  display:inline-flex; align-items:center; justify-content:center; }
.iconbtn:hover { background:rgba(255,255,255,.14); }
.iconbtn[disabled] { opacity:.4; cursor:default; background:none; }
.btn { border:0; border-radius:20px; padding:0 18px; height:36px; font-size:14px; font-weight:500; cursor:pointer;
  display:inline-flex; align-items:center; gap:6px; letter-spacing:.2px; }
.btn.primary { background:#fff; color:var(--primary-color); }
.btn.primary.dirty { box-shadow:0 0 0 3px rgba(255,255,255,.35); }
.btn.ghost { background:rgba(255,255,255,.16); color:inherit; }
.btn.danger { background:none; color:var(--error-color, #db4437); border:1px solid currentColor; }
.btn.soft { background:var(--secondary-background-color, #f2f2f2); color:var(--primary-text-color); }
select.frame { background:rgba(255,255,255,.16); color:inherit; border:0; border-radius:18px; height:34px; padding:0 10px; }
select.frame option { color:#000; }
.body { display:grid; grid-template-columns:270px 1fr 320px; min-height:0; }
aside { background:var(--panel-bg); overflow:auto; min-height:0; }
aside.left { border-right:1px solid var(--line); }
aside.right { border-left:1px solid var(--line); }
.sec { padding:16px; border-bottom:1px solid var(--line); }
.sec h2 { font-size:12px; text-transform:uppercase; letter-spacing:1px; color:var(--muted); margin:0 0 12px; font-weight:600; }
.palette { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.tile { border:1px solid var(--line); border-radius:12px; padding:10px 6px; overflow-wrap:anywhere; hyphens:auto; display:flex; flex-direction:column; align-items:center;
  gap:6px; cursor:grab; user-select:none; font-size:12.5px; text-align:center; background:var(--panel-bg); transition:.15s; }
.tile:hover { border-color:var(--accent); color:var(--accent); transform:translateY(-1px); box-shadow:0 4px 12px rgba(0,0,0,.06); }
.tile ha-icon { --mdc-icon-size:24px; }
.templates { display:flex; flex-direction:column; gap:6px; }
.templates button { text-align:left; border:1px solid var(--line); background:var(--panel-bg); color:var(--primary-text-color);
  border-radius:10px; padding:9px 12px; cursor:pointer; font-size:13.5px; display:flex; align-items:center; gap:8px; }
.templates button:hover { border-color:var(--accent); color:var(--accent); }
.templates ha-icon { --mdc-icon-size:18px; }
.layers { display:flex; flex-direction:column; gap:2px; }
.layer { display:flex; align-items:center; gap:8px; padding:6px 8px; border-radius:8px; cursor:pointer; font-size:13.5px; }
.layer:hover { background:var(--secondary-background-color, #f5f5f5); }
.layer.sel { background:rgba(var(--rgb-primary-color, 3,169,244), .14); color:var(--accent); }
.layer ha-icon { --mdc-icon-size:18px; color:var(--muted); }
.layer.sel ha-icon { color:var(--accent); }
.layer .name { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.layer .mini { opacity:0; }
.layer:hover .mini { opacity:1; }
.mini { background:none; border:0; color:var(--muted); cursor:pointer; padding:2px; border-radius:6px; display:inline-flex; }
.mini:hover { color:var(--primary-text-color); background:var(--line); }
.mini ha-icon { --mdc-icon-size:16px; }
main { overflow:auto; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:28px; min-height:0;
  background-image:radial-gradient(var(--line) 1px, transparent 1px); background-size:18px 18px; }
.frame-wrap { position:relative; border-radius:22px; padding:18px; background:#2b2622;
  box-shadow:0 18px 50px rgba(0,0,0,.25), inset 0 0 0 2px #3b342e; }
.frame-wrap::after { content:""; position:absolute; inset:8px; border-radius:16px; border:1px solid rgba(255,255,255,.06); pointer-events:none; }
.mat { background:#fff; padding:6px; border-radius:4px; }
.stage-outer { position:relative; overflow:hidden; }
.stage { position:absolute; left:0; top:0; width:${W}px; height:${H}px; transform-origin:0 0; background:#fff; }
.stage img { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; user-select:none; }
.stage .busy { position:absolute; right:8px; top:8px; width:18px; height:18px; border-radius:50%; border:3px solid rgba(0,0,0,.15);
  border-top-color:var(--accent); animation:spin .8s linear infinite; display:none; }
.stage.loading .busy { display:block; }
@keyframes spin { to { transform:rotate(360deg); } }
.box { position:absolute; outline:1px dashed transparent; cursor:move; }
.stage:hover .box { outline-color:rgba(3,169,244,.35); }
.box:hover { outline:1.5px solid rgba(3,169,244,.7) !important; }
.box.sel { outline:2px solid var(--accent) !important; }
.box .tag { position:absolute; left:-2px; top:-24px; background:var(--accent); color:#fff; font-size:11px; padding:3px 8px;
  border-radius:6px 6px 6px 0; white-space:nowrap; display:none; pointer-events:none; font-weight:500; }
.box.sel .tag { display:block; }
.h { position:absolute; width:12px; height:12px; background:#fff; border:2px solid var(--accent); border-radius:50%; display:none; }
.box.sel .h { display:block; }
.h.nw{left:-7px;top:-7px;cursor:nwse-resize}.h.n{left:calc(50% - 6px);top:-7px;cursor:ns-resize}.h.ne{right:-7px;top:-7px;cursor:nesw-resize}
.h.e{right:-7px;top:calc(50% - 6px);cursor:ew-resize}.h.se{right:-7px;bottom:-7px;cursor:nwse-resize}.h.s{left:calc(50% - 6px);bottom:-7px;cursor:ns-resize}
.h.sw{left:-7px;bottom:-7px;cursor:nesw-resize}.h.w{left:-7px;top:calc(50% - 6px);cursor:ew-resize}
.guide { position:absolute; background:#ff2d75; pointer-events:none; z-index:5; }
.guide.v { width:1px; top:0; bottom:0; } .guide.hz { height:1px; left:0; right:0; }
.drop-hint { position:absolute; inset:0; border:3px dashed var(--accent); display:none; pointer-events:none; }
.stage.dragover .drop-hint { display:block; }
.below { margin-top:16px; display:flex; gap:10px; align-items:center; color:var(--muted); font-size:13px; flex-wrap:wrap; justify-content:center; }
.kbd { border:1px solid var(--line); border-bottom-width:2px; border-radius:5px; padding:0 5px; font-size:11.5px; background:var(--panel-bg); }
.field { margin-bottom:14px; }
.field label { display:block; font-size:12.5px; color:var(--muted); margin-bottom:5px; font-weight:500; }
input[type=text], input[type=number], select.in { width:100%; height:38px; border:1px solid var(--line); border-radius:10px; padding:0 11px;
  font-size:14px; background:var(--panel-bg); color:var(--primary-text-color); outline:none; transition:border .15s; }
input:focus, select.in:focus { border-color:var(--accent); box-shadow:0 0 0 3px rgba(var(--rgb-primary-color, 3,169,244), .15); }
.grid4 { display:grid; grid-template-columns:repeat(4, 1fr); gap:6px; }
.grid4 .field { margin:0; } .grid4 input { padding:0 6px; text-align:center; }
.checks { display:flex; flex-wrap:wrap; gap:6px; }
.checks button { border:1px solid var(--line); background:var(--panel-bg); color:var(--primary-text-color); border-radius:16px;
  padding:5px 11px; font-size:12.5px; cursor:pointer; }
.checks button.on { background:var(--accent); border-color:var(--accent); color:#fff; }
.seg { display:flex; background:var(--secondary-background-color, #f2f2f2); border-radius:10px; padding:3px; gap:3px; }
.seg button { flex:1; border:0; background:none; border-radius:8px; height:32px; cursor:pointer; color:var(--primary-text-color); font-size:13px; }
.seg button.on { background:var(--panel-bg); box-shadow:0 1px 3px rgba(0,0,0,.15); font-weight:600; }
.swatches { display:flex; gap:8px; flex-wrap:wrap; }
.swatch { width:30px; height:30px; border-radius:50%; cursor:pointer; border:2px solid var(--line); position:relative; }
.swatch.on::after { content:""; position:absolute; inset:-6px; border-radius:50%; border:2px solid var(--accent); }
.toggle { display:flex; align-items:center; justify-content:space-between; cursor:pointer; font-size:14px; }
.toggle input { width:40px; height:22px; appearance:none; background:var(--line); border-radius:11px; position:relative; cursor:pointer; transition:.2s; }
.toggle input::after { content:""; position:absolute; width:18px; height:18px; border-radius:50%; background:#fff; top:2px; left:2px; transition:.2s; box-shadow:0 1px 2px rgba(0,0,0,.3); }
.toggle input:checked { background:var(--accent); } .toggle input:checked::after { left:20px; }
.picker { position:relative; }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:6px; }
.chip { display:inline-flex; align-items:center; gap:4px; background:var(--secondary-background-color, #f0f0f0); border-radius:16px;
  padding:4px 4px 4px 10px; font-size:12.5px; max-width:100%; }
.chip span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.chip button { border:0; background:none; cursor:pointer; color:var(--muted); display:inline-flex; padding:0; }
.chip ha-icon { --mdc-icon-size:16px; }
.dd { position:absolute; left:0; right:0; top:100%; margin-top:4px; background:var(--panel-bg); border:1px solid var(--line); border-radius:10px;
  box-shadow:0 10px 30px rgba(0,0,0,.15); max-height:260px; overflow:auto; z-index:20; display:none; }
.dd.open { display:block; }
.opt { padding:8px 12px; cursor:pointer; font-size:13.5px; display:flex; flex-direction:column; }
.opt small { color:var(--muted); font-size:11.5px; }
.opt:hover, .opt.hi { background:var(--secondary-background-color, #f4f4f4); }
.empty { color:var(--muted); font-size:13.5px; line-height:1.5; }
.empty ha-icon { --mdc-icon-size:40px; display:block; margin-bottom:8px; opacity:.5; }
.typehead { display:flex; align-items:center; gap:10px; margin-bottom:4px; }
.typehead ha-icon { color:var(--accent); }
.typehead b { font-size:16px; }
.actions { display:flex; gap:8px; flex-wrap:wrap; }
.toast { position:fixed; left:50%; bottom:24px; transform:translateX(-50%) translateY(120px); background:#323232; color:#fff; padding:12px 20px;
  border-radius:10px; font-size:14px; transition:.25s; z-index:100; box-shadow:0 6px 20px rgba(0,0,0,.3); }
.toast.show { transform:translateX(-50%) translateY(0); }
@media (max-width: 1100px) { .body { grid-template-columns:200px 1fr 280px; } }
@media (max-width: 860px) { .body { grid-template-columns:1fr; } aside.left { display:none; } aside.right { border:0; } }
`;

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const uid = () => Math.random().toString(16).slice(2, 10);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ACCENTS = { red: "#e00", blue: "#0033dd", green: "#0b0", yellow: "#ffd600", black: "#000", white: "#fff" };

class BilderrahmenPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._layout = null; this._catalog = []; this._sel = null; this._frames = []; this._entry = null;
    this._undo = []; this._redo = []; this._dirty = false; this._scale = 1; this._previewTimer = null;
    this._reqSeq = 0; this._built = false;
  }
  set hass(h) { const first = !this._hass; this._hass = h; if (first) this._init(); }
  get hass() { return this._hass; }
  set narrow(n) { this._narrow = n; }
  set panel(p) { this._panel = p; }

  async _init() {
    this._build();
    try {
      const { frames } = await this._ws({ type: "bilderrahmen/frames" });
      this._frames = frames;
      if (!frames.length) { this._msg("Noch kein Bilderrahmen eingerichtet. Füge ihn unter Einstellungen → Geräte & Dienste hinzu."); return; }
      const saved = localStorage.getItem("bilderrahmen.entry");
      this._entry = (frames.find((f) => f.entry_id === saved) || frames[0]).entry_id;
      await this._load();
    } catch (e) { this._msg("Fehler beim Laden: " + (e.message || e)); }
  }

  _ws(msg) { return this._hass.callWS(msg); }

  async _load() {
    const r = await this._ws({ type: "bilderrahmen/get", entry_id: this._entry });
    this._catalog = r.catalog; this._themeFields = r.theme_fields; this._layout = r.layout; this._templates = r.templates || [];
    this._byType = Object.fromEntries(this._catalog.map((c) => [c.type, c]));
    this._sel = null; this._undo = []; this._redo = []; this._setDirty(false);
    this._status(r.status);
    this._renderAll(); this._preview(0);
  }

  // ------------------------------------------------------------------ Grundgerüst
  _build() {
    const s = this.shadowRoot;
    s.innerHTML = `<style>${css}</style>
    <div class="app">
      <header>
        <button class="iconbtn" id="menu" title="Menü"><ha-icon icon="mdi:menu"></ha-icon></button>
        <h1>Bilderrahmen</h1>
        <select class="frame" id="frameSel" hidden></select>
        <span class="spacer"></span>
        <span class="status" id="status"></span>
        <button class="iconbtn" id="undo" title="Rückgängig (Strg+Z)"><ha-icon icon="mdi:undo"></ha-icon></button>
        <button class="iconbtn" id="redo" title="Wiederholen (Strg+Y)"><ha-icon icon="mdi:redo"></ha-icon></button>
        <button class="btn ghost" id="push" title="Gespeichertes Layout jetzt anzeigen"><ha-icon icon="mdi:refresh"></ha-icon>Rahmen aktualisieren</button>
        <button class="btn primary" id="save"><ha-icon icon="mdi:content-save-outline"></ha-icon>Speichern</button>
      </header>
      <div class="body">
        <aside class="left">
          <div class="sec"><h2>Elemente</h2><div class="palette" id="palette"></div></div>
          <div class="sec"><h2>Vorlagen</h2><div class="templates" id="templates"></div></div>
          <div class="sec"><h2>Ebenen</h2><div class="layers" id="layers"></div></div>
        </aside>
        <main id="main">
          <div class="frame-wrap"><div class="mat"><div class="stage-outer" id="outer">
            <div class="stage loading" id="stage"><img id="img" alt=""><div id="boxes"></div><div class="busy"></div><div class="drop-hint"></div></div>
          </div></div></div>
          <div class="below">
            <span><span class="kbd">Pfeile</span> verschieben</span><span><span class="kbd">Shift</span> in 10er-Schritten</span>
            <span><span class="kbd">Entf</span> löschen</span><span><span class="kbd">Strg D</span> duplizieren</span><span><span class="kbd">Alt</span> ohne Einrasten</span>
          </div>
        </main>
        <aside class="right" id="props"></aside>
      </div>
    </div>
    <div class="toast" id="toast"></div>`;
    const $ = (id) => s.getElementById(id);
    this.$ = $;
    $("menu").onclick = () => this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
    $("save").onclick = () => this._save();
    $("push").onclick = () => this._push();
    $("undo").onclick = () => this._doUndo();
    $("redo").onclick = () => this._doRedo();
    $("frameSel").onchange = async (e) => {
      if (this._dirty && !confirm("Ungespeicherte Änderungen verwerfen?")) { e.target.value = this._entry; return; }
      this._entry = e.target.value; localStorage.setItem("bilderrahmen.entry", this._entry); await this._load();
    };
    const stage = $("stage");
    stage.addEventListener("pointerdown", (e) => { if (e.target === stage || e.target.id === "img" || e.target.id === "boxes") { this._select(null); } });
    stage.addEventListener("dragover", (e) => { e.preventDefault(); stage.classList.add("dragover"); });
    stage.addEventListener("dragleave", () => stage.classList.remove("dragover"));
    stage.addEventListener("drop", (e) => {
      e.preventDefault(); stage.classList.remove("dragover");
      const type = e.dataTransfer.getData("text/bilderrahmen"); if (!type) return;
      const r = stage.getBoundingClientRect();
      this._add(type, (e.clientX - r.left) / this._scale, (e.clientY - r.top) / this._scale);
    });
    this._onKey = (e) => this._key(e);
    window.addEventListener("keydown", this._onKey);
    this._ro = new ResizeObserver(() => this._fit());
    this._ro.observe($("main"));
  }

  disconnectedCallback() { window.removeEventListener("keydown", this._onKey); this._ro?.disconnect(); }
  connectedCallback() { if (this.$) this._fit(); }

  _msg(t) { this.$("props").innerHTML = `<div class="sec empty">${esc(t)}</div>`; }
  _status(t) { this.$("status").textContent = t ? `Rahmen: ${t}` : ""; }
  _toast(t) { const el = this.$("toast"); el.textContent = t; el.classList.add("show"); clearTimeout(this._tt); this._tt = setTimeout(() => el.classList.remove("show"), 2600); }

  _fit() {
    const main = this.$("main"); if (!main) return;
    const avail = Math.max(240, main.clientWidth - 56 - 48);
    const availH = Math.max(160, main.clientHeight - 56 - 48 - 40);
    this._scale = Math.min(1.25, avail / W, availH / H);
    const outer = this.$("outer"), stage = this.$("stage");
    outer.style.width = W * this._scale + "px"; outer.style.height = H * this._scale + "px";
    stage.style.transform = `scale(${this._scale})`;
  }

  // ------------------------------------------------------------------ Zustand
  _snapshot() { this._undo.push(JSON.stringify(this._layout)); if (this._undo.length > 80) this._undo.shift(); this._redo = []; this._updUndo(); }
  _doUndo() { if (!this._undo.length) return; this._redo.push(JSON.stringify(this._layout)); this._layout = JSON.parse(this._undo.pop()); this._afterChange(); }
  _doRedo() { if (!this._redo.length) return; this._undo.push(JSON.stringify(this._layout)); this._layout = JSON.parse(this._redo.pop()); this._afterChange(); }
  _updUndo() { this.$("undo").disabled = !this._undo.length; this.$("redo").disabled = !this._redo.length; }
  _setDirty(d) { this._dirty = d; const b = this.$("save"); b.classList.toggle("dirty", d); b.innerHTML = `<ha-icon icon="mdi:content-save-outline"></ha-icon>${d ? "Speichern & anzeigen" : "Gespeichert"}`; }
  _afterChange(props = true) {
    if (this._sel && !this._w(this._sel)) this._sel = null;
    this._setDirty(true); this._updUndo(); this._renderBoxes(); this._renderLayers(); if (props) this._renderProps(); this._preview();
  }
  _w(id) { return this._layout.widgets.find((w) => w.id === id); }

  // ------------------------------------------------------------------ Vorschau
  _preview(delay = 300) {
    clearTimeout(this._previewTimer);
    this._previewTimer = setTimeout(async () => {
      const seq = ++this._reqSeq; const stage = this.$("stage"); stage.classList.add("loading");
      try {
        const r = await this._ws({ type: "bilderrahmen/preview", entry_id: this._entry, layout: this._layout });
        if (seq === this._reqSeq) this.$("img").src = "data:image/png;base64," + r.image;
      } catch (e) { this._toast("Vorschau fehlgeschlagen: " + (e.message || e)); }
      finally { if (seq === this._reqSeq) stage.classList.remove("loading"); }
    }, delay);
  }

  async _save() {
    try {
      const r = await this._ws({ type: "bilderrahmen/save", entry_id: this._entry, layout: this._layout });
      this._layout = r.layout; this._setDirty(false); this._renderAll(); this._preview(0);
      this._toast("Gespeichert – der Rahmen wird neu gezeichnet (ca. 30–60 s)");
      setTimeout(() => this._refreshStatus(), 4000);
    } catch (e) { this._toast("Speichern fehlgeschlagen: " + (e.message || e)); }
  }
  async _push() {
    this._toast("Rahmen wird aktualisiert …");
    try { const r = await this._ws({ type: "bilderrahmen/push", entry_id: this._entry }); this._status(r.status); this._toast(`Rahmen: ${r.status}`); }
    catch (e) { this._toast("Fehler: " + (e.message || e)); }
  }
  async _refreshStatus() { try { const { frames } = await this._ws({ type: "bilderrahmen/frames" }); const f = frames.find((x) => x.entry_id === this._entry); if (f) this._status(f.status); } catch (_) {} }

  // ------------------------------------------------------------------ Darstellung
  _renderAll() {
    const fs = this.$("frameSel");
    fs.hidden = this._frames.length < 2;
    fs.innerHTML = this._frames.map((f) => `<option value="${f.entry_id}" ${f.entry_id === this._entry ? "selected" : ""}>${esc(f.title)}</option>`).join("");
    this._renderPalette(); this._renderTemplates(); this._renderBoxes(); this._renderLayers(); this._renderProps(); this._updUndo(); this._fit();
  }

  _renderPalette() {
    const p = this.$("palette");
    p.innerHTML = this._catalog.map((c) => `<div class="tile" draggable="true" data-type="${c.type}" title="Klicken oder auf die Fläche ziehen">
      <ha-icon icon="${c.icon}"></ha-icon>${esc(c.label)}</div>`).join("");
    p.querySelectorAll(".tile").forEach((t) => {
      t.onclick = () => this._add(t.dataset.type);
      t.ondragstart = (e) => { e.dataTransfer.setData("text/bilderrahmen", t.dataset.type); e.dataTransfer.effectAllowed = "copy"; };
    });
  }

  _renderTemplates() {
    const T = this.$("templates");
    T.innerHTML = this._templates.map((t) => `<button data-t="${t.id}"><ha-icon icon="${t.id === "station" ? "mdi:weather-partly-cloudy" : "mdi:view-dashboard-outline"}"></ha-icon>${esc(t.label)}</button>`).join("");
    T.querySelectorAll("button").forEach((b) => b.onclick = async () => {
      if (this._layout.widgets.length && !confirm("Aktuelles Layout durch die Vorlage ersetzen? (Rückgängig mit Strg+Z möglich)")) return;
      try {
        const r = await this._ws({ type: "bilderrahmen/template", entry_id: this._entry, name: b.dataset.t });
        this._snapshot(); this._layout = r.layout; this._sel = null; this._afterChange();
        this._toast("Vorlage geladen – mit „Speichern & anzeigen“ übernehmen");
      } catch (e) { this._toast("Vorlage fehlgeschlagen: " + (e.message || e)); }
    });
  }

  _label(w) {
    const c = this._byType[w.type] || {};
    const p = w.props || {};
    let extra = p.title || p.text || "";
    if (!extra && p.entity) extra = this._name(p.entity);
    return { icon: c.icon || "mdi:shape", name: c.label || w.type, extra };
  }

  _renderLayers() {
    const L = this.$("layers");
    const ws = [...this._layout.widgets].reverse();
    if (!ws.length) { L.innerHTML = `<div class="empty">Noch leer – füge oben ein Element hinzu.</div>`; return; }
    L.innerHTML = ws.map((w) => { const l = this._label(w); return `<div class="layer ${w.id === this._sel ? "sel" : ""}" data-id="${w.id}">
      <ha-icon icon="${l.icon}"></ha-icon><span class="name">${esc(l.name)}${l.extra ? ` <span style="opacity:.6">· ${esc(l.extra)}</span>` : ""}</span>
      <button class="mini" data-act="up" title="Nach vorne"><ha-icon icon="mdi:arrow-up"></ha-icon></button>
      <button class="mini" data-act="down" title="Nach hinten"><ha-icon icon="mdi:arrow-down"></ha-icon></button>
      <button class="mini" data-act="del" title="Löschen"><ha-icon icon="mdi:delete-outline"></ha-icon></button></div>`; }).join("");
    L.querySelectorAll(".layer").forEach((el) => {
      el.onclick = (e) => {
        const act = e.target.closest("[data-act]")?.dataset.act; const id = el.dataset.id;
        if (act === "del") { this._delete(id); return; }
        if (act === "up" || act === "down") { this._order(id, act === "up" ? 1 : -1); return; }
        this._select(id);
      };
    });
  }

  _renderBoxes() {
    const B = this.$("boxes");
    B.innerHTML = this._layout.widgets.map((w) => `<div class="box ${w.id === this._sel ? "sel" : ""}" data-id="${w.id}"
      style="left:${w.x}px;top:${w.y}px;width:${w.w}px;height:${w.h}px">
      <div class="tag">${esc(this._label(w).name)} · ${w.w}×${w.h}</div>
      ${["nw", "n", "ne", "e", "se", "s", "sw", "w"].map((h) => `<div class="h ${h}" data-h="${h}"></div>`).join("")}</div>`).join("");
    B.querySelectorAll(".box").forEach((el) => el.addEventListener("pointerdown", (e) => this._startDrag(e, el.dataset.id, e.target.dataset.h)));
  }

  _posBox(w) {
    const el = this.shadowRoot.querySelector(`.box[data-id="${w.id}"]`);
    if (!el) return;
    Object.assign(el.style, { left: w.x + "px", top: w.y + "px", width: w.w + "px", height: w.h + "px" });
    const tag = el.querySelector(".tag"); if (tag) tag.textContent = `${this._label(w).name} · ${w.w}×${w.h}`;
  }

  // ------------------------------------------------------------------ Eigenschaften
  _renderProps() {
    const P = this.$("props");
    const w = this._sel && this._w(this._sel);
    if (!w) { P.innerHTML = this._themeHtml(); this._bindTheme(P); return; }
    const c = this._byType[w.type];
    P.innerHTML = `<div class="sec">
        <div class="typehead"><ha-icon icon="${c.icon}"></ha-icon><b>${esc(c.label)}</b></div>
      </div>
      <div class="sec"><h2>Position & Größe</h2><div class="grid4">
        ${["x", "y", "w", "h"].map((k) => `<div class="field"><label>${{ x: "X", y: "Y", w: "Breite", h: "Höhe" }[k]}</label>
          <input type="number" data-geo="${k}" value="${w[k]}"></div>`).join("")}</div></div>
      <div class="sec"><h2>Inhalt & Stil</h2>${c.fields.map((f) => this._fieldHtml(f, w.props[f.key])).join("")}</div>
      <div class="sec actions">
        <button class="btn soft" id="dup"><ha-icon icon="mdi:content-copy"></ha-icon>Duplizieren</button>
        <button class="btn danger" id="del"><ha-icon icon="mdi:delete-outline"></ha-icon>Löschen</button>
      </div>`;
    P.querySelectorAll("[data-geo]").forEach((inp) => {
      inp.onfocus = () => this._snapshot();
      inp.oninput = () => { const k = inp.dataset.geo; const v = parseInt(inp.value, 10); if (isNaN(v)) return;
        w[k] = k === "w" || k === "h" ? clamp(v, 4, k === "w" ? W : H) : v; this._posBox(w); this._setDirty(true); this._preview(); };
    });
    P.querySelector("#dup").onclick = () => this._duplicate(w.id);
    P.querySelector("#del").onclick = () => this._delete(w.id);
    this._bindFields(P, c.fields, w.props, () => { this._setDirty(true); this._renderLayers(); this._preview(); });
  }

  _themeHtml() {
    const t = this._layout?.theme || {};
    return `<div class="sec"><h2>Design</h2>
      <div class="field"><label>Hintergrund</label><div class="seg" id="mode">
        ${[["light", "Hell"], ["paper", "Papiergrau"], ["dark", "Dunkel"]].map(([v, l]) => `<button data-v="${v}" class="${(t.mode || "light") === v ? "on" : ""}">${l}</button>`).join("")}</div></div>
      <div class="field"><label>Akzentfarbe</label><div class="swatches" id="acc">
        ${Object.entries(ACCENTS).map(([k, c]) => `<div class="swatch ${t.accent === k ? "on" : ""}" data-v="${k}" title="${k}" style="background:${c}"></div>`).join("")}</div></div>
      </div>
      <div class="sec empty"><ha-icon icon="mdi:gesture-tap"></ha-icon>
        Wähle ein Element auf der Fläche, um es zu bearbeiten.<br><br>
        Neue Elemente ziehst du aus der linken Leiste auf die Fläche. Die Vorschau zeigt, wie der Rahmen aussieht: Grau, Orange und Pastell entstehen dort aus feinen Punkten der sechs Displayfarben.</div>`;
  }
  _bindTheme(P) {
    P.querySelectorAll("#mode button").forEach((b) => b.onclick = () => { this._snapshot(); this._layout.theme.mode = b.dataset.v; this._afterChange(); });
    P.querySelectorAll("#acc .swatch").forEach((b) => b.onclick = () => { this._snapshot(); this._layout.theme.accent = b.dataset.v; this._afterChange(); });
  }

  _fieldHtml(f, v) {
    const id = `f_${f.key}`;
    if (f.type === "bool") return `<div class="field"><label class="toggle">${esc(f.label)}<input type="checkbox" id="${id}" ${v ? "checked" : ""}></label></div>`;
    if (f.type === "select") return `<div class="field"><label>${esc(f.label)}</label><select class="in" id="${id}">
      ${f.options.map((o) => `<option value="${o.value}" ${o.value === v ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select></div>`;
    if (f.type === "checks") {
      const cur = Array.isArray(v) ? v : [];
      return `<div class="field"><label>${esc(f.label)}</label><div class="checks" id="${id}">
        ${f.options.map((o) => `<button type="button" data-v="${o.value}" class="${cur.includes(o.value) ? "on" : ""}">${esc(o.label)}</button>`).join("")}</div></div>`;
    }
    if (f.type === "number") return `<div class="field"><label>${esc(f.label)}${f.unit ? ` (${f.unit})` : ""}</label>
      <input type="number" id="${id}" min="${f.min ?? ""}" max="${f.max ?? ""}" value="${v ?? f.default ?? ""}"></div>`;
    if (f.type === "entity") {
      const vals = f.multiple ? (v || []) : (v ? [v] : []);
      return `<div class="field"><label>${esc(f.label)}</label><div class="picker" id="${id}">
        ${f.multiple ? `<div class="chips">${vals.map((e) => `<span class="chip" title="${esc(e)}"><span>${esc(this._name(e))}</span><button data-rm="${esc(e)}"><ha-icon icon="mdi:close"></ha-icon></button></span>`).join("")}</div>` : ""}
        <input type="text" placeholder="${f.multiple ? "Hinzufügen – tippen zum Suchen" : "Tippen zum Suchen"}" value="${f.multiple ? "" : esc(v ? this._name(v) : "")}" data-eid="${esc(f.multiple ? "" : v || "")}">
        <div class="dd"></div></div></div>`;
    }
    return `<div class="field"><label>${esc(f.label)}</label><input type="text" id="${id}" value="${esc(v ?? "")}"></div>`;
  }

  _bindFields(P, fields, props, changed) {
    for (const f of fields) {
      const el = P.querySelector(`#f_${f.key}`); if (!el) continue;
      if (f.type === "bool") el.onchange = () => { this._snapshot(); props[f.key] = el.checked; changed(); };
      else if (f.type === "select") el.onchange = () => { this._snapshot(); props[f.key] = el.value; changed(); };
      else if (f.type === "number") { el.onfocus = () => this._snapshot(); el.oninput = () => { const n = parseFloat(el.value); if (!isNaN(n)) { props[f.key] = n; changed(); } }; }
      else if (f.type === "entity") this._bindPicker(el, f, props, changed);
      else if (f.type === "checks") el.querySelectorAll("button").forEach((b) => b.onclick = () => {
        this._snapshot(); const cur = new Set(props[f.key] || []);
        cur.has(b.dataset.v) ? cur.delete(b.dataset.v) : cur.add(b.dataset.v);
        props[f.key] = f.options.map((o) => o.value).filter((x) => cur.has(x)); b.classList.toggle("on"); changed(); });
      else { el.onfocus = () => this._snapshot(); el.oninput = () => { props[f.key] = el.value; changed(); }; }
    }
  }

  _name(eid) { const s = this._hass?.states?.[eid]; return s?.attributes?.friendly_name || eid; }

  _bindPicker(root, f, props, changed) {
    const inp = root.querySelector("input"); const dd = root.querySelector(".dd");
    let hi = 0, list = [];
    const all = () => Object.keys(this._hass.states).filter((e) => !f.domain || e.startsWith(f.domain + "."))
      .map((e) => ({ e, n: this._name(e) })).sort((a, b) => a.n.localeCompare(b.n, "de"));
    const show = () => {
      const q = inp.value.trim().toLowerCase();
      const taken = f.multiple ? props[f.key] || [] : [];
      list = all().filter((x) => !taken.includes(x.e) && (!q || x.n.toLowerCase().includes(q) || x.e.includes(q))).slice(0, 60);
      hi = 0;
      dd.innerHTML = list.length ? list.map((x, i) => `<div class="opt ${i === 0 ? "hi" : ""}" data-e="${esc(x.e)}">${esc(x.n)}<small>${esc(x.e)}</small></div>`).join("")
        : `<div class="opt"><small>Keine Treffer</small></div>`;
      dd.classList.add("open");
      dd.querySelectorAll(".opt[data-e]").forEach((o) => o.onmousedown = (ev) => { ev.preventDefault(); pick(o.dataset.e); });
    };
    const pick = (e) => {
      this._snapshot();
      if (f.multiple) { props[f.key] = [...(props[f.key] || []), e]; changed(); this._renderProps(); return; }
      props[f.key] = e; inp.value = this._name(e); inp.dataset.eid = e; dd.classList.remove("open"); changed(); inp.blur();
    };
    inp.onfocus = () => { if (!f.multiple) inp.select(); show(); };
    inp.oninput = show;
    inp.onblur = () => setTimeout(() => { dd.classList.remove("open"); if (!f.multiple) inp.value = props[f.key] ? this._name(props[f.key]) : ""; }, 120);
    inp.onkeydown = (e) => {
      const opts = dd.querySelectorAll(".opt[data-e]");
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); hi = clamp(hi + (e.key === "ArrowDown" ? 1 : -1), 0, opts.length - 1);
        opts.forEach((o, i) => o.classList.toggle("hi", i === hi)); opts[hi]?.scrollIntoView({ block: "nearest" }); }
      else if (e.key === "Enter" && list[hi]) { e.preventDefault(); pick(list[hi].e); }
      else if (e.key === "Escape") { inp.blur(); }
      e.stopPropagation();
    };
    root.querySelectorAll("[data-rm]").forEach((b) => b.onclick = () => { this._snapshot(); props[f.key] = (props[f.key] || []).filter((x) => x !== b.dataset.rm); changed(); this._renderProps(); });
    if (!f.multiple && !props[f.key]) inp.placeholder = "Automatisch / tippen zum Suchen";
  }

  // ------------------------------------------------------------------ Aktionen
  _select(id) {
    if (this._sel === id) return;
    this._sel = id;
    this.shadowRoot.querySelectorAll(".box").forEach((b) => b.classList.toggle("sel", b.dataset.id === id));
    this._renderLayers(); this._renderProps();
  }

  _free(w, h) {
    const hit = (x, y) => this._layout.widgets.some((o) => x < o.x + o.w && x + w > o.x && y < o.y + o.h && y + h > o.y);
    for (let y = 16; y + h <= H - 8; y += 16) for (let x = 16; x + w <= W - 8; x += 16) if (!hit(x, y)) return [x, y];
    return [clamp((W - w) / 2, 0, W), clamp((H - h) / 2, 0, H)];
  }

  _add(type, cx, cy) {
    const c = this._byType[type]; if (!c) return;
    this._snapshot();
    const props = {}; c.fields.forEach((f) => { if ("default" in f) props[f.key] = JSON.parse(JSON.stringify(f.default)); });
    const ent = c.fields.find((f) => f.type === "entity" && f.domain && !f.multiple);
    if (ent) { const first = Object.keys(this._hass.states).find((e) => e.startsWith(ent.domain + ".")); if (first) props[ent.key] = first; }
    let x, y; const w = Math.min(c.w, W), h = Math.min(c.h, H);
    if (cx !== undefined) { x = Math.round(clamp(cx - w / 2, 0, W - w) / GRID) * GRID; y = Math.round(clamp(cy - h / 2, 0, H - h) / GRID) * GRID; }
    else [x, y] = this._free(w, h);
    const nw = { id: uid(), type, x, y, w, h, props };
    this._layout.widgets.push(nw); this._sel = nw.id; this._afterChange();
  }

  _delete(id) { this._snapshot(); this._layout.widgets = this._layout.widgets.filter((w) => w.id !== id); if (this._sel === id) this._sel = null; this._afterChange(); }
  _duplicate(id) {
    const w = this._w(id); if (!w) return; this._snapshot();
    const c = JSON.parse(JSON.stringify(w)); c.id = uid(); c.x = clamp(w.x + 16, 0, W - 20); c.y = clamp(w.y + 16, 0, H - 20);
    this._layout.widgets.push(c); this._sel = c.id; this._afterChange();
  }
  _order(id, dir) {
    const a = this._layout.widgets; const i = a.findIndex((w) => w.id === id); const j = i + dir;
    if (i < 0 || j < 0 || j >= a.length) return; this._snapshot(); [a[i], a[j]] = [a[j], a[i]]; this._afterChange(false);
  }

  _key(e) {
    if (!this.isConnected || !this._layout) return;
    const tag = (e.composedPath()[0]?.tagName || "").toLowerCase();
    const typing = tag === "input" || tag === "select" || tag === "textarea";
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); this._save(); return; }
    if (typing) return;
    if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? this._doRedo() : this._doUndo(); return; }
    if (mod && e.key.toLowerCase() === "y") { e.preventDefault(); this._doRedo(); return; }
    const w = this._sel && this._w(this._sel); if (!w) return;
    if (mod && e.key.toLowerCase() === "d") { e.preventDefault(); this._duplicate(w.id); return; }
    if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); this._delete(w.id); return; }
    if (e.key === "Escape") { this._select(null); return; }
    const step = e.shiftKey ? 10 : 1;
    const mv = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (mv) {
      e.preventDefault();
      if (!this._nudging) { this._snapshot(); this._nudging = true; }
      clearTimeout(this._nudgeT); this._nudgeT = setTimeout(() => { this._nudging = false; }, 600);
      w.x += mv[0]; w.y += mv[1]; this._posBox(w); this._setDirty(true); this._syncGeo(w); this._preview();
    }
  }

  _syncGeo(w) { this.shadowRoot.querySelectorAll("[data-geo]").forEach((i) => { if (this.shadowRoot.activeElement !== i) i.value = w[i.dataset.geo]; }); }

  // ------------------------------------------------------------------ Ziehen & Größe ändern mit Hilfslinien
  _startDrag(e, id, handle) {
    if (e.button !== 0) return;
    e.preventDefault(); e.stopPropagation();
    this._select(id);
    const w = this._w(id); const start = { x: w.x, y: w.y, w: w.w, h: w.h }; const px = e.clientX, py = e.clientY;
    let moved = false;
    const others = this._layout.widgets.filter((o) => o.id !== id);
    const xs = [0, W / 2, W, ...others.flatMap((o) => [o.x, o.x + o.w / 2, o.x + o.w])];
    const ys = [0, H / 2, H, ...others.flatMap((o) => [o.y, o.y + o.h / 2, o.y + o.h])];
    const snap = (vals, targets, free) => {
      if (free) return [0, null];
      let best = null;
      for (const v of vals) for (const t of targets) { const d = t - v; if (Math.abs(d) <= SNAP && (!best || Math.abs(d) < Math.abs(best[0]))) best = [d, t]; }
      return best || [0, null];
    };
    const move = (ev) => {
      const dx = (ev.clientX - px) / this._scale, dy = (ev.clientY - py) / this._scale;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 2) return;
      if (!moved) { this._snapshot(); moved = true; }
      const free = ev.altKey; const g = (v) => free ? Math.round(v) : Math.round(v / GRID) * GRID;
      let gx = null, gy = null;
      if (!handle) {
        let x = g(start.x + dx), y = g(start.y + dy);
        const [sx, tx] = snap([x, x + w.w / 2, x + w.w], xs, free); const [sy, ty] = snap([y, y + w.h / 2, y + w.h], ys, free);
        w.x = x + sx; w.y = y + sy; gx = tx; gy = ty;
      } else {
        let { x, y, w: ww, h: hh } = start;
        if (handle.includes("e")) { let r = g(x + ww + dx); const [s, t] = snap([r], xs, free); r += s; gx = t; ww = r - x; }
        if (handle.includes("s")) { let b = g(y + hh + dy); const [s, t] = snap([b], ys, free); b += s; gy = t; hh = b - y; }
        if (handle.includes("w")) { let l = g(x + dx); const [s, t] = snap([l], xs, free); l += s; gx = t; ww = x + ww - l; x = l; }
        if (handle.includes("n")) { let tp = g(y + dy); const [s, t] = snap([tp], ys, free); tp += s; gy = t; hh = y + hh - tp; y = tp; }
        if (ww < 12) { if (handle.includes("w")) x -= 12 - ww; ww = 12; }
        if (hh < 8) { if (handle.includes("n")) y -= 8 - hh; hh = 8; }
        Object.assign(w, { x, y, w: ww, h: hh });
      }
      this._posBox(w); this._guides(gx, gy); this._syncGeo(w);
    };
    const up = () => {
      window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up);
      this._guides(null, null);
      if (moved) { this._setDirty(true); this._updUndo(); this._preview(50); }
    };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  }

  _guides(x, y) {
    const st = this.$("stage");
    st.querySelectorAll(".guide").forEach((g) => g.remove());
    if (x !== null && x !== undefined) { const g = document.createElement("div"); g.className = "guide v"; g.style.left = x + "px"; st.appendChild(g); }
    if (y !== null && y !== undefined) { const g = document.createElement("div"); g.className = "guide hz"; g.style.top = y + "px"; st.appendChild(g); }
  }
}

customElements.define("bilderrahmen-panel", BilderrahmenPanel);
