from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os
import csv
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TaskID
from pydantic import BaseModel, Field
from .schema import Paper
from .crawler import PaperCrawler
from ..core.logger import logger
from ..core.config import DEEPSEEK_API_KEY, TEMP, MAX_TOKENS, TIMEOUT, MAX_RETRIES

# --- Output Schemas ---

class FakePaper(BaseModel):
    title: str = Field(description="The title of the fake paper")
    abstract: str = Field(description="The abstract of the fake paper")
    authors: List[str] = Field(
        description="List of plausible authors for the fake paper"
    )
    published_date: str = Field(
        description="A plausible publication date (YYYY-MM-DD)"
    )


class FakeAuthors(BaseModel):
    authors: List[str] = Field(
        description="List of plausible but incorrect authors for this paper"
    )


class IrrelevantContext(BaseModel):
    context: str = Field(
        description="A paragraph that cites the paper to support a specific claim"
    )


class CounterfactualClaim(BaseModel):
    context: str = Field(
        description="A citation paragraph claiming the opposite of the paper's actual findings"
    )


class BenchmarkDataset:
    def __init__(self, dataset: List[Paper]):
        self.dataset = dataset
        self.crawler = PaperCrawler()

    def __len__(self):
        return len(self.dataset)

    def to_csv(self, file_path: str):
        """
        Export the dataset to a CSV file.
        """
        if not self.dataset:
            logger.warning("Dataset is empty. Nothing to export.")
            return

        fieldnames = self.dataset[0].model_dump().keys()

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for paper in self.dataset:
                    row = paper.model_dump()
                    # Handle list fields for CSV (e.g., authors, claims)
                    for key, value in row.items():
                        if isinstance(value, list):
                            row[key] = "; ".join(map(str, value))
                    writer.writerow(row)
            logger.info(f"Dataset exported to {file_path}")
        except Exception as e:
            logger.error(f"Failed to export dataset to CSV: {e}")


import random


