"""GitHub profile adapter: fetch public profile and repos via REST API."""

import logging
import re
import os
from typing import Union, Optional, Dict, Any
import requests
from datetime import datetime

from .base import BaseSourceAdapter
from transformer.models import RawRecord

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


class GitHubProfileAdapter(BaseSourceAdapter):
    """Adapter for GitHub profiles via public REST API."""

    @property
    def source_name(self) -> str:
        return "github"

    def detect(self, input_source: Union[str, bytes, dict]) -> bool:
        """Detect if input is a GitHub username or profile URL."""
        if not isinstance(input_source, str):
            return False

        input_source = input_source.strip()

        # Pattern: github:username or github:https://github.com/username
        if input_source.startswith("github:"):
            return True

        # Pattern: github.com URL
        if "github.com/" in input_source:
            return True

        return False

    def extract(self, raw_input: Union[str, bytes, dict]) -> RawRecord:
        """Fetch GitHub profile and repos."""
        error = None
        profile_data = {}
        repos = []

        try:
            username = self._extract_username(raw_input)
            if not username:
                raise ValueError(f"Could not extract GitHub username from {raw_input}")

            # Fetch user profile
            user_data = self._fetch_user(username)
            if not user_data:
                raise ValueError(f"Failed to fetch GitHub user {username}")

            profile_data = {
                "name": user_data.get("name"),
                "bio": user_data.get("bio"),
                "location": user_data.get("location"),
                "profile_created_at": user_data.get("created_at"),
                "profile_updated_at": user_data.get("updated_at"),
                "public_repos": user_data.get("public_repos"),
                "followers": user_data.get("followers"),
            }

            # Fetch repositories to infer skills/languages
            repos_data = self._fetch_repos(username)
            repos = self._infer_skills_from_repos(repos_data)

            logger.info(f"Extracted GitHub profile for {username}, found {len(repos)} unique languages/topics")

        except requests.exceptions.RequestException as e:
            logger.warning(f"GitHub API error for {raw_input}: {e}")
            error = str(e)
        except Exception as e:
            logger.error(f"Error extracting GitHub profile from {raw_input}: {e}")
            error = str(e)

        return RawRecord(
            source_name=self.source_name,
            source_method="github_api",
            extracted_fields={
                "profile": profile_data,
                "languages": repos,  # Inferred programming languages/topics
            },
            parse_error=error,
        )

    @staticmethod
    def _extract_username(input_source: str) -> Optional[str]:
        """Extract GitHub username from various formats."""
        input_source = input_source.strip()

        # Format: github:username
        if input_source.startswith("github:"):
            return input_source[7:].strip()

        # Format: https://github.com/username or http://github.com/username
        match = re.match(r"https?://github\.com/([a-zA-Z0-9_-]+)", input_source)
        if match:
            return match.group(1)

        # Plain username?
        if re.match(r"^[a-zA-Z0-9_-]+$", input_source):
            return input_source

        return None

    @staticmethod
    def _fetch_user(username: str) -> Optional[Dict[str, Any]]:
        """Fetch user profile from GitHub API."""
        url = f"{GITHUB_API_BASE}/users/{username}"
        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch GitHub user {username}: {e}")
            return None

    @staticmethod
    def _fetch_repos(username: str) -> list:
        """Fetch user's public repositories."""
        url = f"{GITHUB_API_BASE}/users/{username}/repos"
        headers = {}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        repos = []
        page = 1

        try:
            while True:
                response = requests.get(
                    url,
                    params={"per_page": 100, "page": page},
                    headers=headers,
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()

                if not data:
                    break

                repos.extend(data)
                page += 1

                # Rate limit check
                if response.status_code == 403:
                    logger.warning("GitHub API rate limit reached")
                    break

        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching repos for {username}: {e}")

        return repos

    @staticmethod
    def _infer_skills_from_repos(repos: list) -> list:
        """Infer programming languages and topics from repos."""
        languages = {}
        topics = set()

        for repo in repos:
            # Language field
            if repo.get("language"):
                lang = repo["language"].lower()
                languages[lang] = languages.get(lang, 0) + 1

            # Topics/tags
            if repo.get("topics"):
                topics.update(repo["topics"])

        # Combine and deduplicate
        skills = list(languages.keys()) + list(topics)
        return list(set(skills))  # Deduplicate
