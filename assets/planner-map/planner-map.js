/* プランナーQRマップ（G-3 Map Viewer ＋ G-3.1 Visual / UX Polish）。
 *
 * 守ること（HD-PLANNERQRMAP-006 / -008 / -012。G-3.1 は見た目だけを変え、以下は G-3 から変えない）:
 *   - 計画は G-2 の GET tile だけで取る（画面を覆う data tile のみ。全件取得しない）
 *   - page 表示・pan・zoom・tile 取得・marker / group 表示・選択の強調では POST open を呼ばない
 *   - 計画を人が明示的に開いたときだけ POST open（= activity）。そこで初めて fragment を受け取る
 *   - 「計画を見る」は既存 Viewer（/share#fragment）へそのまま渡す
 *   - 地理院タイルは browser から直接取得し、出典を常に表示する。proxy / cache / preload をしない
 *   - 表示する文字は textContent だけ（受け取った文字列を HTML として解釈させない）
 *
 * G-3.1（Human Review: 「緑の○が地図に埋もれる」）: 撮影計画を主役にする。
 *   - 1 件 = 撮影地点を指す pin（上に記号、下の先端が撮影地点）。まとまり = 「N 件」の吹き出し（形も文字も違う）
 *   - 記号の意味は Planner の正本（☀ 太陽 / ☾ 月）に合わせ、SVG で描く（emoji・OS の字形に頼らない）。名前は必ず文字でも出す
 *   - 選んでいる地点は 大きさ ＋ 外枠 ＋ 色 で示す（色だけにしない）
 *   - 詳細・近くの計画は card で見せる（将来 写真・撮影者を足せる構造。今は placeholder を出さない）
 */
