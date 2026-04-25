"""Tests for pipeline state management."""

from src.core.state import ValidationPhase, PipelineState
from src.bench.schema import Reference


class TestValidationPhase:
    """Test ValidationPhase enum."""

    def test_phase_values(self):
        """Test that all expected phases exist."""
        assert ValidationPhase.IDLE.value == "idle"
        assert ValidationPhase.EXTRACTION.value == "extraction"
        assert ValidationPhase.DETECTION.value == "detection"
        assert ValidationPhase.COMPLETED.value == "completed"
        assert ValidationPhase.ERROR.value == "error"


class TestPipelineState:
    """Test PipelineState dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        state = PipelineState()
        assert state.phase == ValidationPhase.IDLE
        assert state.current_file is None
        assert state.extraction_found == 0
        assert state.detection_total == 0
        assert state.detection_processed == 0
        assert state.current_reference is None
        assert state.error is None
        assert state.extracted_refs == []

    def test_custom_initialization(self):
        """Test custom initialization."""
        ref = Reference(title="Test", authors=[], date="2024")
        state = PipelineState(
            phase=ValidationPhase.EXTRACTION,
            current_file="test.pdf",
            extraction_found=5,
            extracted_refs=[ref],
        )
        assert state.phase == ValidationPhase.EXTRACTION
        assert state.current_file == "test.pdf"
        assert state.extraction_found == 5
        assert len(state.extracted_refs) == 1
        assert state.extracted_refs[0].title == "Test"

    def test_to_dict(self):
        """Test serialization to dict."""
        state = PipelineState(
            phase=ValidationPhase.DETECTION,
            current_file="paper.pdf",
            extraction_found=10,
            detection_total=10,
            detection_processed=5,
            current_reference="Test Paper",
        )
        data = state.to_dict()

        assert data["phase"] == "detection"
        assert data["current_file"] == "paper.pdf"
        assert data["extraction_found"] == 10
        assert data["detection_total"] == 10
        assert data["detection_processed"] == 5
        assert data["current_reference"] == "Test Paper"
        assert data["error"] is None

    def test_phase_transitions(self):
        """Test state transitions through pipeline lifecycle."""
        state = PipelineState(current_file="test.pdf")

        # Start extraction
        state.phase = ValidationPhase.EXTRACTION
        state.extraction_found = 3
        assert state.phase.value == "extraction"

        # Move to detection
        state.phase = ValidationPhase.DETECTION
        state.detection_total = 3
        state.detection_processed = 1
        state.current_reference = "Paper 1"
        assert state.phase.value == "detection"
        assert state.detection_processed == 1

        # Complete
        state.phase = ValidationPhase.COMPLETED
        state.detection_processed = 3
        assert state.phase.value == "completed"

        # Error state
        state.phase = ValidationPhase.ERROR
        state.error = "Something went wrong"
        assert state.phase.value == "error"
        assert state.error == "Something went wrong"
