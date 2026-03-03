import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from src.core.tools import ArxivSearch, OpenReviewSearch, OpenAlexSearch, SearchTool


class TestSearchTools:
    """
    Test cases for search tools in src.core.tools.
    """

    @patch("src.core.tools.httpx.AsyncClient")
    def test_arxiv_search(self, mock_client_cls):
        """
        Test ArxivSearch tool with async httpx.
        """
        async def run_test():
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
    <entry>
        <title>Attention Is All You Need</title>
        <summary>Abstract content</summary>
        <published>2017-06-12T00:00:00Z</published>
        <author><name>Ashish Vaswani</name></author>
        <author><name>Noam Shazeer</name></author>
        <link title="pdf" href="http://arxiv.org/pdf/1706.03762v5"/>
        <id>http://arxiv.org/abs/1706.03762v5</id>
    </entry>
</feed>"""

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            # Execute search
            tool = ArxivSearch()
            results = await tool.asearch("Attention Is All You Need")

            # Verify results
            assert len(results) == 1
            assert results[0].title == "Attention Is All You Need"
            assert results[0].authors == ["Ashish Vaswani", "Noam Shazeer"]
            assert results[0].published_date == "2017-06-12"
            assert results[0].source == "arxiv"

        asyncio.run(run_test())

    @patch("src.core.tools.httpx.AsyncClient")
    def test_arxiv_search_failure(self, mock_client_cls):
        """
        Test ArxivSearch failure handling.
        """
        async def run_test():
            # Simulate an exception
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=Exception("ArXiv API Error"))
            mock_client_cls.return_value = mock_client

            tool = ArxivSearch()
            results = await tool.asearch("Query")

            # Should return empty list on error
            assert results == []

        asyncio.run(run_test())

    @patch("src.core.tools.httpx.AsyncClient")
    def test_openreview_search(self, mock_client_cls):
        """
        Test OpenReviewSearch tool with async httpx.
        """
        async def run_test():
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "notes": [
                    {
                        "id": "note_id",
                        "cdate": 1600000000000,
                        "content": {
                            "title": {"value": "OpenReview Paper"},
                            "authors": {"value": ["Author One", "Author Two"]},
                            "abstract": {"value": "Abstract content"},
                        }
                    }
                ]
            }

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            # Execute search
            tool = OpenReviewSearch()
            results = await tool.asearch("OpenReview Paper")

            # Verify results
            assert len(results) == 1
            assert results[0].title == "OpenReview Paper"
            assert results[0].authors == ["Author One", "Author Two"]
            assert results[0].source == "openreview_v2"

        asyncio.run(run_test())

    @patch("src.core.tools.httpx.AsyncClient")
    def test_openalex_search(self, mock_client_cls):
        """
        Test OpenAlexSearch tool with async httpx.
        """
        async def run_test():
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "results": [
                    {
                        "title": "OpenAlex Paper",
                        "authorships": [
                            {"author": {"display_name": "Alex One"}},
                            {"author": {"display_name": "Alex Two"}},
                        ],
                        "publication_year": 2023,
                        "primary_location": {
                            "source": {"display_name": "Journal of Open Science"}
                        },
                        "doi": "https://doi.org/10.1234/openalex",
                        "id": "https://openalex.org/W123456789",
                    }
                ]
            }

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            # Execute search
            tool = OpenAlexSearch()
            results = await tool.asearch("OpenAlex Paper")

            # Verify results
            assert len(results) == 1
            assert results[0].title == "OpenAlex Paper"
            assert results[0].authors == ["Alex One", "Alex Two"]
            assert results[0].published_date == "2023"
            assert results[0].venue == "Journal of Open Science"
            assert results[0].source == "openalex"

        asyncio.run(run_test())

    @patch("src.core.tools.httpx.AsyncClient")
    def test_openalex_search_failure(self, mock_client_cls):
        """
        Test OpenAlexSearch failure handling.
        """
        async def run_test():
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=Exception("Connection Error"))
            mock_client_cls.return_value = mock_client

            tool = OpenAlexSearch()
            results = await tool.asearch("Query")

            assert results == []

        asyncio.run(run_test())

    def test_search_tool_interface(self):
        """
        Test base SearchTool._perform_asearch raises NotImplementedError.
        """
        tool = SearchTool()
        with pytest.raises(NotImplementedError):
            # Directly call the abstract method
            asyncio.run(tool._perform_asearch("query", 5))
