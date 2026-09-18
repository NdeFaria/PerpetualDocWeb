# PerpetualDoc Web

Interface web para consultar, num só lugar, várias documentações geradas pelo [PasDoc](https://pasdoc.github.io/) (Object Pascal / Delphi) — com busca instantânea por classe, unit ou conteúdo, e apresentando cada documentação **exatamente como ela é gerada**, sem alterar CSS, layout ou os recursos próprios dela (incluindo busca nativa, quando existir).

Repositório: **https://github.com/NdeFaria/PerpetualDocWeb**

## Tela de abertura

Ao abrir o site (primeira vez, ou depois de limpar os dados do navegador), você vê a tela de conexão:

![Selecionar pasta de documentação](screenshots/selecionar-pasta.png)

Clique em **Selecionar pasta** e escolha a **pasta raiz onde ficam todos os projetos de documentação** (a pasta que contém uma subpasta por projeto, cada uma com seu próprio `index.html` gerado pelo PasDoc — por exemplo `docs/`, contendo `docs/rh_folha/`, `docs/servidorthreads/` etc.). A varredura dessa pasta acontece só localmente, dentro do seu navegador — nada é enviado a lugar nenhum.

Da próxima vez que abrir o site (mesmo navegador, mesmo computador), ele lembra da pasta escolhida e só pede uma confirmação de um clique, sem precisar navegar até a pasta de novo.

## Como funciona (e por que é seguro)

Este site **não tem backend, não tem banco de dados e não guarda nada em nenhum servidor**. Tudo acontece dentro do seu próprio navegador:

1. Você escolhe, uma vez, a pasta onde as documentações estão salvas (local ou uma unidade de rede mapeada). O navegador pede sua permissão explícita pra isso — é a [File System Access API](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API), um recurso nativo do Chrome/Edge.
2. Essa permissão fica guardada só no seu navegador (IndexedDB local). O site nunca recebe o caminho real da pasta no disco, só o conteúdo dos arquivos que você autorizou.
3. Um [Service Worker](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API) — também um recurso nativo do navegador, sem servidor nenhum por trás — intercepta os pedidos de arquivo da documentação (HTML, CSS, imagens, scripts) e responde lendo o arquivo direto do disco, exatamente como está. Nada disso passa pela internet.
4. Busca por conteúdo (a barra do topo) também é feita 100% no seu navegador, lendo o texto dos arquivos localmente.

Pode conferir todo o código-fonte neste repositório — não existe nenhuma chamada de rede pra fora do seu navegador, em lugar nenhum.

## Requisitos

- **Google Chrome ou Microsoft Edge** (ou outro navegador baseado em Chromium). A File System Access API não existe no Firefox nem no Safari.
- Servir os arquivos via **http/https** — não funciona abrindo o `index.html` direto com duplo clique (`file://`), porque o Service Worker exige isso. Veja as opções abaixo.

## Arquivos do projeto

```
index.html      → a aplicação em si
sw.js           → Service Worker (tem que ficar na MESMA pasta que o index.html)
favicon.ico     → ícone do site
```

Os três precisam ser publicados juntos, na mesma pasta.

## Como rodar

### Testar localmente

Abrir o `index.html` direto não funciona (ver Requisitos). Suba um servidor bem simples na pasta do projeto:

```bash
python3 -m http.server 8080
# ou
npx serve .
```

E acesse `http://localhost:8080`.

### Publicar no Netlify

1. Coloque `index.html`, `sw.js` e `favicon.ico` numa pasta.
2. Acesse [app.netlify.com/drop](https://app.netlify.com/drop) e arraste a pasta (sem precisar de conta pra um teste rápido).
3. Pronto — link público gerado na hora.

### Publicar no GitHub Pages

1. Suba os três arquivos na raiz do repositório (ou na branch/pasta que o Pages vai servir).
2. Em **Settings → Pages**, aponte pra essa branch/pasta.
3. O site fica em `usuario.github.io/nome-do-repo/`.

> Funciona tanto na raiz de um domínio quanto num subcaminho (como o do GitHub Pages) — o app calcula os caminhos sozinho a partir de onde os arquivos estão.

## Como usar

1. Abra o site e clique em **Selecionar pasta**, apontando pra pasta raiz onde as documentações (uma subpasta por projeto, cada uma com seu `index.html`) estão salvas.
2. Digite na barra de busca do topo — os resultados aparecem por título, caminho ou conteúdo, conforme você digita.
3. Clique num resultado pra abrir a documentação daquele projeto, exatamente como o PasDoc gerou (CSS, navegação, busca própria — tudo intacto).
4. Dentro de uma documentação aberta, use o campo **Buscar nesta página** pra encontrar termos e navegar entre as ocorrências.
5. O ícone de sol/lua no topo alterna entre tema claro (documentação como veio) e escuro (uma paleta escura aplicada por cima, opcional).
6. Da próxima vez que abrir o site, ele lembra da pasta — só confirma o acesso com um clique.
7. Se alguém trocar de branch, atualizar os fontes ou adicionar/remover documentações na pasta conectada, use o botão de **reescanear** (o ícone de setas circulares, ao lado de "Trocar pasta") pra atualizar o índice de busca sem precisar reconectar a pasta do zero.

## Limitações conhecidas

- Só funciona em navegadores Chromium (Chrome, Edge).
- Não existe login com usuário/senha — cada pessoa conecta a própria pasta no próprio navegador. Isso é proposital: não ter isso é o que permite o site nunca ter acesso aos dados reais pela internet.
