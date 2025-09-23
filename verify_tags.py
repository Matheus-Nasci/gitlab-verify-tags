import os
import sys
import gitlab
import argparse
from typing import List
from dotenv import load_dotenv
from gitlab.exceptions import GitlabError

load_dotenv()

def handle_gitlab_error(context: str, error: Exception, exit_on_error: bool = True):
    if isinstance(error, GitlabError):
        print(f"Erro no {context}: {error.error_message if hasattr(error, 'error_message') else str(error)}")
    else:
        print(f"Erro inesperado no {context}: {str(error)}")

    if exit_on_error:
        sys.exit(1)

def parse_args() -> argparse.Namespace:
    # argumentos para as funções
    parser = argparse.ArgumentParser(description="Verify GitLab tags for production.")
    parser.add_argument(
        "--gitlab-url",
        required=True,
        default=os.environ.get("GITLAB_URL"),
        help="GitLab instance URL"
    )
    parser.add_argument(
        "--private-token",
        required=True,
        default=os.environ.get("GITLAB_TOKEN"),
        help="Private token for GitLab API"
    )
    parser.add_argument(
        "--project-id",
        required=True,
        default=os.environ.get("GITLAB_PROJECT_ID"),
        help="GitLab project ID"
    )
    parser.add_argument(
        "--tag-name",
        required=True,
        default=os.environ.get("TAG_NAME"),
        help="Tag name to verify"
    )
    parser.add_argument(
        "--branch-name",
        required=True,
        default=os.environ.get("BRANCH_NAME"),
        help="Branch name to check pipelines"
    )

    return parser.parse_args()

def login_to_gitlab(gitlab_url: str, private_token: str) -> gitlab.Gitlab:
    # autenticação no GitLab via token
    try:
        gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
        gl.auth()
        return gl
    except GitlabError as e:
        handle_gitlab_error("login_to_gitlab", e)

def get_commit_from_tag(gl: gitlab.Gitlab, project_id: str, tag: str) -> str:
    try:
        project = gl.projects.get(project_id)
        tag_obj = project.tags.get(tag)
        return tag_obj.commit["id"]
    except Exception as e:
        handle_gitlab_error("get_commit_from_tag", e)

def check_branch_pipeline(gl: gitlab.Gitlab, project_id: str, commit_sha: str, tag: str, branch: str) -> bool:
    # pega todas as pipelines com a tag
    try:
        project = gl.projects.get(project_id)

        # pega todos commits da branch
        commits = project.commits.list(ref_name=branch, per_page=100)

        # verifica se o commit da tag existe na branch
        commit_in_branch = any(c.id == commit_sha for c in commits)

        if not commit_in_branch:
            print(f"O commit da tag {tag} não existe na branch {branch}.")
            return False

        # se o commit existe, verifica se alguma pipeline da homologation passou com sucesso
        pipelines = project.pipelines.list(ref="", per_page=100)
        for p in pipelines:
            pipeline = project.pipelines.get(p.id)
            if pipeline.status == "success":
                print(f"Tag {tag} já passou pela branch {branch} com sucesso.")
                return True

        print(f"Tag {tag} ainda não teve pipeline bem-sucedida em {branch}.")
        return False

    except Exception as e:
        handle_gitlab_error("check_homologation_pipeline", e)

def main():
    # carregando os argumentos do .env ou linha de comando
    args = parse_args()

    # login no GitLab
    gl = login_to_gitlab(args.gitlab_url, args.private_token)

    # pega o commit SHA da tag
    commit_sha = get_commit_from_tag(gl, args.project_id, args.tag_name)
    
    # validação da tag 
    check_branch_pipeline(gl, args.project_id, commit_sha, args.tag_name, args.branch_name)

if __name__ == "__main__":
    sys.exit(main())