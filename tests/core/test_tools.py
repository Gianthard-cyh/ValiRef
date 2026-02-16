
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.core.tools import ArxivSearch, OpenReviewSearch, OpenAlexSearch, SearchTool

class TestSearchTools:
    """
    Test cases for search tools in src.core.tools.
    """

    @patch('src.core.tools.arxiv.Client')
    @patch('src.core.tools.arxiv.Search')
    def test_arxiv_search(self, mock_arxiv_search, mock_arxiv_client):
        """
        Test ArxivSearch tool.
        """
        # Setup mock return values
        mock_result = MagicMock()
        mock_result.title = "Attention Is All You Need"
        mock_result.authors = [MagicMock(name="Ashish Vaswani"), MagicMock(name="Noam Shazeer")]
        # Mock names for authors
        mock_result.authors[0].name = "Ashish Vaswani"
        mock_result.authors[1].name = "Noam Shazeer"
        
        mock_result.published = datetime(2017, 6, 12)
        mock_result.summary = "Abstract content"
        mock_result.pdf_url = "http://arxiv.org/pdf/1706.03762v5"
        mock_result.entry_id = "http://arxiv.org/abs/1706.03762v5"

        mock_client_instance = mock_arxiv_client.return_value
        mock_client_instance.results.return_value = [mock_result]

        # Execute search
        tool = ArxivSearch()
        results = tool.search("Attention Is All You Need")

        # Verify results
        assert len(results) == 1
        assert results[0]['title'] == "Attention Is All You Need"
        assert results[0]['authors'] == ["Ashish Vaswani", "Noam Shazeer"]
        assert results[0]['published'] == "2017-06-12"
        assert results[0]['source'] == "arxiv"

    @patch('src.core.tools.arxiv.Client')
    @patch('src.core.tools.arxiv.Search')
    def test_arxiv_search_failure(self, mock_arxiv_search, mock_arxiv_client):
        """
        Test ArxivSearch failure handling.
        """
        # Simulate an exception
        mock_client_instance = mock_arxiv_client.return_value
        mock_client_instance.results.side_effect = Exception("ArXiv API Error")

        tool = ArxivSearch()
        results = tool.search("Query")

        # Should return empty list and log error (logging not verified here)
        assert results == []

    @patch('src.core.tools.openreview.api.OpenReviewClient')
    def test_openreview_search(self, mock_client_cls):
        """
        Test OpenReviewSearch tool.
        """
        # Setup mock client
        mock_client = mock_client_cls.return_value
        
        # Setup mock note
        mock_note = MagicMock()
        mock_note.id = "note_id"
        mock_note.cdate = 1600000000000 # Timestamp
        # v2 structure uses 'value'
        mock_note.content = {
            "title": {"value": "OpenReview Paper"},
            "authors": {"value": ["Author One", "Author Two"]},
            "abstract": {"value": "Abstract content"}
        }
        
        mock_client.search_notes.return_value = [mock_note]

        # Execute search
        tool = OpenReviewSearch()
        results = tool.search("OpenReview Paper")

        # Verify results
        assert len(results) == 1
        assert results[0]['title'] == "OpenReview Paper"
        assert results[0]['authors'] == ["Author One", "Author Two"]
        assert results[0]['source'] == "openreview_v2"
        
    @patch('src.core.tools.requests.get')
    def test_openalex_search(self, mock_get):
        """
        Test OpenAlexSearch tool.
        """
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_data = {
            "results": [
                {
                    "title": "OpenAlex Paper",
                    "authorships": [
                        {"author": {"display_name": "Alex One"}},
                        {"author": {"display_name": "Alex Two"}}
                    ],
                    "publication_year": 2023,
                    "primary_location": {
                        "source": {"display_name": "Journal of Open Science"}
                    },
                    "doi": "https://doi.org/10.1234/openalex",
                    "id": "https://openalex.org/W123456789"
                }
            ]
        }
        mock_response.json.return_value = mock_data
        mock_get.return_value = mock_response

        # Execute search
        tool = OpenAlexSearch()
        results = tool.search("OpenAlex Paper")

        # Verify results
        assert len(results) == 1
        assert results[0]['title'] == "OpenAlex Paper"
        assert results[0]['authors'] == ["Alex One", "Alex Two"]
        assert results[0]['published'] == "2023"
        assert results[0]['venue'] == "Journal of Open Science"
        assert results[0]['source'] == "openalex"

    @patch('src.core.tools.requests.get')
    def test_openalex_search_failure(self, mock_get):
        """
        Test OpenAlexSearch failure handling (e.g., 404 or connection error).
        """
        mock_get.side_effect = Exception("Connection Error")

        tool = OpenAlexSearch()
        results = tool.search("Query")

        assert results == []

    def test_search_tool_interface(self):
        """
        Test base SearchTool raises NotImplementedError.
        """
        tool = SearchTool()
        with pytest.raises(NotImplementedError):
            tool.search("query")