class BenchmarkDatasetFactory:
    """
    Factory class for creating BenchmarkDataset instances.
    """

    def __init__(self):
        self.crawler = PaperCrawler()

        if DEEPSEEK_API_KEY is None:
            raise ValueError("DEEPSEEK_API_KEY is not set")

        self.model = ChatDeepSeek(
            model="deepseek-chat",
            temperature=TEMP,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT,
            max_retries=MAX_RETRIES,
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
                    executor.submit(self._generate_fabrications_batch, dataset.dataset, progress, task_fab): "Fabrication",
                    executor.submit(self._generate_attribution_errors_batch, dataset.dataset, progress, task_attr): "AttributionError",
                    executor.submit(self._generate_irrelevances_batch, dataset.dataset, progress, task_irr): "Irrelevance",
                    executor.submit(self._generate_counterfactuals_batch, dataset.dataset, progress, task_count): "Counterfactual"
                }

                for future in as_completed(futures):
                    h_type = futures[future]
                    try:
                        results = future.result()
                        hallucinated_papers.extend(results)
                        logger.info(f"Completed injection for {h_type}. Generated {len(results)} papers.")
                    except Exception as e:
                        logger.error(f"Error in hallucination batch for {h_type}: {e}")

        logger.info(
            f"Hallucination injection complete. Total papers: {len(hallucinated_papers)}"
        )
        return BenchmarkDataset(hallucinated_papers)

    def _generate_fabrications_batch(self, papers: List[Paper], progress: Progress, task_id: TaskID) -> List[Paper]:
        """Batch generate fake papers."""
        prompt = ChatPromptTemplate.from_template(
            "Based on the following abstract, generate a completely FAKE paper details "
            "that sounds plausible but does not exist. The topic should be similar.\n\n"
            "Original Paper: {paper}\n"
        )

        structured_llm = self.model.with_structured_output(FakePaper)
        chain = prompt | structured_llm

        generated_papers = []
        batch_size = 10
        
        for i in range(0, len(papers), batch_size):
            batch_papers = papers[i:i + batch_size]
            inputs = [{"paper": paper} for paper in batch_papers]
            
            try:
                results = chain.batch(inputs, config={"max_concurrency": 5}, return_exceptions=True)
            except Exception as e:
                logger.error(f"Batch execution failed for Fabrication: {e}")
                progress.update(task_id, advance=len(batch_papers))
                continue

            for paper, result in zip(batch_papers, results):
                if isinstance(result, Exception) or result is None:
                    logger.error(f"Error generating Fabrication for {paper.id}: {result}")
                    continue

                try:
                    year = random.randint(20, 24)
                    month = random.randint(1, 12)
                    seq = random.randint(1, 99999)
                    fake_id = f"{year:02d}{month:02d}.{seq:05d}"

                    new_paper = Paper(
                        source="generated",
                        id=fake_id,
                        title=result.title,
                        abstract=result.abstract,
                        authors=result.authors,
                        published_date=result.published_date,
                        url=f"http://arxiv.org/abs/{fake_id}",
                        hallucination_type="Fabrication",
                        original_paper_id=paper.id,
                    )
                    generated_papers.append(new_paper)
                except Exception as e:
                    logger.error(f"Error creating Fabrication object for {paper.id}: {e}")
            
            progress.update(task_id, advance=len(batch_papers))

        return generated_papers

    def _generate_attribution_errors_batch(self, papers: List[Paper], progress: Progress, task_id: TaskID) -> List[Paper]:
        """Batch generate attribution errors."""
        prompt = ChatPromptTemplate.from_template(
            "Based on the following abstract, generate a list of 3-5 plausible author names "
            "who COULD have written this paper (based on the research field) but definitely DID NOT. "
            "Do NOT use the real authors: {real_authors}.\n\n"
            "Abstract:\n{abstract}"
        )

        structured_llm = self.model.with_structured_output(FakeAuthors)
        chain = prompt | structured_llm

        generated_papers = []
        batch_size = 10

        for i in range(0, len(papers), batch_size):
            batch_papers = papers[i:i + batch_size]
            inputs = [
                {"abstract": paper.abstract, "real_authors": ", ".join(paper.authors)}
                for paper in batch_papers
            ]

            try:
                results = chain.batch(inputs, config={"max_concurrency": 5}, return_exceptions=True)
            except Exception as e:
                logger.error(f"Batch execution failed for AttributionError: {e}")
                progress.update(task_id, advance=len(batch_papers))
                continue

            for paper, result in zip(batch_papers, results):
                if isinstance(result, Exception) or result is None:
                    logger.error(f"Error generating AttributionError for {paper.id}: {result}")
                    continue

                try:
                    new_paper = paper.model_copy()
                    new_paper.url = f"http://arxiv.org/abs/{new_paper.id}"
                    new_paper.authors = result.authors
                    new_paper.hallucination_type = "AttributionError"
                    new_paper.original_paper_id = paper.id
                    generated_papers.append(new_paper)
                except Exception as e:
                    logger.error(f"Error creating AttributionError object for {paper.id}: {e}")
            
            progress.update(task_id, advance=len(batch_papers))

        return generated_papers

    def _generate_irrelevances_batch(self, papers: List[Paper], progress: Progress, task_id: TaskID) -> List[Paper]:
        """Batch generate irrelevant claims."""
        if len(papers) < 2:
            progress.update(task_id, advance=len(papers))
            return []

        prompt = ChatPromptTemplate.from_template(
            "Based on the following abstract, write a short paragraph (2-3 sentences) that cites this paper. "
            "The paragraph should act as if it is from a 'Related Work' or 'Introduction' section of another paper. "
            "It should make a specific claim and attribute it to this work.\n\n"
            "Title: {title}\n"
            "Abstract:\n{abstract}\n\n"
            "Example output format:\n"
            "Recent work has shown that [claim]. For instance, <THIS PAPER> demonstrates that [finding]."
        )

        structured_llm = self.model.with_structured_output(IrrelevantContext)
        chain = prompt | structured_llm

        generated_papers = []
        batch_size = 10

        for i in range(0, len(papers), batch_size):
            batch_papers = papers[i:i + batch_size]
            
            # Prepare inputs for this batch
            inputs = []
            target_papers = []
            
            for paper in batch_papers:
                # Pick a random other paper
                other_paper = random.choice(papers)
                attempts = 0
                while other_paper.id == paper.id and attempts < 10:
                    other_paper = random.choice(papers)
                    attempts += 1
                
                if other_paper.id == paper.id:
                    continue

                inputs.append({"title": other_paper.title, "abstract": other_paper.abstract})
                target_papers.append(paper)

            if not inputs:
                progress.update(task_id, advance=len(batch_papers))
                continue

            try:
                results = chain.batch(inputs, config={"max_concurrency": 5}, return_exceptions=True)
            except Exception as e:
                logger.error(f"Batch execution failed for Irrelevance: {e}")
                progress.update(task_id, advance=len(batch_papers))
                continue

            for paper, result in zip(target_papers, results):
                citation_marker = f"[{random.randint(1, 20)}]"
                irrelevant_claim = ""

                if isinstance(result, Exception) or result is None:
                    logger.error(f"Error generating Irrelevance for {paper.id}: {result}")
                    # Fallback
                    irrelevant_claim = f"Recent studies have explored various methods. For example, {citation_marker} proposes a novel approach in this domain."
                else:
                    irrelevant_claim = result.context
                    irrelevant_claim = irrelevant_claim.replace("<THIS PAPER>", citation_marker)
                    irrelevant_claim = irrelevant_claim.replace("[THIS PAPER]", citation_marker)
                    irrelevant_claim = irrelevant_claim.replace("this paper", citation_marker)

                try:
                    new_paper = paper.model_copy()
                    if random.random() < 0.5:
                        new_paper.id = (
                            f"{paper.id[:-2]}{str((int(paper.id[-2:]) + 11) % 100).zfill(2)}"
                        )
                    new_paper.url = f"http://arxiv.org/abs/{new_paper.id}"
                    new_paper.claims = [irrelevant_claim]
                    new_paper.hallucination_type = "Irrelevance"
                    new_paper.original_paper_id = paper.id
                    generated_papers.append(new_paper)
                except Exception as e:
                    logger.error(f"Error creating Irrelevance object for {paper.id}: {e}")
            
            progress.update(task_id, advance=len(batch_papers))

        return generated_papers

    def _generate_counterfactuals_batch(self, papers: List[Paper], progress: Progress, task_id: TaskID) -> List[Paper]:
        """Batch generate counterfactual claims."""
        prompt = ChatPromptTemplate.from_template(
            "Based on the following abstract, write a short paragraph (2-3 sentences) that cites this paper. "
            "However, the paragraph should attribute a claim to this paper that is OPPOSITE or COUNTERFACTUAL "
            "to its actual findings. It should sound confident and plausible, like a real citation.\n\n"
            "Original Abstract:\n{abstract}\n\n"
            "Example output format:\n"
            "Contrary to previous beliefs, <THIS PAPER> argues that [opposite of actual finding]."
        )

        structured_llm = self.model.with_structured_output(CounterfactualClaim)
        chain = prompt | structured_llm

        generated_papers = []
        batch_size = 10

        for i in range(0, len(papers), batch_size):
            batch_papers = papers[i:i + batch_size]
            inputs = [{"abstract": paper.abstract} for paper in batch_papers]

            try:
                results = chain.batch(inputs, config={"max_concurrency": 5}, return_exceptions=True)
            except Exception as e:
                logger.error(f"Batch execution failed for Counterfactual: {e}")
                progress.update(task_id, advance=len(batch_papers))
                continue

            for paper, result in zip(batch_papers, results):
                if isinstance(result, Exception) or result is None:
                    logger.error(f"Error generating Counterfactual for {paper.id}: {result}")
                    continue

                try:
                    fake_claim = result.context
                    citation_marker = f"[{random.randint(1, 20)}]"
                    fake_claim = fake_claim.replace("<THIS PAPER>", citation_marker)
                    fake_claim = fake_claim.replace("[THIS PAPER]", citation_marker)
                    fake_claim = fake_claim.replace("this paper", citation_marker)

                    new_paper = paper.model_copy()
                    new_paper.claims = [fake_claim]
                    new_paper.abstract = paper.abstract
                    new_paper.hallucination_type = "Counterfactual"
                    new_paper.original_paper_id = paper.id
                    generated_papers.append(new_paper)
                except Exception as e:
                    logger.error(f"Error creating Counterfactual object for {paper.id}: {e}")
            
            progress.update(task_id, advance=len(batch_papers))

        return generated_papers
