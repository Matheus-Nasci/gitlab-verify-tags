import os
import re
import sys
import gitlab
import argparse
import urllib3
from dotenv import load_dotenv
from gitlab.exceptions import GitlabError

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def handle_gitlab_error(context: str, error: Exception, exit_on_error: bool = True):
    if isinstance(error, GitlabError):
        print(f"Erro em {context}: {error.error_message if hasattr(error, 'error_message') else str(error)}")
    else:
        print(f"Erro inesperado em {context}: {str(error)}")

    if exit_on_error:
        sys.exit(1)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verificar Tags do GitLab para produção.")
    parser.add_argument(
        "--gitlab-url",
        required=True,
        default=os.environ.get("GITLAB_URL"),
        help="URL da instância do GitLab"
    )
    parser.add_argument(
        "--private-token",
        required=True,
        default=os.environ.get("GITLAB_TOKEN"),
        help="Token privado para a API do GitLab"
    )
    parser.add_argument(
        "--project-id",
        required=True,
        default=os.environ.get("GITLAB_PROJECT_ID"),
        help="ID do projeto no GitLab"
    )
    parser.add_argument(
        "--tag-name",
        required=True,
        default=os.environ.get("TAG_NAME"),
        help="Nome da tag para verificar"
    )
    parser.add_argument(
        "--ignore-ssl",
        required=True,
        default=os.environ.get("IGNORE_SSL"),
        help="Ignorar verificação de certificados SSL"
    )

    return parser.parse_args()

def login_to_gitlab(gitlab_url: str, private_token: str, ignore_ssl: bool) -> gitlab.Gitlab:
    try:
        if ignore_ssl.lower() == "true":
            gl = gitlab.Gitlab(gitlab_url, private_token=private_token, ssl_verify=False)
        else:
            gl = gitlab.Gitlab(gitlab_url, private_token=private_token)

        gl.auth()
        return gl
    except GitlabError as e:
        handle_gitlab_error("login_to_gitlab", e)

def extract_base_version(tag_name: str) -> str:
    """Extrai a versão base da tag"""
    match = re.match(r"v\d+\.\d+\.\d+", tag_name)
    if not match:
        raise SystemExit(f"Formato de tag inválido: {tag_name}. Esperado formato: vX.Y.Z[-sufixo]")
    return match.group()

def get_tag_type(tag_name: str) -> str:
    """Identifica o tipo da tag: 'beta', 'rc' ou 'release'""" 
    if "-beta." in tag_name:
        return "beta"
    elif "-rc." in tag_name:
        return "rc"
    else:
        return "release"

def check_version_pipeline(gl, project_id: str, tag_name: str, branch: str) -> bool:
    """
    Verifica se uma tag específica passou com sucesso pelo pipeline da branch especificada.
    
    Args:
        gl: Instância do GitLab
        project_id: ID do projeto
        tag_name: Nome completo da tag
        branch: Nome da branch para verificar
    
    Returns:
        True se encontrou pipeline com sucesso, False caso contrário
    """
    try:
        project = gl.projects.get(project_id)
        
        # Busca a tag específica
        tags = project.tags.list(search=tag_name, all=True)
        
        for tag in tags:
            if tag.name == tag_name:
                commit_sha = tag.commit['id']
                
                # Busca pipelines para o commit na branch especificada
                # Para branches com prefixo (release/*), busca todas as branches release
                if branch.startswith("release/"):
                    # Busca pipelines em qualquer branch que comece com release/
                    pipelines = project.pipelines.list(sha=commit_sha, per_page=100)
                    # Filtra pipelines que estão em branches release/*
                    release_pipelines = [p for p in pipelines if p.ref and p.ref.startswith("release/")]
                    if any(p.status == "success" for p in release_pipelines):
                        print(f"✓ Tag {tag_name} passou com sucesso no pipeline da branch {branch}")
                        return True
                else:
                    # Para branches específicas (development, homologation)
                    pipelines = project.pipelines.list(sha=commit_sha, ref=branch, per_page=100)
                    if any(p.status == "success" for p in pipelines):
                        print(f"✓ Tag {tag_name} passou com sucesso no pipeline da branch {branch}")
                        return True
        
        print(f"✗ Tag {tag_name} NÃO passou com sucesso no pipeline da branch {branch}")
        return False
    except Exception as e:
        handle_gitlab_error("check_version_pipeline", e)
        return False

