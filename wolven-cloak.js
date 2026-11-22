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
        hits.push({ id: c.id, d: d, lat: c.lat, lon: c.lon, flock: !!c.flock, name: c.name || '', dir: c.dir || '' });
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

  var CARDINAL = {
    n: 0, nne: 22.5, ne: 45, ene: 67.5, e: 90, ese: 112.5, se: 135, sse: 157.5,
    s: 180, ssw: 202.5, sw: 225, wsw: 247.5, w: 270, wnw: 292.5, nw: 315, nnw: 337.5
  };

  function oneBearing(token) {
    var t = String(token || '').trim().toLowerCase();
    if (!t) return null;
    if (Object.prototype.hasOwnProperty.call(CARDINAL, t)) return CARDINAL[t];
    if (/^-?\d+(?:\.\d+)?$/.test(t)) {
      var n = Number(t);
      if (n >= 0 && n <= 360) return n % 360;
    }
    return null;
  }

  /** Mapped camera facing. Bearing is degrees clockwise from north. Null when the tag has no direction. */
  function parseFacing(dir) {
    if (dir == null) return null;
    var raw = String(dir).trim();
    if (!raw || /forward|backward|both|all/i.test(raw)) return null;
    var parts = raw.split(/\s*(?:-|;|–|to)\s*/i).filter(Boolean);
    var a = oneBearing(parts[0]);
    if (a == null) return null;
    if (parts.length < 2) {
      return { bearing: a, span: 50, label: compass(a) };
    }
    var b = oneBearing(parts[1]);
    if (b == null) return { bearing: a, span: 50, label: compass(a) };
    var cw = (b - a + 360) % 360;
    var start = a;
    var span = cw;
    if (cw > 180) {
      start = b;
      span = 360 - cw;
    }
    if (span < 16) span = 16;
    return { bearing: (start + span / 2) % 360, span: span, label: compass((start + span / 2) % 360) };
  }

  /** Geographic wedge in front of a camera. Ring is [lat, lon] for a map polygon. */
  function wedgeRing(lat, lon, bearing, span, lengthM) {
    var wide = span == null ? 50 : span;
    if (wide < 16) wide = 16;
    if (wide > 120) wide = 120;
    var reach = lengthM || 90;
    var steps = Math.max(2, Math.round(wide / 14));
    var begin = bearing - wide / 2;
    var ring = [[lat, lon]];
    for (var i = 0; i <= steps; i++) {
      var p = offsetPoint(lat, lon, begin + wide * (i / steps), reach);
      ring.push([p.lat, p.lon]);
    }
    ring.push([lat, lon]);
    return ring;
  }

  function junctionKind(type) {
    if (type === 'merge') return 'merge';
    if (type === 'turn' || type === 'end of road' || type === 'fork' ||
        type === 'roundabout' || type === 'rotary' || type === 'exit roundabout' ||
        type === 'exit rotary' || type === 'on ramp' || type === 'off ramp') return 'turn';
    return '';
  }

  function junctionLabel(step) {
    var kind = junctionKind(step && step.type);
    if (!kind) return '';
    var mod = String((step && step.modifier) || '').replace(/_/g, ' ');
    if (kind === 'merge') return mod ? ('Merge ' + mod) : 'Merge';
    if (step.type === 'roundabout' || step.type === 'rotary' || step.type === 'exit roundabout' || step.type === 'exit rotary') return 'Roundabout';
    if (step.type === 'on ramp') return 'On ramp';
    if (step.type === 'off ramp') return 'Off ramp';
    return mod ? ('Turn ' + mod) : 'Turn';
  }

  function buildAnchors(start, end, rawSteps) {
    var mids = [];
    var steps = rawSteps || [];
    for (var i = 0; i < steps.length; i++) {
      var step = steps[i];
      var kind = junctionKind(step.type);
      if (!kind || step.lat == null || step.lon == null) continue;
      var last = mids[mids.length - 1];
      if (last && haversineM(last.lat, last.lon, step.lat, step.lon) < 35) continue;
      mids.push({
        lat: step.lat,
        lon: step.lon,
        kind: kind,
        label: junctionLabel(step)
      });
    }
    if (mids.length > 40) {
      var trimmed = [];
      for (var k = 0; k < 40; k++) {
        trimmed.push(mids[Math.round(k * (mids.length - 1) / 39)]);
      }
      mids = trimmed;
    }
    return [{ lat: start.lat, lon: start.lon, kind: 'start', label: 'Start' }]
      .concat(mids)
      .concat([{ lat: end.lat, lon: end.lon, kind: 'end', label: 'End' }]);
  }

  function closestIndex(coords, lat, lon, from) {
    var bestI = from;
    var best = Infinity;
    for (var i = from; i < coords.length; i++) {
      var d = haversineM(lat, lon, coords[i][1], coords[i][0]);
      if (d < best) {
        best = d;
        bestI = i;
      }
    }
    return bestI;
  }

  /** Split a [lon, lat] line at anchors. Legs between unmoved anchors stay intact when one pin is swapped. */
  function sliceLegs(coords, anchors) {
    var legs = [];
    if (!coords || coords.length < 2 || !anchors || anchors.length < 2) return legs;
    var idxs = [0];
    var from = 0;
    for (var a = 1; a < anchors.length - 1; a++) {
      var idx = closestIndex(coords, anchors[a].lat, anchors[a].lon, from);
      if (idx <= from) idx = Math.min(coords.length - 1, from + 1);
      idxs.push(idx);
      from = idx;
    }
    idxs.push(coords.length - 1);
    for (var i = 0; i < idxs.length - 1; i++) {
      var slice = coords.slice(idxs[i], idxs[i + 1] + 1);
      if (slice.length < 2) {
        var p = coords[idxs[i]] || coords[0];
        var q = coords[Math.min(coords.length - 1, idxs[i + 1])] || p;
        slice = [p, q];
      }
      legs.push(slice);
    }
    return legs;
  }

  function joinLegs(legs) {
    var out = [];
    for (var i = 0; i < (legs || []).length; i++) {
      var leg = legs[i] || [];
      for (var j = (i === 0 ? 0 : 1); j < leg.length; j++) out.push(leg[j]);
    }
    return out;
  }

  function pathLengthM(coords) {
    var meters = 0;
    if (!coords || coords.length < 2) return 0;
    for (var i = 1; i < coords.length; i++) {
      meters += haversineM(coords[i - 1][1], coords[i - 1][0], coords[i][1], coords[i][0]);
    }
    return meters;
  }

  function flockAlong(coords, cameras, radiusM) {
    var hits = [];
    if (!coords || coords.length < 2) return hits;
    var pad = Math.max(0.02, (radiusM || 400) / 111320 * 4);
    var box = routeBBox(coords, pad);
    for (var i = 0; i < (cameras || []).length; i++) {
      var c = cameras[i];
      if (!c.flock || !inBBox(c.lat, c.lon, box)) continue;
      var d = distToPolylineM(c.lat, c.lon, coords);
      if (d > radiusM) continue;
      hits.push({
        id: c.id,
        lat: c.lat,
        lon: c.lon,
        flock: true,
        name: c.name || 'Flock Safety',
        dir: c.dir || '',
        d: d,
        facing: parseFacing(c.dir)
      });
    }
    hits.sort(function (a, b) { return a.d - b.d; });
    return hits;
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

  function wrapBearing(deg) {
    return ((deg % 360) + 360) % 360;
  }

  /** Signed shortest turn, degrees in (-180, 180]. */
  function turnToward(from, to) {
    var d = wrapBearing(to) - wrapBearing(from);
    if (d > 180) d -= 360;
    if (d <= -180) d += 360;
    return d;
  }

  /** Ease a heading so a noisy fix does not spin the map. alpha is 0..1. */
  function smoothBearing(prev, next, alpha) {
    if (next == null || isNaN(next)) {
      return prev == null || isNaN(prev) ? 0 : wrapBearing(prev);
    }
    if (prev == null || isNaN(prev)) return wrapBearing(next);
    var a = alpha == null ? 0.45 : alpha;
    if (a < 0) a = 0;
    if (a > 1) a = 1;
    return wrapBearing(prev + turnToward(prev, next) * a);
  }

  function projectSeg(lat, lon, lat1, lon1, lat2, lon2) {
    var mLat = 111132;
    var mLon = 111320 * Math.cos(lat * Math.PI / 180);
    if (Math.abs(mLon) < 1) mLon = 1;
    var x = (lon - lon1) * mLon;
    var y = (lat - lat1) * mLat;
    var dx = (lon2 - lon1) * mLon;
    var dy = (lat2 - lat1) * mLat;
    var len2 = dx * dx + dy * dy;
    var t = len2 > 0 ? (x * dx + y * dy) / len2 : 0;
    if (t < 0) t = 0;
    else if (t > 1) t = 1;
    var px = t * dx;
    var py = t * dy;
    return {
      t: t,
      d: Math.sqrt((x - px) * (x - px) + (y - py) * (y - py)),
      lat: lat1 + (py / mLat),
      lon: lon1 + (px / mLon)
    };
  }

  /** Where a phone sits on a [lon, lat] line: distance along, distance off, and the travel bearing. */
  function progressOnLine(lat, lon, coords) {
    if (!coords || coords.length < 2 || lat == null || lon == null) return null;
    var bestI = 0;
    var best = Infinity;
    var step = coords.length > 1600 ? 4 : 1;
    for (var i = 0; i < coords.length; i += step) {
      var d = haversineM(lat, lon, coords[i][1], coords[i][0]);
      if (d < best) {
        best = d;
        bestI = i;
      }
    }
    var i0 = Math.max(0, bestI - step);
    var i1 = Math.min(coords.length - 2, bestI + step);
    var seg = i0;
    var proj = null;
    var off = Infinity;
    for (var s = i0; s <= i1; s++) {
      var hit = projectSeg(lat, lon, coords[s][1], coords[s][0], coords[s + 1][1], coords[s + 1][0]);
      if (hit.d < off) {
        off = hit.d;
        seg = s;
        proj = hit;
      }
    }
    if (!proj) return null;
    var cum = 0;
    var atSeg = 0;
    for (var k = 1; k < coords.length; k++) {
      cum += haversineM(coords[k - 1][1], coords[k - 1][0], coords[k][1], coords[k][0]);
      if (k === seg) atSeg = cum;
    }
    var along = atSeg + haversineM(coords[seg][1], coords[seg][0], proj.lat, proj.lon);
    var bearing = bearingDeg(proj.lat, proj.lon, coords[seg + 1][1], coords[seg + 1][0]);
    if (proj.t > 0.98 && seg + 2 < coords.length) {
      bearing = bearingDeg(coords[seg + 1][1], coords[seg + 1][0], coords[seg + 2][1], coords[seg + 2][0]);
    }
    return {
      index: seg,
      t: proj.t,
      alongM: along,
      remainM: Math.max(0, cum - along),
      totalM: cum,
      offM: off,
      bearing: bearing,
      lat: proj.lat,
      lon: proj.lon
    };
  }

  /** Next cue whose along-distance is still ahead. cues are {alongM, label}. */
  function nextCue(alongM, cues) {
    if (!cues || !cues.length || alongM == null || !isFinite(alongM)) return null;
    var best = null;
    for (var i = 0; i < cues.length; i++) {
      var c = cues[i];
      if (!c || c.alongM == null || !isFinite(c.alongM)) continue;
      if (c.alongM < alongM + 25) continue;
      if (!best || c.alongM < best.alongM) best = c;
    }
    var cue = best;
    var passed = false;
    if (!cue) {
      cue = cues[cues.length - 1];
      passed = true;
    }
    if (!cue) return null;
    return { cue: cue, distanceM: Math.max(0, cue.alongM - alongM), passed: passed };
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

    var faceN = parseFacing('N');
    var face90 = parseFacing('90');
    var faceSpan = parseFacing('0-90');
    check('facing north', faceN && faceN.bearing === 0 && faceN.label === 'N');
    check('facing degrees', face90 && face90.bearing === 90);
    check('facing span', faceSpan && Math.abs(faceSpan.bearing - 45) < 0.01 && faceSpan.span === 90);
    check('facing unknown', parseFacing('') === null && parseFacing('forward') === null);
    var wedge = wedgeRing(30.27, -97.74, 90, 50, 90);
    var east = offsetPoint(30.27, -97.74, 90, 90);
    var wedgeEast = false;
    for (var w = 0; w < wedge.length; w++) {
      if (Math.abs(wedge[w][0] - east.lat) < 0.0004 && Math.abs(wedge[w][1] - east.lon) < 0.0004) wedgeEast = true;
    }
    check('wedge points east', wedge.length >= 4 && wedgeEast);

    var line = [[-97.80, 30.20], [-97.79, 30.21], [-97.78, 30.22], [-97.77, 30.23], [-97.76, 30.24]];
    var anchors = buildAnchors(
      { lat: 30.20, lon: -97.80 },
      { lat: 30.24, lon: -97.76 },
      [
        { type: 'depart', lat: 30.20, lon: -97.80 },
        { type: 'continue', modifier: 'straight', lat: 30.21, lon: -97.79 },
        { type: 'turn', modifier: 'right', lat: 30.22, lon: -97.78 },
        { type: 'new name', lat: 30.225, lon: -97.775 },
        { type: 'merge', modifier: 'left', lat: 30.23, lon: -97.77 },
        { type: 'arrive', lat: 30.24, lon: -97.76 }
      ]
    );
    check('turn and merge pins', anchors.length === 4 && anchors[1].kind === 'turn' && anchors[2].kind === 'merge');
    var legs = sliceLegs(line, anchors);
    var joined = joinLegs(legs);
    check('legs join back', legs.length === 3 && joined.length === line.length && joined[2][0] === line[2][0]);
    var kept = legs[1].slice();
    var keptLast = legs[2].slice();
    legs[0] = [[-97.80, 30.20], [-97.785, 30.215], [-97.78, 30.22]];
    var swapped = joinLegs(legs);
    check('pin swap keeps later legs', legs[1].length === kept.length && legs[1][0][0] === kept[0][0] &&
      legs[2][legs[2].length - 1][0] === keptLast[keptLast.length - 1][0] && swapped[0][0] === -97.80);

    var along = flockAlong(through, [
      { id: 'flock', lat: 30.27, lon: -97.74, flock: true, dir: 'E', name: 'Flock Safety' },
      { id: 'other', lat: 30.2702, lon: -97.74, flock: false, dir: 'N' },
      { id: 'far', lat: 30.30, lon: -97.74, flock: true, dir: 'S' }
    ], 400);
    check('flock along route', along.length === 1 && along[0].id === 'flock' && along[0].facing && along[0].facing.label === 'E');

    check('short turn across north', turnToward(350, 10) === 20 && turnToward(10, 350) === -20);
    var eased = smoothBearing(350, 10, 0.5);
    check('smooth heading across north', eased < 1 || eased > 359);
    check('smooth heading from empty', smoothBearing(null, 90, 1) === 90);
    var mid = progressOnLine(30.27, -97.74, [[-97.76, 30.27], [-97.72, 30.27]]);
    check('progress halfway', mid && Math.abs(mid.alongM - mid.remainM) < 40 && mid.offM < 5 && angleDelta(mid.bearing, 90) < 5);
    var side = progressOnLine(30.27 + (120 / 111132), -97.74, [[-97.76, 30.27], [-97.72, 30.27]]);
    check('progress offset', side && Math.abs(side.offM - 120) < 25);
    var cue = nextCue(100, [
      { alongM: 40, label: 'behind' },
      { alongM: 400, label: 'Turn right' },
      { alongM: 900, label: 'End' }
    ]);
    check('next cue', cue && cue.cue.label === 'Turn right' && Math.abs(cue.distanceM - 300) < 0.1 && !cue.passed);

    return { ok: failures.length === 0, failures: failures, checks: 34 };
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
    parseFacing: parseFacing,
    wedgeRing: wedgeRing,
    junctionKind: junctionKind,
    buildAnchors: buildAnchors,
    sliceLegs: sliceLegs,
    joinLegs: joinLegs,
    pathLengthM: pathLengthM,
    flockAlong: flockAlong,
    wrapBearing: wrapBearing,
    turnToward: turnToward,
    smoothBearing: smoothBearing,
    progressOnLine: progressOnLine,
    nextCue: nextCue,
    selfTest: selfTest
  };
});
