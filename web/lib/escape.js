// The one way the kit's pages put text into HTML: escapes & < > and quotes, so it is safe in markup and in
// attribute values. Used by the AI page, the print pack and the Markdown reader (lib/md.js).
window.escapeHtml = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
