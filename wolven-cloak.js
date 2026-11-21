/* Wolven-cloak — distance math for routes around mapped ALPR pins.
   Camera pins are public OpenStreetMap tags. This file does not call the network. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.WolvenCloak = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  var EARTH_M = 6371000;

  function haversineM(lat1, lon1, lat2, lon2) {
    var p1 = lat1 * Math.PI / 180;
    var p2 = lat2 * Math.PI / 180;
    var dphi = (lat2 - lat1) * Math.PI / 180;
    var dl = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dphi / 2) * Math.sin(dphi / 2) +
      Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return 2 * EARTH_M * Math.asin(Math.min(1, Math.sqrt(a)));
  }

  function bearingDeg(lat1, lon1, lat2, lon2) {
    var p1 = lat1 * Math.PI / 180;
    var p2 = lat2 * Math.PI / 180;
    var dl = (lon2 - lon1) * Math.PI / 180;
    var y = Math.sin(dl) * Math.cos(p2);
    var x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  }

  function angleDelta(a, b) {
    var d = Math.abs(a - b) % 360;
    return d > 180 ? 360 - d : d;
  }

  function compass(deg) {
    var names = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    if (deg == null || isNaN(deg)) return '';
    return names[Math.round(((deg % 360) + 360) % 360 / 45) % 8];
  }

  function offsetPoint(lat, lon, bearing, distM) {
    var delta = distM / EARTH_M;
    var theta = bearing * Math.PI / 180;
    var p1 = lat * Math.PI / 180;
    var l1 = lon * Math.PI / 180;
    var p2 = Math.asin(Math.sin(p1) * Math.cos(delta) + Math.cos(p1) * Math.sin(delta) * Math.cos(theta));
    var l2 = l1 + Math.atan2(
      Math.sin(theta) * Math.sin(delta) * Math.cos(p1),
      Math.cos(delta) - Math.sin(p1) * Math.sin(p2)
    );
    return { lat: p2 * 180 / Math.PI, lon: ((l2 * 180 / Math.PI + 540) % 360) - 180 };
  }

  /** Meters from a point to a segment. Local equirectangular, fine under a few km. */
  function pointSegDistM(lat, lon, lat1, lon1, lat2, lon2) {
    var lat0 = lat * Math.PI / 180;
    var mLat = 111132;
    var mLon = 111320 * Math.cos(lat0);
    var x = (lon - lon1) * mLon;
    var y = (lat - lat1) * mLat;
    var dx = (lon2 - lon1) * mLon;
    var dy = (lat2 - lat1) * mLat;
    var len2 = dx * dx + dy * dy;
    var t = len2 > 0 ? (x * dx + y * dy) / len2 : 0;
    if (t < 0) t = 0;
    else if (t > 1) t = 1;
    var px = x - t * dx;
    var py = y - t * dy;
    return Math.sqrt(px * px + py * py);
  }

  function distToPolylineM(lat, lon, coords) {
    if (!coords || !coords.length) return Infinity;
    if (coords.length === 1) return haversineM(lat, lon, coords[0][1], coords[0][0]);
    var best = Infinity;
    var bestI = 0;
    var step = coords.length > 1200 ? 2 : 1;
    for (var i = 0; i < coords.length; i += step) {
      var d = haversineM(lat, lon, coords[i][1], coords[i][0]);
      if (d < best) {
        best = d;
        bestI = i;
      }
    }
    var i0 = Math.max(0, bestI - step);
    var i1 = Math.min(coords.length - 2, bestI + step);
    for (var s = i0; s <= i1; s++) {
      var sd = pointSegDistM(lat, lon, coords[s][1], coords[s][0], coords[s + 1][1], coords[s + 1][0]);
      if (sd < best) best = sd;
    }
    return best;
  }

  function isFlock(tags) {
    if (!tags) return false;
    var blob = [tags.manufacturer, tags.brand, tags.operator, tags.name, tags['surveillance:model'], tags.model]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return blob.indexOf('flock') >= 0;
  }

  function parseOverpass(data) {
    var out = [];
    var elements = (data && data.elements) || [];
    for (var i = 0; i < elements.length; i++) {
      var el = elements[i];
      var lat = el.lat != null ? el.lat : (el.center && el.center.lat);
      var lon = el.lon != null ? el.lon : (el.center && el.center.lon);
      if (lat == null || lon == null) continue;
      var tags = el.tags || {};
      var flock = isFlock(tags);
      out.push({
        id: (el.type || 'n') + '/' + el.id,
        lat: lat,
        lon: lon,
        flock: flock,
        name: tags.name || tags.manufacturer || (flock ? 'Flock Safety' : 'ALPR'),
        maker: tags.manufacturer || tags.brand || '',
        dir: tags['camera:direction'] || tags.direction || tags['surveillance:direction'] || ''
      });
    }
    return out;
  }

  function routeBBox(coords, padDeg) {
    var s = 90;
    var w = 180;
    var n = -90;
    var e = -180;
    for (var i = 0; i < coords.length; i++) {
      var lon = coords[i][0];
      var lat = coords[i][1];
      if (lat < s) s = lat;
      if (lat > n) n = lat;
      if (lon < w) w = lon;
      if (lon > e) e = lon;
    }
    var pad = padDeg || 0;
    return { s: s - pad, w: w - pad, n: n + pad, e: e + pad };
  }

  function inBBox(lat, lon, box) {
    return lat >= box.s && lat <= box.n && lon >= box.w && lon <= box.e;
  }

  function scoreRoute(coords, cameras, bufferM) {
    var hits = [];
    var minD = null;
    if (!coords || coords.length < 2) {
      return { hits: hits, hitCount: 0, flockHits: 0, minD: null };
    }
    var pad = Math.max(0.02, (bufferM || 250) / 111320 * 4);
    var box = routeBBox(coords, pad);
    for (var i = 0; i < cameras.length; i++) {
      var c = cameras[i];
      if (!inBBox(c.lat, c.lon, box)) continue;
      var d = distToPolylineM(c.lat, c.lon, coords);
      if (minD == null || d < minD) minD = d;
      if (d <= bufferM) {
        hits.push({ id: c.id, d: d, lat: c.lat, lon: c.lon, flock: !!c.flock, name: c.name || '' });
      }
    }
    var flockHits = 0;
    for (var h = 0; h < hits.length; h++) if (hits[h].flock) flockHits++;
    return { hits: hits, hitCount: hits.length, flockHits: flockHits, minD: minD };
  }

  function pickRoute(scored) {
    var list = (scored || []).slice();
    list.sort(function (a, b) {
      if (a.hitCount !== b.hitCount) return a.hitCount - b.hitCount;
      var am = a.minD == null ? 1e12 : a.minD;
      var bm = b.minD == null ? 1e12 : b.minD;
      if (am !== bm) return bm - am;
      return (a.distanceM || 0) - (b.distanceM || 0);
    });
    return list[0] || null;
  }

  function countNear(point, cameras, radiusM) {
    var n = 0;
    for (var i = 0; i < cameras.length; i++) {
      if (haversineM(point.lat, point.lon, cameras[i].lat, cameras[i].lon) <= radiusM) n++;
    }
    return n;
  }

  function detourVias(coords, hits, cameras, bufferM) {
    if (!hits || !hits.length || !coords || coords.length < 2) return [];
    var placed = [];
    var step = Math.max(1, Math.floor(coords.length / 200));
    for (var h = 0; h < hits.length; h++) {
      var hit = hits[h];
      var bestI = 0;
      var bestD = Infinity;
      for (var i = 0; i < coords.length; i += step) {
        var d = haversineM(hit.lat, hit.lon, coords[i][1], coords[i][0]);
        if (d < bestD) {
          bestD = d;
          bestI = i;
        }
      }
      placed.push({ i: bestI });
    }
    placed.sort(function (a, b) { return a.i - b.i; });
    var picks = [];
    var gap = Math.max(8, Math.floor(coords.length * 0.08));
    for (var p = 0; p < placed.length && picks.length < 3; p++) {
      if (picks.length && placed[p].i - picks[picks.length - 1].i < gap) continue;
      picks.push(placed[p]);
    }
    var pushM = Math.max(350, bufferM * 2.4);
    var nearR = bufferM * 1.6;
    var vias = [];
    for (var k = 0; k < picks.length; k++) {
      var idx = Math.min(coords.length - 2, picks[k].i);
      var b = bearingDeg(coords[idx][1], coords[idx][0], coords[idx + 1][1], coords[idx + 1][0]);
      var left = offsetPoint(coords[idx][1], coords[idx][0], b - 90, pushM);
      var right = offsetPoint(coords[idx][1], coords[idx][0], b + 90, pushM);
      var quieter = countNear(left, cameras, nearR) <= countNear(right, cameras, nearR) ? left : right;
      vias.push(quieter);
    }
    return vias;
  }

  function camerasForAvoidance(cameras, avoidAll) {
    if (avoidAll) return { cameras: cameras || [], fallback: false };
    var flock = [];
    for (var i = 0; i < (cameras || []).length; i++) {
      if (cameras[i].flock) flock.push(cameras[i]);
    }
    if (flock.length) return { cameras: flock, fallback: false };
    return { cameras: cameras || [], fallback: true };
  }

  function keepCandidate(directDistanceM, candidateDistanceM) {
    if (!directDistanceM || !candidateDistanceM) return true;
    return candidateDistanceM <= directDistanceM * 2.2;
  }

  function nearestCameras(lat, lon, cameras, limit) {
    var rows = [];
    for (var i = 0; i < cameras.length; i++) {
      var c = cameras[i];
      var d = haversineM(lat, lon, c.lat, c.lon);
      rows.push({
        camera: c,
        d: d,
        bearing: bearingDeg(lat, lon, c.lat, c.lon)
      });
    }
    rows.sort(function (a, b) { return a.d - b.d; });
    return rows.slice(0, limit || 8);
  }

  function aheadCameras(lat, lon, heading, cameras, bufferM, lookaheadM) {
    var out = [];
    var moving = heading != null && !isNaN(heading);
    for (var i = 0; i < cameras.length; i++) {
      var c = cameras[i];
      var d = haversineM(lat, lon, c.lat, c.lon);
      if (d > lookaheadM) continue;
      if (moving && d > 15) {
        var b = bearingDeg(lat, lon, c.lat, c.lon);
        var inFront = angleDelta(heading, b) <= 55;
        if (!inFront && d > bufferM) continue;
      }
      out.push({ camera: c, d: d, inBuffer: d <= bufferM });
    }
    out.sort(function (a, b) { return a.d - b.d; });
    return out;
  }

  function parseLatLon(q) {
    var m = /^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/.exec(q || '');
    if (!m) return null;
    var lat = Number(m[1]);
    var lon = Number(m[2]);
    if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
    return { lat: lat, lon: lon, label: lat.toFixed(5) + ', ' + lon.toFixed(5) };
  }

  function bboxAround(lat, lon, km) {
    var dLat = km / 111.32;
    var cos = Math.cos(lat * Math.PI / 180);
    var dLon = km / (111.32 * (Math.abs(cos) < 0.01 ? 0.01 : cos));
    return { s: lat - dLat, w: lon - dLon, n: lat + dLat, e: lon + dLon };
  }

  function mergeCameras(existing, incoming, center, maxKeep) {
    var map = {};
    var list = (existing || []).concat(incoming || []);
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      if (!c || c.lat == null || c.lon == null) continue;
      var id = c.id || (c.lat.toFixed(5) + ',' + c.lon.toFixed(5));
      map[id] = {
        id: id,
        lat: c.lat,
        lon: c.lon,
        flock: !!c.flock,
        name: c.name || '',
        maker: c.maker || '',
        dir: c.dir || ''
      };
    }
    var merged = [];
    for (var k in map) merged.push(map[k]);
    var cap = maxKeep || 8000;
    if (merged.length > cap && center) {
      merged.sort(function (a, b) {
        return haversineM(center.lat, center.lon, a.lat, a.lon) -
          haversineM(center.lat, center.lon, b.lat, b.lon);
      });
      merged = merged.slice(0, cap);
    }
    return merged;
  }

  function overpassQuery(box) {
    var b = [box.s, box.w, box.n, box.e].map(function (n) { return Number(n).toFixed(5); }).join(',');
    return '[out:json][timeout:25];(' +
      'node["surveillance:type"="ALPR"](' + b + ');' +
      'node["surveillance"="ALPR"](' + b + ');' +
      'node["surveillance:type"="alpr"](' + b + ');' +
      'way["surveillance:type"="ALPR"](' + b + ');' +
      'way["surveillance"="ALPR"](' + b + ');' +
      'way["surveillance:type"="alpr"](' + b + ');' +
      ');out center tags;';
  }

  function formatKm(meters) {
    if (meters == null || !isFinite(meters)) return '—';
    if (meters < 1000) return Math.round(meters) + ' m';
    return (meters / 1000).toFixed(1) + ' km';
  }

  function formatMin(seconds) {
    if (seconds == null || !isFinite(seconds)) return '';
    var m = Math.max(1, Math.round(seconds / 60));
    if (m < 60) return m + ' min';
    var h = Math.floor(m / 60);
    return h + ' h ' + (m % 60) + ' min';
  }

  function selfTest() {
    var failures = [];
    function check(name, cond) {
      if (!cond) failures.push(name);
    }
    var onSeg = pointSegDistM(30.27, -97.74, 30.27, -97.76, 30.27, -97.72);
    check('point on segment', onSeg < 2);
    var north = pointSegDistM(30.27 + (100 / 111132), -97.74, 30.27, -97.76, 30.27, -97.72);
    check('100m off segment', Math.abs(north - 100) < 15);

    var cam = [{ id: 'a', lat: 30.27, lon: -97.74, flock: true, name: 'Flock Safety' }];
    var through = [[-97.76, 30.27], [-97.72, 30.27]];
    var clear = [[-97.76, 30.27 + 0.0072], [-97.72, 30.27 + 0.0072]];
    var hit = scoreRoute(through, cam, 250);
    var miss = scoreRoute(clear, cam, 250);
    check('route through pin hits', hit.hitCount === 1 && hit.flockHits === 1);
    check('parallel route misses', miss.hitCount === 0 && miss.minD > 700);

    var chosen = pickRoute([
      { hitCount: hit.hitCount, minD: hit.minD, distanceM: 4000, id: 'direct' },
      { hitCount: miss.hitCount, minD: miss.minD, distanceM: 4500, id: 'cloak' }
    ]);
    check('pick clear route', chosen && chosen.id === 'cloak');

    check('flock tag', isFlock({ manufacturer: 'Flock Safety' }));
    check('other maker', !isFlock({ manufacturer: 'Genetec' }));

    var moved = offsetPoint(30.27, -97.74, 90, 400);
    var movedD = haversineM(30.27, -97.74, moved.lat, moved.lon);
    check('offset 400m', Math.abs(movedD - 400) < 30);

    var parsed = parseOverpass({
      elements: [
        { type: 'node', id: 1, lat: 1, lon: 2, tags: { manufacturer: 'Flock Safety', 'camera:direction': 'N' } },
        { type: 'way', id: 2, center: { lat: 3, lon: 4 }, tags: { surveillance: 'ALPR' } }
      ]
    });
    check('parse node and way', parsed.length === 2 && parsed[0].flock && parsed[0].dir === 'N' && !parsed[1].flock);

    var vias = detourVias(through, hit.hits, cam, 250);
    check('detour via exists', vias.length === 1);
    if (vias.length) {
      var away = haversineM(30.27, -97.74, vias[0].lat, vias[0].lon);
      check('detour steps off the pin', away > 300);
    }

    var set = camerasForAvoidance([{ flock: false }, { flock: true }], false);
    check('flock filter', set.cameras.length === 1 && !set.fallback);
    var fallback = camerasForAvoidance([{ flock: false }], false);
    check('fallback when no flock tags', fallback.fallback && fallback.cameras.length === 1);

    check('keep sane detour', keepCandidate(10000, 18000) && !keepCandidate(10000, 25000));
    var near = nearestCameras(30.27, -97.74, [
      { id: 'far', lat: 30.5, lon: -97.74 },
      { id: 'near', lat: 30.271, lon: -97.74 }
    ], 1);
    check('nearest', near.length === 1 && near[0].camera.id === 'near');

    var ahead = aheadCameras(30.27, -97.75, 90, cam, 250, 2000);
    check('ahead cone', ahead.length === 1);
    var behind = aheadCameras(30.27, -97.73, 90, cam, 250, 2000);
    check('behind pin ignored', behind.length === 0);

    var ll = parseLatLon('30.27, -97.74');
    check('parse latlon', ll && Math.abs(ll.lat - 30.27) < 1e-9 && ll.lon === -97.74);
    check('reject bad latlon', parseLatLon('nope') === null);

    var box = bboxAround(30.27, -97.74, 8);
    check('bbox', box.n > box.s && box.e > box.w);
    var q = overpassQuery(box);
    check('overpass has ALPR', q.indexOf('surveillance:type"="ALPR"') > 0 && q.indexOf('out center') > 0);

    var merged = mergeCameras(
      [{ id: 'a', lat: 1, lon: 2, flock: false }],
      [{ id: 'a', lat: 1, lon: 2, flock: true, name: 'Flock Safety' }, { id: 'b', lat: 9, lon: 9, flock: false }],
      { lat: 1, lon: 2 },
      8000
    );
    check('merge prefers later id', merged.length === 2 && merged.filter(function (c) { return c.id === 'a' && c.flock; }).length === 1);

    check('km format', formatKm(180) === '180 m' && formatKm(14100) === '14.1 km');
    check('compass', compass(0) === 'N' && compass(45) === 'NE');

    return { ok: failures.length === 0, failures: failures, checks: 20 };
  }

  return {
    haversineM: haversineM,
    bearingDeg: bearingDeg,
    angleDelta: angleDelta,
    compass: compass,
    offsetPoint: offsetPoint,
    pointSegDistM: pointSegDistM,
    distToPolylineM: distToPolylineM,
    isFlock: isFlock,
    parseOverpass: parseOverpass,
    routeBBox: routeBBox,
    scoreRoute: scoreRoute,
    pickRoute: pickRoute,
    detourVias: detourVias,
    camerasForAvoidance: camerasForAvoidance,
    keepCandidate: keepCandidate,
    nearestCameras: nearestCameras,
    aheadCameras: aheadCameras,
    parseLatLon: parseLatLon,
    bboxAround: bboxAround,
    mergeCameras: mergeCameras,
    overpassQuery: overpassQuery,
    formatKm: formatKm,
    formatMin: formatMin,
    selfTest: selfTest
  };
});
