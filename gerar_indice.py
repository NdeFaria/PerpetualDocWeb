#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gerar_indice.py — PerpetualDoc Web

Varre a pasta raiz onde ficam os projetos de documentação (gerados pelo
PasDoc) e gera um único arquivo JSON (_perpetualdoc_index.json) com tudo que
o site precisa pra montar a busca, sem precisar ler e processar cada HTML na
hora que alguém abre o site no navegador.

Não depende de nenhuma biblioteca externa — só a biblioteca padrão do Python
(funciona com qualquer Python 3, sem "pip install" de nada).

Uso:
    python gerar_indice.py
        (varre a MESMA pasta onde este arquivo gerar_indice.py está salvo —
        é o uso normal: coloque o script dentro da pasta raiz da documentação)

    python gerar_indice.py --compacto                (grava sem indentação, arquivo menor)
    python gerar_indice.py "C:/outra/pasta"          (varre outra pasta em vez da própria)
    python gerar_indice.py --saida "C:/outro/lugar/indice.json"

Se já existir um JSON com o mesmo nome, o conteúdo novo é comparado com o
existente (ignorando só a data de geração); se não houver nenhuma mudança de
verdade nas documentações, o arquivo NÃO é regravado — evita ficar sujando o
controle de versão com um commit toda vez que o script roda sem nada ter
mudado.
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser

NOME_JSON_PADRAO = "_perpetualdoc_index.json"
PASTAS_IGNORADAS = {".git", ".svn", "__pycache__", "node_modules", ".vscode", ".idea"}
VERSAO_FORMATO = 1

