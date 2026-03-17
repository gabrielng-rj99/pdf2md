# Re-export all submodules for backwards compatibility
# This file ensures old imports like "from app.utils.image_filter import X" still work

# Text processing
from app.utils.text.text_cleaner import PDFTextCleaner, TextType
from app.utils.text.list_detector import ListDetector, get_list_detector

# Image processing
from app.utils.image.image_filter import ImageFilter
from app.utils.image.image_reference_mapper import ImageReferenceMapper

# Heading processing
from app.utils.headings.heading_scorer import (
    HeadingScorer,
    ScoringConfig,
    ScoringStrategy,
    quick_score,
    create_candidate_from_span,
)
from app.utils.headings.heading_filter import HeadingFilter

# Formula processing
from app.utils.formula.formula_detector import FormulaDetector
from app.utils.formula.formula_merger import FormulaMerger
from app.utils.formula.formula_reconstruction import FormulaReconstruction
from app.utils.formula.formula_reconstructor import FormulaReconstructor
from app.utils.formula.formula_ai import FormulaAI
from app.utils.formula.formula_image_detector import FormulaImageDetector
from app.utils.formula.latex_converter import LaTeXConverter
from app.utils.formula.llm_formula_converter import LLMFormulaConverter
from app.utils.formula.api_formula_converter import get_api_converter, APIFormulaConverter
from app.utils.formula.surgical_latex_converter import SurgicalLaTeXConverter
from app.utils.formula.math_postprocessor import MathPostProcessor
from app.utils.formula.math_span_detector import MathSpanDetector
from app.utils.formula.math_zone_detector import MathZoneDetector

# Analysis
from app.utils.analysis.orphan_reference_cleaner import OrphanReferenceCleaner
from app.utils.analysis.spatial_extractor import SpatialExtractor

# Helpers
from app.utils.helpers import Helpers  # if exists

__all__ = [
    # Text
    'PDFTextCleaner',
    'TextType',
    'ListDetector',
    'get_list_detector',
    # Image
    'ImageFilter',
    'ImageReferenceMapper',
    # Headings
    'HeadingScorer',
    'ScoringConfig',
    'ScoringStrategy',
    'quick_score',
    'create_candidate_from_span',
    'HeadingFilter',
    # Formula
    'FormulaDetector',
    'FormulaMerger',
    'FormulaReconstruction',
    'FormulaReconstructor',
    'FormulaAI',
    'FormulaImageDetector',
    'LaTeXConverter',
    'LLMFormulaConverter',
    'get_api_converter',
    'APIFormulaConverter',
    'SurgicalLaTeXConverter',
    'MathPostProcessor',
    'MathSpanDetector',
    'MathZoneDetector',
    # Analysis
    'OrphanReferenceCleaner',
    'SpatialExtractor',
]
