#!/usr/bin/env python

import argparse
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
    current = None
    for line in markdown.splitlines():
        if line.startswith("### "):
            current = line[3:].strip()
            sections[current] = []
        elif current and line.strip():
            sections[current].append(line.strip())
    for sec, lines in sections.items():
        sections[sec] = [l[2:] if l.startswith("* ") else l for l in lines]
    return sections


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

# 4. Print out the notes
if release is not None:
    sections = parse_sections(release.body or "")

    catagories = {}
    for title, items in sections.items():
        if any(x in title for x in ["Other Changes", "Documentation", "Maintenance", "Tests"]):
            continue
        parsed = []
        for item in items:
            change = re.search("^(.*) by @.* in (.*)$", item)
            change_title = change.group(1)
            pr_link = change.group(2)
            pr_number = re.search(r"^.*/(\d+)$", pr_link)
            parsed.append({"pr_number": pr_number.group(1), "pr_url": pr_link, "title": change_title})
            # update the PR title with a capitalized first letter
            parsed[-1]["title"] = parsed[-1]["title"].capitalize()
        catagories[title] = parsed

data = {
    "version": NIC_VERSION,
    "release_date": RELEASE_DATE,
    "sections": catagories,
    "HELM_CHART_VERSION": HELM_CHART_VERSION,
    "K8S_VERSIONS": K8S_VERSIONS,
}

# Render with Jinja2
print(template.render(**data))

# todo
# group by type of change in depencencies

# To close connections after use
g.close()
