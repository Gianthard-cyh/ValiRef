import os
import shutil
from pathlib import Path
from typing import Optional
from ...core.config import PDF_STORAGE_PATH


class PDFStorage:
    """PDF文件临时存储管理"""

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(storage_path or PDF_STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, task_id: str, filename: str) -> Path:
        """生成存储路径"""
        task_dir = self.storage_path / task_id[:2] / task_id[2:4]
        task_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-").rstrip()
        return task_dir / f"{task_id}_{safe_filename}"

    async def save(self, task_id: str, filename: str, content: bytes) -> str:
        """保存PDF文件，返回存储路径"""
        file_path = self._get_file_path(task_id, filename)
        with open(file_path, "wb") as f:
            f.write(content)
        return str(file_path)

    def get(self, task_id: str, filename: str) -> Optional[str]:
        """获取PDF文件路径（不检查是否存在）"""
        return str(self._get_file_path(task_id, filename))

    def delete(self, task_id: str, filename: str) -> bool:
        """删除PDF文件"""
        file_path = self._get_file_path(task_id, filename)
        try:
            file_path.unlink()
            return True
        except FileNotFoundError:
            return False
