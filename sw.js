"use strict";

/* =========================================================================
   PerpetualDoc — Service Worker
   Atua como um servidor local dentro do navegador: intercepta pedidos para
   /__pd_docs__/<caminho> e pede o arquivo de verdade pra aba que tem a pasta
   conectada (via postMessage), devolvendo os bytes exatamente como vieram —
   sem reescrever CSS, HTML ou qualquer outra coisa. Não guarda nem transmite
   nada pra fora deste navegador.
   ========================================================================= */

// Calculado a partir de onde o próprio sw.js está, pra bater exatamente com o
// que o index.html calcula — funciona em qualquer subcaminho (raiz, Netlify,
// projeto do GitHub Pages, etc.), desde que os dois arquivos fiquem juntos.
const PREFIXO = self.location.pathname.replace(/[^/]*$/, "") + "__pd_docs__/";

// Cópia local dos arquivos DO SITE (index.html, ícones, manifest) — nunca da
// documentação. Serve só pro app abrir mesmo sem internet; com internet, a
// versão publicada sempre vem primeiro (rede primeiro, cópia só como reserva).
const CACHE_SITE = "perpetualdoc-site-v1";
const BASE = self.location.pathname.replace(/[^/]*$/, "");
const ARQUIVOS_SITE = ["", "index.html", "favicon.ico", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "icons/apple-touch-icon.png"];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_SITE)
      .then((c) => Promise.all(ARQUIVOS_SITE.map((a) => c.add(BASE + a).catch(() => null))))
      .catch(() => null)
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const nomes = await caches.keys();
    await Promise.all(nomes.filter((n) => n.startsWith("perpetualdoc-site-") && n !== CACHE_SITE).map((n) => caches.delete(n)));
    await self.clients.claim();
  })());
});

async function redePrimeiro(request, ehNavegacao){
  const cache = await caches.open(CACHE_SITE);
  try {
    const resp = await fetch(request);
    if (resp && resp.ok && resp.type === "basic") cache.put(request, resp.clone()).catch(() => {});
    return resp;
  } catch(e) {
    const salvo = await cache.match(request, { ignoreSearch: ehNavegacao });
    if (salvo) return salvo;
    if (ehNavegacao){
      const index = await cache.match(BASE + "index.html") || await cache.match(BASE);
      if (index) return index;
    }
    throw e;
  }
}

let proximoId = 1;
const pendentes = new Map();

self.addEventListener("message", (event) => {
  const data = event.data || {};
  if (data.type === "pd-file-response" && pendentes.has(data.id)) {
    pendentes.get(data.id)(data);
    pendentes.delete(data.id);
  }
});

async function pedirArquivoParaAAba(relPath) {
  const clientes = await self.clients.matchAll({ includeUncontrolled: true, type: "window" });
  if (!clientes.length) return null;

  const id = proximoId++;
  const resultado = new Promise((resolve) => pendentes.set(id, resolve));
  clientes.forEach((c) => c.postMessage({ type: "pd-file-request", id, path: relPath }));

  const timeout = new Promise((resolve) => setTimeout(() => resolve(null), 10000));
  return Promise.race([resultado, timeout]);
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  // Arquivos do próprio site (não da documentação): rede primeiro, cópia local se offline.
  if (!url.pathname.startsWith(PREFIXO)){
    if (event.request.method !== "GET" || url.pathname === BASE + "sw.js") return;
    const rel = url.pathname.slice(BASE.length);
    const ehNavegacao = event.request.mode === "navigate";
    if (ehNavegacao || ARQUIVOS_SITE.includes(rel)) event.respondWith(redePrimeiro(event.request, ehNavegacao));
    return;
  }

  const relPath = decodeURIComponent(url.pathname.slice(PREFIXO.length));

  event.respondWith((async () => {
    const resposta = await pedirArquivoParaAAba(relPath);

    if (!resposta) {
      return new Response(
        "Não foi possível falar com a página do PerpetualDoc. Volte e abra a documentação de novo.",
        { status: 504, headers: { "Content-Type": "text/plain; charset=utf-8" } }
      );
    }
    if (!resposta.ok) {
      return new Response(resposta.mensagem || "Não encontrado.", {
        status: resposta.status || 404,
        headers: { "Content-Type": "text/plain; charset=utf-8" }
      });
    }
    if (resposta.texto !== undefined) {
      return new Response(resposta.texto, { headers: { "Content-Type": resposta.tipo } });
    }
    return new Response(resposta.buffer, { headers: { "Content-Type": resposta.tipo } });
  })());
});
