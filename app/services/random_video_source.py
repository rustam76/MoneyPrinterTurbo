"""
Random video source selector yang mengambil dari multiple providers.

Sistem ini mencari video dari Pexels, Pixabay, dan Coverr berdasarkan search term,
kemudian memilih satu secara random dari hasil yang terkumpul.
"""

import random
from typing import List, Optional

from loguru import logger

from app.models.schema import MaterialInfo, VideoAspect
from app.services.material import (
    search_videos_pexels,
    search_videos_pixabay,
    search_videos_coverr,
)


class RandomVideoSelector:
    """Selector untuk memilih video random dari multiple sources."""

    def __init__(self, timeout: int = 30, min_results: int = 1):
        """
        Initialize selector.

        Args:
            timeout: Timeout untuk setiap provider search (seconds)
            min_results: Minimum results yang diperlukan sebelum random selection
        """
        self.timeout = timeout
        self.min_results = min_results
        self.providers = ["pexels", "pixabay", "coverr"]

    def search_from_all_sources(
        self,
        search_term: str,
        minimum_duration: int = 5,
        video_aspect: VideoAspect = VideoAspect.portrait,
        enabled_providers: Optional[List[str]] = None,
    ) -> List[MaterialInfo]:
        """
        Search video dari semua enabled providers.

        Args:
            search_term: Keyword untuk search
            minimum_duration: Minimum durasi video dalam detik
            video_aspect: Aspect ratio (portrait, landscape, square)
            enabled_providers: List of providers to search (default: all)

        Returns:
            List of MaterialInfo dari semua sources
        """
        if enabled_providers is None:
            enabled_providers = self.providers

        all_results = []

        for provider in enabled_providers:
            try:
                logger.info(
                    f"searching {provider} for: {search_term!r}, "
                    f"aspect={video_aspect.name}"
                )

                if provider == "pexels":
                    results = search_videos_pexels(
                        search_term=search_term,
                        minimum_duration=minimum_duration,
                        video_aspect=video_aspect,
                    )
                elif provider == "pixabay":
                    results = search_videos_pixabay(
                        search_term=search_term,
                        minimum_duration=minimum_duration,
                        video_aspect=video_aspect,
                    )
                elif provider == "coverr":
                    results = search_videos_coverr(
                        search_term=search_term,
                        minimum_duration=minimum_duration,
                        video_aspect=video_aspect,
                    )
                else:
                    logger.warning(f"unknown provider: {provider}")
                    continue

                if results:
                    logger.info(
                        f"{provider} returned {len(results)} results for {search_term!r}"
                    )
                    all_results.extend(results)
            except Exception as e:
                logger.error(
                    f"error searching {provider}: {type(e).__name__}: {e}"
                )
                continue

        return all_results

    def select_random(
        self,
        search_term: str,
        minimum_duration: int = 5,
        video_aspect: VideoAspect = VideoAspect.portrait,
        enabled_providers: Optional[List[str]] = None,
    ) -> Optional[MaterialInfo]:
        """
        Search dari semua sources dan pilih satu secara random.

        Args:
            search_term: Keyword untuk search
            minimum_duration: Minimum durasi video
            video_aspect: Aspect ratio target
            enabled_providers: List of providers to search

        Returns:
            MaterialInfo yang dipilih random, atau None jika tidak ada hasil
        """
        all_results = self.search_from_all_sources(
            search_term=search_term,
            minimum_duration=minimum_duration,
            video_aspect=video_aspect,
            enabled_providers=enabled_providers,
        )

        if not all_results:
            logger.warning(
                f"no videos found for: {search_term!r}, aspect={video_aspect.name}"
            )
            return None

        if len(all_results) < self.min_results:
            logger.warning(
                f"insufficient results ({len(all_results)}) for {search_term!r}, "
                f"need minimum {self.min_results}"
            )
            return None

        selected = random.choice(all_results)
        logger.info(
            f"randomly selected video from {selected.provider}: "
            f"id={selected.source_info.get('asset_id') if isinstance(selected.source_info, dict) else 'unknown'}, "
            f"duration={selected.duration}s"
        )

        return selected

    def select_multiple_random(
        self,
        search_term: str,
        count: int = 5,
        minimum_duration: int = 5,
        video_aspect: VideoAspect = VideoAspect.portrait,
        enabled_providers: Optional[List[str]] = None,
    ) -> List[MaterialInfo]:
        """
        Search dan pilih beberapa videos secara random (without replacement).

        Args:
            search_term: Keyword untuk search
            count: Jumlah videos yang diinginkan
            minimum_duration: Minimum durasi video
            video_aspect: Aspect ratio target
            enabled_providers: List of providers to search

        Returns:
            List of MaterialInfo yang dipilih random
        """
        all_results = self.search_from_all_sources(
            search_term=search_term,
            minimum_duration=minimum_duration,
            video_aspect=video_aspect,
            enabled_providers=enabled_providers,
        )

        if not all_results:
            logger.warning(f"no videos found for: {search_term!r}")
            return []

        # Select up to count items without replacement
        selected_count = min(count, len(all_results))
        selected = random.sample(all_results, selected_count)

        logger.info(
            f"randomly selected {len(selected)} videos for {search_term!r} "
            f"from {len(all_results)} total results"
        )

        return selected


# Global instance
_selector = None


def get_selector() -> RandomVideoSelector:
    """Get or create global RandomVideoSelector instance."""
    global _selector
    if _selector is None:
        _selector = RandomVideoSelector()
    return _selector


def search_and_select_random(
    search_term: str,
    minimum_duration: int = 5,
    video_aspect: VideoAspect = VideoAspect.portrait,
    enabled_providers: Optional[List[str]] = None,
) -> Optional[MaterialInfo]:
    """
    Convenience function untuk random selection.

    Args:
        search_term: Keyword untuk search
        minimum_duration: Minimum durasi video
        video_aspect: Aspect ratio
        enabled_providers: List of providers

    Returns:
        Random MaterialInfo atau None
    """
    selector = get_selector()
    return selector.select_random(
        search_term=search_term,
        minimum_duration=minimum_duration,
        video_aspect=video_aspect,
        enabled_providers=enabled_providers,
    )


def search_and_select_multiple(
    search_term: str,
    count: int = 5,
    minimum_duration: int = 5,
    video_aspect: VideoAspect = VideoAspect.portrait,
    enabled_providers: Optional[List[str]] = None,
) -> List[MaterialInfo]:
    """
    Convenience function untuk multiple random selections.

    Args:
        search_term: Keyword untuk search
        count: Jumlah videos
        minimum_duration: Minimum durasi video
        video_aspect: Aspect ratio
        enabled_providers: List of providers

    Returns:
        List of random MaterialInfo
    """
    selector = get_selector()
    return selector.select_multiple_random(
        search_term=search_term,
        count=count,
        minimum_duration=minimum_duration,
        video_aspect=video_aspect,
        enabled_providers=enabled_providers,
    )
