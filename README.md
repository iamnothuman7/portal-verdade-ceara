# Portal Verdade Ceará — Gestão interna

Sistema privado para administrar a operação comercial e financeira do Portal Verdade Ceará.

## Funcionalidades

- login obrigatório e painel responsivo;
- cadastro de clientes (lojas, empresas e prestadores de serviços);
- estúdio de contratos com modelos reutilizáveis e campos automáticos;
- contratos em PDF A4 com identidade visual, vigência, valor e pacote de materiais;
- cotas mensais de stories, feed, vídeo, reels, matérias, banners e outros;
- quadro de produção por etapas e acompanhamento de status;
- assinatura eletrônica por link individual, com data, IP e comprovante criptográfico;
- financeiro com previsto x realizado, filtros, contas pendentes e atrasadas;
- relatórios financeiros e contratos em PDF A4 com papel timbrado;
- cadastros personalizados e área administrativa avançada com a identidade do Portal.

## Desenvolvimento

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

No Windows, substitua `.venv/bin/` por `.venv\Scripts\`.

Copie `.env.example` para um arquivo `.env` apenas se o seu ambiente carregar esse arquivo. Em produção, as variáveis são carregadas pelo `systemd` a partir de um arquivo externo ao repositório.

## Testes

```bash
python manage.py check
python manage.py makemigrations --check
python manage.py test
```

Consulte [docs/producao.md](docs/producao.md) para implantação, atualização, backup e rollback.
