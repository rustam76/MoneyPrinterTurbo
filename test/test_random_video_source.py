"""
Test cases untuk Random Video Source System
"""

import pytest
from unittest.mock import Mock, patch
from app.services.random_video_source import (
    RandomVideoSelector,
    search_and_select_random,
    search_and_select_multiple,
)
from app.models.schema import MaterialInfo, VideoAspect


def create_mock_material(provider: str, duration: int = 10) -> MaterialInfo:
    """Helper untuk membuat mock MaterialInfo"""
    item = MaterialInfo()
    item.provider = provider
    item.url = f"https://example.com/{provider}/video.mp4"
    item.duration = duration
    item.source_info = {
        "provider": provider,
        "search_term": "test",
        "asset_id": f"{provider}_123",
    }
    return item


class TestRandomVideoSelector:
    """Test cases untuk RandomVideoSelector class"""

    def test_initialization(self):
        """Test selector dapat diinisialisasi dengan default values"""
        selector = RandomVideoSelector()
        assert selector.timeout == 30
        assert selector.min_results == 1
        assert len(selector.providers) == 3

    def test_initialization_with_custom_values(self):
        """Test selector dapat diinisialisasi dengan custom values"""
        selector = RandomVideoSelector(timeout=60, min_results=2)
        assert selector.timeout == 60
        assert selector.min_results == 2

    @patch("app.services.random_video_source.search_videos_pexels")
    @patch("app.services.random_video_source.search_videos_pixabay")
    @patch("app.services.random_video_source.search_videos_coverr")
    def test_search_from_all_sources(self, mock_coverr, mock_pixabay, mock_pexels):
        """Test search_from_all_sources mengumpulkan hasil dari semua provider"""
        # Setup mocks
        pexels_result = [create_mock_material("pexels")]
        pixabay_result = [create_mock_material("pixabay")]
        coverr_result = [create_mock_material("coverr")]

        mock_pexels.return_value = pexels_result
        mock_pixabay.return_value = pixabay_result
        mock_coverr.return_value = coverr_result

        selector = RandomVideoSelector()
        results = selector.search_from_all_sources(
            search_term="nature",
            minimum_duration=5,
            video_aspect=VideoAspect.portrait,
        )

        # Verify semua providers dicall
        mock_pexels.assert_called_once()
        mock_pixabay.assert_called_once()
        mock_coverr.assert_called_once()

        # Verify results mengandung semua
        assert len(results) == 3
        assert results[0].provider == "pexels"
        assert results[1].provider == "pixabay"
        assert results[2].provider == "coverr"

    @patch("app.services.random_video_source.search_videos_pexels")
    @patch("app.services.random_video_source.search_videos_pixabay")
    @patch("app.services.random_video_source.search_videos_coverr")
    def test_search_with_enabled_providers(self, mock_coverr, mock_pixabay, mock_pexels):
        """Test search hanya ke enabled providers"""
        mock_pexels.return_value = [create_mock_material("pexels")]
        mock_pixabay.return_value = []
        mock_coverr.return_value = []

        selector = RandomVideoSelector()
        results = selector.search_from_all_sources(
            search_term="test",
            enabled_providers=["pexels"],
        )

        # Verify hanya pexels yang dicall
        mock_pexels.assert_called_once()
        mock_pixabay.assert_not_called()
        mock_coverr.assert_not_called()
        assert len(results) == 1

    @patch("app.services.random_video_source.search_videos_pexels")
    @patch("app.services.random_video_source.search_videos_pixabay")
    @patch("app.services.random_video_source.search_videos_coverr")
    def test_select_random_success(self, mock_coverr, mock_pixabay, mock_pexels):
        """Test select_random mengembalikan satu item"""
        mock_pexels.return_value = [create_mock_material("pexels")]
        mock_pixabay.return_value = [create_mock_material("pixabay")]
        mock_coverr.return_value = []

        selector = RandomVideoSelector()
        result = selector.select_random(search_term="test")

        assert result is not None
        assert result.provider in ["pexels", "pixabay"]

    @patch("app.services.random_video_source.search_videos_pexels")
    @patch("app.services.random_video_source.search_videos_pixabay")
    @patch("app.services.random_video_source.search_videos_coverr")
    def test_select_random_no_results(self, mock_coverr, mock_pixabay, mock_pexels):
        """Test select_random return None jika tidak ada hasil"""
        mock_pexels.return_value = []
        mock_pixabay.return_value = []
        mock_coverr.return_value = []

        selector = RandomVideoSelector()
        result = selector.select_random(search_term="xyz")

        assert result is None

    @patch("app.services.random_video_source.search_videos_pexels")
    @patch("app.services.random_video_source.search_videos_pixabay")
    @patch("app.services.random_video_source.search_videos_coverr")
    def test_select_multiple_random(self, mock_coverr, mock_pixabay, mock_pexels):
        """Test select_multiple_random mengembalikan list"""
        mock_pexels.return_value = [
            create_mock_material("pexels", 10),
            create_mock_material("pexels", 15),
        ]
        mock_pixabay.return_value = [
            create_mock_material("pixabay", 12),
            create_mock_material("pixabay", 8),
        ]
        mock_coverr.return_value = [create_mock_material("coverr", 20)]

        selector = RandomVideoSelector()
        results = selector.select_multiple_random(
            search_term="test",
            count=3,
        )

        assert len(results) == 3
        # Verify semua hasil unique (no replacement)
        urls = [r.url for r in results]
        assert len(urls) == len(set(urls))

    @patch("app.services.random_video_source.search_videos_pexels")
    @patch("app.services.random_video_source.search_videos_pixabay")
    @patch("app.services.random_video_source.search_videos_coverr")
    def test_select_multiple_random_count_exceeds_available(
        self, mock_coverr, mock_pixabay, mock_pexels
    ):
        """Test select_multiple_random ketika count lebih besar dari available"""
        mock_pexels.return_value = [create_mock_material("pexels")]
        mock_pixabay.return_value = []
        mock_coverr.return_value = []

        selector = RandomVideoSelector()
        results = selector.select_multiple_random(
            search_term="test",
            count=10,  # Request 10 tapi hanya 1 available
        )

        assert len(results) == 1  # Should return only 1

    @patch("app.services.random_video_source.search_videos_pexels")
    def test_select_random_with_aspect_ratio(self, mock_pexels):
        """Test select_random pass aspect ratio ke provider"""
        mock_pexels.return_value = [create_mock_material("pexels")]

        selector = RandomVideoSelector()
        result = selector.select_random(
            search_term="test",
            video_aspect=VideoAspect.landscape,
            enabled_providers=["pexels"],
        )

        # Verify aspect ratio dipassing
        mock_pexels.assert_called_once()
        call_kwargs = mock_pexels.call_args[1]
        assert call_kwargs["video_aspect"] == VideoAspect.landscape

    @patch("app.services.random_video_source.search_videos_pexels")
    def test_select_random_with_min_duration(self, mock_pexels):
        """Test select_random pass minimum_duration ke provider"""
        mock_pexels.return_value = [create_mock_material("pexels")]

        selector = RandomVideoSelector()
        selector.select_random(
            search_term="test",
            minimum_duration=10,
            enabled_providers=["pexels"],
        )

        # Verify minimum_duration dipassing
        call_kwargs = mock_pexels.call_args[1]
        assert call_kwargs["minimum_duration"] == 10


