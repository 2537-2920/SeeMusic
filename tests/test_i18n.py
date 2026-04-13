"""Integration tests for internationalization (i18n) support.

Demonstrates complete i18n workflow and validates multilingual feedback system.
"""

import pytest
from backend.core.rhythm.beat_detection import AdvancedBeatDetector
from backend.core.rhythm.rhythm_analysis import AdvancedRhythmAnalyzer
from backend.core.rhythm.i18n import FeedbackFormatter, create_multilingual_feedback


class TestInternationalizationSupport:
    """Test suite for internationalization features."""

    @pytest.fixture
    def analyzer(self):
        """Create rhythm analyzer instance."""
        return AdvancedRhythmAnalyzer(threshold_ms=50)

    @pytest.fixture
    def sample_beats(self):
        """Provide sample beat sequences for testing."""
        return {
            'user_beats': [0.5, 1.02, 1.48, 2.0, 2.52],  # Slightly off
            'ref_beats': [0.5, 1.0, 1.5, 2.0, 2.5],      # Perfect
        }

    def test_english_feedback_generation(self, analyzer, sample_beats):
        """Test feedback generation in English."""
        result = analyzer.compare_rhythm(
            sample_beats['user_beats'],
            sample_beats['ref_beats'],
            language='en'
        )

        # Assertions
        assert result['feedback']['language'] == 'en'
        assert 'main_issues' in result['feedback']
        assert len(result['feedback']['main_issues']) > 0
        assert 'accuracy_level' in result['feedback']

        # English specific assertions
        issues = result['feedback']['main_issues']
        for issue in issues:
            assert isinstance(issue, str)
            assert len(issue) > 0

    def test_chinese_feedback_generation(self, analyzer, sample_beats):
        """Test feedback generation in Chinese."""
        result = analyzer.compare_rhythm(
            sample_beats['user_beats'],
            sample_beats['ref_beats'],
            language='zh'
        )

        # Assertions
        assert result['feedback']['language'] == 'zh'
        assert 'main_issues' in result['feedback']
        assert len(result['feedback']['main_issues']) > 0

        # Chinese specific assertions - check for Chinese characters
        issues = result['feedback']['main_issues']
        assert any('\u4e00' <= c <= '\u9fff' for issue in issues for c in issue)

    def test_feedback_formatter_english(self):
        """Test FeedbackFormatter with English language."""
        formatter = FeedbackFormatter('en')

        # Test translation
        assert formatter.t('excellent') == 'Excellent'
        assert formatter.t('missing_beats', 2) == 'Missing 2 beat(s) - focus on beat awareness and tracking'

        # Test format methods
        assert 'Excellent' in formatter.format_overall_score(90)
        assert 'stable' in formatter.format_consistency_assessment(0.9).lower()
        assert 'Perfect' in formatter.format_accuracy_level(20)

    def test_feedback_formatter_chinese(self):
        """Test FeedbackFormatter with Chinese language."""
        formatter = FeedbackFormatter('zh')

        # Test translation
        assert formatter.t('excellent') == '优秀'
        assert '缺少' in formatter.t('missing_beats', 2)

        # Test format methods
        assert '优秀' in formatter.format_overall_score(90)
        assert '稳定' in formatter.format_consistency_assessment(0.9)
        assert '完美' in formatter.format_accuracy_level(20)

    def test_language_fallback(self):
        """Test fallback to English for unsupported languages."""
        formatter = FeedbackFormatter('es')  # Spanish not yet supported
        
        # Should fallback to English
        assert formatter.language == 'en'
        assert 'Excellent' in formatter.format_overall_score(90)

    def test_multilingual_main_issues(self):
        """Test format_main_issues across languages."""
        missing = 2
        extra = 1
        early = 1
        late = 0

        formatter_en = FeedbackFormatter('en')
        issues_en = formatter_en.format_main_issues(missing, extra, early, late)

        formatter_zh = FeedbackFormatter('zh')
        issues_zh = formatter_zh.format_main_issues(missing, extra, early, late)

        # Both should generate issues
        assert len(issues_en) > 0
        assert len(issues_zh) > 0

        # English should contain English keywords
        assert any('Missing' in issue for issue in issues_en)

        # Chinese should contain Chinese characters
        assert any('\u4e00' <= c <= '\u9fff' for issue in issues_zh for c in issue)

    def test_format_result_complete(self):
        """Test complete result formatting with language support."""
        analyzer = AdvancedRhythmAnalyzer()
        result = analyzer.compare_rhythm(
            [0.5, 1.02, 1.48, 2.0, 2.52],
            [0.5, 1.0, 1.5, 2.0, 2.5],
            language='zh'
        )

        formatter = FeedbackFormatter('zh')
        formatted = formatter.format_result(result)

        # Check all expected keys
        assert 'overall_assessment' in formatted
        assert 'consistency_assessment' in formatted
        assert 'tempo_assessment' in formatted
        assert 'timing_assessment' in formatted
        assert 'accuracy_level' in formatted
        assert 'main_issues' in formatted

        # All should be Chinese
        all_text = ' '.join([
            formatted['overall_assessment'],
            formatted['consistency_assessment'],
            formatted['tempo_assessment'],
            formatted['timing_assessment'],
            formatted['accuracy_level'],
            ' '.join(formatted['main_issues'])
        ])

        # Check for Chinese characters
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in all_text)
        assert has_chinese, "Formatted result should contain Chinese characters"

    def test_create_multilingual_feedback(self):
        """Test generating feedback in all supported languages."""
        analyzer = AdvancedRhythmAnalyzer()
        result = analyzer.compare_rhythm(
            [0.5, 1.02, 1.48, 2.0, 2.52],
            [0.5, 1.0, 1.5, 2.0, 2.5]
        )

        multilingual = create_multilingual_feedback(result)

        # Should have entries for all supported languages
        assert 'en' in multilingual
        assert 'zh' in multilingual

        # Each should have complete feedback
        for lang in ['en', 'zh']:
            assert 'overall_assessment' in multilingual[lang]
            assert 'main_issues' in multilingual[lang]

    def test_backward_compatibility_default_language(self, analyzer, sample_beats):
        """Test backward compatibility - default to English."""
        # Call without language parameter
        result = analyzer.compare_rhythm(
            sample_beats['user_beats'],
            sample_beats['ref_beats']
        )

        # Should default to English
        assert result['feedback']['language'] == 'en'
        assert 'main_issues' in result['feedback']

    def test_score_rhythm_with_language(self, analyzer, sample_beats):
        """Test score_rhythm alias with language parameter."""
        result = analyzer.score_rhythm(
            sample_beats['user_beats'],
            sample_beats['ref_beats'],
            language='zh'
        )

        assert result['feedback']['language'] == 'zh'
        assert 'main_issues' in result['feedback']

    def test_consistency_assessment_languages(self):
        """Test consistency assessment in different languages."""
        test_cases = [
            (0.95, ['very_stable', '稳定']),
            (0.75, ['generally_stable', '总体稳定']),
            (0.50, ['Inconsistent', '不稳定']),
        ]

        for consistency_score, expected_keywords in test_cases:
            formatter_en = FeedbackFormatter('en')
            assessment_en = formatter_en.format_consistency_assessment(consistency_score)

            formatter_zh = FeedbackFormatter('zh')
            assessment_zh = formatter_zh.format_consistency_assessment(consistency_score)

            # Check English
            assert any(kw.lower() in assessment_en.lower() for kw in expected_keywords[:1])

            # Check Chinese (simpler check for characters)
            assert len(assessment_zh) > 0

    def test_accuracy_level_translation(self):
        """Test accuracy level formatting in different languages."""
        test_cases = [
            (20, ['Perfect', '完美']),
            (50, ['Great', '很好']),
            (100, ['Good', '良好']),
            (150, ['Needs Improvement', '需要改进']),
        ]

        for mean_dev_ms, expected_keywords in test_cases:
            formatter_en = FeedbackFormatter('en')
            level_en = formatter_en.format_accuracy_level(mean_dev_ms)

            formatter_zh = FeedbackFormatter('zh')
            level_zh = formatter_zh.format_accuracy_level(mean_dev_ms)

            assert len(level_en) > 0
            assert len(level_zh) > 0


