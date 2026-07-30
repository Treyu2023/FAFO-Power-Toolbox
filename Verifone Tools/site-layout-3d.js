/**
 * FAFO Site Layout 3D — lightweight island viewer (CAD-lite, not commercial Gilbarco CAD).
 * Maps aerial layout items → simple meshes; click → equipment knowledge; explode for inspect.
 *
 * Expects Three.js + OrbitControls on window (loaded by host page).
 * Usage:
 *   const view = FAFOSite3D.mount(containerEl, { layout, onSelect, getKnowledge });
 *   view.setExplode(true|false); view.refresh(layout); view.dispose();
 */
(function (g) {
  'use strict';

  const TYPE_H = {
    building: 40,
    parking: 2,
    driveway: 1,
    pump: 28,
    crind: 18,
    card_reader: 18,
    tank: 22,
    manhole: 4,
    register: 16,
    other: 12,
  };

  function hexColor(c, fallback) {
    if (!c || typeof c !== 'string') return fallback || 0x64748b;
    const m = c.trim().match(/^#?([0-9a-f]{6})$/i);
    if (m) return parseInt(m[1], 16);
    return fallback || 0x64748b;
  }

  function layoutToWorld(layout) {
    const W = layout.width || 1000;
    const H = layout.height || 700;
    // Center layout on XZ plane; 1 layout unit ≈ 0.08 world units
    const scale = 0.08;
    return { W, H, scale, ox: W / 2, oy: H / 2 };
  }

  function makeMesh(THREE, item, map) {
    const type = item.type || 'other';
    const w = Math.max(8, Number(item.w) || 40) * map.scale;
    const d = Math.max(8, Number(item.h) || 40) * map.scale;
    const h = (TYPE_H[type] != null ? TYPE_H[type] : 12) * map.scale * 4;
    const color = hexColor(item.color, type === 'pump' ? 0x0ea5e9 : type === 'tank' ? 0xf59e0b : 0x64748b);

    let geo;
    if (type === 'tank' || type === 'manhole') {
      geo = new THREE.CylinderGeometry(Math.min(w, d) / 2, Math.min(w, d) / 2, h, 16);
    } else if (type === 'pump') {
      // pump body + short “column” feel
      geo = new THREE.BoxGeometry(w * 0.7, h, d * 0.55);
    } else if (type === 'crind' || type === 'card_reader') {
      geo = new THREE.BoxGeometry(w * 0.9, h, d * 0.4);
    } else if (type === 'register') {
      geo = new THREE.BoxGeometry(w, h * 0.7, d);
    } else if (type === 'parking' || type === 'driveway') {
      geo = new THREE.BoxGeometry(w, Math.max(0.4, h * 0.15), d);
    } else {
      geo = new THREE.BoxGeometry(w, h, d);
    }

    const mat = new THREE.MeshStandardMaterial({
      color,
      metalness: type === 'pump' || type === 'crind' ? 0.35 : 0.1,
      roughness: 0.55,
      emissive: 0x000000,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;

    const cx = (Number(item.x) || 0) + (Number(item.w) || 40) / 2;
    const cy = (Number(item.y) || 0) + (Number(item.h) || 40) / 2;
    mesh.position.x = (cx - map.ox) * map.scale;
    mesh.position.z = (cy - map.oy) * map.scale;
    mesh.position.y = h / 2;

    // home pose for explode
    mesh.userData.home = {
      x: mesh.position.x,
      y: mesh.position.y,
      z: mesh.position.z,
    };
    mesh.userData.item = item;
    mesh.userData.itemId = item.id;
    mesh.userData.type = type;
    // explode offset directions by type
    const ex = {
      pump: { x: 0, y: 8, z: 0 },
      crind: { x: 0, y: 14, z: -4 },
      card_reader: { x: 0, y: 14, z: -4 },
      tank: { x: 6, y: 4, z: 0 },
      register: { x: 0, y: 10, z: 4 },
      building: { x: 0, y: 2, z: 0 },
    };
    mesh.userData.explode = ex[type] || { x: 0, y: 6, z: 0 };

    return mesh;
  }

  function mount(container, opts) {
    opts = opts || {};
    const THREE = g.THREE;
    if (!THREE) {
      container.innerHTML = '<div class="empty" style="padding:24px">Three.js failed to load (check network / CDN).</div>';
      return { dispose: function () {}, refresh: function () {}, setExplode: function () {} };
    }

    const layout = opts.layout || { width: 1000, height: 700, items: [] };
    let onSelect = opts.onSelect || function () {};
    let getKnowledge = opts.getKnowledge || function () { return Promise.resolve([]); };

    container.innerHTML = '';
    container.style.position = 'relative';
    container.style.minHeight = '420px';
    container.style.background = 'radial-gradient(ellipse at 50% 20%, #1a2836 0%, #0a1018 70%)';
    container.style.borderRadius = '10px';
    container.style.overflow = 'hidden';
    container.style.border = '1px solid rgba(56,189,248,.25)';

    const hud = document.createElement('div');
    hud.style.cssText = 'position:absolute;left:10px;top:10px;z-index:2;display:flex;flex-wrap:wrap;gap:6px;max-width:70%';
    hud.innerHTML = `
      <button type="button" class="btn" data-3d="reset" style="font-size:11px;padding:4px 10px">Reset cam</button>
      <button type="button" class="btn amber" data-3d="explode" style="font-size:11px;padding:4px 10px">Explode</button>
      <button type="button" class="btn" data-3d="assemble" style="font-size:11px;padding:4px 10px">Assemble</button>
      <span style="font-size:11px;color:#94a3b8;align-self:center">Drag orbit · scroll zoom · click equipment</span>
    `;
    container.appendChild(hud);

    const info = document.createElement('div');
    info.style.cssText = 'position:absolute;right:10px;top:10px;bottom:10px;width:min(300px,42%);z-index:2;overflow:auto;background:rgba(8,12,18,.88);border:1px solid rgba(56,189,248,.3);border-radius:10px;padding:10px 12px;font-size:12px;color:#e2e8f0;display:none';
    container.appendChild(info);

    const canvasHost = document.createElement('div');
    canvasHost.style.cssText = 'position:absolute;inset:0;';
    container.appendChild(canvasHost);

    const w0 = Math.max(320, container.clientWidth || 800);
    const h0 = Math.max(400, container.clientHeight || 420);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x0a1018, 80, 220);

    const camera = new THREE.PerspectiveCamera(45, w0 / h0, 0.1, 500);
    camera.position.set(28, 36, 42);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w0, h0);
    renderer.shadowMap.enabled = true;
    canvasHost.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight(0xb1e1ff, 0x444422, 0.85);
    scene.add(hemi);
    const dir = new THREE.DirectionalLight(0xffffff, 1.05);
    dir.position.set(40, 60, 20);
    dir.castShadow = true;
    scene.add(dir);
    const amb = new THREE.AmbientLight(0x404860, 0.35);
    scene.add(amb);

    // ground
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(160, 160),
      new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.95, metalness: 0.05 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const grid = new THREE.GridHelper(120, 40, 0x334155, 0x1e293b);
    grid.position.y = 0.02;
    scene.add(grid);

    // Lightweight orbit (no OrbitControls CDN dependency — works with three.min.js alone)
    const target = new THREE.Vector3(0, 4, 0);
    let spherical = { radius: 55, theta: 0.7, phi: 1.0 };
    let dragging = false;
    let moved = false;
    let lastX = 0;
    let lastY = 0;
    let downX = 0;
    let downY = 0;

    function applyCam() {
      const phi = Math.max(0.12, Math.min(Math.PI * 0.48, spherical.phi));
      const th = spherical.theta;
      const r = Math.max(8, Math.min(120, spherical.radius));
      spherical.phi = phi;
      spherical.radius = r;
      camera.position.set(
        target.x + r * Math.sin(phi) * Math.sin(th),
        target.y + r * Math.cos(phi),
        target.z + r * Math.sin(phi) * Math.cos(th)
      );
      camera.lookAt(target);
    }
    applyCam();

    renderer.domElement.addEventListener('pointerdown', (ev) => {
      if (ev.button !== 0) return;
      dragging = true;
      moved = false;
      lastX = downX = ev.clientX;
      lastY = downY = ev.clientY;
      try { renderer.domElement.setPointerCapture(ev.pointerId); } catch (_) {}
    });
    renderer.domElement.addEventListener('pointermove', (ev) => {
      if (!dragging) return;
      const dx = ev.clientX - lastX;
      const dy = ev.clientY - lastY;
      lastX = ev.clientX;
      lastY = ev.clientY;
      if (Math.abs(ev.clientX - downX) + Math.abs(ev.clientY - downY) > 4) moved = true;
      if (!moved) return;
      spherical.theta -= dx * 0.008;
      spherical.phi -= dy * 0.008;
      applyCam();
    });
    renderer.domElement.addEventListener('pointerup', (ev) => {
      const wasClick = dragging && !moved;
      dragging = false;
      try { renderer.domElement.releasePointerCapture(ev.pointerId); } catch (_) {}
      if (wasClick) pickAt(ev);
    });
    renderer.domElement.addEventListener(
      'wheel',
      (ev) => {
        ev.preventDefault();
        spherical.radius *= ev.deltaY > 0 ? 1.08 : 0.92;
        applyCam();
      },
      { passive: false }
    );

    const controls = {
      target,
      update: function () {},
      get enabled() { return true; },
    };

    const root = new THREE.Group();
    scene.add(root);
    const meshes = [];
    let explodeT = 0; // 0 assembled → 1 exploded
    let explodeTarget = 0;
    let selectedId = null;
    let raf = 0;
    let disposed = false;

    function clearMeshes() {
      while (root.children.length) {
        const ch = root.children[0];
        root.remove(ch);
        if (ch.geometry) ch.geometry.dispose();
        if (ch.material) ch.material.dispose();
      }
      meshes.length = 0;
    }

    function rebuild(L) {
      clearMeshes();
      const map = layoutToWorld(L || layout);
      const items = (L && L.items) || layout.items || [];
      items.forEach((it) => {
        if (!it || it.paletteOnly) return;
        const mesh = makeMesh(THREE, it, map);
        root.add(mesh);
        meshes.push(mesh);
      });
      // auto-frame
      if (meshes.length) {
        const box = new THREE.Box3().setFromObject(root);
        const c = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z, 10);
        target.copy(c);
        target.y = Math.max(2, c.y);
        spherical.radius = Math.max(18, maxDim * 1.8);
        spherical.theta = 0.75;
        spherical.phi = 1.05;
        applyCam();
      }
    }

    function applyExplode(t) {
      meshes.forEach((m) => {
        const home = m.userData.home;
        const ex = m.userData.explode || { x: 0, y: 6, z: 0 };
        m.position.x = home.x + ex.x * t;
        m.position.y = home.y + ex.y * t;
        m.position.z = home.z + ex.z * t;
      });
    }

    function highlight(id) {
      selectedId = id;
      meshes.forEach((m) => {
        const on = m.userData.itemId === id;
        m.material.emissive = new THREE.Color(on ? 0x334155 : 0x000000);
        m.material.emissiveIntensity = on ? 0.55 : 0;
        m.scale.setScalar(on ? 1.08 : 1);
      });
    }

    async function showInfo(item) {
      if (!item) {
        info.style.display = 'none';
        return;
      }
      info.style.display = 'block';
      info.innerHTML = `<div class="note">Loading tips…</div><div><strong>${escapeHtml(item.label || item.type)}</strong></div>`;
      const meta = item.meta || {};
      let tips = [];
      try {
        tips = (await getKnowledge(item)) || [];
      } catch (_) {
        tips = [];
      }
      const tipHtml = tips.length
        ? tips
            .slice(0, 4)
            .map((t) => {
              const pros = (t.pros || []).slice(0, 3).map((p) => `<li style="color:#86efac">${escapeHtml(p)}</li>`).join('');
              const cons = (t.cons || []).slice(0, 3).map((p) => `<li style="color:#fcd34d">${escapeHtml(p)}</li>`).join('');
              return `<div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,.08)">
                <strong>${escapeHtml(t.title || 'Tip')}</strong>
                ${t.scope === 'library' ? '<span style="color:#34d399;font-size:10px"> · library</span>' : '<span style="color:#fbbf24;font-size:10px"> · this site</span>'}
                <ul style="margin:4px 0 0 14px;padding:0">${pros}${cons || '<li class="note">No pros/cons yet</li>'}</ul>
              </div>`;
            })
            .join('')
        : `<p style="margin-top:8px;color:#94a3b8">No gear tips yet. Use <strong>💡 Tip from selection</strong> on 2D or Gear knowledge tab.</p>`;

      info.innerHTML = `
        <div style="font-size:10px;color:#38bdf8;text-transform:uppercase;letter-spacing:.08em">Selected equipment</div>
        <div style="font-size:15px;font-weight:700;margin:4px 0 6px">${escapeHtml(item.label || item.type)}</div>
        <div style="color:#94a3b8;font-size:11px">${escapeHtml(item.type || '')}
          ${meta.dispenserBrand ? ' · ' + escapeHtml(meta.dispenserBrand) : ''}
          ${meta.dcrBrand ? ' · CRIND ' + escapeHtml(meta.dcrBrand) : ''}
          ${meta.position != null ? ' · FP ' + escapeHtml(String(meta.position)) : ''}
        </div>
        ${tipHtml}
        <p style="margin-top:10px;font-size:10px;color:#64748b">CAD-lite explode — not commercial service CAD. Knowledge is tech-edited per site.</p>
      `;
      onSelect(item);
    }

    function escapeHtml(s) {
      return String(s ?? '').replace(/[&<>"']/g, (c) =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
      );
    }

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    function pickAt(ev) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(meshes, false);
      if (hits.length) {
        const m = hits[0].object;
        highlight(m.userData.itemId);
        showInfo(m.userData.item);
      }
    }

    hud.querySelector('[data-3d="reset"]').onclick = () => {
      rebuild(opts.layout);
      explodeT = 0;
      explodeTarget = 0;
      applyExplode(0);
    };
    hud.querySelector('[data-3d="explode"]').onclick = () => {
      explodeTarget = 1;
    };
    hud.querySelector('[data-3d="assemble"]').onclick = () => {
      explodeTarget = 0;
    };

    function onResize() {
      if (disposed) return;
      const w = Math.max(320, container.clientWidth || 800);
      const h = Math.max(400, container.clientHeight || 420);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }
    window.addEventListener('resize', onResize);

    function tick() {
      if (disposed) return;
      raf = requestAnimationFrame(tick);
      if (Math.abs(explodeT - explodeTarget) > 0.001) {
        explodeT += (explodeTarget - explodeT) * 0.08;
        applyExplode(explodeT);
      }
      if (controls) controls.update();
      renderer.render(scene, camera);
    }

    rebuild(layout);
    tick();

    return {
      refresh: function (L) {
        opts.layout = L || opts.layout;
        rebuild(opts.layout);
        applyExplode(explodeT);
      },
      setExplode: function (on) {
        explodeTarget = on ? 1 : 0;
      },
      selectId: function (id) {
        const m = meshes.find((x) => x.userData.itemId === id);
        if (m) {
          highlight(id);
          showInfo(m.userData.item);
        }
      },
      dispose: function () {
        disposed = true;
        cancelAnimationFrame(raf);
        window.removeEventListener('resize', onResize);
        clearMeshes();
        renderer.dispose();
        container.innerHTML = '';
      },
    };
  }

  g.FAFOSite3D = { mount: mount };
})(typeof window !== 'undefined' ? window : globalThis);
