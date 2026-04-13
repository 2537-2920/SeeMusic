"""International feedback formatter for rhythm analysis results.

Supports multiple languages for user-friendly feedback messaging.
Currently supports: English, Chinese (Simplified)

Usage:
    ```python
    from backend.core.rhythm.i18n import FeedbackFormatter
    
    formatter = FeedbackFormatter(language='zh')  # Chinese
    feedback = formatter.format_score(85, 'professional')
    print(feedback)  # "优秀 - 专业级表现"
    ```
"""

from typing import Dict, Literal, Any, Optional
from enum import Enum


class Language(str, Enum):
    """Supported languages."""
    ENGLISH = 'en'
    CHINESE = 'zh'
    SPANISH = 'es'  # For future expansion
    FRENCH = 'fr'   # For future expansion


class FeedbackFormatter:
    """Multi-language feedback formatter for rhythm analysis.
    
    Translates numeric scores and metrics into natural language
    feedback in the user's preferred language.
    """

    # Translation dictionary: {language: {key: translation}}
    TRANSLATIONS: Dict[str, Dict[str, str]] = {
        'en': {
            # Overall performance
            'excellent': 'Excellent',
            'excellent_desc': 'Professional level performance',
            'good': 'Good',
            'good_desc': 'Strong performance with minor issues',
            'fair': 'Fair',
            'fair_desc': 'Moderate issues that need attention',
            'needs_improvement': 'Needs Improvement',
            'needs_improvement_desc': 'Significant rhythm problems',
            
            # Consistency assessment
            'very_stable': 'Very stable beat timing',
            'generally_stable': 'Generally stable with some variation',
            'inconsistent': 'Inconsistent timing - focus on regularity',
            
            # Tempo assessment
            'steady_tempo': 'Maintained steady tempo',
            'accelerating': 'Detected accelerating tempo during performance',
            'decelerating': 'Detected decelerating tempo during performance',
            
            # Timing tendency
            'all_well_timed': 'All beats well-timed',
            'ahead_of_beat': 'Tendency to play ahead of the beat',
            'behind_beat': 'Tendency to play behind the beat',
            'balanced_timing': 'Balanced timing distribution',
            
            # Accuracy levels
            'perfect': 'Perfect',
            'great': 'Great',
            'good_acc': 'Good',
            'needs_improvement_acc': 'Needs Improvement',
            
            # Feedback messages
            'missing_beats': 'Missing {} beat(s) - focus on beat awareness and tracking',
            'extra_beats': 'Extra {} beat(s) - tighten control to match reference',
            'ahead_advice': 'Playing ahead of beat - wait for the downbeat before entering',
            'behind_advice': 'Playing behind beat - practice with a metronome for tighter timing',
            'well_done': 'Well done! Continue consistent practice',
            
            # Metrics labels
            'score': 'Score',
            'timing_accuracy': 'Timing Accuracy',
            'mean_deviation': 'Mean Deviation',
            'consistency': 'Consistency',
            'confidence': 'Confidence',
        },
        'zh': {
            # Overall performance
            'excellent': '优秀',
            'excellent_desc': '专业级表现',
            'good': '良好',
            'good_desc': '表现强劲，有小问题',
            'fair': '一般',
            'fair_desc': '有中等问题需要改进',
            'needs_improvement': '需要改进',
            'needs_improvement_desc': '节奏问题明显',
            
            # Consistency assessment
            'very_stable': '节拍时序非常稳定',
            'generally_stable': '总体稳定，略有变化',
            'inconsistent': '节拍不稳定 - 需要改进规律性',
            
            # Tempo assessment
            'steady_tempo': '保持了稳定的节奏',
            'accelerating': '检测到节奏在加速',
            'decelerating': '检测到节奏在减速',
            
            # Timing tendency
            'all_well_timed': '所有节拍都很准时',
            'ahead_of_beat': '有提前打拍的倾向',
            'behind_beat': '有延迟打拍的倾向',
            'balanced_timing': '打拍时序分布均衡',
            
            # Accuracy levels
            'perfect': '完美',
            'great': '很好',
            'good_acc': '良好',
            'needs_improvement_acc': '需要改进',
            
            # Feedback messages
            'missing_beats': '缺少{}个节拍 - 提高节拍意识和追踪能力',
            'extra_beats': '多了{}个节拍 - 加强控制以匹配参考',
            'ahead_advice': '有提前的倾向 - 等待起拍后再开始演唱',
            'behind_advice': '有延迟的倾向 - 使用节拍器练习，提高时序准确性',
            'well_done': '做得很好！继续坚持练习',
            
            # Metrics labels
            'score': '得分',
            'timing_accuracy': '时序准确度',
            'mean_deviation': '平均偏差',
            'consistency': '一致性',
            'confidence': '置信度',
        }
    }

    def __init__(self, language: str = 'en') -> None:
        """Initialize formatter with target language.
        
        Args:
            language: Language code ('en' or 'zh'). Defaults to English.
                     Falls back to English for unsupported languages.
        
        Example:
            ```python
            formatter_en = FeedbackFormatter('en')
            formatter_zh = FeedbackFormatter('zh')
            ```
        """
        self.language = language if language in self.TRANSLATIONS else 'en'
        self.texts = self.TRANSLATIONS[self.language]

    def t(self, key: str, *args: Any, **kwargs: Any) -> str:
        """Translate key to current language.
        
        Args:
            key: Translation key.
            *args: Positional arguments for string formatting.
            **kwargs: Keyword arguments for string formatting.
            
        Returns:
            Translated text, formatted with any provided arguments.
        
        Example:
            ```python
            formatter = FeedbackFormatter('zh')
            msg = formatter.t('missing_beats', 3)
            print(msg)  # "缺少3个节拍 - 提高节拍意识和追踪能力"
            ```
        """
        text = self.texts.get(key, key)
        if args:
            return text.format(*args)
        if kwargs:
            return text.format(**kwargs)
        return text

    def format_overall_score(self, score: float) -> str:
        """Format overall performance score.
        
        Args:
            score: Score value (0-100).
            
        Returns:
            Descriptive text for the score.
            
        Example:
            ```python
            formatter = FeedbackFormatter('zh')
            desc = formatter.format_overall_score(85)
            print(desc)  # "优秀 - 专业级表现"
            ```
        """
        if score >= 85:
            return f"{self.t('excellent')} - {self.t('excellent_desc')}"
        elif score >= 70:
            return f"{self.t('good')} - {self.t('good_desc')}"
        elif score >= 50:
            return f"{self.t('fair')} - {self.t('fair_desc')}"
        else:
            return f"{self.t('needs_improvement')} - {self.t('needs_improvement_desc')}"

    def format_consistency_assessment(self, consistency_score: float) -> str:
        """Format consistency assessment.
        
        Args:
            consistency_score: Consistency value (0.0-1.0).
            
        Returns:
            Consistency assessment text.
        """
        if consistency_score >= 0.85:
            return self.t('very_stable')
        elif consistency_score >= 0.70:
            return self.t('generally_stable')
        else:
            return self.t('inconsistent')

    def format_tempo_assessment(self, has_change: bool, drift_detected: str) -> str:
        """Format tempo change assessment.
        
        Args:
            has_change: Whether tempo change was detected.
            drift_detected: Type of drift ('accelerating', 'decelerating', 'stable').
            
        Returns:
            Tempo assessment text.
        """
        if not has_change:
            return self.t('steady_tempo')
        elif drift_detected == 'accelerating':
            return self.t('accelerating')
        elif drift_detected == 'decelerating':
            return self.t('decelerating')
        else:
            return self.t('steady_tempo')

    def format_timing_assessment(self, on_time: int, early: int, late: int) -> str:
        """Format timing tendency assessment.
        
        Args:
            on_time: Number of on-time beats.
            early: Number of early beats.
            late: Number of late beats.
            
        Returns:
            Timing assessment text.
        """
        total = on_time + early + late
        if total == 0:
            return 'N/A'
        elif on_time == total:
            return self.t('all_well_timed')
        elif early > late * 1.5:
            return self.t('ahead_of_beat')
        elif late > early * 1.5:
            return self.t('behind_beat')
        else:
            return self.t('balanced_timing')

    def format_accuracy_level(self, mean_deviation_ms: float) -> str:
        """Format accuracy level based on mean deviation.
        
        Args:
            mean_deviation_ms: Mean timing deviation in milliseconds.
            
        Returns:
            Accuracy level text.
        """
        if mean_deviation_ms < 30:
            return self.t('perfect')
        elif mean_deviation_ms < 70:
            return self.t('great')
        elif mean_deviation_ms < 120:
            return self.t('good_acc')
        else:
            return self.t('needs_improvement_acc')

    def format_main_issues(
        self,
        missing: int,
        extra: int,
        early: int,
        late: int
    ) -> list[str]:
        """Format main feedback issues.
        
        Args:
            missing: Number of missing beats.
            extra: Number of extra beats.
            early: Number of early beats.
            late: Number of late beats.
            
        Returns:
            List of feedback messages.
        """
        issues: list[str] = []

        if missing > 0:
            issues.append(self.t('missing_beats', missing))

        if extra > 0:
            issues.append(self.t('extra_beats', extra))

        if early > late and early > 0:
            issues.append(self.t('ahead_advice'))
        elif late > early and late > 0:
            issues.append(self.t('behind_advice'))

        if not issues:
            issues.append(self.t('well_done'))

        return issues

    def format_result(
        self, result: Dict[str, Any], include_details: bool = True
    ) -> Dict[str, Any]:
        """Format complete rhythm analysis result with translations.
        
        Args:
            result: Raw analysis result from compare_rhythm().
            include_details: Whether to include detailed assessment.
            
        Returns:
            Formatted result with translated feedback.
        
        Example:
            ```python
            analyzer = AdvancedRhythmAnalyzer()
            result = analyzer.compare_rhythm(user_beats, ref_beats)
            
            formatter = FeedbackFormatter('zh')
            translated = formatter.format_result(result)
            
            print(translated['overall_assessment'])
            # "优秀 - 专业级表现"
            ```
        """
        if 'error' in result:
            return {
                'error': result['error'],
                'error_zh': self.t(result['error'], Language.CHINESE)
                if self.language == 'en' else result['error']
            }

        error_class = result.get('error_classification', {})
        assessment = result.get('detailed_assessment', {})
        
        return {
            # Translated scores and metrics
            'overall_assessment': self.format_overall_score(result['score']),
            'consistency_assessment': self.format_consistency_assessment(
                assessment.get('consistency_score', 0)
            ),
            'tempo_assessment': self.format_tempo_assessment(
                result['tempo_analysis']['has_tempo_change'],
                result['tempo_analysis']['drift_detected']
            ),
            'timing_assessment': self.format_timing_assessment(
                error_class.get('on_time', 0),
                error_class.get('early', 0),
                error_class.get('late', 0)
            ),
            'accuracy_level': self.format_accuracy_level(
                result['mean_deviation_ms']
            ),
            
            # Translated feedback
            'main_issues': self.format_main_issues(
                result['missing_beats'],
                result['extra_beats'],
                error_class.get('early', 0),
                error_class.get('late', 0)
            ),
            
            # Original data for reference
            **result,
        }


def create_multilingual_feedback(
    result: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """Create feedback in all supported languages.
    
    Args:
        result: Raw analysis result from compare_rhythm().
        
    Returns:
        Dict with formatted feedback for each language.
    
    Example:
        ```python
        result = analyzer.compare_rhythm(user_beats, ref_beats)
        multilingual = create_multilingual_feedback(result)
        
        # English feedback
        print(multilingual['en']['overall_assessment'])
        
        # Chinese feedback
        print(multilingual['zh']['overall_assessment'])
        ```
    """
    languages = {
        'en': 'English',
        'zh': 'Chinese',
    }
    
    return {
        lang_code: FeedbackFormatter(lang_code).format_result(result)
        for lang_code in languages.keys()
    }
