import logging
from rich.logging import RichHandler
from rich.console import Console

# 全局 Console 实例，可用于直接打印富文本
console = Console()


def setup_logger(name: str = "valiref", level: int = logging.INFO) -> logging.Logger:
    """
    Configures and returns a logger instance using Rich.

    Args:
        name: The name of the logger.
        level: The logging level.

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Check if the logger already has handlers to avoid duplicate logs
    if not logger.handlers:
        logger.setLevel(level)

        # Create Rich handler
        handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            show_path=False,
        )
        handler.setLevel(level)

        # Format is handled by RichHandler, but we can set a basic one if needed
        # For RichHandler, it ignores the format string mostly, focusing on the message
        formatter = logging.Formatter("%(message)s", datefmt="[%X]")
        handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(handler)

    return logger


# Create a default logger instance
logger = setup_logger()
