import unittest
from src.bench.data_engine import PaperCrawler
from src.bench.schema import Paper

class TestSeedHarvester(unittest.TestCase):
    
    def setUp(self):
        self.harvester = PaperCrawler(source="arxiv")

    def test_fetch_seeds(self):
        """Test fetching seeds from arXiv"""
        # Fetch a small number of papers to avoid long wait times
        count = 3
        seeds = self.harvester.fetch_seeds(topic="cs.CL", count=count)
        
        self.assertIsInstance(seeds, list)
        self.assertTrue(len(seeds) <= count) # arXiv API might return fewer or slightly more, but typically exact
        
        if len(seeds) > 0:
            paper = seeds[0]
            self.assertIsInstance(paper, Paper)
            self.assertIsNotNone(paper.title)
            self.assertIsNotNone(paper.abstract)
            self.assertIsNotNone(paper.url)
            self.assertEqual(paper.source, "arxiv")
            
            # Print info for manual verification
            print(f"\nFetched {len(seeds)} papers.")
            print(f"Sample Title: {paper.title}")

if __name__ == '__main__':
    unittest.main()
