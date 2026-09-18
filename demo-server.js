// Демо-сервер: отдаёт проект как /divn/* (нужно из-за абсолютных путей CSS).
// Запуск: node demo-server.js  →  http://127.0.0.1:8791/divn/index.html
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = __dirname;
http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/divn/' || p === '/divn') p = '/divn/index.html';
  if (p.startsWith('/divn')) p = '/' + p.slice(5);
  const f = path.join(ROOT, p);
  if (!f.startsWith(ROOT)) { res.writeHead(403); res.end('forbidden'); return; }
  fs.readFile(f, (e, d) => {
    if (e) { res.writeHead(404); res.end('not found'); return; }
    const ext = path.extname(f);
    const mime = { '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.html': 'text/html', '.png': 'image/png', '.ttf': 'font/ttf' }[ext] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': mime, 'Access-Control-Allow-Origin': '*' });
    res.end(d);
  });
}).listen(8791, '127.0.0.1', () => console.log('http://127.0.0.1:8791/divn/index.html'));
