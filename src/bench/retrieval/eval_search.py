"""
评估用的本地搜索工具 - 支持动态设置 Ground Truth
"""

import csv
import json
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, TypedDict

from ...core.search.base import SearchResult
from ...core.search.sources.local_db import LocalDBSearch


class PaperGroundTruth(TypedDict):
    """Ground Truth 论文信息"""
    id: str
    title: str
    authors: List[str]


@dataclass
class QueryRecord:
    """单次查询记录"""
    sample_id: str               # 所属样本ID
    sample_title: str            # 样本标题（用于识别）
    query: str                   # 查询字符串
    hit_rank: Optional[int]      # Ground Truth 在结果中的排名
    result_count: int            # 返回结果数
    duration_ms: float           # 查询耗时


class EvalLocalSearch(LocalDBSearch):
    """
    用于评估的本地搜索工具 - 保存所有查询供后续分析

    支持动态设置 Ground Truth，所有查询记录保留在内存中，
    评估结束后可导出为 JSON/CSV 供后续分析。

    使用方式:
        search = EvalLocalSearch()

        for paper in samples:
            search.set_ground_truth({
                'id': paper.id,
                'title': paper.title,
                'authors': paper.authors,
            })

            # 运行检测
            result = await detector.acheck_reference(paper)

        # 评估结束后导出所有查询
        all_records = search.get_records()
        search.export_records("results/all_queries.json")
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._gt: Optional[PaperGroundTruth] = None
        self._records: List[QueryRecord] = []
        self._current_sample_id: Optional[str] = None

    def set_ground_truth(self, ground_truth: PaperGroundTruth) -> None:
        """
        设置当前 Ground Truth（每个样本开始前调用）

        Args:
            ground_truth: Ground Truth 论文信息
        """
        self._gt = ground_truth
        self._current_sample_id = ground_truth["id"]

    def clear_ground_truth(self) -> None:
        """清空 Ground Truth（可选，在样本结束后调用）"""
        self._gt = None
        self._current_sample_id = None

    async def asearch(self, query: str, limit: int = 5) -> List[SearchResult]:
        """执行搜索并记录查询"""
        start = time.time()
        results = await super().asearch(query, limit)
        duration_ms = (time.time() - start) * 1000

        # 计算命中排名
        hit_rank = self._find_hit_rank(results) if self._gt else None

        # 记录查询（包含样本信息）
        self._records.append(QueryRecord(
            sample_id=self._current_sample_id or "unknown",
            sample_title=self._gt["title"] if self._gt else "unknown",
            query=query,
            hit_rank=hit_rank,
            result_count=len(results),
            duration_ms=duration_ms
        ))
        return results

    def _find_hit_rank(self, results: List[SearchResult]) -> Optional[int]:
        """找到 Ground Truth 在结果中的排名"""
        if not self._gt:
            return None

        gt_id = self._gt["id"]
        gt_title = self._gt["title"].lower()

        for idx, r in enumerate(results, 1):
            if gt_id in r.url:
                return idx
            if SequenceMatcher(None, gt_title, r.title.lower()).ratio() > 0.85:
                return idx
        return None

    def get_records(self) -> List[QueryRecord]:
        """获取所有查询记录（整个评估过程的所有查询）"""
        return self._records.copy()

    def clear_records(self) -> None:
        """清空所有查询记录"""
        self._records = []

    def export_records(self, filepath: str, format: str = "json") -> None:
        """
        导出查询记录到文件

        Args:
            filepath: 输出文件路径
            format: 格式，"json" 或 "csv"
        """
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
                for r in self._records
            ]
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        elif format == "csv":
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["sample_id", "sample_title", "query", "hit_rank",
                                "result_count", "duration_ms"])
                for r in self._records:
                    writer.writerow([r.sample_id, r.sample_title, r.query,
                                   r.hit_rank, r.result_count, r.duration_ms])

    def get_metrics(self) -> dict:
        """计算整体检索指标（基于所有查询）"""
        if not self._records:
            return {
                "recall@1": 0.0,
                "recall@3": 0.0,
                "recall@5": 0.0,
                "mrr": 0.0,
                "total_queries": 0
            }

        total = len(self._records)
        hit_at_1 = sum(1 for r in self._records if r.hit_rank == 1)
        hit_at_3 = sum(1 for r in self._records if r.hit_rank and r.hit_rank <= 3)
        hit_at_5 = sum(1 for r in self._records if r.hit_rank and r.hit_rank <= 5)
        mrr_sum = sum(1 / r.hit_rank if r.hit_rank else 0 for r in self._records)

        return {
            "recall@1": hit_at_1 / total,
            "recall@3": hit_at_3 / total,
            "recall@5": hit_at_5 / total,
            "mrr": mrr_sum / total,
            "total_queries": total,
            "avg_results": sum(r.result_count for r in self._records) / total,
            "avg_duration_ms": sum(r.duration_ms for r in self._records) / total,
        }

    def get_sample_metrics(self, sample_id: str) -> dict:
        """获取指定样本的检索指标"""
        sample_records = [r for r in self._records if r.sample_id == sample_id]
        if not sample_records:
            return {"recall@5": 0.0, "mrr": 0.0, "queries": 0}

        total = len(sample_records)
        hit_at_5 = sum(1 for r in sample_records if r.hit_rank and r.hit_rank <= 5)
        mrr_sum = sum(1 / r.hit_rank if r.hit_rank else 0 for r in sample_records)

        return {
            "recall@5": hit_at_5 / total,
            "mrr": mrr_sum / total,
            "queries": total,
        }
