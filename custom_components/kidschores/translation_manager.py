"""
Translation Manager for Kids Chores Dashboard

This module handles downloading and caching translation files from a remote source.
It provides functionality to fetch translations, manage cache expiration, and retrieve
cached translation data.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_DURATION = timedelta(hours=24)
TRANSLATIONS_CACHE_DIR = "translations_cache"


class TranslationManager:
    """Manages translation downloads and caching for the Kids Chores dashboard."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_duration: timedelta = DEFAULT_CACHE_DURATION,
    ):
        """
        Initialize the TranslationManager.

        Args:
            cache_dir: Directory to store cached translations. Defaults to a local cache directory.
            cache_duration: How long to keep translations in cache. Defaults to 24 hours.
        """
        self.cache_dir = cache_dir or Path(TRANSLATIONS_CACHE_DIR)
        self.cache_duration = cache_duration
        self.cache_metadata_file = self.cache_dir / "metadata.json"
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure the cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_metadata(self) -> Dict[str, Any]:
        """
        Load cache metadata from disk.

        Returns:
            Dictionary containing cache metadata with timestamps.
        """
        if not self.cache_metadata_file.exists():
            return {}

        try:
            with open(self.cache_metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            _LOGGER.warning(f"Failed to load cache metadata: {e}")
            return {}

    def _save_cache_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Save cache metadata to disk.

        Args:
            metadata: Dictionary containing cache metadata to save.
        """
        try:
            with open(self.cache_metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
        except IOError as e:
            _LOGGER.error(f"Failed to save cache metadata: {e}")

    def _is_cache_valid(self, language_code: str) -> bool:
        """
        Check if cached translation for a language is still valid.

        Args:
            language_code: Language code (e.g., 'en', 'es', 'fr').

        Returns:
            True if cache is valid and fresh, False otherwise.
        """
        metadata = self._get_cache_metadata()

        if language_code not in metadata:
            return False

        try:
            timestamp = datetime.fromisoformat(metadata[language_code]["timestamp"])
            return datetime.utcnow() - timestamp < self.cache_duration
        except (KeyError, ValueError) as e:
            _LOGGER.warning(f"Invalid cache metadata for {language_code}: {e}")
            return False

    def _get_cache_file_path(self, language_code: str) -> Path:
        """
        Get the file path for cached translations of a specific language.

        Args:
            language_code: Language code (e.g., 'en', 'es', 'fr').

        Returns:
            Path to the cache file.
        """
        return self.cache_dir / f"{language_code}.json"

    async def download_translation(
        self, language_code: str, remote_url: str
    ) -> Optional[Dict[str, str]]:
        """
        Download a translation file from a remote URL.

        Args:
            language_code: Language code for the translation.
            remote_url: URL to download the translation from.

        Returns:
            Dictionary containing the translation data, or None if download failed.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(remote_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        translation_data = await response.json()
                        _LOGGER.info(f"Successfully downloaded translation for {language_code}")
                        return translation_data
                    else:
                        _LOGGER.error(f"Failed to download translation for {language_code}: HTTP {response.status}")
                        return None
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout downloading translation for {language_code}")
            return None
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Network error downloading translation for {language_code}: {e}")
            return None
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Invalid JSON in translation for {language_code}: {e}")
            return None

    def _save_translation_cache(
        self, language_code: str, translation_data: Dict[str, str]
    ) -> bool:
        """
        Save translation data to cache.

        Args:
            language_code: Language code for the translation.
            translation_data: Translation data to cache.

        Returns:
            True if save was successful, False otherwise.
        """
        try:
            cache_file = self._get_cache_file_path(language_code)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(translation_data, f, ensure_ascii=False, indent=2)

            # Update metadata
            metadata = self._get_cache_metadata()
            metadata[language_code] = {
                "timestamp": datetime.utcnow().isoformat(),
                "size": len(str(translation_data)),
            }
            self._save_cache_metadata(metadata)

            _LOGGER.info(f"Cached translation for {language_code}")
            return True
        except IOError as e:
            _LOGGER.error(f"Failed to cache translation for {language_code}: {e}")
            return False

    def get_cached_translation(self, language_code: str) -> Optional[Dict[str, str]]:
        """
        Retrieve cached translation for a language.

        Args:
            language_code: Language code (e.g., 'en', 'es', 'fr').

        Returns:
            Dictionary containing the translation data, or None if not cached or expired.
        """
        if not self._is_cache_valid(language_code):
            return None

        cache_file = self._get_cache_file_path(language_code)
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            _LOGGER.warning(f"Failed to load cached translation for {language_code}: {e}")
            return None

    async def get_translation(
        self, language_code: str, remote_url: str, use_cache: bool = True
    ) -> Optional[Dict[str, str]]:
        """
        Get translation for a language, using cache if available.

        Attempts to use cached translation if it's still valid. If cache is expired
        or doesn't exist, downloads fresh translation from the remote URL.

        Args:
            language_code: Language code (e.g., 'en', 'es', 'fr').
            remote_url: URL to download the translation from if not cached.
            use_cache: Whether to use cached translations. Defaults to True.

        Returns:
            Dictionary containing the translation data, or None if all attempts failed.
        """
        # Try to get from cache first
        if use_cache:
            cached = self.get_cached_translation(language_code)
            if cached is not None:
                _LOGGER.debug(f"Using cached translation for {language_code}")
                return cached

        # Download fresh translation
        translation_data = await self.download_translation(language_code, remote_url)

        # Cache the downloaded translation
        if translation_data is not None:
            self._save_translation_cache(language_code, translation_data)

        return translation_data

    def clear_cache(self, language_code: Optional[str] = None) -> bool:
        """
        Clear cached translations.

        Args:
            language_code: Specific language to clear. If None, clears all translations.

        Returns:
            True if clear was successful, False otherwise.
        """
        try:
            if language_code is None:
                # Clear all translations
                for cache_file in self.cache_dir.glob("*.json"):
                    if cache_file.name != "metadata.json":
                        cache_file.unlink()
                self.cache_metadata_file.unlink(missing_ok=True)
                _LOGGER.info("Cleared all translation caches")
            else:
                # Clear specific language
                cache_file = self._get_cache_file_path(language_code)
                if cache_file.exists():
                    cache_file.unlink()

                # Update metadata
                metadata = self._get_cache_metadata()
                metadata.pop(language_code, None)
                if metadata:
                    self._save_cache_metadata(metadata)
                else:
                    self.cache_metadata_file.unlink(missing_ok=True)

                _LOGGER.info(f"Cleared translation cache for {language_code}")

            return True
        except IOError as e:
            _LOGGER.error(f"Failed to clear cache: {e}")
            return False

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about cached translations.

        Returns:
            Dictionary containing cache statistics and metadata.
        """
        metadata = self._get_cache_metadata()
        cache_info = {
            "total_languages": len(metadata),
            "languages": [],
            "cache_directory": str(self.cache_dir),
            "cache_duration_hours": self.cache_duration.total_seconds() / 3600,
        }

        for language_code, data in metadata.items():
            cache_info["languages"].append(
                {
                    "code": language_code,
                    "cached_at": data.get("timestamp"),
                    "size_bytes": data.get("size", 0),
                }
            )

        return cache_info
