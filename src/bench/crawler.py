import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
from typing import List
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from ..core.logger import logger
from ..core.config import TOKEN_BUCKET_RATE_ARXIV
from .schema import Paper


class PaperCrawler:
    """
    Seed Sourcing: Crawl real papers (Abstract + Metadata) from arXiv.
    """

    ARXIV_API_URL = "http://export.arxiv.org/api/query"

    def __init__(self, source: str = "arxiv"):
        self.source = source.lower()
        self._last_request_time = 0.0
        # Use same rate limit as search tools: interval = 1/rate
        self._rate_limit_delay = 1.0 / TOKEN_BUCKET_RATE_ARXIV

    def fetch_seeds(self, topic: str = "cs.AI", count: int = 10) -> List[Paper]:
        """
        Fetch seed papers.

        Args:
            topic: Search topic (e.g., "cs.AI", "machine learning")
            count: Number of papers to fetch

        Returns:
            List of Paper objects
        """
        logger.info(
            f"Starting seed sourcing from {self.source} for topic '{topic}', count={count}"
        )

        if self.source == "arxiv":
            papers = []
            batch_size = 100

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task(f"[cyan]Crawling {topic}...", total=count)

                for start in range(0, count, batch_size):
                    current_batch_size = min(batch_size, count - start)
                    batch_papers = self._fetch_from_arxiv(
                        topic, current_batch_size, start=start
                    )

                    if not batch_papers:
                        logger.warning(
                            f"No more papers found or error occurred at start={start}"
                        )
                        break

                    papers.extend(batch_papers)
                    progress.update(task, advance=len(batch_papers))

            return papers
        else:
            raise NotImplementedError(f"Source '{self.source}' is not supported yet.")

    def _fetch_from_arxiv(
        self, query: str, max_results: int, start: int = 0
    ) -> List[Paper]:
        """
        从 arXiv API 获取数据。
        API 文档: https://arxiv.org/help/api/user-manual
        """
        # Rate limiting - ensure minimum delay between requests
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            sleep_time = self._rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        # 构建查询参数
        # 如果 query 没有前缀，默认搜索所有字段
        search_query = f"all:{query}" if ":" not in query else query

        params = {
            "search_query": search_query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        url_params = urllib.parse.urlencode(params)
        url = f"{self.ARXIV_API_URL}?{url_params}"

        logger.info(f"Querying arXiv API: {url}")

        try:
            self._last_request_time = time.time()
            with urllib.request.urlopen(url) as response:
                xml_data = response.read().decode("utf-8")

            return self._parse_arxiv_response(xml_data)
        except Exception as e:
            logger.error(f"Failed to fetch data from arXiv: {e}")
            return []

    def _parse_arxiv_response(self, xml_data: str) -> List[Paper]:
        """Parse XML data returned by arXiv"""
        papers = []
        # arXiv API returns Atom XML format
        # Namespace handling
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        root = ET.fromstring(xml_data)

        for entry in root.findall("atom:entry", ns):
            try:
                # extract paper id
                id_url = entry.find("atom:id", ns).text
                paper_id = id_url.split("/")[-1].split("v")[0]

                title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
                summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
                published = entry.find("atom:published", ns).text
                updated = entry.find("atom:updated", ns).text

                # extract authors
                authors = []
                for author in entry.findall("atom:author", ns):
                    name = author.find("atom:name", ns).text
                    authors.append(name)

                # extract pdf url
                pdf_url = None
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href")

                paper = Paper(
                    source="arxiv",
                    id=paper_id,
                    title=title,
                    abstract=summary,
                    authors=authors,
                    published_date=published,
                    updated_date=updated,
                    url=id_url,
                    pdf_url=pdf_url,
                    claims=[],
                )
                papers.append(paper)

            except Exception as e:
                logger.warning(f"Error parsing an entry: {e}")
                continue

        logger.info(f"Successfully parsed {len(papers)} papers")
        return papers