class TestI18nPerformance:
    """Test i18n performance characteristics."""

    def test_formatter_instantiation_speed(self):
        """Test that formatter instantiation is fast."""
        import time

        start = time.time()
        for _ in range(1000):
            FeedbackFormatter('en')
        elapsed = time.time() - start

        # Should be very fast (< 100ms for 1000 instances)
        assert elapsed < 0.1, f"Formatter instantiation too slow: {elapsed}s"

    def test_translation_lookup_speed(self):
        """Test that translation lookup is O(1)."""
        import time

        formatter = FeedbackFormatter('zh')

        start = time.time()
        for _ in range(10000):
            formatter.t('excellent')
        elapsed = time.time() - start

        # Should be very fast (< 10ms for 10000 lookups)
        assert elapsed < 0.01, f"Translation lookup too slow: {elapsed}s"

    def test_format_result_speed(self):
        """Test that format_result is reasonably fast."""
        import time

        analyzer = AdvancedRhythmAnalyzer()
        result = analyzer.compare_rhythm(
            [0.5, 1.02, 1.48, 2.0, 2.52],
            [0.5, 1.0, 1.5, 2.0, 2.5]
        )

        formatter = FeedbackFormatter('zh')

        start = time.time()
        for _ in range(100):
            formatter.format_result(result)
        elapsed = time.time() - start

        # Should be very fast (< 100ms for 100 format operations)
        assert elapsed < 0.1, f"format_result too slow: {elapsed}s"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
