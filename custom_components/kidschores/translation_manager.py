"""Translation Manager for Kids Chores Home Assistant integration.

This module provides functionality for:
- Downloading translations from remote sources
- Caching translations locally for offline use
- Validating translation data integrity
- Managing translation updates and fallbacks
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin

import aiofiles
import aiohttp

_LOGGER = logging.getLogger(__name__)

# Translation cache configuration
CACHE_DIR = "translations"
CACHE_EXPIRY_DAYS = 30
MIN_REQUIRED_KEYS = {"en": 10}  # Minimum required translation keys per language
SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "ja", "ko", "pt", "ru", "zh"]

# Translation sources
TRANSLATION_SOURCES = {
    "primary": "https://translations.example.com/kidschores/",
    "fallback": "https://fallback-cdn.example.com/kidschores/",
}


class TranslationValidationError(Exception):
    """Raised when translation data validation fails."""

    pass


class TranslationDownloadError(Exception):
    """Raised when translation download fails."""

    pass


class TranslationCacheManager:
    """Manages translation caching and retrieval with validation."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the translation cache manager.

        Args:
            cache_dir: Directory for caching translations. Defaults to temp directory.
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path("/tmp/kidschores_translations")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def initialize(self) -> None:
        """Initialize the session and load cached translations."""
        self._session = aiohttp.ClientSession()
        await self._load_cache()

    async def shutdown(self) -> None:
        """Shutdown the session and save cache."""
        if self._session:
            await self._session.close()

    async def _load_cache(self) -> None:
        """Load translations from cache directory."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                lang = cache_file.stem
                try:
                    async with aiofiles.open(cache_file, "r") as f:
                        content = await f.read()
                        data = json.loads(content)
                        self._cache[lang] = data["translations"]
                        # Restore timestamp
                        if "timestamp" in data:
                            self._cache_timestamps[lang] = datetime.fromisoformat(
                                data["timestamp"]
                            )
                        _LOGGER.debug(f"Loaded {lang} translations from cache")
                except (json.JSONDecodeError, KeyError) as e:
                    _LOGGER.warning(f"Failed to load cache for {lang}: {e}")
        except Exception as e:
            _LOGGER.error(f"Error loading translation cache: {e}")

    async def _save_cache(self, lang: str, translations: Dict[str, str]) -> None:
        """Save translations to cache file.

        Args:
            lang: Language code
            translations: Translation dictionary
        """
        try:
            cache_file = self.cache_dir / f"{lang}.json"
            cache_data = {
                "language": lang,
                "timestamp": datetime.utcnow().isoformat(),
                "translations": translations,
                "checksum": self._calculate_checksum(translations),
            }

            async with aiofiles.open(cache_file, "w") as f:
                await f.write(json.dumps(cache_data, indent=2, ensure_ascii=False))

            self._cache[lang] = translations
            self._cache_timestamps[lang] = datetime.utcnow()
            _LOGGER.debug(f"Saved {lang} translations to cache")
        except Exception as e:
            _LOGGER.error(f"Error saving cache for {lang}: {e}")

    @staticmethod
    def _calculate_checksum(translations: Dict[str, str]) -> str:
        """Calculate checksum for translation data.

        Args:
            translations: Translation dictionary

        Returns:
            SHA256 checksum of the translations
        """
        data = json.dumps(translations, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _validate_translations(
        lang: str, translations: Dict[str, str], checksum: Optional[str] = None
    ) -> None:
        """Validate translation data.

        Args:
            lang: Language code
            translations: Translation dictionary
            checksum: Optional checksum to validate against

        Raises:
            TranslationValidationError: If validation fails
        """
        if not isinstance(translations, dict):
            raise TranslationValidationError(f"Translations must be a dictionary for {lang}")

        min_keys = MIN_REQUIRED_KEYS.get(lang, MIN_REQUIRED_KEYS.get("en", 10))
        if len(translations) < min_keys:
            raise TranslationValidationError(
                f"Insufficient translations for {lang}: "
                f"expected at least {min_keys}, got {len(translations)}"
            )

        # Validate all keys and values are strings
        for key, value in translations.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TranslationValidationError(
                    f"Invalid translation entry in {lang}: key={key}, value={value}"
                )

        # Validate checksum if provided
        if checksum:
            calculated = TranslationCacheManager._calculate_checksum(translations)
            if calculated != checksum:
                raise TranslationValidationError(
                    f"Checksum mismatch for {lang}: expected {checksum}, got {calculated}"
                )

    def _is_cache_expired(self, lang: str) -> bool:
        """Check if cache is expired for a language.

        Args:
            lang: Language code

        Returns:
            True if cache is expired or missing
        """
        if lang not in self._cache_timestamps:
            return True

        age = datetime.utcnow() - self._cache_timestamps[lang]
        return age > timedelta(days=CACHE_EXPIRY_DAYS)

    async def _download_from_source(
        self, lang: str, source_url: str, timeout: int = 10
    ) -> Optional[Dict[str, str]]:
        """Download translations from a specific source.

        Args:
            lang: Language code
            source_url: Base URL of the translation source
            timeout: Request timeout in seconds

        Returns:
            Translation dictionary or None if download fails
        """
        if not self._session:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        url = urljoin(source_url, f"{lang}.json")

        try:
            async with self._session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()

                    # Extract translations and metadata
                    if isinstance(data, dict) and "translations" in data:
                        translations = data["translations"]
                        checksum = data.get("checksum")
                    else:
                        translations = data

                    # Validate before returning
                    self._validate_translations(lang, translations, checksum)
                    return translations

                _LOGGER.warning(f"Failed to download {lang} from {url}: {response.status}")
                return None

        except asyncio.TimeoutError:
            _LOGGER.warning(f"Timeout downloading {lang} from {url}")
            return None
        except aiohttp.ClientError as e:
            _LOGGER.warning(f"Client error downloading {lang}: {e}")
            return None
        except TranslationValidationError as e:
            _LOGGER.warning(f"Validation error for {lang}: {e}")
            return None
        except Exception as e:
            _LOGGER.error(f"Unexpected error downloading {lang}: {e}")
            return None

    async def get_translations(self, lang: str, force_refresh: bool = False) -> Dict[str, str]:
        """Get translations for a language with fallback strategy.

        Args:
            lang: Language code
            force_refresh: Force download even if cached

        Returns:
            Translation dictionary

        Raises:
            TranslationDownloadError: If all sources fail and no cache available
        """
        if not self._session:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        # Return cached translations if fresh and not forcing refresh
        if lang in self._cache and not force_refresh and not self._is_cache_expired(lang):
            _LOGGER.debug(f"Returning cached translations for {lang}")
            return self._cache[lang]

        # Try to download from all sources
        for source_name, source_url in TRANSLATION_SOURCES.items():
            _LOGGER.debug(f"Attempting to download {lang} from {source_name}")
            translations = await self._download_from_source(lang, source_url)

            if translations:
                await self._save_cache(lang, translations)
                _LOGGER.info(f"Successfully downloaded {lang} translations from {source_name}")
                return translations

        # Fall back to cached translations if available
        if lang in self._cache:
            _LOGGER.warning(
                f"Using stale cached translations for {lang} after download failures"
            )
            return self._cache[lang]

        # No translations available
        raise TranslationDownloadError(f"Failed to obtain translations for {lang}")

    async def get_all_translations(self, languages: Optional[list] = None) -> Dict[str, Dict]:
        """Get translations for multiple languages.

        Args:
            languages: List of language codes. Defaults to SUPPORTED_LANGUAGES

        Returns:
            Dictionary mapping language codes to translation dictionaries
        """
        languages = languages or SUPPORTED_LANGUAGES
        results = {}

        # Use asyncio.gather for parallel downloads
        tasks = [self.get_translations(lang) for lang in languages]

        try:
            translations_list = await asyncio.gather(*tasks, return_exceptions=True)

            for lang, translations in zip(languages, translations_list):
                if isinstance(translations, Exception):
                    _LOGGER.warning(f"Failed to get translations for {lang}: {translations}")
                else:
                    results[lang] = translations

        except Exception as e:
            _LOGGER.error(f"Error fetching multiple translations: {e}")

        return results

    async def export_translations(
        self, output_path: Path, languages: Optional[list] = None
    ) -> None:
        """Export translations to a file.

        Args:
            output_path: Path to export translations to
            languages: List of language codes to export
        """
        try:
            all_translations = await self.get_all_translations(languages)
            export_data = {
                "export_date": datetime.utcnow().isoformat(),
                "languages": all_translations,
                "count": {lang: len(trans) for lang, trans in all_translations.items()},
            }

            async with aiofiles.open(output_path, "w") as f:
                await f.write(json.dumps(export_data, indent=2, ensure_ascii=False))

            _LOGGER.info(f"Exported translations to {output_path}")

        except Exception as e:
            _LOGGER.error(f"Error exporting translations: {e}")
            raise

    async def validate_cache(self) -> Dict[str, bool]:
        """Validate all cached translations.

        Returns:
            Dictionary mapping language codes to validation status
        """
        results = {}

        for lang, translations in self._cache.items():
            try:
                self._validate_translations(lang, translations)
                results[lang] = True
                _LOGGER.debug(f"Cache validation passed for {lang}")
            except TranslationValidationError as e:
                results[lang] = False
                _LOGGER.warning(f"Cache validation failed for {lang}: {e}")

        return results

    async def clear_cache(self, lang: Optional[str] = None) -> None:
        """Clear cache for specified language(s).

        Args:
            lang: Language code to clear. If None, clears all cache.
        """
        try:
            if lang:
                cache_file = self.cache_dir / f"{lang}.json"
                if cache_file.exists():
                    cache_file.unlink()
                self._cache.pop(lang, None)
                self._cache_timestamps.pop(lang, None)
                _LOGGER.info(f"Cleared cache for {lang}")
            else:
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                self._cache.clear()
                self._cache_timestamps.clear()
                _LOGGER.info("Cleared all translation cache")

        except Exception as e:
            _LOGGER.error(f"Error clearing cache: {e}")
            raise


class TranslationManager:
    """High-level interface for translation management."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the translation manager.

        Args:
            cache_dir: Directory for caching translations
        """
        self._cache_manager = TranslationCacheManager(cache_dir)

    async def initialize(self) -> None:
        """Initialize the manager."""
        await self._cache_manager.initialize()

    async def shutdown(self) -> None:
        """Shutdown the manager."""
        await self._cache_manager.shutdown()

    async def get_translation(
        self, lang: str, key: str, default: str = ""
    ) -> str:
        """Get a single translation string.

        Args:
            lang: Language code
            key: Translation key
            default: Default value if translation not found

        Returns:
            Translation string or default
        """
        try:
            translations = await self._cache_manager.get_translations(lang)
            return translations.get(key, default)
        except Exception as e:
            _LOGGER.warning(f"Error getting translation for {lang}.{key}: {e}")
            return default

    async def get_dict(self, lang: str) -> Dict[str, str]:
        """Get all translations for a language.

        Args:
            lang: Language code

        Returns:
            Translation dictionary
        """
        try:
            return await self._cache_manager.get_translations(lang)
        except Exception as e:
            _LOGGER.error(f"Error getting translations for {lang}: {e}")
            return {}

    async def refresh(self, lang: Optional[str] = None) -> None:
        """Refresh translations from source.

        Args:
            lang: Specific language to refresh. If None, refreshes all.
        """
        if lang:
            await self._cache_manager.get_translations(lang, force_refresh=True)
        else:
            await self._cache_manager.get_all_translations(force_refresh=True)

    async def export(self, output_path: Path, languages: Optional[list] = None) -> None:
        """Export translations to file.

        Args:
            output_path: Path to export to
            languages: Languages to export
        """
        await self._cache_manager.export_translations(output_path, languages)

    async def validate(self) -> Dict[str, bool]:
        """Validate cached translations.

        Returns:
            Validation results by language
        """
        return await self._cache_manager.validate_cache()

    async def clear_cache(self, lang: Optional[str] = None) -> None:
        """Clear translation cache.

        Args:
            lang: Specific language to clear. If None, clears all.
        """
        await self._cache_manager.clear_cache(lang)