(function () {
  "use strict";
  var core = window.PlannerMapCore;
  var API = "/api/qr-map";
  var GROUP_RADIUS_PX = 36;   // 表示上のまとまり（G-3 と同じ。identity ではない）
  var SVG_NS = "http://www.w3.org/2000/svg";

  var statusEl = document.getElementById("pm-status");
  var panelEl = document.getElementById("pm-panel");
  var panelBody = document.getElementById("pm-panel-body");
  var panelClose = document.getElementById("pm-panel-close");
  var cueEl = document.getElementById("pm-cue");

  // First Action Cue（G-3.3）: pin が見えている間だけ出し、最初に pin を選んだら消す（この page を開いている間だけ。記憶しない）
  var cueDismissed = false;
  function updateCue() {
    cueEl.hidden = cueDismissed || markerLayer.getLayers().length === 0;
  }

  function el(tag, className, text) {
    var e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }

  function svg(tag, attrs) {
    var e = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    return e;
  }

  // ---- ジャンルの記号（SVG。中心 (0,0)、半径およそ 9 の中に収める） ----
  function symbolGroup(kind) {
    var g = svg("g", { "class": "pm-sym pm-sym-" + kind });
    var i;
    if (kind === "sun") {
      g.appendChild(svg("circle", { cx: 0, cy: 0, r: 4.2 }));
      for (i = 0; i < 8; i += 1) {
        var a = i * Math.PI / 4;
        g.appendChild(svg("line", { x1: (6.2 * Math.cos(a)).toFixed(2), y1: (6.2 * Math.sin(a)).toFixed(2),
          x2: (8.8 * Math.cos(a)).toFixed(2), y2: (8.8 * Math.sin(a)).toFixed(2), "class": "pm-sym-stroke" }));
      }
    } else if (kind === "moon") {
      g.appendChild(svg("path", { d: "M2.5 -8.2 A8.4 8.4 0 1 0 2.5 8.2 A6.6 6.6 0 1 1 2.5 -8.2 Z" }));
    } else if (kind === "sunmoon") {
      g.appendChild(svg("circle", { cx: -3.6, cy: -2.6, r: 3.6 }));
      for (i = 0; i < 6; i += 1) {
        var b = i * Math.PI / 3 + Math.PI / 6;
        g.appendChild(svg("line", { x1: (-3.6 + 5.2 * Math.cos(b)).toFixed(2), y1: (-2.6 + 5.2 * Math.sin(b)).toFixed(2),
          x2: (-3.6 + 7.0 * Math.cos(b)).toFixed(2), y2: (-2.6 + 7.0 * Math.sin(b)).toFixed(2), "class": "pm-sym-stroke" }));
      }
      g.appendChild(svg("path", { d: "M6.2 -0.6 A5.2 5.2 0 1 0 6.2 9.6 A4.0 4.0 0 1 1 6.2 -0.6 Z" }));
    } else if (kind === "star") {
      var pts = [];
      for (i = 0; i < 10; i += 1) {
        var r = i % 2 === 0 ? 9 : 3.8;
        var c = -Math.PI / 2 + i * Math.PI / 5;
        pts.push((r * Math.cos(c)).toFixed(2) + "," + (r * Math.sin(c)).toFixed(2));
      }
      g.appendChild(svg("polygon", { points: pts.join(" ") }));
    } else if (kind === "trails") {
      g.appendChild(svg("circle", { cx: 0, cy: 0, r: 1.8 }));
      [3.9, 6.2, 8.5].forEach(function (rr) {
        g.appendChild(svg("path", { d: "M" + (-rr) + " 0 A" + rr + " " + rr + " 0 1 1 " + (rr * 0.5).toFixed(2) + " " + (rr * 0.866).toFixed(2),
          "class": "pm-sym-stroke pm-sym-arc" }));
      });
    } else {
      g.appendChild(svg("circle", { cx: 0, cy: 0, r: 5 }));
    }
    return g;
  }

  // 1 件の pin: 上が記号の入る丸、下の先端が撮影地点（Leaflet の anchor = 先端）
  function pinSvg(kind, className) {
    var s = svg("svg", { viewBox: "0 0 40 52", width: 40, height: 52, "class": className || "pm-pin-svg", "aria-hidden": "true", focusable: "false" });
    s.appendChild(svg("path", { "class": "pm-pin-shape", d: "M20 50.5 C20 50.5 4 31.5 4 19 A16 16 0 1 1 36 19 C36 31.5 20 50.5 20 50.5 Z" }));
    var g = symbolGroup(kind);
    g.setAttribute("transform", "translate(20 19)");
    s.appendChild(g);
    return s;
  }

  // 複数の pin（G-3.2）: 1 件の pin と同じ形（同じ path）の前に件数、後ろにもう 1 本の pin を重ねて「束」に見せる。
  // 先端（前の pin）が地点を指す。件数は 99 まで数字、それ以上は「99+」（正確な件数は aria-label / tooltip）。
  var PIN_PATH = "M20 50.5 C20 50.5 4 31.5 4 19 A16 16 0 1 1 36 19 C36 31.5 20 50.5 20 50.5 Z";
  function groupPinSvg(count, className) {
    var s = svg("svg", { viewBox: "0 0 48 56", width: 48, height: 56, "class": className || "pm-pin-svg pm-pin-svg-group", "aria-hidden": "true", focusable: "false" });
    s.appendChild(svg("path", { "class": "pm-pin-shape pm-pin-stack", d: PIN_PATH, transform: "translate(8 0)" }));
    var front = svg("g", { transform: "translate(0 4)" });
    front.appendChild(svg("path", { "class": "pm-pin-shape", d: PIN_PATH }));
    var label = count > 99 ? "99+" : String(count);
    var t = svg("text", { x: 20, y: 19, "class": "pm-group-count", "text-anchor": "middle", "dominant-baseline": "central",
      "font-size": label.length === 1 ? 19 : label.length === 2 ? 16 : 12 });
    t.textContent = label;
    front.appendChild(t);
    s.appendChild(front);
    return s;
  }

  function setStatus(kind, text, retry, retryLabel) {
    statusEl.textContent = "";
    statusEl.dataset.kind = kind || "";
    if (!text) { statusEl.hidden = true; return; }
    statusEl.hidden = false;
    statusEl.appendChild(el("span", null, text));
    if (retry) {
      var b = el("button", "pm-retry", retryLabel || "もう一度読み込む");
      b.type = "button";
      b.addEventListener("click", retry);
      statusEl.appendChild(b);
    }
  }

  // ---- 地図（地理院タイル pale、browser から直接） ----
  var map = L.map("pm-map", { minZoom: 5, maxZoom: 18, zoomControl: true, attributionControl: true });
  map.attributionControl.setPrefix('<a href="https://leafletjs.com" target="_blank" rel="noopener noreferrer">Leaflet</a>');
  L.tileLayer("https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png", {
    minZoom: 5,
    maxZoom: 18,
    attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener noreferrer">地理院タイル</a>（国土地理院）に撮影計画の位置を追記して表示'
  }).addTo(map);
  // 初期表示は map-core の INITIAL_VIEW（関東〜中部。MVP の暫定。開いた瞬間に撮影計画の pin が見える範囲）
  map.setView(core.INITIAL_VIEW.center, core.INITIAL_VIEW.zoom);

  var markerLayer = L.layerGroup().addTo(map);

  // ---- 選択（表示だけ。open とは独立） ----
  var selectedIds = new Set();   // いま panel に出している計画（1 件 or 近くの計画の一覧）
  var lastGroup = null;          // 一覧から詳細へ進んだときの「一覧へ戻る」用
  var lastGroupAt = null;
  // panel が開いて地図が狭くなっても、選んだ地点が見える範囲に残るようにする（表示だけ。open しない）
  function keepInView(at) {
    if (at) map.panInside(at, { padding: [48, 64], animate: false });
  }
  function setSelected(ids) {
    selectedIds = new Set(ids);
    markerLayer.eachLayer(function (m) {
      var e = m.getElement();
      if (!e) return;
      var on = (e.dataset.planIds || "").split(",").some(function (id) { return selectedIds.has(id); });
      e.classList.toggle("pm-selected", on);
      e.setAttribute("aria-pressed", on ? "true" : "false");
      e.dataset.selected = on ? "true" : "false";
      m.setZIndexOffset(on ? 1000 : 0);
    });
  }

  // ---- PublicPlan の取得（G-2 GET tile のみ） ----
  var loader = core.createTileLoader({
    ttlMs: 60000,
    fetchJson: function (tile) {
      var url = API + "?op=tile&z=" + tile.z + "&x=" + tile.x + "&y=" + tile.y;
      return fetch(url, { method: "GET", credentials: "same-origin", referrerPolicy: "no-referrer" })
        .then(function (res) {
          if (!res.ok) throw new Error("tile " + res.status);
          return res.json();
        });
    }
  });

  var requestSeq = 0;
  function refresh() {
    var seq = ++requestSeq;
    var size = map.getSize();
    if (!(size.x > 0 && size.y > 0)) return; // 地図がまだ描画されていない（大きさ 0）。判定しない
    var zoom = map.getZoom();
    var level = core.serverLevelFor(zoom);
    if (level === null) {
      markerLayer.clearLayers();
      updateCue();
      setStatus("hint", "もう少し地図を拡大すると、撮影計画を表示できます。");
      return;
    }
    var b = map.getBounds();
    var plan = core.tilesForBounds({ north: b.getNorth(), south: b.getSouth(), east: b.getEast(), west: b.getWest() }, level);
    if (plan.tooMany) {
      markerLayer.clearLayers();
      updateCue();
      setStatus("hint", "もう少し地図を拡大すると、撮影計画を表示できます。");
      return;
    }
    setStatus("loading", "撮影計画を読み込んでいます…");
    Promise.all(plan.tiles.map(function (t) { return loader.load(t); })).then(function (results) {
      if (seq !== requestSeq) return; // 古い要求の結果は描かない
      var truncatedCount = 0;
      results.forEach(function (r) { if (r.truncated) truncatedCount += r.count - r.plans.length; });
      lastResult = { plans: core.uniquePlans(results.map(function (r) { return r.plans; })), truncatedCount: truncatedCount, bounds: b };
      applyFilter();
    }, function () {
      if (seq !== requestSeq) return;
      lastResult = null;
      markerLayer.clearLayers();
      updateCue();
      updateFilterUi();
      setStatus("error", "撮影計画を読み込めませんでした。時間をおいてもう一度お試しください。", refresh);
    });
  }

  // ---- G-6 Map Discovery Filter: 取得済みの計画（表示範囲の tile）を 期間 × 撮影対象 で絞る ----
  // server へ全件を求めない（地域 = 表示範囲。地図を動かすと今までどおり自動で取り直す、HD-1）。
  // 初期は「今後すべて」× すべての撮影対象。過去は「過去を見る」で明示的に選んだときだけ（HD-4 訂正）。
  var Filter = window.PlannerMapFilter;
  var filterState = Filter.defaultState();
  var lastResult = null;   // { plans, truncatedCount, bounds }（最後に取得した表示範囲の計画。絞る前）

  function applyFilter() {
    if (!lastResult) { updateFilterUi(); return; }
    var b = lastResult.bounds;
    var shown = Filter.filterPlans(lastResult.plans, filterState, Date.now());
    render(shown);
    updateCue();
    var visible = shown.filter(function (p) { return b.contains([p.lat, p.lon]); }).length;
    updateFilterUi(visible);
    if (lastResult.truncatedCount > 0) {
      setStatus("hint", "この範囲には、表示しきれない撮影計画があります（ほか " + lastResult.truncatedCount + " 件）。地図を拡大してください。");
    } else if (filterState.categories.length === 0) {
      setStatus("empty", "撮影対象が選ばれていません", selectAllCategories, "すべて選ぶ");
    } else if (Filter.customPastState(filterState, Date.now()) === "all") {
      setStatus("empty", Filter.CUSTOM_ALL_PAST_HINT);   // 自動で「過去を見る」には切り替えない
    } else if (visible === 0 && lastResult.plans.length === 0) {
      setStatus("empty", "この範囲には、公開された撮影計画はまだありません。");
    } else if (visible === 0) {
      setStatus("empty", "この範囲には、選んだ条件に合う撮影計画はありません。");
    } else {
      setStatus("", "");
    }
  }

  var filterBox = el("div", "pm-filter");
  var filterToggle = el("button", "pm-filter-toggle");
  filterToggle.type = "button";
  filterToggle.id = "pm-filter-toggle";
  filterToggle.setAttribute("aria-expanded", "false");
  filterToggle.setAttribute("aria-controls", "pm-filter-panel");
  filterToggle.appendChild(el("span", "pm-filter-label", "絞り込み"));
  var filterSummary = el("span", "pm-filter-summary");
  filterSummary.id = "pm-filter-summary";
  filterToggle.appendChild(filterSummary);
  var filterCount = el("p", "pm-filter-count");
  filterCount.id = "pm-filter-count";
  filterCount.setAttribute("role", "status");
  filterCount.setAttribute("aria-live", "polite");
  var pastNoticeEl = el("p", "pm-past-notice", Filter.PAST_NOTICE);
  pastNoticeEl.id = "pm-past-notice";
  pastNoticeEl.setAttribute("role", "note");
  pastNoticeEl.hidden = true;

  var filterPanel = el("section", "pm-filter-panel");
  filterPanel.id = "pm-filter-panel";
  filterPanel.setAttribute("aria-label", "撮影計画の絞り込み");
  filterPanel.hidden = true;

  function radio(name, value, label, checked) {
    var wrap = el("label", "pm-filter-option");
    var input = el("input");
    input.type = "radio";
    input.name = name;
    input.value = value;
    input.checked = checked;
    wrap.appendChild(input);
    wrap.appendChild(el("span", null, label));
    return wrap;
  }

  // 期間: 未来の検索（今後すべて・今週末・7日間・30日間・期間指定）と、過去を見る を分けて置く
  var periodSet = el("fieldset", "pm-filter-group");
  periodSet.appendChild(el("legend", null, "撮影日時"));
  Filter.PERIODS.forEach(function (p) {
    if (p.id === "past") return;
    periodSet.appendChild(radio("pm-period", p.id, p.label, filterState.period === p.id));
  });
  var customBox = el("div", "pm-filter-custom");
  customBox.hidden = true;
  var fromInput = el("input");
  fromInput.type = "date";
  fromInput.id = "pm-filter-from";
  fromInput.setAttribute("aria-label", "開始日");
  var toInput = el("input");
  toInput.type = "date";
  toInput.id = "pm-filter-to";
  toInput.setAttribute("aria-label", "終了日");
  customBox.appendChild(fromInput);
  customBox.appendChild(el("span", null, "〜"));
  customBox.appendChild(toInput);
  periodSet.appendChild(customBox);
  var customHintEl = el("p", "pm-filter-note", Filter.CUSTOM_PAST_HINT);
  customHintEl.id = "pm-filter-custom-hint";
  customHintEl.hidden = true;
  periodSet.appendChild(customHintEl);
  var pastSet = el("fieldset", "pm-filter-group pm-filter-past");
  pastSet.appendChild(el("legend", null, "過去の撮影計画"));
  pastSet.appendChild(radio("pm-period", "past", "過去を見る", filterState.period === "past"));
  pastSet.appendChild(el("p", "pm-filter-note", "撮影日時を過ぎた計画です。現在も同じ条件で撮影できるとは限りません。"));

  var catSet = el("fieldset", "pm-filter-group");
  catSet.appendChild(el("legend", null, "撮影対象"));
  var catInputs = Filter.CATEGORIES.map(function (c) {
    var wrap = el("label", "pm-filter-option");
    var input = el("input");
    input.type = "checkbox";
    input.value = c.id;
    input.checked = filterState.categories.indexOf(c.id) >= 0;
    wrap.appendChild(input);
    wrap.appendChild(el("span", null, c.label));
    catSet.appendChild(wrap);
    return input;
  });
  var allButton = el("button", "pm-filter-all", "すべて選ぶ");
  allButton.type = "button";
  catSet.appendChild(allButton);

  var panelFoot = el("div", "pm-filter-foot");
  var resetButton = el("button", "pm-filter-reset", "初期の条件に戻す");
  resetButton.type = "button";
  var doneButton = el("button", "pm-filter-done", "閉じる");
  doneButton.type = "button";
  panelFoot.appendChild(resetButton);
  panelFoot.appendChild(doneButton);
  filterPanel.appendChild(periodSet);
  filterPanel.appendChild(pastSet);
  filterPanel.appendChild(catSet);
  filterPanel.appendChild(panelFoot);
  filterBox.appendChild(filterToggle);
  filterBox.appendChild(filterCount);
  filterBox.appendChild(pastNoticeEl);
  filterBox.appendChild(filterPanel);

  function updateFilterUi(visible) {
    filterSummary.textContent = Filter.summary(filterState);
    filterToggle.dataset.filtered = Filter.isDefault(filterState) ? "false" : "true";
    customBox.hidden = filterState.period !== "custom";
    pastNoticeEl.hidden = !Filter.pastNotice(filterState);
    var customPast = Filter.customPastState(filterState, Date.now());
    customHintEl.hidden = customPast === "none";
    customHintEl.textContent = customPast === "all" ? Filter.CUSTOM_ALL_PAST_HINT : Filter.CUSTOM_PAST_HINT;
    customHintEl.dataset.pastState = customPast;
    if (typeof visible === "number") {
      filterCount.textContent = "この範囲 " + visible + "件" + (lastResult && lastResult.truncatedCount > 0 ? "以上" : "");
      filterCount.hidden = false;
    } else {
      filterCount.textContent = "";
      filterCount.hidden = true;
    }
  }

  function readFilterControls() {
    var checked = filterPanel.querySelector('input[name="pm-period"]:checked');
    filterState = {
      period: checked ? checked.value : Filter.DEFAULT_PERIOD,
      from: fromInput.value,
      to: toInput.value,
      categories: catInputs.filter(function (i) { return i.checked; }).map(function (i) { return i.value; })
    };
    applyFilter();
  }

  function writeFilterControls() {
    Array.prototype.forEach.call(filterPanel.querySelectorAll('input[name="pm-period"]'), function (r) {
      r.checked = r.value === filterState.period;
    });
    fromInput.value = filterState.from || "";
    toInput.value = filterState.to || "";
    catInputs.forEach(function (i) { i.checked = filterState.categories.indexOf(i.value) >= 0; });
  }

  function selectAllCategories() {
    catInputs.forEach(function (i) { i.checked = true; });
    readFilterControls();
  }

  function setFilterOpen(open) {
    filterPanel.hidden = !open;
    filterToggle.setAttribute("aria-expanded", open ? "true" : "false");
    filterBox.classList.toggle("pm-filter-open", open);
    // スマートフォンの sheet（position: fixed）が右下の出典（Leaflet control）の下に隠れないよう、開いている間だけ
    // 右上の control 群を前に出す（出典は消さない）
    if (filterBox.parentElement) filterBox.parentElement.classList.toggle("pm-filter-raised", open);
    if (open) {
      var first = filterPanel.querySelector('input[name="pm-period"]:checked');
      if (first) first.focus();
    }
  }

  filterPanel.addEventListener("change", readFilterControls);
  allButton.addEventListener("click", selectAllCategories);
  resetButton.addEventListener("click", function () { filterState = Filter.defaultState(); writeFilterControls(); applyFilter(); });
  doneButton.addEventListener("click", function () { setFilterOpen(false); filterToggle.focus(); });
  filterToggle.addEventListener("click", function () { setFilterOpen(filterPanel.hidden); });
  filterPanel.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") { ev.preventDefault(); setFilterOpen(false); filterToggle.focus(); }
  });

  // 地図の上の小さな control（右上）。地図の中に置くので、詳細の panel と重ならない。操作が地図の pan / zoom にならない
  var FilterControl = L.Control.extend({
    options: { position: "topright" },
    onAdd: function () {
      L.DomEvent.disableClickPropagation(filterBox);
      L.DomEvent.disableScrollPropagation(filterBox);
      return filterBox;
    }
  });
  map.addControl(new FilterControl());
  updateFilterUi();

  // 1 件 = pin（ジャンル記号入り）、複数 = 同じ pin ＋ 件数 ＋ 後ろに重なったもう 1 本（G-3.2）。
  // 同じ「撮影計画がある地点」の family として見せ、中身（記号 / 数字）と重なりで区別する（色だけにしない）
  function markerIcon(plans) {
    var node;
    if (plans.length === 1) {
      var kind = core.genreSymbol(plans[0].genre);
      node = el("div", "pm-marker pm-pin-single");
      node.dataset.symbol = kind;
      node.dataset.genre = plans[0].genre;
      node.appendChild(pinSvg(kind));
      return L.divIcon({ html: node, className: "pm-marker-wrap", iconSize: [44, 56], iconAnchor: [22, 54] });
    }
    node = el("div", "pm-marker pm-pin-group");
    node.dataset.symbol = "count";
    node.appendChild(groupPinSvg(plans.length));
    // 前の pin の先端 = (2 + 20, 4 + 54.5)（wrap 52×60 の下端中央寄せ）
    return L.divIcon({ html: node, className: "pm-marker-wrap", iconSize: [52, 60], iconAnchor: [22, 58] });
  }

  function render(plans) {
    markerLayer.clearLayers();
    var points = plans.map(function (plan) {
      var pt = map.latLngToContainerPoint([plan.lat, plan.lon]);
      return { plan: plan, x: pt.x, y: pt.y };
    });
    core.groupPoints(points, GROUP_RADIUS_PX).forEach(function (g) {
      var count = g.plans.length;
      var label = count > 1
        ? count + "件の撮影計画がこの付近にあります。選ぶと一覧を表示します"
        : "撮影計画: " + core.planCaption(g.plans[0]) + "、" + core.formatJstCompact(g.plans[0].t_d) + "。選ぶと詳細を表示します";
      var m = L.marker([g.lat, g.lon], { icon: markerIcon(g.plans), title: label, alt: label, keyboard: true, riseOnHover: true });
      m.on("click", function () {
        cueDismissed = true;
        updateCue();
        if (count === 1) { lastGroup = null; openDetail(g.plans[0].plan_id, [g.lat, g.lon]); } // 人が 1 件を選んだ = 明示的に開く
        else showGroup(g.plans, [g.lat, g.lon]);                                 // 一覧を出すだけ（open しない）
      });
      m.on("add", function () {
        var e = m.getElement();
        if (e) {
          e.setAttribute("role", "button");
          e.setAttribute("aria-label", label);
          e.dataset.planIds = g.plans.map(function (p) { return p.plan_id; }).join(",");
          e.dataset.count = String(count);
          // keyboard: Enter / Space で選ぶ（button と同じ。既定動作を止めるので Leaflet 側と二重にならない）
          e.addEventListener("keydown", function (ev) {
            if (ev.key === "Enter" || ev.key === " ") {
              ev.preventDefault();
              m.fire("click");
            }
          });
        }
      });
      markerLayer.addLayer(m);
    });
    setSelected(Array.from(selectedIds)); // 再描画しても選択を保つ
  }

  // ---- panel ----
  // panel の開閉で地図の大きさが変わる（desktop は横、mobile は縦）。Leaflet に知らせて表示範囲を合わせる
  function showPanel() {
    if (panelEl.hidden) { panelEl.hidden = false; map.invalidateSize({ pan: false }); }
  }
  function hidePanel() {
    panelEl.hidden = true;
    panelBody.textContent = "";
    lastGroup = null;
    setSelected([]);
    map.invalidateSize({ pan: false });
  }
  panelClose.addEventListener("click", hidePanel);

  // 撮影計画の card。構造: genre（記号 ＋ 名前）／ 主題（被写体・天体）／ 日時 ／ actions。
  // 将来 写真（.pm-card-media）・撮影者（.pm-card-meta）を header の前・body の後に足せる（今は出さない）
  function planCard(p, tag) {
    var card = el(tag || "article", "pm-card");
    card.dataset.planId = p.plan_id;
    var head = el("div", "pm-card-genre");
    var sym = pinSvg(core.genreSymbol(p.genre), "pm-card-symbol");
    head.appendChild(sym);
    head.appendChild(el("span", "pm-card-genre-label", p.genre_label || "撮影計画"));
    card.appendChild(head);
    var body = el("div", "pm-card-body");
    var subject = p.target_label || p.sky_object_label || "";
    if (subject) body.appendChild(el("p", "pm-card-title", subject));
    if (p.sky_object_label && p.target_label) body.appendChild(el("p", "pm-card-sub", p.sky_object_label + " を狙う計画"));
    var when = el("p", "pm-card-date");
    when.appendChild(el("span", null, core.formatJstCompact(p.t_d)));
    when.appendChild(el("span", "pm-card-tz", "日本時間"));
    body.appendChild(when);
    card.appendChild(body);
    var actions = el("div", "pm-card-actions");
    card.appendChild(actions);
    return { card: card, actions: actions, body: body };
  }

  // 近くの計画の一覧（ここでは open しない）
  function showGroup(plans, at) {
    lastGroup = plans;
    lastGroupAt = at;
    panelBody.textContent = "";
    panelBody.appendChild(el("h2", "pm-panel-title", "この付近の撮影計画（" + plans.length + " 件）"));
    panelBody.appendChild(el("p", "pm-panel-lead", "見たい計画を選んでください。"));
    var list = el("ul", "pm-card-list");
    plans.forEach(function (p) {
      var li = el("li", "pm-group-item");
      li.dataset.planId = p.plan_id;
      var c = planCard(p, "div");
      var b = el("button", "pm-open", "詳しく見る");
      b.type = "button";
      b.setAttribute("aria-label", "詳しく見る: " + core.planCaption(p));
      b.addEventListener("click", function () { openDetail(p.plan_id, at); });
      c.actions.appendChild(b);
      li.appendChild(c.card);
      list.appendChild(li);
    });
    panelBody.appendChild(list);
    showPanel();
    setSelected(plans.map(function (p) { return p.plan_id; }));
    keepInView(at);
    panelBody.scrollTop = 0;
  }

  function backToGroup() {
    if (!lastGroup) return null;
    var back = el("button", "pm-back", "← この付近の計画一覧へ戻る");
    back.type = "button";
    var group = lastGroup;
    var groupAt = lastGroupAt;
    back.addEventListener("click", function () { showGroup(group, groupAt); });
    return back;
  }

  // 計画を明示的に開く（= activity）。fragment はここで初めて受け取る
  function openDetail(planId, at) {
    panelBody.textContent = "";
    panelBody.appendChild(el("p", "pm-loading", "計画を開いています…"));
    showPanel();
    setSelected([planId]);
    keepInView(at);
    fetch(API + "?op=open", {
      method: "POST",
      credentials: "same-origin",
      referrerPolicy: "no-referrer",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan_id: planId })
    }).then(function (res) {
      if (res.status === 404) return { unavailable: true };
      if (!res.ok) throw new Error("open " + res.status);
      return res.json();
    }).then(function (d) {
      panelBody.textContent = "";
      var back = backToGroup();
      if (back) panelBody.appendChild(back);
      if (d.unavailable) {
        panelBody.appendChild(el("h2", "pm-panel-title", "この計画は表示できません"));
        panelBody.appendChild(el("p", "pm-line", "公開が終了したか、掲載期間が過ぎた可能性があります。"));
        return;
      }
      panelBody.appendChild(el("h2", "pm-panel-title pm-visually-hidden", "撮影計画の詳細"));
      var c = planCard(d, "article");
      c.card.classList.add("pm-detail");
      var where = el("p", "pm-card-place");
      where.appendChild(el("span", "pm-card-place-label", "撮影地点"));
      where.appendChild(el("span", null, Number(d.lat).toFixed(5) + ", " + Number(d.lon).toFixed(5)));
      c.body.appendChild(where);
      c.body.appendChild(el("p", "pm-note", "地図のピンの先が、この計画を立てた人が選んだ撮影地点です。"));
      var url = core.viewerUrl(d.fragment);
      if (url) {
        var a = el("a", "pm-view", "計画を見る");
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        c.actions.appendChild(a);
      }
      panelBody.appendChild(c.card);
      panelBody.scrollTop = 0;
    }).catch(function () {
      panelBody.textContent = "";
      panelBody.appendChild(el("h2", "pm-panel-title", "計画を開けませんでした"));
      panelBody.appendChild(el("p", "pm-line", "時間をおいてもう一度お試しください。"));
    });
  }

  var timer = null;
  map.on("moveend", function () {
    clearTimeout(timer);
    timer = setTimeout(refresh, 200);
  });
  refresh();

  // 自動 test 用（地図の操作だけ。API の呼び出し口は出さない）
  window.PlannerMap = { map: map };
}());
