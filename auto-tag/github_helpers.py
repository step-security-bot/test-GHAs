"""
PyGitHub wrapper
"""

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Self

import requests
from github import Commit, Github, InputGitAuthor
from semver import Version, VersionInfo

from configuration import BumpStrategy, Configuration


@dataclass
class Tag:
    """Tag resource"""

    name: str
    commit: str
    message: str = ""
    type: str = "commit"
    date: datetime = datetime.now()

    def bump_version(self, strategy: BumpStrategy, config: Configuration) -> Self:
        """Create a new Tag resource with the increased version number"""
        current_version = Version.parse(
            self.name.removeprefix(config.PREFIX).removesuffix(config.SUFFIX)
        )
        new_version = current_version
        if strategy == BumpStrategy.MAJOR.value:
            new_version = current_version.bump_major()
        elif strategy == BumpStrategy.MINOR.value:
            new_version = current_version.bump_minor()
        elif strategy == BumpStrategy.PATCH.value:
            new_version = current_version.bump_patch()

        self.name = config.PREFIX + str(new_version) + config.SUFFIX
        return self


class GitHubHelper:
    """PyGitHub support class"""

    def __init__(self, token, config) -> None:
        self.token: str = token
        self.config: Configuration = config
        self.repo = Github(token).get_repo(self.config.REPOSITORY)
        self.last_available_tag = self.get_latest_tag()
        self.last_available_major_tag = self.get_latest_major_tag()

    def get_commits_since(self, since: datetime):
        """Get a PaginatedList[Commit] since a predefined datetime"""
        return self.repo.get_commits(
            since=since + timedelta(seconds=1),
        )

    def get_last_commit(self) -> Commit.Commit:
        """Get the latest commit available on the repository"""
        return self.repo.get_commit(
            os.environ.get("GITHUB_SHA", self.repo.get_commits().get_page(0)[0].sha)
        )

    def get_latest_tag(self) -> Tag:
        """Get the latest tag matching prefix and suffix on the repository (e.g. test-v0.2.1)"""
        last_available_tag = None
        for tag in self.repo.get_tags():
            if (
                tag.name.startswith(self.config.PREFIX)
                and tag.name.endswith(self.config.SUFFIX)
                and VersionInfo.is_valid(
                    tag.name.removeprefix(self.config.PREFIX).removesuffix(
                        self.config.SUFFIX
                    )
                )
            ):
                last_available_tag = Tag(
                    name=tag.name,
                    commit=tag.commit.sha,
                    message=tag.commit.commit.message,
                    date=tag.commit.last_modified_datetime or datetime.now(),
                )
                break
        if last_available_tag is None:
            last_available_tag = Tag(
                name=self.config.PREFIX + "0.0.0" + self.config.SUFFIX,
                commit=self.get_last_commit().commit.sha,
            )
        return last_available_tag

    def get_latest_major_tag(self) -> Tag:
        """Get the latest major tag matching prefix and suffix on the repository (e.g. test-v1)"""
        last_available_major_tag = None
        for tag in self.repo.get_tags():
            if (
                tag.name.startswith(self.config.PREFIX)
                and tag.name.endswith(self.config.SUFFIX)
                and not VersionInfo.is_valid(
                    tag.name.removeprefix(self.config.PREFIX).removesuffix(
                        self.config.SUFFIX
                    )
                )
            ):
                last_available_major_tag = Tag(
                    name=tag.name,
                    commit=tag.commit.sha,
                    date=tag.commit.last_modified_datetime or datetime.now(),
                    message=tag.commit.commit.message,
                )
        if last_available_major_tag is None:
            last_available_major_tag = Tag(
                name=self.config.PREFIX + "0" + self.config.SUFFIX,
                commit=self.get_last_commit().commit.sha,
            )
        return last_available_major_tag

    def create_git_tag(self, tag: Tag) -> None:
        """Create a new tag on the repository bound to a specific commit"""
        commit = self.repo.get_commit(tag.commit)
        self.repo.create_git_tag(
            tag=tag.name,
            message=tag.message,
            object=tag.commit,
            type="commit",
            tagger=InputGitAuthor(
                name=str(commit.author.name),
                email=str(commit.author.email),
                date=str(datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")),
            ),
        )
        if not self.config.DRY_RUN:
            self.__create_git_ref(f"refs/tags/{tag.name}", tag.commit)

    def __create_git_ref(self, ref_name: str, sha: str) -> None:
        """Internal function to create the reference on GitHub"""
        self.repo.create_git_ref(ref_name, sha)

    def delete_git_tag(self, tag_name: str) -> None:
        """Custom function to delete a tag on the repository"""
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"https://api.github.com/repos/{self.config.REPOSITORY}/git/refs/tags/{tag_name}"
        requests.delete(url, headers=headers, timeout=10)
