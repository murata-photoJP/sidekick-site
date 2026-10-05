/* プランナーQRマップ（G-3 Map Viewer）。
 *
 * 守ること（HD-PLANNERQRMAP-006 / -008 / -012）:
 *   - 計画は G-2 の GET tile だけで取る（画面を覆う data tile のみ。全件取得しない）
 *   - page 表示・pan・zoom・tile 取得・marker / group 表示では POST open を呼ばない
 *   - 計画を人が明示的に開いたときだけ POST open（= activity）。そこで初めて fragment を受け取る
 *   - 「計画を見る」は既存 Viewer（/share#fragment）へそのまま渡す
 *   - 地理院タイルは browser から直接取得し、出典を常に表示する。proxy / cache / preload をしない
 *   - 表示する文字は textContent だけ（受け取った文字列を HTML として解釈させない）
 */
(function () {
  "use strict";
  var core = window.PlannerMapCore;
  var API = "/api/qr-map";
  var GROUP_RADIUS_PX = 36;

  var statusEl = document.getElementById("pm-status");
  var panelEl = document.getElementById("pm-panel");
  var panelBody = document.getElementById("pm-panel-body");
  var panelClose = document.getElementById("pm-panel-close");

  function el(tag, className, text) {
    var e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }

  function setStatus(kind, text, retry) {
    statusEl.textContent = "";
    statusEl.dataset.kind = kind || "";
    if (!text) { statusEl.hidden = true; return; }
    statusEl.hidden = false;
    statusEl.appendChild(el("span", null, text));
    if (retry) {
      var b = el("button", "pm-retry", "もう一度読み込む");
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
  map.setView([36.2, 137.8], 6);

  var markerLayer = L.layerGroup().addTo(map);

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
      setStatus("hint", "地図を拡大すると、公開された撮影計画が表示されます。");
      return;
    }
    var b = map.getBounds();
    var plan = core.tilesForBounds({ north: b.getNorth(), south: b.getSouth(), east: b.getEast(), west: b.getWest() }, level);
    if (plan.tooMany) {
      markerLayer.clearLayers();
      setStatus("hint", "表示範囲が広すぎます。地図を拡大してください。");
      return;
    }
    setStatus("loading", "撮影計画を読み込んでいます…");
    Promise.all(plan.tiles.map(function (t) { return loader.load(t); })).then(function (results) {
      if (seq !== requestSeq) return; // 古い要求の結果は描かない
      var truncatedCount = 0;
      results.forEach(function (r) { if (r.truncated) truncatedCount += r.count - r.plans.length; });
      var plans = core.uniquePlans(results.map(function (r) { return r.plans; }));
      render(plans);
      var visible = plans.filter(function (p) { return b.contains([p.lat, p.lon]); }).length;
      if (truncatedCount > 0) {
        setStatus("hint", "この範囲には、表示しきれない撮影計画があります（ほか " + truncatedCount + " 件）。地図を拡大してください。");
      } else if (visible === 0) {
        setStatus("empty", "この範囲には、公開された撮影計画はまだありません。");
      } else {
        setStatus("", "");
      }
    }, function () {
      if (seq !== requestSeq) return;
      markerLayer.clearLayers();
      setStatus("error", "撮影計画を読み込めませんでした。時間をおいてもう一度お試しください。", refresh);
    });
  }

  function markerIcon(count) {
    var node = el("div", count > 1 ? "pm-pin pm-pin-group" : "pm-pin", count > 1 ? count : "");
    node.setAttribute("aria-hidden", "true");
    return L.divIcon({ html: node, className: "pm-pin-wrap", iconSize: [34, 34], iconAnchor: [17, 17] });
  }

  function render(plans) {
    markerLayer.clearLayers();
    var points = plans.map(function (plan) {
      var pt = map.latLngToContainerPoint([plan.lat, plan.lon]);
      return { plan: plan, x: pt.x, y: pt.y };
    });
    core.groupPoints(points, GROUP_RADIUS_PX).forEach(function (g) {
      var count = g.plans.length;
      var label = count > 1 ? "この付近の撮影計画 " + count + " 件" : "撮影計画: " + (g.plans[0].genre_label || "");
      var m = L.marker([g.lat, g.lon], { icon: markerIcon(count), title: label, alt: label, keyboard: true });
      m.on("click", function () {
        if (count === 1) openDetail(g.plans[0].plan_id);   // 人が 1 件を選んだ = 明示的に開く
        else showGroup(g.plans);                            // 一覧を出すだけ（open しない）
      });
      m.on("add", function () {
        var e = m.getElement();
        if (e) {
          e.setAttribute("aria-label", label);
          e.dataset.planIds = g.plans.map(function (p) { return p.plan_id; }).join(",");
          e.dataset.count = String(count);
        }
      });
      markerLayer.addLayer(m);
    });
  }

  // ---- 詳細 panel ----
  // panel の開閉で地図の大きさが変わる（desktop は横、mobile は縦）。Leaflet に知らせて表示範囲を合わせる
  function showPanel() {
    if (panelEl.hidden) { panelEl.hidden = false; map.invalidateSize({ pan: false }); }
  }
  function hidePanel() {
    panelEl.hidden = true;
    panelBody.textContent = "";
    map.invalidateSize({ pan: false });
  }
  panelClose.addEventListener("click", hidePanel);

  // withGenre: 一覧ではジャンルを各行に出す。詳細では見出しにあるので出さない
  function summaryLines(p, withGenre) {
    var box = el("div", "pm-summary");
    if (withGenre) box.appendChild(el("p", "pm-genre", p.genre_label || ""));
    if (p.sky_object_label) box.appendChild(el("p", "pm-line", "天体: " + p.sky_object_label));
    if (p.target_label) box.appendChild(el("p", "pm-line", "被写体: " + p.target_label));
    box.appendChild(el("p", "pm-line", "撮影日時: " + core.formatJst(p.t_d)));
    return box;
  }

  // 同じ付近の計画の一覧（ここでは open しない）
  function showGroup(plans) {
    panelBody.textContent = "";
    panelBody.appendChild(el("h2", "pm-panel-title", "この付近の撮影計画（" + plans.length + " 件）"));
    var list = el("ul", "pm-group-list");
    plans.forEach(function (p) {
      var li = el("li", "pm-group-item");
      li.dataset.planId = p.plan_id;
      li.appendChild(summaryLines(p, true));
      var b = el("button", "pm-open", "この計画を開く");
      b.type = "button";
      b.addEventListener("click", function () { openDetail(p.plan_id); });
      li.appendChild(b);
      list.appendChild(li);
    });
    panelBody.appendChild(list);
    showPanel();
  }

  // 計画を明示的に開く（= activity）。fragment はここで初めて受け取る
  function openDetail(planId) {
    panelBody.textContent = "";
    panelBody.appendChild(el("p", "pm-loading", "計画を開いています…"));
    showPanel();
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
      if (d.unavailable) {
        panelBody.appendChild(el("h2", "pm-panel-title", "この計画は表示できません"));
        panelBody.appendChild(el("p", "pm-line", "公開が終了したか、掲載期間が過ぎた可能性があります。"));
        return;
      }
      var detail = el("article", "pm-detail");
      detail.dataset.planId = d.plan_id;
      detail.appendChild(el("h2", "pm-panel-title", d.genre_label || "撮影計画"));
      detail.appendChild(summaryLines(d, false));
      detail.appendChild(el("p", "pm-line", "撮影地点: " + Number(d.lat).toFixed(5) + ", " + Number(d.lon).toFixed(5)));
      detail.appendChild(el("p", "pm-note", "地図の位置は、この計画を立てた人が選んだ撮影地点です。"));
      var url = core.viewerUrl(d.fragment);
      if (url) {
        var a = el("a", "pm-view", "計画を見る");
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        detail.appendChild(a);
      }
      panelBody.appendChild(detail);
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
