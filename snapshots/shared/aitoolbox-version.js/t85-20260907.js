/** Keep in sync with /VERSION */
(function (g) {
  var V = '1.16.50';
  g.AITOOLBOX_VERSION = V;
  g.AIToolboxCacheBust = function (url) {
    if (!url) return url;
    var v = String(g.AITOOLBOX_VERSION || V);
    if (/[?&]v=/.test(url)) return url.replace(/([?&]v=)[^&]*/, '$1' + encodeURIComponent(v));
    return url + (url.indexOf('?') >= 0 ? '&' : '?') + 'v=' + encodeURIComponent(v);
  };
})(typeof window !== 'undefined' ? window : globalThis);
