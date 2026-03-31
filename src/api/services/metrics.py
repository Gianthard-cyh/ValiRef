"""Prometheus metrics for ValiRef."""
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Counter - 只增不减，用于累计值
tasks_submitted = Counter(
    "valiref_tasks_submitted_total",
    "Total number of submitted tasks"
)

tasks_completed = Counter(
    "valiref_tasks_completed_total",
    "Total number of completed tasks"
)

tasks_failed = Counter(
    "valiref_tasks_failed_total",
    "Total number of failed tasks",
    ["permanent"]  # true=永久失败, false=可重试
)

# Gauge - 当前值，用于实时状态
tasks_active = Gauge(
    "valiref_tasks_active",
    "Current number of active tasks by status",
    ["status"]  # pending, processing, retrying
)

# Histogram - 处理时长分布，多 Worker 可聚合
# 9 个桶覆盖从 10 秒到 1 小时
task_duration_seconds = Histogram(
    "valiref_task_duration_seconds",
    "Task processing duration in seconds",
    buckets=[10, 30, 60, 120, 300, 600, 900, 1800, 3600]  # 10s, 30s, 1min, 2min, 5min, 10min, 15min, 30min, 1hour
)


def get_metrics():
    """Generate Prometheus metrics output."""
    return generate_latest(), CONTENT_TYPE_LATEST