# Pasta onde este próprio arquivo .py está — é sempre a pasta varrida por padrão,
# não importa de onde o script for chamado (agendador de tarefas, duplo clique,
# terminal aberto em outro lugar etc.).
PASTA_DO_SCRIPT = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Leitura de HTML com o encoding certo (documentação PasDoc/Delphi antiga
# costuma sair em windows-1252 ou ISO-8859-1, não UTF-8) — mesma lógica de
# cascata usada no site: charset declarado no próprio arquivo -> utf-8 ->
# windows-1252 -> iso-8859-1.
# ---------------------------------------------------------------------------

def ler_como_texto(caminho):
    with open(caminho, "rb") as f:
        dados = f.read()

    declarado = None
    try:
        cabecalho = dados[:4096].decode("iso-8859-1", errors="replace")
        m = re.search(r'charset\s*=\s*["\']?\s*([a-zA-Z0-9_\-]+)', cabecalho, re.IGNORECASE)
        if m:
            declarado = m.group(1).lower()
    except Exception:
        pass

    tentativas = []
    if declarado:
        tentativas.append(declarado)
    tentativas += ["utf-8", "windows-1252", "iso-8859-1"]

    for enc in tentativas:
        try:
            return dados.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return dados.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Extração de texto visível e do <title>, ignorando <script>/<style> — mesma
# ideia do DOMParser + textContent usado no site.
# ---------------------------------------------------------------------------

class ExtratorTexto(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._partes = []
        self._pular = 0
        self._dentro_titulo = False
        self._titulo_partes = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._pular += 1
        elif tag == "title":
            self._dentro_titulo = True

    def handle_startendtag(self, tag, attrs):
        pass  # tags auto-fechadas (<img/>, <br/>, etc.) não têm conteúdo de texto

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._pular > 0:
            self._pular -= 1
        elif tag == "title":
            self._dentro_titulo = False

    def handle_data(self, data):
        if self._dentro_titulo:
            self._titulo_partes.append(data)
        if self._pular == 0:
            self._partes.append(data)

    def texto(self):
        return re.sub(r"\s+", " ", "".join(self._partes)).strip()

    def titulo(self):
        t = "".join(self._titulo_partes).strip()
        return t or None


def extrair_arquivo(caminho_absoluto):
    texto_html = ler_como_texto(caminho_absoluto)
    extrator = ExtratorTexto()
    try:
        extrator.feed(texto_html)
    except Exception:
        pass
    return extrator.texto(), extrator.titulo()


# ---------------------------------------------------------------------------
# Normalização — idêntica à função normalizar() do site (sem acento,
# minúsculo, só [a-z0-9_-./ ]) — pra a busca funcionar do mesmo jeito
# independente de vir do JSON ou de uma varredura ao vivo.
# ---------------------------------------------------------------------------

def normalizar(texto):
    texto = texto or ""
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9_\-./ ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# ---------------------------------------------------------------------------
# Varredura da pasta
# ---------------------------------------------------------------------------

def caminho_posix(rel):
    return rel.replace(os.sep, "/")


def escanear(pasta_raiz):
    """Retorna (lista de caminhos relativos de arquivos .html, lista de
    pastas — relativas — que têm um index.html direto nelas)."""
    html_files = []
    doc_folders = []

    for atual, subpastas, arquivos in os.walk(pasta_raiz):
        subpastas[:] = sorted(d for d in subpastas if d.lower() not in PASTAS_IGNORADAS)

        rel_atual = os.path.relpath(atual, pasta_raiz)
        rel_atual = "" if rel_atual == "." else caminho_posix(rel_atual)

        tem_index = False
        for nome in sorted(arquivos):
            if nome.lower().endswith((".html", ".htm")):
                relp = (rel_atual + "/" + nome) if rel_atual else nome
                html_files.append(relp)
                if nome.lower() == "index.html":
                    tem_index = True

        if tem_index:
            doc_folders.append(rel_atual)

    return html_files, doc_folders


def montar_documentos(pasta_raiz, html_files, doc_folders):
    textos = {}
    titulos = {}

    for relp in html_files:
        caminho_abs = os.path.join(pasta_raiz, *relp.split("/"))
        try:
            texto, titulo = extrair_arquivo(caminho_abs)
        except Exception as e:
            print(f"  aviso: não consegui ler '{relp}' ({e}); seguindo sem ele", file=sys.stderr)
            texto, titulo = "", None
        textos[relp] = texto
        titulos[relp] = titulo

    nome_raiz = os.path.basename(os.path.abspath(pasta_raiz).rstrip("/\\")) or pasta_raiz

    documentos = []
    for rel_folder in doc_folders:
        index_path = (rel_folder + "/index.html") if rel_folder else "index.html"
        if index_path not in textos:
            continue

        nome_pasta = rel_folder.split("/")[-1] if rel_folder else nome_raiz
        title = titulos.get(index_path) or nome_pasta
        index_text = textos.get(index_path, "")

        prefixo = (rel_folder + "/") if rel_folder else ""
        texto_combinado = f"{title} {rel_folder} {index_text}"
        for relp in html_files:
            if relp == index_path or not relp.startswith(prefixo):
                continue
            texto_combinado += f" {relp} {textos.get(relp, '')}"

        documentos.append({
            "title": title,
            "relFolder": rel_folder,
            "indexPath": index_path,
            "normText": normalizar(texto_combinado),
            "normTitle": normalizar(title),
            "normPath": normalizar(rel_folder),
            "snippetSource": index_text or texto_combinado,
        })

    documentos.sort(key=lambda d: d["relFolder"])
    return documentos


# ---------------------------------------------------------------------------
# Geração + comparação com o arquivo existente
# ---------------------------------------------------------------------------

def gerar(pasta_raiz, caminho_json, compacto=False):
    print(f"Varrendo '{pasta_raiz}'...")
    html_files, doc_folders = escanear(pasta_raiz)
    print(f"  {len(html_files)} arquivo(s) .html encontrados, {len(doc_folders)} documentação(ões) (pastas com index.html)")

    documentos = montar_documentos(pasta_raiz, html_files, doc_folders)

    anterior = None
    if os.path.exists(caminho_json):
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                anterior = json.load(f)
        except Exception as e:
            print(f"  aviso: não consegui ler o JSON existente ({e}); vou tratar como se não existisse", file=sys.stderr)
            anterior = None

    mudou = anterior is None or anterior.get("documentos") != documentos

    if not mudou:
        print(f"Sem mudanças de conteúdo — arquivo mantido como está: {caminho_json}")
        return False

    novo = {
        "versao": VERSAO_FORMATO,
        "geradoEm": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "documentos": documentos,
    }

    # Formatado (indentado) por padrão, pra dar pra ver as alterações num diff
    # (SVN, Git etc.) — cada campo e cada documento numa linha própria.
    kwargs = {"ensure_ascii": False, "sort_keys": True}
    if compacto:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2

    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(novo, f, **kwargs)

    print(f"Atualizado — {len(documentos)} documentação(ões): {caminho_json}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Gera o índice de busca (_perpetualdoc_index.json) pro PerpetualDoc Web."
    )
    parser.add_argument("pasta", nargs="?", default=PASTA_DO_SCRIPT, help="Pasta raiz onde estão as documentações (padrão: a mesma pasta onde este script .py está salvo)")
    parser.add_argument("--saida", default=None, help="Caminho do arquivo JSON de saída (padrão: <pasta>/_perpetualdoc_index.json)")
    parser.add_argument("--compacto", action="store_true", help="Grava o JSON sem indentação (arquivo menor, mas fica ruim de ler num diff). Por padrão, sai formatado/indentado.")
    args = parser.parse_args()

    pasta_raiz = os.path.abspath(args.pasta)
    if not os.path.isdir(pasta_raiz):
        print(f"Pasta não encontrada: {pasta_raiz}", file=sys.stderr)
        sys.exit(1)

    caminho_json = args.saida or os.path.join(pasta_raiz, NOME_JSON_PADRAO)

    try:
        gerar(pasta_raiz, caminho_json, compacto=args.compacto)
    except Exception as e:
        print(f"Erro ao gerar o índice: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
