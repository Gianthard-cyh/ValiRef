"""Attribution error hallucination generator."""
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from rich.progress import Progress, TaskID

from src.core.logger import logger
from src.bench.models.hallucination import FakeAuthors
from src.bench.schema import Paper


def _generate_attribution_errors_batch(
    papers: List[Paper],
    progress: Progress,
    task_id: TaskID,
    model,
) -> List[Paper]:
    """Batch generate attribution errors."""
    prompt = ChatPromptTemplate.from_template(
        "Based on the following abstract, generate a list of 3-5 plausible author names "
        "who COULD have written this paper (based on the research field) but definitely DID NOT. "
        "Do NOT use the real authors: {real_authors}.\n\n"
        "Abstract:\n{abstract}"
    )

    structured_llm = model.with_structured_output(FakeAuthors)
    chain = prompt | structured_llm

    generated_papers = []
    batch_size = 10

    for i in range(0, len(papers), batch_size):
        batch_papers = papers[i : i + batch_size]
        inputs = [
            {"abstract": paper.abstract, "real_authors": ", ".join(paper.authors)}
            for paper in batch_papers
        ]

        try:
            results = chain.batch(
                inputs, config={"max_concurrency": 5}, return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Batch execution failed for AttributionError: {e}")
            progress.update(task_id, advance=len(batch_papers))
            continue

        for paper, result in zip(batch_papers, results):
            if isinstance(result, Exception) or result is None:
                logger.error(
                    f"Error generating AttributionError for {paper.id}: {result}"
                )
                continue

            try:
                new_paper = paper.model_copy()
                new_paper.url = f"http://arxiv.org/abs/{new_paper.id}"
                new_paper.authors = result.authors
                new_paper.hallucination_type = "AttributionError"
                new_paper.original_paper_id = paper.id
                generated_papers.append(new_paper)
            except Exception as e:
                logger.error(
                    f"Error creating AttributionError object for {paper.id}: {e}"
                )

        progress.update(task_id, advance=len(batch_papers))

    return generated_papers
