"""
Python script to generate a new GitHub tag bumping its version following semver rules
"""

import os
import sys

from semver import Version

from configuration import BumpStrategy, Configuration
from github_helpers import GitHubHelper

config = Configuration.from_env()

if config.DRY_RUN:
    print("Running in dry-run mode!")

if os.environ.get("GITHUB_REF_NAME") != config.DEFAULT_BRANCH:
    print("Not running from the default branch")
    sys.exit()

github_helper = GitHubHelper(os.environ.get("INPUT_GITHUB_TOKEN", ""), config)
last_tag = github_helper.get_latest_tag()
print(f"Previous tag version: {last_tag}")
bump_strategy = config.get_bump_strategy_from_commits(
    github_helper.get_commits_since(last_tag.date)
)

if bump_strategy == BumpStrategy.SKIP.value:
    print("No need to create a new tag, skipping")
    sys.exit()

# def bump_tag_version(strategy: BumpStrategy, last_available_tag: Tag) -> Tag:
#     """Create a new Tag resource with the increased version number"""
#     current_version = Version.parse(
#         last_available_tag.name.removeprefix(config.PREFIX).removesuffix(config.SUFFIX)
#     )
#     new_version = current_version
#     if strategy == BumpStrategy.MAJOR.value:
#         new_version = current_version.bump_major()
#     elif strategy == BumpStrategy.MINOR.value:
#         new_version = current_version.bump_minor()
#     elif strategy == BumpStrategy.PATCH.value:
#         new_version = current_version.bump_patch()

#     print(strategy, new_version, last_available_tag)
#     return Tag(
#         name=config.PREFIX + str(new_version) + config.SUFFIX,
#         commit=github_helper.get_last_commit().commit.sha,
#     )


new_tag = last_tag.bump_version(bump_strategy, config)
last_commit = github_helper.get_last_commit()
print(f"Creating new tag version: {new_tag}")
github_helper.create_git_tag(new_tag)

if config.BIND_TO_MAJOR:
    last_major_tag = github_helper.get_latest_major_tag()
    last_major_tag.commit = github_helper.get_last_commit().commit.sha
    if bump_strategy != BumpStrategy.MAJOR.value:
        github_helper.delete_git_tag(last_major_tag.name)
        print(
            f"Binding major tag {last_major_tag} to latest commit: {last_major_tag.commit}"
        )
        github_helper.create_git_tag(last_major_tag)
    else:
        new_major_tag_name = (
            config.PREFIX
            + str(
                Version.parse(
                    new_tag.name.removeprefix(config.PREFIX).removesuffix(config.SUFFIX)
                ).major
            )
            + config.SUFFIX
        )
        last_major_tag.name = new_major_tag_name
        print(f"Creating new major tag {last_major_tag}")
        github_helper.create_git_tag(last_major_tag)
