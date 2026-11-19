// Turns the kit's Markdown documents into HTML (headings, lists, tables, bold, italics).
// Used by the reader (web/las/) and the print pack (web/skriv-ut/).
window.renderMarkdown = function (src, opts) {
  opts = opts || {};
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = s => esc(s)
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?!\w)/g, '$1<i>$2</i>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
  let out = '', list = null, para = [], table = [], first = true, title = '';
  const flushP = () => { if (para.length) { out += '<p>' + para.map(inline).join('<br>') + '</p>'; para = []; } };
  const closeL = () => { if (list) { out += `</${list}>`; list = null; } };
  const flushT = () => {
    if (!table.length) return;
    const rows = table.filter(r => !/^\s*\|?\s*:?-{2,}/.test(r)).map(r => r.trim().replace(/^\||\|$/g, '').split('|'));
    out += '<table>' + rows.map((c, i) => '<tr>' + c.map(x => `<${i ? 'td' : 'th'}>${inline(x.trim())}</${i ? 'td' : 'th'}>`).join('') + '</tr>').join('') + '</table>';
    table = [];
  };
  for (const line of src.split('\n')) {
    let m;
    if (/^\s*\|/.test(line)) { flushP(); closeL(); table.push(line); continue; } else flushT();
    if (!line.trim()) { flushP(); closeL(); continue; }
    if ((m = line.match(/^\s{0,3}(#{1,6})\s+(.*)/))) {
      flushP(); closeL();
      if (first && m[1] === '#') { title = m[2]; out += '<h1>' + inline(m[2]) + '</h1>'; }
      else out += '<h4>' + inline(m[2]) + '</h4>';
      first = false; continue;
    }
    first = false;
    if (/^(Källa|Source|Джерело): /.test(line)) { flushP(); out += '<p class="src">' + inline(line) + '</p>'; continue; }
    if ((m = line.match(/^\s*[-*•+]\s+(.*)/))) { flushP(); if (list !== 'ul') { closeL(); out += '<ul>'; list = 'ul'; } out += '<li>' + inline(m[1]) + '</li>'; continue; }
    if ((m = line.match(/^\s*(\d+)[.)]\s+(.*)/))) { flushP(); if (list !== 'ol') { closeL(); out += `<ol start="${m[1]}">`; list = 'ol'; } out += '<li>' + inline(m[2]) + '</li>'; continue; }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) { flushP(); closeL(); out += '<hr>'; continue; }
    closeL(); para.push(line);
  }
  flushT(); flushP(); closeL();
  return { html: out, title };
};
// Fetches a document by its path under the kit's web folder (e.g. "docs/library/...md").
window.fetchDoc = function (path, base) {
  return fetch((base || '../') + path.split('/').map(encodeURIComponent).join('/'))
    .then(r => { if (!r.ok) throw new Error(r.status); return r.text(); });
};
