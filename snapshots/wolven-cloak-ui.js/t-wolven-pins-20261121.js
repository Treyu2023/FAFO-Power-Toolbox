/* Wolven-cloak page. Expects Leaflet (L) and WolvenCloak. */
(function () {
  var W = window.WolvenCloak;
  var CACHE_KEY = 'wolven.cameras.v1';
  var PREF_KEY = 'wolven.prefs.v1';
  var PAGES = 'https://treyu2023.github.io/FAFO-Power-Toolbox/Wolven-cloak.html';

  var statusEl = document.getElementById('status');
  var chip = document.getElementById('gpsChip');
  var banner = document.getElementById('banner');
  var resultEl = document.getElementById('result');
  var nearEl = document.getElementById('near');
  var hitsEl = document.getElementById('hits');
  var qEl = document.getElementById('q');

  var cameras = [];
  var boxes = [];
  var fix = null;
  var startPin = null;
  var endPin = null;
  var dropMode = null;
  var watchId = null;
  var armed = false;
  var insideIds = {};
  var planning = false;
  var planAbort = null;
  var nextGeoAt = 0;
  var buffer = 250;
  var routeHits = [];
  var map, puck, startMark, endMark, cloakLine, directLine, bufferRing, camLayer;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (ch) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch];
    });
  }

  function say(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function loadPrefs() {
    try {
      var p = JSON.parse(localStorage.getItem(PREF_KEY) || '{}');
      if (p.buffer === 150 || p.buffer === 250 || p.buffer === 400) buffer = p.buffer;
      var avoid = document.getElementById('avoidAll');
      var vib = document.getElementById('vibrate');
      var speak = document.getElementById('speak');
      if (avoid && typeof p.avoidAll === 'boolean') avoid.checked = p.avoidAll;
      if (vib && typeof p.vibrate === 'boolean') vib.checked = p.vibrate;
      if (speak && typeof p.speak === 'boolean') speak.checked = p.speak;
    } catch (e) { /* keep defaults */ }
  }

  function savePrefs() {
    try {
      localStorage.setItem(PREF_KEY, JSON.stringify({
        buffer: buffer,
        avoidAll: document.getElementById('avoidAll').checked,
        vibrate: document.getElementById('vibrate').checked,
        speak: document.getElementById('speak').checked
      }));
    } catch (e) { /* private mode */ }
  }

  function loadCache() {
    try {
      var raw = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
      if (!raw || !Array.isArray(raw.cameras)) return;
      cameras = raw.cameras;
      boxes = Array.isArray(raw.boxes) ? raw.boxes : [];
    } catch (e) {
      cameras = [];
      boxes = [];
    }
  }

  function saveCache(center) {
    cameras = W.mergeCameras(cameras, [], center || null, 8000);
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ cameras: cameras, boxes: boxes.slice(-24) }));
    } catch (e) { /* quota */ }
  }

  function bufferM() { return buffer; }

  function avoidAll() {
    var el = document.getElementById('avoidAll');
    return !el || el.checked;
  }

  function setBuffer(m) {
    buffer = m;
    var buttons = document.querySelectorAll('#bufferSeg button');
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].classList.toggle('on', Number(buttons[i].getAttribute('data-m')) === m);
    }
    savePrefs();
    if (armed && fix) drawBuffer();
  }

  function showBanner(html) {
    banner.hidden = false;
    banner.innerHTML = html;
  }

  function secureEnough() {
    return window.isSecureContext === true;
  }

  function currentStart() {
    if (startPin) return startPin;
    if (fix) return { lat: fix.lat, lon: fix.lon, label: 'This phone' };
    return null;
  }

  function initMap() {
    map = L.map('map', { zoomControl: true, attributionControl: true }).setView([39.8, -98.6], 4);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }).addTo(map);
    camLayer = L.layerGroup().addTo(map);
    map.on('click', onMapClick);
    map.on('moveend', drawCameras);
    setTimeout(function () { map.invalidateSize(); }, 200);
  }

  function onMapClick(ev) {
    if (dropMode === 'start') {
      startPin = { lat: ev.latlng.lat, lon: ev.latlng.lng, label: 'Dropped start' };
      drawEnds();
      dropMode = null;
      markDropButtons();
      say('Start pin set. Search a destination or drop an end pin.');
      refreshNear(startPin.lat, startPin.lon);
      return;
    }
    if (dropMode === 'end') {
      setEnd(ev.latlng.lat, ev.latlng.lng, 'Dropped end');
      dropMode = null;
      markDropButtons();
    }
  }

  function markDropButtons() {
    document.getElementById('btnStartPin').classList.toggle('on', dropMode === 'start');
    document.getElementById('btnEndPin').classList.toggle('on', dropMode === 'end');
  }

  function setEnd(lat, lon, label) {
    endPin = { lat: lat, lon: lon, label: label || 'End' };
    drawEnds();
    map.setView([lat, lon], Math.max(map.getZoom(), 13));
    say('End set. Plan cloak when the start looks right.');
    refreshNear(lat, lon);
  }

  function drawEnds() {
    if (startMark) map.removeLayer(startMark);
    if (endMark) map.removeLayer(endMark);
    startMark = null;
    endMark = null;
    if (startPin) {
      startMark = L.circleMarker([startPin.lat, startPin.lon], {
        radius: 8, color: '#041018', weight: 2, fillColor: '#f5c542', fillOpacity: 1
      }).addTo(map).bindTooltip('Start', { permanent: false });
    }
    if (endPin) {
      endMark = L.circleMarker([endPin.lat, endPin.lon], {
        radius: 8, color: '#041018', weight: 2, fillColor: '#2ef5c9', fillOpacity: 1
      }).addTo(map).bindTooltip('End', { permanent: false });
    }
  }

  function drawPuck() {
    if (!fix) return;
    var ll = [fix.lat, fix.lon];
    if (!puck) {
      puck = L.circleMarker(ll, {
        radius: 8, color: '#041018', weight: 2, fillColor: '#00f3ff', fillOpacity: 1
      }).addTo(map);
    } else {
      puck.setLatLng(ll);
    }
    if (armed) drawBuffer();
  }

  function drawBuffer() {
    if (!fix) return;
    var ll = [fix.lat, fix.lon];
    if (!bufferRing) {
      bufferRing = L.circle(ll, {
        radius: bufferM(), color: '#f5c542', weight: 1, fillColor: '#f5c542', fillOpacity: 0.05
      }).addTo(map);
    } else {
      bufferRing.setLatLng(ll);
      bufferRing.setRadius(bufferM());
    }
  }

  function clearBuffer() {
    if (bufferRing) {
      map.removeLayer(bufferRing);
      bufferRing = null;
    }
  }

  function pinLabel(c) {
    var label = c.flock ? 'Flock' : 'ALPR';
    if (c.maker && c.maker.toLowerCase().indexOf('flock') < 0) label += ' · ' + c.maker;
    if (c.dir) label += ' · faces ' + c.dir;
    return label;
  }

  function drawCameras() {
    if (!camLayer || !map) return;
    camLayer.clearLayers();
    var bounds = map.getBounds();
    var center = map.getCenter();
    var rows = [];
    for (var i = 0; i < cameras.length; i++) {
      var c = cameras[i];
      if (!bounds.contains([c.lat, c.lon])) continue;
      rows.push(c);
    }
    if (rows.length > 700) {
      rows.sort(function (a, b) {
        return W.haversineM(center.lat, center.lng, a.lat, a.lon) -
          W.haversineM(center.lat, center.lng, b.lat, b.lon);
      });
      rows = rows.slice(0, 700);
    }
    for (var j = 0; j < rows.length; j++) {
      var pin = rows[j];
      L.circleMarker([pin.lat, pin.lon], {
        radius: pin.flock ? 6 : 4,
        color: pin.flock ? '#f5c542' : '#8b9bb0',
        weight: 1,
        fillColor: pin.flock ? '#f5c542' : '#445066',
        fillOpacity: 0.9
      }).bindTooltip(esc(pinLabel(pin)), { direction: 'top' }).addTo(camLayer);
    }
    paintHits(routeHits, true);
  }

  function paintHits(hits, keep) {
    if (!keep) routeHits = hits || [];
    var list = keep ? routeHits : hits;
    if (!list || !camLayer) return;
    for (var i = 0; i < list.length; i++) {
      var h = list[i];
      L.circleMarker([h.lat, h.lon], {
        radius: 9,
        color: '#ff4d6a',
        weight: 2,
        fillColor: h.flock ? '#f5c542' : '#ff4d6a',
        fillOpacity: 0.95
      }).bindTooltip(esc((h.flock ? 'Flock' : 'ALPR') + ' on the route · ' + W.formatKm(h.d)), { direction: 'top' })
        .addTo(camLayer);
    }
  }

  function refreshNear(lat, lon) {
    nearEl.textContent = '';
    if (lat == null) {
      if (!cameras.length) return;
      return;
    }
    var rows = W.nearestCameras(lat, lon, cameras, 6);
    if (!rows.length) {
      var li = document.createElement('li');
      li.textContent = cameras.length ? 'No saved pins near this point yet.' : 'No pins loaded yet.';
      nearEl.appendChild(li);
      return;
    }
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var item = document.createElement('li');
      item.textContent = pinLabel(row.camera) + ' · ' + W.formatKm(row.d) + ' · ' + W.compass(row.bearing);
      nearEl.appendChild(item);
    }
  }

  function covered(box) {
    var now = Date.now();
    for (var i = 0; i < boxes.length; i++) {
      var b = boxes[i];
      if (now - b.at > 12 * 3600 * 1000) continue;
      if (box.s >= b.s && box.n <= b.n && box.w >= b.w && box.e <= b.e) return true;
    }
    return false;
  }

  function boxTooWide(box) {
    return (box.n - box.s) > 3 || (box.e - box.w) > 3;
  }

  async function fetchOverpass(box, signal) {
    var body = 'data=' + encodeURIComponent(W.overpassQuery(box));
    var urls = [
      'https://overpass-api.de/api/interpreter',
      'https://overpass.kumi.systems/api/interpreter'
    ];
    var last = null;
    for (var i = 0; i < urls.length; i++) {
      try {
        var res = await fetch(urls[i], {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          body: body,
          signal: signal
        });
        if (!res.ok) throw new Error('Camera map answered ' + res.status);
        var json = await res.json();
        if (json.remark && !json.elements) throw new Error('Camera map timed out. Try a shorter trip.');
        return W.parseOverpass(json);
      } catch (e) {
        if (e && e.name === 'AbortError') throw e;
        last = e;
      }
    }
    throw last || new Error('Camera map did not answer.');
  }

  async function ensureCameras(box, signal) {
    if (boxTooWide(box)) throw new Error('That area is too large for one camera load. Zoom in or plan a shorter leg.');
    if (covered(box)) return 0;
    var incoming = await fetchOverpass(box, signal);
    var center = { lat: (box.s + box.n) / 2, lon: (box.w + box.e) / 2 };
    cameras = W.mergeCameras(cameras, incoming, center, 8000);
    boxes.push({
      s: box.s, w: box.w, n: box.n, e: box.e, at: Date.now()
    });
    saveCache(center);
    drawCameras();
    return incoming.length;
  }

  function corridorBox(a, b) {
    var s = Math.min(a.lat, b.lat);
    var n = Math.max(a.lat, b.lat);
    var w = Math.min(a.lon, b.lon);
    var e = Math.max(a.lon, b.lon);
    var km = Math.max(6, W.haversineM(a.lat, a.lon, b.lat, b.lon) / 1000 * 0.2);
    var padLat = km / 111.32;
    var mid = (a.lat + b.lat) / 2;
    var cos = Math.cos(mid * Math.PI / 180);
    var padLon = km / (111.32 * (Math.abs(cos) < 0.01 ? 0.01 : cos));
    return { s: s - padLat, w: w - padLon, n: n + padLat, e: e + padLon };
  }

  function flattenSteps(route) {
    var steps = [];
    var legs = route.legs || [];
    for (var i = 0; i < legs.length; i++) {
      var list = legs[i].steps || [];
      for (var j = 0; j < list.length; j++) {
        var step = list[j];
        var man = (step.maneuver && step.maneuver.type) || 'continue';
        var mod = (step.maneuver && step.maneuver.modifier) || '';
        if (man === 'arrive' || man === 'depart') continue;
        var text = (mod ? mod.replace(/_/g, ' ') + ' · ' : '') + (step.name || man.replace(/_/g, ' '));
        steps.push({ text: text, distanceM: step.distance || 0 });
      }
    }
    return steps.slice(0, 10);
  }

  async function osrm(points, alternatives, signal) {
    var path = points.map(function (p) {
      return Number(p.lon).toFixed(5) + ',' + Number(p.lat).toFixed(5);
    }).join(';');
    var q = '?overview=full&geometries=geojson&steps=true' + (alternatives ? '&alternatives=true' : '');
    var urls = [
      'https://router.project-osrm.org/route/v1/driving/' + path + q,
      'https://routing.openstreetmap.de/routed-car/route/v1/driving/' + path + q
    ];
    var last = null;
    for (var i = 0; i < urls.length; i++) {
      try {
        var res = await fetch(urls[i], { signal: signal });
        if (!res.ok) throw new Error('Router answered ' + res.status);
        var data = await res.json();
        if (!data.routes || !data.routes.length) {
          throw new Error(data.message || 'No driving route between those points.');
        }
        return data.routes.map(function (route) {
          return {
            coords: route.geometry.coordinates,
            distanceM: route.distance,
            durationS: route.duration,
            steps: flattenSteps(route)
          };
        });
      } catch (e) {
        if (e && e.name === 'AbortError') throw e;
        last = e;
      }
    }
    throw last || new Error('Router did not answer.');
  }

  function decorate(route, cams, kind) {
    var score = W.scoreRoute(route.coords, cams, bufferM());
    return {
      kind: kind,
      coords: route.coords,
      distanceM: route.distanceM,
      durationS: route.durationS,
      steps: route.steps,
      hits: score.hits,
      hitCount: score.hitCount,
      flockHits: score.flockHits,
      minD: score.minD
    };
  }

  function lineFrom(coords, style) {
    var latlngs = [];
    for (var i = 0; i < coords.length; i++) latlngs.push([coords[i][1], coords[i][0]]);
    return L.polyline(latlngs, style);
  }

  function drawRoutes(direct, chosen) {
    if (cloakLine) map.removeLayer(cloakLine);
    if (directLine) map.removeLayer(directLine);
    cloakLine = null;
    directLine = null;
    var same = chosen === direct || (chosen.kind === 'direct' && chosen.hitCount === direct.hitCount && chosen.distanceM === direct.distanceM);
    if (!same && direct.hitCount > chosen.hitCount) {
      directLine = lineFrom(direct.coords, { color: '#ff4d6a', weight: 3, opacity: 0.7, dashArray: '8 8' }).addTo(map);
    }
    cloakLine = lineFrom(chosen.coords, { color: '#2ef5c9', weight: 5, opacity: 0.95 }).addTo(map);
    routeHits = chosen.hits || [];
    drawCameras();
    map.fitBounds(cloakLine.getBounds(), { padding: [28, 28] });
  }

  function hitPhrase(route) {
    if (!route.hitCount) {
      var clear = route.minD == null
        ? 'No mapped pin within about 2 km of this line.'
        : 'Nearest mapped pin on this line is ' + W.formatKm(route.minD) + '.';
      return '0 pins inside ' + bufferM() + ' m. ' + clear;
    }
    var flock = route.flockHits ? ' (' + route.flockHits + ' tagged Flock)' : '';
    return route.hitCount + ' pin' + (route.hitCount === 1 ? '' : 's') + ' inside ' + bufferM() + ' m' + flock + '.';
  }

  function showResult(direct, chosen, avoid, tried) {
    resultEl.hidden = false;
    var title = document.getElementById('resultTitle');
    var body = document.getElementById('resultBody');
    var extra = document.getElementById('resultDirect');
    var steps = document.getElementById('steps');
    var clear = chosen.hitCount === 0;
    var usedDirect = chosen.kind === 'direct' && chosen.distanceM === direct.distanceM;
    title.textContent = clear
      ? (usedDirect ? 'Direct drive stays outside the buffer' : 'Cloak drive stays outside the buffer')
      : 'Fewest mapped pins';
    var meta = W.formatKm(chosen.distanceM) + ' · ' + W.formatMin(chosen.durationS);
    body.textContent = meta + '. ' + hitPhrase(chosen) + (avoid.fallback ? ' No Flock brand tag in this corridor, so every ALPR pin counts.' : '');
    if (!usedDirect) {
      var added = chosen.distanceM - direct.distanceM;
      extra.textContent = 'Direct line: ' + hitPhrase(direct) + ' ' + W.formatKm(direct.distanceM) +
        (added > 50 ? ' Cloak adds ' + W.formatKm(added) + '.' : '') +
        ' Tried ' + tried + ' drives.';
    } else if (!clear) {
      extra.textContent = 'Side streets still meet mapped pins inside the buffer. This is the quieter of ' + tried + ' drives.';
    } else {
      extra.textContent = 'Tried ' + tried + ' drives.';
    }
    steps.textContent = '';
    var list = chosen.steps || [];
    for (var i = 0; i < list.length; i++) {
      var li = document.createElement('li');
      li.textContent = list[i].text + ' · ' + W.formatKm(list[i].distanceM);
      steps.appendChild(li);
    }
  }

  async function plan() {
    var start = currentStart();
    if (!start) {
      say('Set a start. Use this phone, or drop a start pin.');
      return;
    }
    if (!endPin) {
      say('Search a destination or drop an end pin.');
      return;
    }
    if (planAbort) planAbort.abort();
    planAbort = new AbortController();
    var signal = planAbort.signal;
    planning = true;
    document.getElementById('btnPlan').disabled = true;
    say('Loading mapped cameras for the corridor…');
    try {
      var box = corridorBox(start, endPin);
      var loaded = await ensureCameras(box, signal);
      say(loaded ? ('Loaded ' + loaded + ' pins. Planning drives…') : 'Planning drives…');
      var directRoutes = await osrm([start, endPin], true, signal);
      var avoid = W.camerasForAvoidance(cameras, avoidAll());
      var scored = [];
      for (var i = 0; i < directRoutes.length; i++) {
        scored.push(decorate(directRoutes[i], avoid.cameras, i === 0 ? 'direct' : 'alt'));
      }
      var best = W.pickRoute(scored);
      if (best && best.hitCount > 0) {
        var vias = W.detourVias(best.coords, best.hits, avoid.cameras, bufferM());
        for (var v = 0; v < vias.length; v++) {
          var viaRoutes = await osrm([start, vias[v], endPin], false, signal);
          if (!viaRoutes.length) continue;
          var cand = decorate(viaRoutes[0], avoid.cameras, 'detour');
          if (!W.keepCandidate(directRoutes[0].distanceM, cand.distanceM)) continue;
          scored.push(cand);
        }
        best = W.pickRoute(scored);
      }
      var direct = scored[0];
      drawRoutes(direct, best);
      showResult(direct, best, avoid, scored.length);
      say(best.hitCount
        ? 'Cloak route still meets ' + best.hitCount + ' mapped pin' + (best.hitCount === 1 ? '' : 's') + ' inside the buffer.'
        : 'Cloak route stays outside the buffer for the pins loaded in this corridor.');
    } catch (e) {
      if (e && e.name === 'AbortError') return;
      say(e && e.message ? e.message : 'Route failed.');
    } finally {
      planning = false;
      document.getElementById('btnPlan').disabled = false;
    }
  }

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  async function nominatim(q) {
    var wait = Math.max(0, nextGeoAt - Date.now());
    nextGeoAt = Date.now() + wait + 1100;
    if (wait) await sleep(wait);
    var url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&q=' + encodeURIComponent(q);
    if (fix) {
      url += '&viewbox=' + [fix.lon - 0.6, fix.lat + 0.6, fix.lon + 0.6, fix.lat - 0.6].join(',') + '&bounded=0';
    }
    var res = await fetch(url, { headers: { 'Accept': 'application/json' } });
    if (!res.ok) throw new Error('Place search answered ' + res.status);
    var data = await res.json();
    var out = [];
    for (var i = 0; i < data.length; i++) {
      out.push({
        lat: Number(data[i].lat),
        lon: Number(data[i].lon),
        label: data[i].display_name
      });
    }
    return out;
  }

  function showHits(rows) {
    hitsEl.textContent = '';
    if (!rows.length) {
      hitsEl.hidden = true;
      say('No place matched that search.');
      return;
    }
    hitsEl.hidden = false;
    for (var i = 0; i < rows.length; i++) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = rows[i].label;
      btn.addEventListener('click', (function (row) {
        return function () {
          hitsEl.hidden = true;
          hitsEl.textContent = '';
          qEl.value = row.label;
          setEnd(row.lat, row.lon, row.label);
        };
      })(rows[i]));
      var li = document.createElement('li');
      li.appendChild(btn);
      hitsEl.appendChild(li);
    }
  }

  async function search() {
    var q = (qEl.value || '').trim();
    if (!q) {
      say('Type an address, a place, or coordinates like 30.27, -97.74.');
      return;
    }
    var parsed = W.parseLatLon(q);
    if (parsed) {
      hitsEl.hidden = true;
      setEnd(parsed.lat, parsed.lon, parsed.label);
      return;
    }
    say('Searching places…');
    try {
      var rows = await nominatim(q);
      showHits(rows);
      if (rows.length) say('Pick a place to set the end.');
    } catch (e) {
      say(e && e.message ? e.message : 'Place search failed.');
    }
  }

  function onFix(pos) {
    var c = pos.coords;
    var first = !fix;
    fix = {
      lat: c.latitude,
      lon: c.longitude,
      accuracy: c.accuracy,
      heading: c.heading,
      speed: c.speed
    };
    chip.textContent = 'GPS ± ' + (c.accuracy ? Math.round(c.accuracy) + ' m' : 'on');
    chip.classList.add('live');
    drawPuck();
    if (first) {
      map.setView([fix.lat, fix.lon], 14);
      ensureCameras(W.bboxAround(fix.lat, fix.lon, 8)).then(function () {
        refreshNear(fix.lat, fix.lon);
      }).catch(function (e) {
        say(e && e.message ? e.message : 'Could not load cameras around this phone.');
        refreshNear(fix.lat, fix.lon);
      });
    } else {
      refreshNear(fix.lat, fix.lon);
    }
    if (armed) checkAhead();
  }

  function onFixErr(err) {
    chip.classList.remove('live');
    if (err && err.code === 1) {
      chip.textContent = 'GPS blocked';
      say('Location permission is off for this site. You can still drop pins or paste coordinates.');
      return;
    }
    chip.textContent = 'GPS wait';
    say('This phone has not returned a fix yet.');
  }

  function startWatch() {
    if (!secureEnough()) {
      showBanner('Live GPS needs a secure page. On the phone open <a href="' + PAGES + '">Wolven-cloak on GitHub Pages</a>. This address can still search places, take coordinates, and plan from pins you drop.');
      say('GPS stays off on a plain http link. Drop pins or paste coordinates.');
      return;
    }
    if (!navigator.geolocation) {
      say('This browser has no location services.');
      return;
    }
    if (watchId != null) {
      say('Already watching this phone.');
      return;
    }
    chip.textContent = 'GPS…';
    say('Asking this phone for a high-accuracy fix.');
    watchId = navigator.geolocation.watchPosition(onFix, onFixErr, {
      enableHighAccuracy: true,
      maximumAge: 2000,
      timeout: 15000
    });
  }

  function checkAhead() {
    if (!fix) return;
    var moving = fix.speed != null && fix.speed > 1.5 && fix.heading != null && !isNaN(fix.heading);
    var heading = moving ? fix.heading : null;
    var look = moving ? 800 : bufferM();
    var avoid = W.camerasForAvoidance(cameras, avoidAll());
    var rows = W.aheadCameras(fix.lat, fix.lon, heading, avoid.cameras, bufferM(), look);
    var nowInside = {};
    var fresh = null;
    for (var i = 0; i < rows.length; i++) {
      if (!rows[i].inBuffer) continue;
      var id = rows[i].camera.id;
      nowInside[id] = true;
      if (!insideIds[id] && !fresh) fresh = rows[i];
    }
    insideIds = nowInside;
    if (!rows.length) {
      chip.textContent = 'Watch clear';
      return;
    }
    var top = rows[0];
    var name = top.camera.flock ? 'Flock pin' : 'ALPR pin';
    chip.textContent = top.inBuffer ? 'Inside buffer' : 'Pin ahead';
    chip.classList.toggle('live', !top.inBuffer);
    say(name + ' ' + W.formatKm(top.d) + (top.inBuffer ? ' — inside the buffer.' : ' ahead.'));
    if (fresh) {
      var vib = document.getElementById('vibrate');
      if (vib && vib.checked && navigator.vibrate) navigator.vibrate([80, 40, 120]);
      var speak = document.getElementById('speak');
      if (speak && speak.checked && window.speechSynthesis) {
        var utter = new SpeechSynthesisUtterance(name + ' ' + Math.round(fresh.d) + ' meters');
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utter);
      }
    }
  }

  function toggleArm() {
    var btn = document.getElementById('btnArm');
    if (armed) {
      armed = false;
      insideIds = {};
      clearBuffer();
      btn.classList.remove('on');
      btn.textContent = 'Arm watch';
      say('Watch off.');
      if (fix) {
        chip.textContent = 'GPS ± ' + (fix.accuracy ? Math.round(fix.accuracy) + ' m' : 'on');
        chip.classList.add('live');
      }
      return;
    }
    if (!fix) {
      startWatch();
      say('Arm turns on after this phone has a fix.');
      btn.dataset.armWhenFix = '1';
      return;
    }
    armed = true;
    btn.classList.add('on');
    btn.textContent = 'Watching';
    btn.dataset.armWhenFix = '';
    drawBuffer();
    checkAhead();
  }

  function bootBanner() {
    if (!secureEnough()) {
      showBanner('Live GPS needs a secure page. On the phone open <a href="' + PAGES + '">Wolven-cloak on GitHub Pages</a>. You can still search places, paste coordinates, and drop pins here.');
    }
  }

  function bind() {
    document.getElementById('btnGps').addEventListener('click', startWatch);
    document.getElementById('btnStartPin').addEventListener('click', function () {
      dropMode = dropMode === 'start' ? null : 'start';
      markDropButtons();
      say(dropMode === 'start' ? 'Tap the map to set the start.' : 'Start drop cancelled.');
    });
    document.getElementById('btnEndPin').addEventListener('click', function () {
      dropMode = dropMode === 'end' ? null : 'end';
      markDropButtons();
      say(dropMode === 'end' ? 'Tap the map to set the end.' : 'End drop cancelled.');
    });
    document.getElementById('btnSearch').addEventListener('click', search);
    qEl.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') {
        ev.preventDefault();
        search();
      }
    });
    document.getElementById('bufferSeg').addEventListener('click', function (ev) {
      var btn = ev.target.closest('button');
      if (!btn) return;
      setBuffer(Number(btn.getAttribute('data-m')));
    });
    document.getElementById('avoidAll').addEventListener('change', savePrefs);
    document.getElementById('vibrate').addEventListener('change', savePrefs);
    document.getElementById('speak').addEventListener('change', savePrefs);
    document.getElementById('btnPlan').addEventListener('click', plan);
    document.getElementById('btnArm').addEventListener('click', toggleArm);
    document.getElementById('btnCameras').addEventListener('click', function () {
      var b = map.getBounds();
      var box = { s: b.getSouth(), w: b.getWest(), n: b.getNorth(), e: b.getEast() };
      say('Loading cameras in view…');
      ensureCameras(box).then(function (n) {
        var here = fix || startPin || endPin;
        if (here) refreshNear(here.lat, here.lon);
        say(n ? ('Loaded ' + n + ' pins in view.') : 'This view is already loaded.');
      }).catch(function (e) {
        say(e && e.message ? e.message : 'Could not load cameras.');
      });
    });
    document.getElementById('btnClearCache').addEventListener('click', function () {
      cameras = [];
      boxes = [];
      try { localStorage.removeItem(CACHE_KEY); } catch (e) { /* ignore */ }
      drawCameras();
      nearEl.textContent = '';
      say('Saved pins cleared. The next plan loads them again.');
    });
    window.addEventListener('resize', function () {
      if (map) map.invalidateSize();
    });
  }

  if (!W || !window.L) {
    document.body.setAttribute('data-boot', 'missing');
    say('Map library failed to load.');
    return;
  }

  loadPrefs();
  setBuffer(buffer);
  loadCache();
  initMap();
  drawCameras();
  bind();
  bootBanner();
  var orig = onFix;
  onFix = function (pos) {
    var was = fix;
    orig(pos);
    var btn = document.getElementById('btnArm');
    if (!was && fix && btn && btn.dataset.armWhenFix === '1' && !armed) toggleArm();
  };
  document.body.setAttribute('data-boot', 'ready');
  if (cameras.length) say('Saved pins are on the map. Use this phone or search a destination.');
})();