class TestConvenienceFunctions:
    """Test cases untuk convenience functions"""

    @patch("app.services.random_video_source.RandomVideoSelector.select_random")
    def test_search_and_select_random(self, mock_select):
        """Test search_and_select_random convenience function"""
        mock_video = create_mock_material("pexels")
        mock_select.return_value = mock_video

        result = search_and_select_random(search_term="test")

        assert result == mock_video
        mock_select.assert_called_once()

    @patch("app.services.random_video_source.RandomVideoSelector.select_multiple_random")
    def test_search_and_select_multiple(self, mock_select):
        """Test search_and_select_multiple convenience function"""
        mock_videos = [create_mock_material("pexels"), create_mock_material("pixabay")]
        mock_select.return_value = mock_videos

        result = search_and_select_multiple(search_term="test", count=2)

        assert result == mock_videos
        mock_select.assert_called_once()


class TestEdgeCases:
    """Test cases untuk edge cases"""

    @patch("app.services.random_video_source.search_videos_pexels")
    def test_provider_exception_continues_to_next(self, mock_pexels):
        """Test jika satu provider error, tetap lanjut ke provider lain"""
        mock_pexels.side_effect = Exception("API Error")

        with patch("app.services.random_video_source.search_videos_pixabay") as mock_pixabay:
            mock_pixabay.return_value = [create_mock_material("pixabay")]

            selector = RandomVideoSelector()
            results = selector.search_from_all_sources(search_term="test")

            # Should return result dari pixabay meski pexels error
            assert len(results) == 1
            assert results[0].provider == "pixabay"

    def test_invalid_provider_skipped(self):
        """Test invalid provider disskip dengan warning"""
        selector = RandomVideoSelector()
        with patch("app.services.random_video_source.search_videos_pexels") as mock_pexels:
            mock_pexels.return_value = [create_mock_material("pexels")]

            results = selector.search_from_all_sources(
                search_term="test",
                enabled_providers=["pexels", "invalid_provider"],
            )

            # Should only return pexels result
            assert len(results) == 1
            assert results[0].provider == "pexels"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
