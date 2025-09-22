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
    return parser.parse_args()

def login_to_gitlab(gitlab_url: str, private_token: str) -> gitlab.Gitlab:
    gl = gitlab.Gitlab(gitlab_url, private_token=private_token)
    gl.auth()
    return gl

def get_tag_project(gl: gitlab.Gitlab, pid_repository: str) -> Iterable:
    errors = []

    try:
        project = gl.projects.get(pid_repository)
        tags = project.tags.list()
        return tags
    except GitlabError as e:  # falta permissão, protegidos por política, etc.
        errors.append((pid_repository, str(e)))
    except Exception as e:
        errors.append((pid_repository, str(e)))

def verify_tags_in_environment(tags: List, environment: str) -> List[str]:
    verified_tags = []
    for tag in tags:
        if environment in tag.name:
            verified_tags.append(tag.name)
    return verified_tags

def main():
    args = parse_args()

    gl = login_to_gitlab(args.gitlab_url, args.private_token)
    tags = get_tag_project(gl, args.project_id)

    # verificando para subir nos ambientes
    for tag in tags:
        print(tag.name)


if __name__ == "__main__":
    sys.exit(main())