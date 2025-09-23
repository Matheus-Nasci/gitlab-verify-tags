# GitLab Verify Tags For Environment

Script em python para verificar se a tag já passou pela branchs específica antes de subir para PRD (production)

## Requisitos

- Python 3.8+
- Dependências:

```
pip install -r requirements.txt
```

## Variáveis de ambiente

Argumentos com .ENV
- `GITLAB_URL`   – URL do seu GitLab (ex.: `https://gitlab.com` ou `https://gitlab.seu-dominio.com`)
- `GITLAB_TOKEN` – Token de acesso pessoal com permissões necessárias
- `GITLAB_PROJECT_ID` – ID do projeto (ex.: '1023090123')
- `TAG_NAME` – Tag que está rodando no momento para ser analisada e verificar se passou pela branch (ex.: 'v1.5.8')
- `BRANCH_NAME` – Branch a ser analisada (ex.: 'homologation')

Argumentos via CLI

```
python3 verify_tags.py 
    --gitlab-url https://gitlab.seu-dominio.com \
    --private-token TOKEN_EXEMPLO \
    --project-id PID_PROJETO 
    --tag-name TAG
    --branch-name SUA_BRANCH 
```
