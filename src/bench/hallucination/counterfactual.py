"""Counterfactual hallucination generator."""
import random
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from rich.progress import Progress, TaskID

from src.core.logger import logger
from src.bench.models.hallucination import CounterfactualClaim
from src.bench.schema import Paper


def _generate_counterfactuals_batch(
    papers: List[Paper],
    progress: Progress,
    task_id: TaskID,
    model,
) -> List[Paper]:
    """Batch generate counterfactual claims."""
    prompt = ChatPromptTemplate.from_template(
        "Based on the following abstract, write a short paragraph (2-3 sentences) that cites this paper. "
        "However, the paragraph should attribute a claim to this paper that is OPPOSITE or COUNTERFACTUAL "
        "to its actual findings. It should sound confident and plausible, like a real citation.\n\n"
        "Original Abstract:\n{abstract}\n\n"
        "Example output format:\n"
        "Contrary to previous beliefs, <THIS PAPER> argues that [opposite of actual finding]."
    )

    structured_llm = model.with_structured_output(CounterfactualClaim)
    chain = prompt | structured_llm

    generated_papers = []
    batch_size = 10

    for i in range(0, len(papers), batch_size):
        batch_papers = papers[i : i + batch_size]
        inputs = [{"abstract": paper.abstract} for paper in batch_papers]

        try:
            results = chain.batch(
                inputs, config={"max_concurrency": 5}, return_exceptions=True
            )
        except Exception as e:
            logger.error("Batch execution failed", hallucination_type="Counterfactual", error=str(e))
            progress.update(task_id, advance=len(batch_papers))
            continue

        for paper, result in zip(batch_papers, results):
            if isinstance(result, Exception) or result is None:
                logger.error(
                    "Error generating Counterfactual", paper_id=paper.id, result=result)
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
                logger.error(
                    "Error creating Counterfactual object", paper_id=paper.id, error=str(e))

        progress.update(task_id, advance=len(batch_papers))

    return generated_papers
