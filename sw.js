"use strict";

/* =========================================================================
   PerpetualDoc — Service Worker
   Atua como um servidor local dentro do navegador: intercepta pedidos para
   /__pd_docs__/<caminho> e pede o arquivo de verdade pra aba que tem a pasta
   conectada (via postMessage), devolvendo os bytes exatamente como vieram —
   sem reescrever CSS, HTML ou qualquer outra coisa. Não guarda nem transmite
   nada pra fora deste navegador.
   ========================================================================= */

const PREFIXO = "/__pd_docs__/";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

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
  if (url.origin !== self.location.origin || !url.pathname.startsWith(PREFIXO)) return;

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
