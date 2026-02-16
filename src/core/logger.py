import logging
from rich.logging import RichHandler
from rich.console import Console

# 全局 Console 实例，可用于直接打印富文本
console = Console()


def setup_logger(name: str = "valiref", level: int = logging.INFO) -> logging.Logger:
    """
    Configures the root logger using basicConfig and returns a specific logger instance.
    This ensures a single handler at the root level, preventing double logging
    and providing consistent formatting across the application.

    Args:
        name: The name of the logger.
        level: The logging level.

    Returns:
        A configured logging.Logger instance.
    """
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                markup=True,
                show_time=True,
                show_path=True,
            )
        ],
        force=True
    )

    # Get the specific logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger


# Create a default logger instance
logger = setup_logger()
