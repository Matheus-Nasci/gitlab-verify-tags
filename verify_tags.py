import argparse
import os
import sys
from dotenv import load_dotenv 
from typing import Iterable, List, Tuple

# Gitab API imports
import gitlab
from gitlab.exceptions import GitlabError 

load_dotenv()

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify GitLab tags for production.")
    parser.add_argument(
        "--gitlab-url",
        required=False,
        default=os.environ.get("GITLAB_URL"),
        help="GitLab instance URL"
    )
    parser.add_argument(
        "--private-token",
        required=False, 
        default=os.environ.get("GITLAB_TOKEN"), 
        help="Private token for GitLab API"
    )
    parser.add_argument(
        "--project-id",
        required=False,
        default=os.environ.get("GITLAB_PROJECT_ID"),
        help="GitLab project ID"
    )
    parser.add_argument(
        "--tag-name",
        required=False,
        default=os.environ.get("TAG_NAME"),
        help="Tag name to verify"
    )

    return parser.parse_args()

def login_to_gitlab(gitlab_url: str, private_token: str) -> gitlab.Gitlab:
    gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
    gl.auth()
    return gl

def get_pipeline_for_tag(gl: gitlab.Gitlab, pid_repository: str, tag_name: str) -> List:
    errors = []
    try:
        project = gl.projects.get(pid_repository)
        pipelines = project.pipelines.list(ref=tag_name)
        return pipelines
    except GitlabError as e:  # falta permissão, protegidos por política, etc.
        errors.append((pid_repository, str(e)))
    except Exception as e:
        errors.append((pid_repository, str(e)))
    
    if not pipelines:
        print(f"Não foi encontrado a tag: {tag_name}")
        return 1

def main():
    args = parse_args()
    # Login no GitLab
    gl = login_to_gitlab(args.gitlab_url, args.private_token)

    get_pipeline_for_tag(gl, args.project_id, args.tag_name)

    pipelines = get_pipeline_for_tag(gl, args.project_id, args.tag_name)

    # verifica se algum pipeline já rodou em homologação com sucesso
    homologation_check = any(
        p.status == "success" and any(b.environment and b.environment['name'] == "homologation" for b in p.jobs.list())
        for p in pipelines
    )

    if not homologation_check:
        print(f"Tag {args.tag_run} ainda não passou por homologação!")
        exit(1)
    else:
        print(f"Tag {args.tag_run} já passou em homologação, pode seguir para produção.")

if __name__ == "__main__":
    sys.exit(main())