def find_rc_tag_for_version(gl, project_id: str, base_version: str) -> str:
    """
    Encontra a tag RC correspondente à versão base.
    Retorna a tag RC mais recente encontrada.
    """
    try:
        project = gl.projects.get(project_id)
        tags = project.tags.list(search=base_version, all=True)
        
        rc_tags = [tag.name for tag in tags if f"{base_version}-rc." in tag.name]
        
        if not rc_tags:
            return None
        
        # Ordena as tags RC e retorna a mais recente (maior número)
        def extract_rc_number(tag):
            match = re.search(r"-rc\.(\d+)", tag)
            return int(match.group(1)) if match else 0
        
        rc_tags.sort(key=extract_rc_number, reverse=True)
        return rc_tags[0]
    except Exception as e:
        handle_gitlab_error("find_rc_tag_for_version", e)
        return None

def find_beta_tag_for_version(gl, project_id: str, base_version: str) -> str:
    """
    Encontra a tag beta correspondente à versão base.
    Retorna a tag beta mais recente encontrada.
    """
    try:
        project = gl.projects.get(project_id)
        tags = project.tags.list(search=base_version, all=True)
        
        beta_tags = [tag.name for tag in tags if f"{base_version}-beta." in tag.name]
        
        if not beta_tags:
            return None
        
        # Ordena as tags beta e retorna a mais recente (maior número)
        def extract_beta_number(tag):
            match = re.search(r"-beta\.(\d+)", tag)
            return int(match.group(1)) if match else 0
        
        beta_tags.sort(key=extract_beta_number, reverse=True)
        return beta_tags[0]
    except Exception as e:
        handle_gitlab_error("find_beta_tag_for_version", e)
        return None

def validate_deploy(gl, project_id: str, tag_name: str):
    """
    Valida se a tag pode ser deployada.
    
    Regras:
    1. Tags beta (development) - podem subir direto, sem validação
    2. Tags rc (homologation) - podem subir direto, sem validação
    3. Tags release (produção) - BLOQUEADAS se não passaram por homologation (rc)
    """
    base_version = extract_base_version(tag_name)
    tag_type = get_tag_type(tag_name)
    
    print(f"\n🔍 Validando tag: {tag_name}")
    print(f"   Tipo: {tag_type}")
    print(f"   Versão base: {base_version}\n")
    
    if tag_type == "beta":
        # Tags beta podem ser deployadas em development sem validação
        print(f"✓ Tag beta {tag_name} pode ser deployada em development")
        return True
    
    elif tag_type == "rc":
        # Tags rc podem ser deployadas em homologation sem validação
        print(f"✓ Tag RC {tag_name} pode ser deployada em homologation")
        return True
    
    elif tag_type == "release":
        # Tags de produção PRECISAM ter passado pelo ambiente de homologation (rc) - OBRIGATÓRIO
        print(f"📋 Verificando se tag RC correspondente passou em homologation...")
        rc_tag = find_rc_tag_for_version(gl, project_id, base_version)
        
        if not rc_tag:
            raise SystemExit(
                f"❌ ERRO: Tag de produção {tag_name} não pode ser deployada.\n"
                f"   Motivo: Não foi encontrada tag RC correspondente ({base_version}-rc.X) que passou em homologation.\n"
                f"   A tag de produção só pode ser deployada após a tag RC ter passado com sucesso no ambiente de homologation.\n"
                f"   Esta é uma regra obrigatória para garantir que o código foi testado antes de ir para produção."
            )
        
        if not check_version_pipeline(gl, project_id, rc_tag, "homologation"):
            raise SystemExit(
                f"❌ ERRO: Tag de produção {tag_name} não pode ser deployada.\n"
                f"   Motivo: Tag RC {rc_tag} não passou com sucesso no pipeline da branch homologation.\n"
                f"   A tag de produção só pode ser deployada após a tag RC ter passado com sucesso no ambiente de homologation.\n"
                f"   Esta é uma regra obrigatória para garantir que o código foi testado antes de ir para produção."
            )
        
        print(f"✓ Tag de produção {tag_name} pode ser deployada (passou por homologation)")
        return True
    
    else:
        raise SystemExit(f"❌ Tipo de tag desconhecido: {tag_type}")

def main():
    args = parse_args()
    gl = login_to_gitlab(args.gitlab_url, args.private_token, args.ignore_ssl.lower())
    
    try:
        permission_deploy_tag = validate_deploy(gl, args.project_id, args.tag_name)
        
        if permission_deploy_tag:
            print(f"\n✅ SUCESSO: A tag {args.tag_name} está autorizada para deploy!")
            return 0
        else:
            print(f"\n❌ FALHA: A tag {args.tag_name} NÃO está autorizada para deploy")
            return 1
    except SystemExit as e:
        print(f"\n{e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
