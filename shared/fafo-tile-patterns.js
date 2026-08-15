/**
 * FAFO tiled fill patterns — shared by AI HTML Toolbox + FAFO Ultimate Tab.
 *
 * Paint-program tiles: 1–3 colors, per-color opacity, scalable cell size.
 * Returns { image, size, repeat, position, color } for CSS backgrounds.
 *
 * background-image may only contain gradients/urls — never raw rgba()
 * base colors (those go in `color` → background-color).
 */
(function (global) {
    'use strict';

    const CATALOG = [
        { id: 'stripes-h', label: 'Stripes H', group: 'stripes' },
        { id: 'stripes-v', label: 'Stripes V', group: 'stripes' },
        { id: 'stripes-diag', label: 'Stripes ╱', group: 'stripes' },
        { id: 'stripes-diag2', label: 'Stripes ╲', group: 'stripes' },
        { id: 'stripes-thick', label: 'Stripes thick', group: 'stripes' },
        { id: 'stripes-thin', label: 'Stripes thin', group: 'stripes' },
        { id: 'bars-3', label: 'Triple bars', group: 'stripes' },
        { id: 'checker', label: 'Checker', group: 'blocks' },
        { id: 'checker-sm', label: 'Checker fine', group: 'blocks' },
        { id: 'pixel', label: 'Pixel blocks', group: 'blocks' },
        { id: 'bricks', label: 'Bricks', group: 'blocks' },
        { id: 'grid', label: 'Grid', group: 'lines' },
        { id: 'grid-bold', label: 'Grid bold', group: 'lines' },
        { id: 'crosshatch', label: 'Crosshatch', group: 'lines' },
        { id: 'crosshatch-dense', label: 'Hatch dense', group: 'lines' },
        { id: 'dots', label: 'Dots', group: 'dots' },
        { id: 'dots-loose', label: 'Dots loose', group: 'dots' },
        { id: 'dots-dense', label: 'Dots dense', group: 'dots' },
        { id: 'rings', label: 'Rings', group: 'dots' },
        { id: 'diamonds', label: 'Diamonds', group: 'geo' },
        { id: 'diamonds-outline', label: 'Diamond outline', group: 'geo' },
        { id: 'triangles', label: 'Triangles', group: 'geo' },
        { id: 'triangles-flip', label: 'Triangles flip', group: 'geo' },
        { id: 'chevron', label: 'Chevron', group: 'geo' },
        { id: 'chevron-v', label: 'Chevron V', group: 'geo' },
        { id: 'zigzag', label: 'Zigzag', group: 'geo' },
        { id: 'plaid', label: 'Plaid', group: 'weave' },
        { id: 'plaid-fine', label: 'Plaid fine', group: 'weave' },
        { id: 'weave', label: 'Basket weave', group: 'weave' },
        { id: 'honey', label: 'Honeycomb', group: 'organic' },
        { id: 'waves', label: 'Waves', group: 'organic' },
        { id: 'scales', label: 'Scales', group: 'organic' },
        { id: 'confetti', label: 'Confetti', group: 'organic' },
        { id: 'noise', label: 'Noise grit', group: 'organic' },
        // FAFO neon tessellations (circuit city / star lattice / hex)
        { id: 'hex', label: 'Hex lattice', group: 'fafo' },
        { id: 'hex-outline', label: 'Hex outline', group: 'fafo' },
        { id: 'circuit', label: 'Circuit board', group: 'fafo' },
        { id: 'circuit-nodes', label: 'Circuit nodes', group: 'fafo' },
        { id: 'star-8', label: 'Star lattice', group: 'fafo' },
        { id: 'plus-grid', label: 'Plus grid', group: 'fafo' },
        { id: 'plus', label: 'Plus marks', group: 'fafo' },
        { id: 'scanlines', label: 'Scanlines', group: 'fafo' },
        { id: 'carbon', label: 'Carbon fiber', group: 'fafo' },
        { id: 'herringbone', label: 'Herringbone', group: 'fafo' },
        { id: 'argyle', label: 'Argyle', group: 'fafo' },
        { id: 'micro-grid', label: 'Micro grid', group: 'fafo' },
    ];

    const GROUPS = [
        { id: 'fafo', label: 'FAFO neon' },
        { id: 'stripes', label: 'Stripes' },
        { id: 'blocks', label: 'Blocks' },
        { id: 'lines', label: 'Lines' },
        { id: 'dots', label: 'Dots' },
        { id: 'geo', label: 'Geometry' },
        { id: 'weave', label: 'Weave' },
        { id: 'organic', label: 'Organic' },
    ];

    /** Default wallpaper / section mapping for the HTML Toolbox. */
    const SECTION_TILES = {
        verifone: 'herringbone',
        media: 'circuit',
        av: 'star-8',
        system: 'hex',
        'files-dev': 'micro-grid',
        tax: 'scanlines',
        utils: 'plus-grid',
        home: 'circuit',
    };

    const SECTION_COLORS = {
        verifone: { a: '#f59e0b', b: '#fb923c', c: '#fde68a' },
        media: { a: '#00f3ff', b: '#38bdf8', c: '#7c5cff' },
        av: { a: '#a78bfa', b: '#c084fc', c: '#00f3ff' },
        system: { a: '#00ff88', b: '#34d399', c: '#00f3ff' },
        'files-dev': { a: '#38bdf8', b: '#00f3ff', c: '#7dd3fc' },
        tax: { a: '#00e8a2', b: '#34d399', c: '#f59e0b' },
        utils: { a: '#f472b6', b: '#fb7185', c: '#a78bfa' },
        home: { a: '#00f3ff', b: '#7c5cff', c: '#00ff88' },
    };

    function clamp(n, a, b) {
        const x = Number(n);
        if (!Number.isFinite(x)) return a;
        return Math.min(b, Math.max(a, x));
    }

    function expandHex(c) {
        const h = String(c || '').trim();
        if (/^#[0-9a-f]{3}$/i.test(h)) {
            return '#' + h[1] + h[1] + h[2] + h[2] + h[3] + h[3];
        }
        if (/^#[0-9a-f]{8}$/i.test(h)) return h.toLowerCase().slice(0, 7);
        if (/^#[0-9a-f]{6}$/i.test(h)) return h.toLowerCase();
        return '#00e5ff';
    }

    function hexToRgb(hex) {
        const h = expandHex(hex).slice(1);
        return {
            r: parseInt(h.slice(0, 2), 16),
            g: parseInt(h.slice(2, 4), 16),
            b: parseInt(h.slice(4, 6), 16),
        };
    }

    function rgba(hex, alpha) {
        try {
            const { r, g, b } = hexToRgb(hex);
            const a = clamp(alpha == null ? 1 : alpha, 0, 1);
            return `rgba(${r},${g},${b},${a})`;
        } catch {
            return hex || '#00e5ff';
        }
    }

    function pack(image, size, color, position, repeat) {
        const img = Array.isArray(image) ? image.filter(Boolean).join(', ') : String(image || '');
        const layers = img ? img.split(',').length : 0;
        let sizeOut = size;
        if (layers > 1 && size && !String(size).includes(',')) {
            sizeOut = Array(layers).fill(size).join(', ');
        }
        let posOut = position || '0 0';
        if (layers > 1 && posOut && !String(posOut).includes(',')) {
            posOut = Array(layers).fill(posOut).join(', ');
        }
        return {
            image: img,
            size: sizeOut,
            repeat: repeat || 'repeat',
            position: posOut,
            color: color,
            css: img,
        };
    }

    /**
     * @param {object} s slot-like: tilePattern, tileScale, fillA/B/C, fillAlpha/B/C, fillColorCount
     */
    function build(s) {
        const slot = s && typeof s === 'object' ? s : {};
        const scale = Math.round(clamp(slot.tileScale ?? 16, 4, 96));
        const n = Math.round(clamp(slot.fillColorCount ?? 2, 1, 3));
        const c1 = rgba(slot.fillA || '#00e5ff', slot.fillAlpha ?? 0.95);
        const c2 = rgba(slot.fillB || '#00ffa8', slot.fillAlphaB ?? 0.85);
        const c3 = rgba(slot.fillC || '#a78bfa', slot.fillAlphaC ?? 0.7);
        const a = c1;
        const b = n >= 2 ? c2 : c1;
        const c = n >= 3 ? c3 : b;
        const id = slot.tilePattern || 'stripes-h';
        const sz = `${scale}px ${scale}px`;
        const sz2 = `${scale * 2}px ${scale * 2}px`;
        const half = Math.max(1, Math.round(scale / 2));
        const third = Math.max(1, Math.round(scale / 3));
        const line = Math.max(1, Math.round(scale * 0.12));
        const lineThin = Math.max(1, Math.round(scale * 0.06));

        const stripe = (angle, band) => {
            const w = Math.max(1, Math.round(scale * band));
            if (n < 3) {
                return pack(
                    `repeating-linear-gradient(${angle}, ${a} 0 ${w}px, ${b} ${w}px ${scale}px)`,
                    sz,
                    a
                );
            }
            return pack(
                `repeating-linear-gradient(${angle}, ${a} 0 ${third}px, ${b} ${third}px ${third * 2}px, ${c} ${third * 2}px ${scale}px)`,
                sz,
                a
            );
        };

        switch (id) {
            case 'stripes-h': return stripe('0deg', 0.5);
            case 'stripes-v': return stripe('90deg', 0.5);
            case 'stripes-diag': return stripe('45deg', 0.5);
            case 'stripes-diag2': return stripe('-45deg', 0.5);
            case 'stripes-thick': return stripe('90deg', 0.72);
            case 'stripes-thin': return stripe('90deg', 0.22);
            case 'bars-3': return stripe('0deg', 0.33);
            case 'checker':
            case 'checker-sm': {
                const cell = id === 'checker-sm' ? Math.max(4, half) : scale;
                const cellSz = `${cell * 2}px ${cell * 2}px`;
                if (n >= 3) {
                    return pack(
                        [
                            `repeating-conic-gradient(${a} 0% 25%, ${b} 0% 50%)`,
                            `repeating-linear-gradient(45deg, ${c} 0 ${Math.max(1, Math.round(cell / 6))}px, transparent ${Math.max(1, Math.round(cell / 6))}px ${cell}px)`,
                        ],
                        cellSz,
                        a
                    );
                }
                return pack(`repeating-conic-gradient(${a} 0% 25%, ${b} 0% 50%)`, cellSz, a);
            }
            case 'pixel':
                return pack(
                    `repeating-conic-gradient(${a} 0% 25%, ${b} 0% 50%, ${c} 0% 75%, ${a} 0% 100%)`,
                    `${half}px ${half}px`,
                    a
                );
            case 'bricks': {
                const bh = half;
                const bw = scale;
                return pack(
                    [
                        `linear-gradient(${a} 50%, ${b} 50%)`,
                        `linear-gradient(${c} 50%, ${a} 50%)`,
                    ],
                    `${bw}px ${bh * 2}px, ${bw}px ${bh * 2}px`,
                    a,
                    `0 0, ${Math.round(bw / 2)}px ${bh}px`
                );
            }
            case 'grid':
                return pack(
                    [
                        `linear-gradient(to right, ${b} ${lineThin}px, transparent ${lineThin}px)`,
                        `linear-gradient(to bottom, ${b} ${lineThin}px, transparent ${lineThin}px)`,
                    ],
                    sz,
                    a
                );
            case 'grid-bold':
                return pack(
                    [
                        `linear-gradient(to right, ${b} ${line}px, transparent ${line}px)`,
                        `linear-gradient(to bottom, ${c} ${line}px, transparent ${line}px)`,
                    ],
                    sz,
                    a
                );
            case 'crosshatch':
                return pack(
                    [
                        `repeating-linear-gradient(45deg, ${b} 0 ${lineThin}px, transparent ${lineThin}px ${scale}px)`,
                        `repeating-linear-gradient(-45deg, ${c} 0 ${lineThin}px, transparent ${lineThin}px ${scale}px)`,
                    ],
                    sz,
                    a
                );
            case 'crosshatch-dense':
                return pack(
                    [
                        `repeating-linear-gradient(45deg, ${b} 0 ${lineThin}px, transparent ${lineThin}px ${half}px)`,
                        `repeating-linear-gradient(-45deg, ${c} 0 ${lineThin}px, transparent ${lineThin}px ${half}px)`,
                    ],
                    `${half}px ${half}px`,
                    a
                );
            case 'dots':
            case 'dots-loose':
            case 'dots-dense': {
                const r =
                    id === 'dots-loose' ? Math.max(1, scale * 0.16)
                        : id === 'dots-dense' ? Math.max(1, scale * 0.32)
                            : Math.max(1, scale * 0.24);
                const step =
                    id === 'dots-loose' ? scale * 1.5
                        : id === 'dots-dense' ? scale * 0.75
                            : scale;
                return pack(
                    `radial-gradient(circle ${r.toFixed(1)}px at 50% 50%, ${b} 96%, transparent 100%)`,
                    `${Math.round(step)}px ${Math.round(step)}px`,
                    a
                );
            }
            case 'rings': {
                const r1 = Math.max(2, scale * 0.2);
                const r2 = Math.max(3, scale * 0.32);
                return pack(
                    `radial-gradient(circle, transparent ${r1}px, ${b} ${r1}px, ${b} ${r2}px, transparent ${r2}px)`,
                    sz,
                    a
                );
            }
            case 'diamonds':
                return pack(
                    [
                        `repeating-linear-gradient(45deg, ${a} 0 ${half}px, ${b} ${half}px ${scale}px)`,
                        `repeating-linear-gradient(-45deg, transparent 0 ${half}px, ${c} ${half}px ${scale}px)`,
                    ],
                    sz,
                    a
                );
            case 'diamonds-outline':
                return pack(
                    [
                        `linear-gradient(45deg, ${b} ${lineThin}px, transparent ${lineThin}px)`,
                        `linear-gradient(-45deg, ${b} ${lineThin}px, transparent ${lineThin}px)`,
                    ],
                    sz,
                    a
                );
            case 'triangles':
                return pack(
                    [
                        `linear-gradient(45deg, ${b} 50%, transparent 50%)`,
                        `linear-gradient(-45deg, ${c} 50%, transparent 50%)`,
                    ],
                    sz,
                    a
                );
            case 'triangles-flip':
                return pack(
                    [
                        `linear-gradient(135deg, ${b} 50%, transparent 50%)`,
                        `linear-gradient(225deg, ${c} 50%, transparent 50%)`,
                    ],
                    sz,
                    a
                );
            case 'chevron':
                return pack(
                    [
                        `repeating-linear-gradient(135deg, ${a} 0 ${half}px, ${b} ${half}px ${scale}px)`,
                        `repeating-linear-gradient(45deg, ${a} 0 ${half}px, ${c} ${half}px ${scale}px)`,
                    ],
                    sz,
                    a
                );
            case 'chevron-v':
                return pack(
                    [
                        `repeating-linear-gradient(45deg, ${a} 0 ${half}px, ${b} ${half}px ${scale}px)`,
                        `repeating-linear-gradient(135deg, ${a} 0 ${half}px, ${c} ${half}px ${scale}px)`,
                    ],
                    sz,
                    a
                );
            case 'zigzag':
                return pack(
                    [
                        `linear-gradient(135deg, ${b} 25%, transparent 25%)`,
                        `linear-gradient(225deg, ${b} 25%, transparent 25%)`,
                        `linear-gradient(315deg, ${b} 25%, transparent 25%)`,
                        `linear-gradient(45deg, ${b} 25%, transparent 25%)`,
                    ],
                    `${sz2}, ${sz2}, ${sz2}, ${sz2}`,
                    a,
                    `-${half}px 0, -${half}px 0, 0 0, 0 0`
                );
            case 'plaid':
            case 'plaid-fine': {
                const t = id === 'plaid-fine' ? Math.max(1, Math.round(scale / 6)) : Math.max(1, Math.round(scale / 4));
                const cell = id === 'plaid-fine' ? half : scale;
                return pack(
                    [
                        `repeating-linear-gradient(90deg, ${b} 0 ${t}px, transparent ${t}px ${cell}px)`,
                        `repeating-linear-gradient(0deg, ${c} 0 ${t}px, transparent ${t}px ${cell}px)`,
                    ],
                    `${cell}px ${cell}px`,
                    a
                );
            }
            case 'weave':
                return pack(
                    [
                        `linear-gradient(90deg, ${a} 50%, ${b} 50%)`,
                        `linear-gradient(0deg, ${c} 50%, transparent 50%)`,
                    ],
                    `${sz}, ${half}px ${half}px`,
                    a
                );
            case 'honey':
                return pack(
                    [
                        `radial-gradient(circle closest-side at 50% 50%, ${b} 96%, transparent 100%)`,
                        `radial-gradient(circle closest-side at 50% 50%, ${c} 96%, transparent 100%)`,
                    ],
                    `${sz}, ${sz}`,
                    a,
                    `0 0, ${half}px ${half}px`
                );
            case 'waves':
                return pack(
                    `repeating-radial-gradient(circle at 0 50%, transparent 0, transparent ${scale * 0.3}px, ${b} ${scale * 0.3}px, ${b} ${scale * 0.42}px, transparent ${scale * 0.42}px, transparent ${scale}px)`,
                    `${scale * 2}px ${scale}px`,
                    a
                );
            case 'scales':
                return pack(
                    [
                        `radial-gradient(circle at 50% 0, ${b} 40%, transparent 41%)`,
                        `radial-gradient(circle at 0 50%, ${c} 40%, transparent 41%)`,
                        `radial-gradient(circle at 100% 50%, ${c} 40%, transparent 41%)`,
                    ],
                    sz,
                    a
                );
            case 'confetti':
                return pack(
                    [
                        `radial-gradient(circle at 20% 30%, ${b} 0 12%, transparent 13%)`,
                        `radial-gradient(circle at 70% 60%, ${c} 0 10%, transparent 11%)`,
                        `radial-gradient(circle at 40% 80%, ${b} 0 8%, transparent 9%)`,
                        `radial-gradient(circle at 85% 25%, ${c} 0 9%, transparent 10%)`,
                    ],
                    sz2,
                    a
                );
            case 'noise':
                return pack(
                    `repeating-conic-gradient(${a} 0% 12%, ${b} 0% 18%, ${a} 0% 30%, ${c} 0% 36%, ${a} 0% 50%)`,
                    `${Math.max(3, Math.round(scale / 3))}px ${Math.max(3, Math.round(scale / 3))}px`,
                    a
                );

            /* ── FAFO neon tessellations ── */
            case 'hex': {
                const h = Math.max(8, Math.round(scale * 0.866));
                return pack(
                    [
                        `repeating-linear-gradient(30deg, ${b} 0 ${half}px, ${a} ${half}px ${scale}px)`,
                        `repeating-linear-gradient(150deg, ${c} 0 ${half}px, transparent ${half}px ${scale}px)`,
                        `repeating-linear-gradient(90deg, transparent 0 ${Math.max(2, Math.round(scale * 0.18))}px, ${b} ${Math.max(2, Math.round(scale * 0.18))}px ${Math.max(3, Math.round(scale * 0.22))}px, transparent ${Math.max(3, Math.round(scale * 0.22))}px ${h}px)`,
                    ],
                    `${scale}px ${h}px`,
                    a
                );
            }
            case 'hex-outline': {
                const t = Math.max(1, Math.round(scale * 0.07));
                const h = Math.max(8, Math.round(scale * 0.866));
                return pack(
                    [
                        `repeating-linear-gradient(0deg, ${b} 0 ${t}px, transparent ${t}px ${h}px)`,
                        `repeating-linear-gradient(60deg, ${b} 0 ${t}px, transparent ${t}px ${scale}px)`,
                        `repeating-linear-gradient(120deg, ${c} 0 ${t}px, transparent ${t}px ${scale}px)`,
                    ],
                    `${scale}px ${h}px`,
                    a
                );
            }
            case 'circuit': {
                const node = Math.max(1.4, scale * 0.13);
                return pack(
                    [
                        `linear-gradient(to right, ${b} ${lineThin}px, transparent ${lineThin}px)`,
                        `linear-gradient(to bottom, ${b} ${lineThin}px, transparent ${lineThin}px)`,
                        `radial-gradient(circle at 0 0, ${c} ${node}px, transparent ${node + 0.6}px)`,
                        `radial-gradient(circle at 70% 30%, ${c} ${node * 0.7}px, transparent ${node * 0.7 + 0.5}px)`,
                    ],
                    `${scale}px ${scale}px, ${scale}px ${scale}px, ${scale}px ${scale}px, ${scale * 2}px ${scale}px`,
                    a
                );
            }
            case 'circuit-nodes': {
                const node = Math.max(1.6, scale * 0.16);
                const arm = Math.max(3, Math.round(scale * 0.38));
                return pack(
                    [
                        `linear-gradient(to right, transparent ${half - 1}px, ${b} ${half - 1}px ${half + lineThin}px, transparent ${half + lineThin}px)`,
                        `linear-gradient(to bottom, transparent ${half - arm}px, ${b} ${half - arm}px ${half + lineThin}px, transparent ${half + lineThin}px)`,
                        `radial-gradient(circle at 50% 50%, ${c} ${node}px, transparent ${node + 0.5}px)`,
                        `radial-gradient(circle at 0 50%, ${c} ${node * 0.65}px, transparent ${node * 0.65 + 0.5}px)`,
                    ],
                    sz,
                    a
                );
            }
            case 'star-8': {
                const t = Math.max(1, Math.round(scale * 0.055));
                return pack(
                    [
                        `repeating-linear-gradient(0deg, ${b} 0 ${t}px, transparent ${t}px ${scale}px)`,
                        `repeating-linear-gradient(90deg, ${b} 0 ${t}px, transparent ${t}px ${scale}px)`,
                        `repeating-linear-gradient(45deg, ${c} 0 ${t}px, transparent ${t}px ${scale}px)`,
                        `repeating-linear-gradient(-45deg, ${c} 0 ${t}px, transparent ${t}px ${scale}px)`,
                    ],
                    sz,
                    a
                );
            }
            case 'plus-grid': {
                const t = Math.max(1, Math.round(scale * 0.08));
                return pack(
                    [
                        `linear-gradient(to right, transparent calc(50% - ${t / 2}px), ${b} calc(50% - ${t / 2}px) calc(50% + ${t / 2}px), transparent calc(50% + ${t / 2}px))`,
                        `linear-gradient(to bottom, transparent calc(50% - ${t / 2}px), ${c} calc(50% - ${t / 2}px) calc(50% + ${t / 2}px), transparent calc(50% + ${t / 2}px))`,
                    ],
                    sz,
                    a
                );
            }
            case 'plus': {
                const t = Math.max(1, Math.round(scale * 0.1));
                const arm = Math.max(3, Math.round(scale * 0.28));
                const mid = 50;
                const lo = `calc(${mid}% - ${arm}px)`;
                const hi = `calc(${mid}% + ${arm}px)`;
                const tLo = `calc(${mid}% - ${t / 2}px)`;
                const tHi = `calc(${mid}% + ${t / 2}px)`;
                return pack(
                    [
                        `linear-gradient(to right, transparent ${tLo}, ${b} ${tLo} ${tHi}, transparent ${tHi})`,
                        `linear-gradient(to bottom, transparent ${lo}, ${c} ${lo} ${hi}, transparent ${hi})`,
                    ],
                    sz,
                    a
                );
            }
            case 'scanlines': {
                const t = Math.max(1, Math.round(scale * 0.18));
                return pack(
                    `repeating-linear-gradient(0deg, ${a} 0 ${t}px, ${b} ${t}px ${t + lineThin}px, ${a} ${t + lineThin}px ${scale}px)`,
                    sz,
                    a
                );
            }
            case 'carbon': {
                const t = Math.max(1, Math.round(scale / 8));
                return pack(
                    [
                        `repeating-linear-gradient(45deg, ${a} 0 ${t}px, ${b} ${t}px ${t * 2}px, ${a} ${t * 2}px ${t * 3}px, ${c} ${t * 3}px ${t * 4}px)`,
                        `repeating-linear-gradient(-45deg, transparent 0 ${t}px, rgba(0,0,0,0.28) ${t}px ${t * 2}px)`,
                    ],
                    sz,
                    a
                );
            }
            case 'herringbone':
                return pack(
                    [
                        `repeating-linear-gradient(45deg, ${a} 0 ${half}px, ${b} ${half}px ${scale}px)`,
                        `repeating-linear-gradient(-45deg, ${c} 0 ${half}px, transparent ${half}px ${scale}px)`,
                    ],
                    `${scale}px ${half}px`,
                    a
                );
            case 'argyle':
                return pack(
                    [
                        `repeating-linear-gradient(45deg, ${a} 0 ${half}px, ${b} ${half}px ${scale}px)`,
                        `repeating-linear-gradient(-45deg, transparent 0 ${half}px, ${c} ${half}px ${scale}px)`,
                        `repeating-linear-gradient(45deg, ${b} 0 ${lineThin}px, transparent ${lineThin}px ${scale}px)`,
                        `repeating-linear-gradient(-45deg, ${c} 0 ${lineThin}px, transparent ${lineThin}px ${scale}px)`,
                    ],
                    sz,
                    a
                );
            case 'micro-grid': {
                const cell = Math.max(4, Math.round(scale / 2));
                const t = 1;
                return pack(
                    [
                        `linear-gradient(to right, ${b} ${t}px, transparent ${t}px)`,
                        `linear-gradient(to bottom, ${c} ${t}px, transparent ${t}px)`,
                    ],
                    `${cell}px ${cell}px`,
                    a
                );
            }
            default:
                return stripe('0deg', 0.5);
        }
    }

    function applyToEl(el, spec, extra) {
        if (!el || !spec) return;
        const img = spec.image || spec.css || '';
        el.style.backgroundColor = spec.color || '';
        el.style.backgroundImage = img;
        el.style.backgroundSize = spec.size || '';
        el.style.backgroundRepeat = spec.repeat || 'repeat';
        el.style.backgroundPosition = spec.position || '0 0';
        if (extra && extra.blend) el.style.backgroundBlendMode = extra.blend;
    }

    function wallpaperSpec(patternId, opts) {
        const o = opts || {};
        const colors = o.colors || SECTION_COLORS.home;
        return build({
            tilePattern: patternId || 'circuit',
            tileScale: o.scale ?? 28,
            fillA: colors.a,
            fillB: colors.b,
            fillC: colors.c,
            fillAlpha: o.alphaA ?? 0.22,
            fillAlphaB: o.alphaB ?? 0.16,
            fillAlphaC: o.alphaC ?? 0.12,
            fillColorCount: 3,
        });
    }

    function sectionSpec(secId, opts) {
        const o = opts || {};
        const id = SECTION_TILES[secId] || 'circuit';
        const colors = SECTION_COLORS[secId] || SECTION_COLORS.home;
        return build({
            tilePattern: o.tilePattern || id,
            tileScale: o.scale ?? 18,
            fillA: colors.a,
            fillB: colors.b,
            fillC: colors.c,
            fillAlpha: o.alphaA ?? 0.28,
            fillAlphaB: o.alphaB ?? 0.18,
            fillAlphaC: o.alphaC ?? 0.12,
            fillColorCount: 3,
        });
    }

    function byId(id) {
        return CATALOG.find((p) => p.id === id) || null;
    }

    global.FAFOTilePatterns = {
        CATALOG,
        GROUPS,
        SECTION_TILES,
        SECTION_COLORS,
        build,
        applyToEl,
        wallpaperSpec,
        sectionSpec,
        byId,
        rgba,
        expandHex,
    };
})(typeof window !== 'undefined' ? window : globalThis);
