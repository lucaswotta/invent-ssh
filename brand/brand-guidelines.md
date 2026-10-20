# Diretrizes visuais do Invenux

## Conceito

Interface utilitária inspirada em sistemas operacionais desktop modernos (macOS Dark Mode), focada em legibilidade de tabelas densas, baixo ruído visual e precisão técnica.

## Paleta de Cores

- `bg_window`: `#1C1C1E` — fundo principal da janela e área de tabela
- `bg_sidebar`: `#232326` — navegação lateral e listas secundárias
- `bg_toolbar`: `#252528` — barra superior unificada
- `bg_card`: `#262629` — painéis de distribuição e cartões de resumo
- `bg_control`: `#36363A` — botões e gatilhos de popover
- `text_primary`: `#F5F5F7` — texto principal
- `text_secondary`: `#98989D` — rótulos secundários e cabeçalhos
- `text_tertiary`: `#6E6E73` — metadados de apoio
- `accent_blue`: `#0A84FF` — ação primária e seleção de linha
- `status_online`: `#30D158` — indicador de máquina online
- `status_warning`: `#FF9F0A` — falha de autenticação ou coleta parcial
- `status_offline`: `#FF453A` — máquina inacessível

## Tipografia

- Pilha principal: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", system-ui, sans-serif`
- Alinhamento numérico: `font-variant-numeric: tabular-nums` em endereços IP, contadores, capacidades e durações.

## Ícone

- Fonte: `icon.svg` (1024 px) e `icon-small.svg` (32 px, traço simplificado para 16 a 32 px).
- Desenho: quadrado arredondado escuro com três linhas; a primeira, azul (`#0A84FF`), traz o prompt `›_` (SSH); as duas seguintes são máquinas do inventário com status verde (`#30D158`).
- Arquivos gerados por `scripts/render_brand.py`: `icons/invenux-{16..1024}.png`, `invenux.ico`, `invenux.icns`, `social-preview.png` e os wordmarks do README em `docs/media/`.
- Wordmark: ícone + "Invenux" em Inter Display SemiBold, espaçamento -0,035em; texto `#F5F5F7` no tema escuro e `#1C1C1E` no claro.
