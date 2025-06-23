#!/usr/bin/env python

import os
import re

from github import Auth, Github
from github.GithubException import UnknownObjectException


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
repo = g.get_organization("nginx").get_repo("kubernetes-ingress")
release = None
releases = repo.get_releases()
for rel in releases:
    if rel.tag_name == "v5.1.0":
        release = rel
        break

# # 4. Print out the notes
if release is not None:
    # print(release.body or "[no release notes]")

    sections = parse_sections(release.body or "")

    # 6) Print out your structured data
    for title, items in sections.items():
        if any(x in title for x in ["Other Changes", "Documentation", "Maintenance", "Tests"]):
            continue
        print(f"\nSection: {title}")
        for item in items:
            change = re.search("^(.*) by @.* in (.*)$", item)
            change_title = change.group(1)
            pr_link = change.group(2)
            pr_number = re.search(r"^.*/(\d+)$", pr_link)
            print(f"- [{pr_number.group(1)}]({pr_link}) {change_title}")

# todo
# group by type of change in depencencies

# To close connections after use
g.close()
