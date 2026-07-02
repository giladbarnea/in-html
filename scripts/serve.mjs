#!/usr/bin/env node
// Static preview server for layer-1/2 pages — the sibling of annotation-writer.mjs
// (which serves *and* persists annotations for layer 3). This one only serves the
// built page over http, so a layer-2 page can be viewed without file:// quirks and
// with no dependencies. Honors the same PORT / SERVE_DIR env contract as
// annotation-writer.mjs, so build.mjs starts either one the same way.
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';

const port = Number(process.env.PORT ?? 8765);
const rootDirectory = path.resolve(process.env.SERVE_DIR ?? '.');
const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8'
};

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {'Content-Type': 'application/json; charset=utf-8'});
  response.end(`${JSON.stringify(payload)}\n`);
}

function resolveStaticPath(pathname) {
  const decodedPathname = decodeURIComponent(pathname);
  const relativePath = decodedPathname === '/' ? 'index.html' : decodedPathname.replace(/^\/+/, '');
  const filePath = path.resolve(rootDirectory, relativePath);
  const isInsideRoot = filePath === rootDirectory || filePath.startsWith(`${rootDirectory}${path.sep}`);
  if (!isInsideRoot) {
    throw new Error('Static file path escapes the serve directory.');
  }
  return filePath;
}

async function sendStaticFile(request, response, requestUrl) {
  let filePath = resolveStaticPath(requestUrl.pathname);
  const fileStat = await fs.stat(filePath).catch(error => {
    if (error.code === 'ENOENT') {
      return null;
    }
    throw error;
  });

  if (!fileStat) {
    sendJson(response, 404, {ok: false, error: 'File not found.'});
    return;
  }

  if (fileStat.isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }

  const content = await fs.readFile(filePath);
  const contentType = contentTypes[path.extname(filePath)] ?? 'application/octet-stream';
  response.writeHead(200, {'Content-Type': contentType});
  if (request.method !== 'HEAD') {
    response.end(content);
    return;
  }
  response.end();
}

const server = http.createServer(async (request, response) => {
  try {
    const requestUrl = new URL(request.url, `http://${request.headers.host}`);
    if (!['GET', 'HEAD'].includes(request.method)) {
      sendJson(response, 405, {ok: false, error: 'Use GET or HEAD.'});
      return;
    }
    await sendStaticFile(request, response, requestUrl);
  } catch (error) {
    sendJson(response, 500, {ok: false, error: error.message});
  }
});

server.listen(port, '0.0.0.0', () => {
  console.log(`in-html server listening on http://0.0.0.0:${port}`);
  console.log(`Serving ${rootDirectory}`);
});
