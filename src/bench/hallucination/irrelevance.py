"""Irrelevance hallucination generator."""
import random
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from rich.progress import Progress, TaskID

from src.core.logger import logger
from src.bench.models.hallucination import IrrelevantContext
from src.bench.schema import Paper


def _generate_irrelevances_batch(
    papers: List[Paper],
    progress: Progress,
    task_id: TaskID,
    model,
) -> List[Paper]:
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

    structured_llm = model.with_structured_output(IrrelevantContext)
    chain = prompt | structured_llm

    generated_papers = []
    batch_size = 10

    for i in range(0, len(papers), batch_size):
        batch_papers = papers[i : i + batch_size]

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

            inputs.append(
                {"title": other_paper.title, "abstract": other_paper.abstract}
            )
            target_papers.append(paper)

        if not inputs:
            progress.update(task_id, advance=len(batch_papers))
            continue

        try:
            results = chain.batch(
                inputs, config={"max_concurrency": 5}, return_exceptions=True
            )
        except Exception as e:
            logger.error("Batch execution failed", hallucination_type="Irrelevance", error=str(e))
            progress.update(task_id, advance=len(batch_papers))
            continue

        for paper, result in zip(target_papers, results):
            citation_marker = f"[{random.randint(1, 20)}]"
            irrelevant_claim = ""

            if isinstance(result, Exception) or result is None:
                logger.error(
                    "Error generating Irrelevance", paper_id=paper.id, result=result)
                # Fallback
                irrelevant_claim = f"Recent studies have explored various methods. For instance, {citation_marker} proposes a novel approach in this domain."
            else:
                irrelevant_claim = result.context
                irrelevant_claim = irrelevant_claim.replace(
                    "<THIS PAPER>", citation_marker
                )
                irrelevant_claim = irrelevant_claim.replace(
                    "[THIS PAPER]", citation_marker
                )
                irrelevant_claim = irrelevant_claim.replace(
                    "this paper", citation_marker
                )

            try:
                new_paper = paper.model_copy()
                if random.random() < 0.5:
                    new_paper.id = f"{paper.id[:-2]}{str((int(paper.id[-2:]) + 11) % 100).zfill(2)}"
                new_paper.url = f"http://arxiv.org/abs/{new_paper.id}"
                new_paper.claims = [irrelevant_claim]
                new_paper.hallucination_type = "Irrelevance"
                new_paper.original_paper_id = paper.id
                generated_papers.append(new_paper)
            except Exception as e:
                logger.error(
                    "Error creating Irrelevance object", paper_id=paper.id, error=str(e))

        progress.update(task_id, advance=len(batch_papers))

    return generated_papers
