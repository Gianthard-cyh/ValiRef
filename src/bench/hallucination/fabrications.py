"""Fabrication hallucination generator."""
import random
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from rich.progress import Progress, TaskID

from src.core.logger import logger
from src.bench.models.hallucination import FakePaper
from src.bench.schema import Paper


def _generate_fabrications_batch(
    papers: List[Paper],
    progress: Progress,
    task_id: TaskID,
    model,
) -> List[Paper]:
    """Batch generate fake papers."""
    prompt = ChatPromptTemplate.from_template(
        "Based on the following abstract, generate a completely FAKE paper details "
        "that sounds plausible but does not exist. The topic should be similar.\n\n"
        "Original Paper: {paper}\n"
    )

    structured_llm = model.with_structured_output(FakePaper)
    chain = prompt | structured_llm

    generated_papers = []
    batch_size = 10

    for i in range(0, len(papers), batch_size):
        batch_papers = papers[i : i + batch_size]
        inputs = [{"paper": paper} for paper in batch_papers]

        try:
            results = chain.batch(
                inputs, config={"max_concurrency": 5}, return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Batch execution failed for Fabrication: {e}")
            progress.update(task_id, advance=len(batch_papers))
            continue

        for paper, result in zip(batch_papers, results):
            if isinstance(result, Exception) or result is None:
                logger.error(
                    f"Error generating Fabrication for {paper.id}: {result}"
                )
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
                logger.error(
                    f"Error creating Fabrication object for {paper.id}: {e}"
                )

        progress.update(task_id, advance=len(batch_papers))

    return generated_papers
