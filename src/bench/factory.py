"""Benchmark dataset factory."""
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_deepseek import ChatDeepSeek
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from src.core.config import (
    DEEPSEEK_API_KEY,
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
)
from src.core.logger import logger
from src.bench.crawler import PaperCrawler
from src.bench.dataset.dataset import BenchmarkDataset
from src.bench.hallucination import (
    _generate_attribution_errors_batch,
    _generate_counterfactuals_batch,
    _generate_fabrications_batch,
    _generate_irrelevances_batch,
)


class BenchmarkDatasetFactory:
    """
    Factory class for creating BenchmarkDataset instances.
    """

    def __init__(self):
        self.crawler = PaperCrawler()

        if DEEPSEEK_API_KEY is None:
            raise ValueError("DEEPSEEK_API_KEY is not set")

        self.model = ChatDeepSeek(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            timeout=LLM_TIMEOUT,
            max_retries=LLM_MAX_RETRIES,
            api_key=DEEPSEEK_API_KEY,
        )

    def crawl(self, topic: str, count: int = 100) -> BenchmarkDataset:
        """
        Crawl papers from arXiv for the given topic and create a BenchmarkDataset.

        :param topic: The topic to crawl papers about (e.g., 'cs.CL').
        :param count: The number of papers to crawl. Default is 100.
        :return: A BenchmarkDataset instance containing the crawled papers.
        """
        papers = self.crawler.fetch_seeds(topic=topic, count=count)
        return BenchmarkDataset(papers)

    def hallucinate(self, dataset: BenchmarkDataset) -> BenchmarkDataset:
        """
        Inject hallucinations into the dataset using parallel batch processing.
        Types:
        - Fabrication: Completely fake paper.
        - AttributionError: Real paper, wrong authors.
        - Irrelevance: Real paper, irrelevant claim.
        - Counterfactual: Modified abstract with opposite claims.
        """
        logger.info("Starting hallucination injection...")
        hallucinated_papers = []

        # Add original papers
        hallucinated_papers.extend(dataset.dataset)

        # Parallelize the generation of different hallucination types
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ) as progress:
            # Create tasks
            task_fab = progress.add_task("[green]Fabrication", total=len(dataset))
            task_attr = progress.add_task("[blue]AttributionError", total=len(dataset))
            task_irr = progress.add_task("[magenta]Irrelevance", total=len(dataset))
            task_count = progress.add_task("[yellow]Counterfactual", total=len(dataset))

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(
                        _generate_fabrications_batch,
                        dataset.dataset,
                        progress,
                        task_fab,
                        self.model,
                    ): "Fabrication",
                    executor.submit(
                        _generate_attribution_errors_batch,
                        dataset.dataset,
                        progress,
                        task_attr,
                        self.model,
                    ): "AttributionError",
                    executor.submit(
                        _generate_irrelevances_batch,
                        dataset.dataset,
                        progress,
                        task_irr,
                        self.model,
                    ): "Irrelevance",
                    executor.submit(
                        _generate_counterfactuals_batch,
                        dataset.dataset,
                        progress,
                        task_count,
                        self.model,
                    ): "Counterfactual",
                }

                for future in as_completed(futures):
                    h_type = futures[future]
                    try:
                        results = future.result()
                        hallucinated_papers.extend(results)
                        logger.info(
                            "Completed injection", hallucination_type=h_type, generated_count=len(results))
                    except Exception as e:
                        logger.error("Error in hallucination batch", hallucination_type=h_type, error=str(e))

        logger.info(
            "Hallucination injection complete",
            total_papers=len(hallucinated_papers),
        )
        return BenchmarkDataset(hallucinated_papers)
