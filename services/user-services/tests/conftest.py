"""Shared fixtures and environment for user-service unit tests."""
import os

os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")
