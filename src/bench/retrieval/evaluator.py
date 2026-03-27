"""
检索评估器 - 使用构造时搜索工具注入，支持并发处理
"""

import asyncio
import csv
from dataclasses import dataclass
from typing import List, Optional

from ...core.detector import HallucinationDetector
from ...core.logger import logger
from ...bench.schema import Paper
from .eval_search import EvalLocalSearch, PaperGroundTruth, QueryRecord


@dataclass
class RetrievalEvalResult:
    """评估结果"""
    total_samples: int
    total_queries: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    per_sample: List[dict]
    all_records: List[QueryRecord]  # 所有查询记录，用于导出分析

    def export_queries(self, filepath: str, format: str = "json") -> None:
        """导出所有查询记录到文件供后续分析"""
        import json
        import csv

        if format == "json":
            data = [
                {
                    "sample_id": r.sample_id,
                    "sample_title": r.sample_title,
                    "query": r.query,
                    "hit_rank": r.hit_rank,
                    "result_count": r.result_count,
                    "duration_ms": r.duration_ms,
                }
                for r in self.all_records
            ]
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        elif format == "csv":
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["sample_id", "sample_title", "query", "hit_rank",
                                "result_count", "duration_ms"])
                for r in self.all_records:
                    writer.writerow([r.sample_id, r.sample_title, r.query,
                                   r.hit_rank, r.result_count, r.duration_ms])

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_samples": self.total_samples,
            "total_queries": self.total_queries,
            "recall_at_1": self.recall_at_1,
            "recall_at_3": self.recall_at_3,
            "recall_at_5": self.recall_at_5,
            "mrr": self.mrr,
        }


class RetrievalEvaluator:
    """检索评估器 - 保留所有查询供后续分析，支持并发处理"""

    def __init__(self):
        self._all_records: List[QueryRecord] = []

    def _load_samples(self, dataset_path: str, sample_size: int) -> List[Paper]:
        """Load samples from CSV dataset."""
        import csv
        from ...bench.schema import Paper

        papers = []
        with open(dataset_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse authors and claims from semicolon-separated strings
                authors = row.get('authors', '').split('; ') if row.get('authors') else []
                claims = row.get('claims', '').split('; ') if row.get('claims') else []

                paper = Paper(
                    source=row.get('source', 'unknown'),
                    id=row.get('id', ''),
                    title=row.get('title', ''),
                    abstract=row.get('abstract', ''),
                    authors=authors,
                    published_date=row.get('published_date', ''),
                    updated_date=row.get('updated_date'),
                    url=row.get('url', ''),
                    pdf_url=row.get('pdf_url'),
                    claims=claims,
                    hallucination_type=row.get('hallucination_type'),
                    original_paper_id=row.get('original_paper_id'),
                    venue=row.get('venue'),
                )
                papers.append(paper)

                if len(papers) >= sample_size:
                    break

        return papers

    async def _process_single_sample(
        self,
        paper: Paper,
        semaphore: asyncio.Semaphore,
        idx: int,
        total: int,
        verbose: bool,
    ) -> List[QueryRecord]:
        """处理单个样本（带并发控制），返回该样本的所有查询记录"""
        async with semaphore:
            if verbose:
                logger.info(f"Processing sample {idx + 1}/{total}: {paper.title[:50]}...")

            # 每个样本使用独立的 EvalLocalSearch 实例
            eval_search = EvalLocalSearch()

            # 设置当前样本的 GT
            eval_search.set_ground_truth(
                PaperGroundTruth(
                    id=paper.id,
                    title=paper.title,
                    authors=paper.authors,
                )
            )

            # 构造 detector（注入 eval_search）
            detector = HallucinationDetector(search=eval_search)

            # 运行检测
            try:
                await detector.acheck_reference(paper)
            except Exception as e:
                logger.error(f"Error processing {paper.id}: {e}")

            # 返回该样本的所有查询记录
            return eval_search.get_records()

    async def evaluate(
        self,
        dataset_path: str,
        sample_size: int = 100,
        workers: int = 5,
        verbose: bool = False,
    ) -> "RetrievalEvalResult":
        """
        评估检索性能（支持并发处理）

        Args:
            dataset_path: 数据集路径
            sample_size: 样本数量
            workers: 并发工作数（默认5）
            verbose: 是否输出详细日志

        Returns:
            RetrievalEvalResult 评估结果
        """
        samples = self._load_samples(dataset_path, sample_size)

        if verbose:
            logger.info(f"Loaded {len(samples)} samples from {dataset_path}")
            logger.info(f"Processing with {workers} concurrent workers")

        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(workers)

        # 创建所有任务（每个样本独立处理）
        tasks = [
            self._process_single_sample(
                paper=paper,
                semaphore=semaphore,
                idx=idx,
                total=len(samples),
                verbose=verbose,
            )
            for idx, paper in enumerate(samples)
        ]

        # 并发执行所有任务，收集每个样本的查询记录
        results = await asyncio.gather(*tasks)

        # 合并所有查询记录
        all_records = []
        for records in results:
            all_records.extend(records)

        if verbose:
            logger.info(f"Completed {len(all_records)} queries total from {len(samples)} samples")

        # 计算指标
        return self._aggregate_results(all_records, samples)

    def _aggregate_results(
        self,
        records: List[QueryRecord],
        samples: List[Paper]
    ) -> "RetrievalEvalResult":
        """汇总评估结果"""
        total = len(records)
        if total == 0:
            return RetrievalEvalResult(
                total_samples=len(samples),
                total_queries=0,
                recall_at_1=0.0,
                recall_at_3=0.0,
                recall_at_5=0.0,
                mrr=0.0,
                per_sample=[],
                all_records=[]
            )

        hit_at_1 = sum(1 for r in records if r.hit_rank == 1)
        hit_at_3 = sum(1 for r in records if r.hit_rank and r.hit_rank <= 3)
        hit_at_5 = sum(1 for r in records if r.hit_rank and r.hit_rank <= 5)
        mrr_sum = sum(1 / r.hit_rank if r.hit_rank else 0 for r in records)

        # 按样本分组统计
        per_sample = []
        for paper in samples:
            sample_records = [r for r in records if r.sample_id == paper.id]
            per_sample.append({
                'paper_id': paper.id,
                'paper_title': paper.title[:50],
                'queries': len(sample_records),
                'records': sample_records,
            })

        return RetrievalEvalResult(
            total_samples=len(samples),
            total_queries=total,
            recall_at_1=hit_at_1 / total,
            recall_at_3=hit_at_3 / total,
            recall_at_5=hit_at_5 / total,
            mrr=mrr_sum / total,
            per_sample=per_sample,
            all_records=records
        )
