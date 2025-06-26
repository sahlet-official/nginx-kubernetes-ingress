#!/usr/bin/env python

import argparse
import json
import os
import re

from github import Auth, Github
from jinja2 import Environment, FileSystemLoader

# parse args
parser = argparse.ArgumentParser()
parser.add_argument("nic_version", help="NGINX Ingress Controller version")
parser.add_argument("helm_chart_version", help="NGINX Ingress Controller Helm chart version")
parser.add_argument("k8s_versions", help="Kubernetes versions")
parser.add_argument("release_date", help="Release date")
args = parser.parse_args()
NIC_VERSION = args.nic_version
HELM_CHART_VERSION = args.helm_chart_version
K8S_VERSIONS = args.k8s_versions
RELEASE_DATE = args.release_date

# Set up Jinja2 environment
template_dir = os.path.dirname(os.path.abspath(__file__))
env = Environment(loader=FileSystemLoader(template_dir))
template = env.get_template("release-notes.j2")


def parse_sections(markdown: str):
    sections = {}
    section_name = None
    for line in markdown.splitlines():
        # Check if the line starts with a section header
        # Section headers start with "### "
        # We will use the section header as the key in the sections dictionary
        # and the lines below it as the values (until the next section header)
        line = line.strip()
        if not line:
            continue  # skip empty lines
        if line.startswith("### "):
            section_name = line[3:].strip()
            sections[section_name] = []
        # If the line starts with "* " and contains "made their first contribution",
        # we will skip it as it is not a change but a contributor note
        elif section_name and line.startswith("* ") and "made their first contribution" in line:
            continue
        # Check if the line starts with "* " or "- "
        # If it does, we will add the line to the current section
        # We will also strip the "* " or "- " from the beginning of the line
        elif section_name and line.strip().startswith("* "):
            sections[section_name].append(line.strip()[2:].strip())
    return sections


def format_pr_groups(prs):
    # join the PR's into a comma, space separated string
    comma_sep_prs = "".join([f"{dep['details']}, " for dep in prs])

    # strip the last comma and space, and add the first PR title
    trimmed_comma_sep_prs = f"{comma_sep_prs.rstrip(', ')} {prs[0]['title']}"

    # split the string by the last comma and join with an ampersand
    split_result = trimmed_comma_sep_prs.rsplit(",", 1)
    return " &".join(split_result)


token = os.environ.get("GITHUB_TOKEN")

# using an access token
auth = Auth.Token(token)

# Public Web Github
g = Github(auth=auth)

# Then play with your Github objects:
ORG = os.getenv("GITHUB_ORG", "nginx")
REPO = os.getenv("GITHUB_REPO", "kubernetes-ingress")

repo = g.get_organization(ORG).get_repo(REPO)
release = None
releases = repo.get_releases()
for rel in releases:
    if rel.tag_name == f"v{NIC_VERSION}":
        release = rel
        break
if release is None:
    print(f"Release v{NIC_VERSION} not found in {ORG}/{REPO}.")
    exit(1)

# Parse the release body to extract sections
sections = parse_sections(release.body or "")

# Close github connection after use
g.close()

# Prepare the data for rendering
# We will create a dictionary with the sections and their changes
# Also, we will handle dependencies separately for Go and Docker images
# and format them accordingly
catagories = {}
dependencies_title = ""
for title, changes in sections.items():
    if any(x in title for x in ["Other Changes", "Documentation", "Maintenance", "Tests"]):
        continue
    parsed = []
    go_dependencies = []
    docker_dependencies = []
    for line in changes:
        print(line)
        change = re.search("^(.*) by @.* in (.*)$", line)
        change_title = change.group(1)
        pr_link = change.group(2)
        pr_number = re.search(r"^.*pull/(\d+)$", pr_link).group(1)
        if "Dependencies" in title:
            dependencies_title = title
            if "go group" in change_title or "go_modules group" in change_title:
                change_title = "Bump Go dependencies"
                pr = {"details": f"[{pr_number}]({pr_link})", "title": change_title}
                go_dependencies.append(pr)
            elif (
                "Docker image update" in change_title
                or "docker group" in change_title
                or "docker-images group" in change_title
                or "in /build" in change_title
            ):
                change_title = "Bump Docker dependencies"
                pr = {"details": f"[{pr_number}]({pr_link})", "title": change_title}
                docker_dependencies.append(pr)
            else:
                pr = f"[{pr_number}]({pr_link}) {change_title.capitalize()}"
                parsed.append(pr)
        else:
            pr = f"[{pr_number}]({pr_link}) {change_title.capitalize()}"
            parsed.append(pr)

    catagories[title] = parsed

# Add grouped dependencies to the Dependencies category
catagories[dependencies_title].append(format_pr_groups(docker_dependencies))
catagories[dependencies_title].append(format_pr_groups(go_dependencies))
catagories[dependencies_title].reverse()

# Populates the data needed for rendering the template
# The data will be passed to the Jinja2 template for rendering
data = {
    "version": NIC_VERSION,
    "release_date": RELEASE_DATE,
    "sections": catagories,
    "HELM_CHART_VERSION": HELM_CHART_VERSION,
    "K8S_VERSIONS": K8S_VERSIONS,
}

# Render with Jinja2
print(template.render(**data))
