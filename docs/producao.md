# Produção — Portal Verdade Ceará

## Arquitetura

- Aplicação: Django + Gunicorn
- Domínio: `portalverdadeceara.nabio.pro`
- Proxy público: Nginx nas portas 80 e 443
- Aplicação interna: `127.0.0.1:8070`
- Serviço: `portalverdadeceara.service`
- Banco: `portalverdadeceara_prod`
- Usuário do banco: `portalverdadeceara_app`
- Usuário do sistema: `portalverdadeceara`

## Diretórios

```text
/var/www/apps/portalverdadeceara/
├── current -> releases/AAAAmmdd-HHMMSS-COMMIT
├── releases/
├── shared/
│   ├── .env
│   ├── media/
│   ├── staticfiles/
│   ├── logs/
│   └── backups/
└── venv/
```

Cada release deve conter exatamente um commit já testado e enviado ao GitHub. O processo roda sem privilégios de root e escuta apenas no endereço local.

## Variáveis necessárias

- `DJANGO_DEBUG`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_HSTS_SECONDS`
- `DJANGO_STATIC_ROOT`
- `DJANGO_MEDIA_ROOT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

Os valores ficam somente em `/var/www/apps/portalverdadeceara/shared/.env`, com modo `0640`, e nunca no Git.

## Deploy inicial

1. Criar o usuário de sistema, os diretórios compartilhados e o ambiente virtual.
2. Criar banco e usuário PostgreSQL exclusivos.
3. Baixar o commit publicado para um novo diretório dentro de `releases/`.
4. Instalar `requirements.txt` no ambiente virtual.
5. Executar `migrate`, `collectstatic --noinput`, `check --deploy` e os testes.
6. Apontar `current` para a release testada.
7. Instalar e iniciar somente `portalverdadeceara.service`.
8. Validar `127.0.0.1:8070/health/`.
9. Instalar `deploy/nginx-http.conf` como configuração Nginx exclusiva, executar `nginx -t` e recarregar o Nginx.
10. Emitir o certificado exclusivamente com `certbot certonly --webroot -w /var/www/apps/portalverdadeceara/shared/acme -d portalverdadeceara.nabio.pro`, sem permitir que o Certbot edite blocos coringa de outros projetos.
11. Substituir a configuração por `deploy/nginx-https.conf`, executar `nginx -t`, recarregar o Nginx, validar HTTPS e então habilitar HSTS.

## Atualização

1. Testar e enviar a alteração ao GitHub.
2. Registrar o commit e criar backup do banco:

```bash
pg_dump portalverdadeceara_prod > /var/www/apps/portalverdadeceara/shared/backups/portalverdadeceara_DATA_HORA_COMMIT.sql
```

3. Criar uma nova release a partir do commit remoto.
4. Instalar dependências, executar testes, migrations e `collectstatic`.
5. Trocar o link `current` de forma atômica.
6. Reiniciar somente `portalverdadeceara.service` e validar os health checks.
7. Manter ao menos a release anterior.

## Rollback

1. Identificar a última release saudável.
2. Reapontar `current` para essa release.
3. Reiniciar somente `portalverdadeceara.service`.
4. Restaurar banco apenas quando uma migration incompatível exigir e após confirmação do backup.
5. Validar a porta local, o domínio e os logs.

## Operação

- Status: `systemctl status portalverdadeceara.service`
- Logs do serviço: `journalctl -u portalverdadeceara.service -n 100 --no-pager`
- Logs da aplicação: `/var/www/apps/portalverdadeceara/shared/logs/`
- Health interno: `curl --fail http://127.0.0.1:8070/health/`
- Health público: `curl --fail https://portalverdadeceara.nabio.pro/health/`
- Teste Nginx: `nginx -t`
- Certificados: `certbot certificates`
- Renovação: `certbot renew --dry-run`

## Emergência

Se a aplicação falhar, não altere outros serviços. Consulte primeiro o status e os logs exclusivos, volte o link `current` para a release anterior e reinicie apenas o serviço do Portal. A porta 8040 e o `jumbi.service` nunca fazem parte deste procedimento.
