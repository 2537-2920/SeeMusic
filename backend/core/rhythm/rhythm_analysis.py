import numpy as np
from typing import List, Dict, Tuple, Any, Optional, Literal

try:
    from fastdtw import fastdtw as _fastdtw
except ImportError:  # pragma: no cover - exercised through fallback path
    _fastdtw = None

from .i18n import FeedbackFormatter


def _fallback_dtw(user_beats: np.ndarray, ref_beats: np.ndarray) -> Tuple[float, List[Tuple[int, int]]]:
    """Compute a simple DTW alignment when fastdtw is unavailable."""
    n_user = len(user_beats)
    n_ref = len(ref_beats)
    cost = np.full((n_user + 1, n_ref + 1), np.inf, dtype=float)
    cost[0, 0] = 0.0

    for i in range(1, n_user + 1):
        for j in range(1, n_ref + 1):
            dist = abs(float(user_beats[i - 1]) - float(ref_beats[j - 1]))
            cost[i, j] = dist + min(cost[i - 1, j], cost[i, j - 1], cost[i - 1, j - 1])

    i = n_user
    j = n_ref
    path: List[Tuple[int, int]] = []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        candidates = [
            (cost[i - 1, j - 1], i - 1, j - 1),
            (cost[i - 1, j], i - 1, j),
            (cost[i, j - 1], i, j - 1),
        ]
        _, i, j = min(candidates, key=lambda item: item[0])

    while i > 0:
        i -= 1
        path.append((i, 0))
    while j > 0:
        j -= 1
        path.append((0, j))

    path.reverse()
    return float(cost[n_user, n_ref]), path


def _compute_dtw_alignment(user_beats: np.ndarray, ref_beats: np.ndarray) -> Tuple[float, List[Tuple[int, int]]]:
    """Use fastdtw when available, otherwise fall back to exact DP DTW."""
    if _fastdtw is not None:
        user_beats_2d = user_beats.reshape(-1, 1)
        ref_beats_2d = ref_beats.reshape(-1, 1)
        return _fastdtw(
            user_beats_2d,
            ref_beats_2d,
            dist=lambda left, right: abs(float(left[0]) - float(right[0])),
        )
    return _fallback_dtw(user_beats, ref_beats)

class AdvancedRhythmAnalyzer:
    """Advanced rhythm analysis with multi-dimensional evaluation.
    
    Comprehensive rhythm assessment using DTW time-series alignment
    and multi-metric scoring:
    - Timing accuracy: mean/max/std deviation from reference
    - Consistency: how regularly spaced are user beats?
    - Tempo stability: acceleration/deceleration detection
    - Error classification: early/on-time/late categorization
    - Actionable feedback: specific improvement suggestions
    
    Typical workflow:
    ```python
    analyzer = AdvancedRhythmAnalyzer(threshold_ms=50)
    result = analyzer.compare_rhythm(user_beats, ref_beats, scoring_model='balanced')
    print(f"Score: {result['score']}/100")
    print(f"Feedback: {result['feedback']['main_issues']}")
    ```
    
    Scoring models:
    - 'strict': High penalties (dev_factor=0.8, 15× error penalty)
    - 'balanced': Moderate penalties (dev_factor=0.6, 10× error penalty) [default]
    - 'lenient': Forgiving (dev_factor=0.4, 5× error penalty)
    """

    def __init__(self, threshold_ms: float = 50.0):
        """Initialize rhythm analyzer.
        
        Args:
            threshold_ms: Time window (ms) for classifying beats as on-time.
                         Default 50ms follows standard metronome tolerance.
        """
        self.threshold_ms = threshold_ms / 1000.0

    def analyze_errors(self, path: List[Tuple[int, int]]) -> Tuple[int, int, List[Tuple[int, int]]]:
        """Analyze DTW path to identify missing beats, extra beats, and valid pairs.
        
        Missing beats: reference beat with no user parallel (user_idx stays same).
        Extra beats: user beat with no reference parallel (ref_idx stays same).
        Valid pairs: both indices advance simultaneously (aligned beats).
        
        Args:
            path: DTW alignment path from fastdtw.
            
        Returns:
            Tuple of (missing_count, extra_count, valid_aligned_pairs).
        """
        if not path:
            return 0, 0, []
        
        missing_beats = 0
        extra_beats = 0
        valid_pairs = [path[0]]

        for k in range(1, len(path)):
            prev_u, prev_r = path[k - 1]
            curr_u, curr_r = path[k]
            
            # Check if indices changed
            user_advanced = curr_u > prev_u
            ref_advanced = curr_r > prev_r

            if not user_advanced and ref_advanced:
                # Reference advanced but user didn't → missing user beat
                missing_beats += 1
            elif user_advanced and not ref_advanced:
                # User advanced but reference didn't → extra user beat
                extra_beats += 1
            elif user_advanced and ref_advanced:
                # Both advanced → valid alignment
                valid_pairs.append((curr_u, curr_r))

        return missing_beats, extra_beats, valid_pairs

    def compute_interval_consistency(self, beats: List[float]) -> Dict[str, float]:
        """Analyze beat interval consistency (spacing regularity).
        
        Measures how regularly spaced beats are using:
        - Mean interval (average time between beats)
        - Standard deviation of intervals
        - Coefficient of variation (CV) = std / mean
        - Consistency score (0=irregular, 1=perfect)
        
        Args:
            beats: List of beat timestamps in seconds.
            
        Returns:
            Dict with consistency metrics.
        """
        if len(beats) < 2:
            return {
                'consistency_score': 0.0,
                'interval_std_ms': 0.0,
                'cv': 0.0,
                'mean_interval_ms': 0.0,
            }

        intervals = np.diff(beats)
        mean_interval = float(np.mean(intervals))
        std_interval = float(np.std(intervals))
        
        # Avoid division by zero
        if mean_interval < 1e-8:
            return {
                'consistency_score': 0.0,
                'interval_std_ms': 0.0,
                'cv': float('inf'),
                'mean_interval_ms': 0.0,
            }
        
        cv = std_interval / mean_interval
        # Use hyperbolic tangent to compress CV into [0, 1] range
        consistency = max(0.0, 1.0 - np.tanh(cv))

        return {
            'consistency_score': float(consistency),
            'interval_std_ms': float(std_interval * 1000.0),
            'cv': float(cv),
            'mean_interval_ms': float(mean_interval * 1000.0),
        }

    def detect_tempo_changes(
        self, user_beats: List[float], ref_beats: List[float]
    ) -> Dict[str, Any]:
        """Detect acceleration or deceleration patterns.
        
        Uses polynomial regression to detect trends in beat interval changes.
        Calculates tempo drift from first to last beat interval.
        
        Args:
            user_beats: User's beat timestamps (seconds).
            ref_beats: Reference beat timestamps (seconds).
            
        Returns:
            Dict with has_tempo_change, tempo_drift, acceleration_rate, drift_detected.
        """
        if len(user_beats) < 3 or len(ref_beats) < 3:
            return {
                'has_tempo_change': False,
                'tempo_drift': 0.0,
                'acceleration_rate': 0.0,
                'drift_detected': 'stable',
            }

        user_intervals = np.diff(user_beats)
        ref_intervals = np.diff(ref_beats)

        if len(user_intervals) < 2:
            return {
                'has_tempo_change': False,
                'tempo_drift': 0.0,
                'acceleration_rate': 0.0,
                'drift_detected': 'stable',
            }

        # Detect trend via polynomial fit (1st order = linear)
        user_trend = np.polyfit(range(len(user_intervals)), user_intervals, 1)[0]
        # ref_trend unused but could be used for relative change detection

        # Calculate tempo drift
        interval_ratio = user_intervals[-1] / (user_intervals[0] + 1e-10)
        tempo_drift = float(interval_ratio - 1.0)
        acceleration_rate = float(user_trend)

        # Detect significant change (>5%)
        has_change = abs(tempo_drift) > 0.05

        return {
            'has_tempo_change': has_change,
            'tempo_drift': float(tempo_drift),
            'acceleration_rate': float(acceleration_rate),
            'drift_detected': (
                'accelerating'
                if tempo_drift > 0.05
                else ('decelerating' if tempo_drift < -0.05 else 'stable')
            ),
        }

    def classify_beat_errors(
        self,
        user_beats: List[float],
        ref_beats: List[float],
        valid_pairs: List[Tuple[int, int]],
    ) -> Dict[str, Any]:
        """Classify and categorize beat errors in detail.
        
        Categorizes each valid beat pair as:
        - On-time: within ±threshold_ms
        - Early: before threshold_ms
        - Late: after threshold_ms
        
        Args:
            user_beats: User's detected beat timestamps.
            ref_beats: Reference beat timestamps.
            valid_pairs: Valid (user_idx, ref_idx) pairs from DTW.
            
        Returns:
            Dict with error classification breakdown and specific error details.
        """
        if not valid_pairs or len(valid_pairs) < 1:
            return {
                'on_time': 0,
                'early': 0,
                'late': 0,
                'early_ratio': 0.0,
                'late_ratio': 0.0,
                'early_beats': [],
                'late_beats': [],
            }

        early_count = 0
        late_count = 0
        early_beats = []
        late_beats = []

        for u, r in valid_pairs:
            # Bounds check
            if u >= len(user_beats) or r >= len(ref_beats):
                continue

            dev = user_beats[u] - ref_beats[r]

            if dev < -self.threshold_ms:
                early_count += 1
                early_beats.append(
                    {
                        'beat_index': int(u),
                        'deviation_ms': float(dev * 1000),
                    }
                )
            elif dev > self.threshold_ms:
                late_count += 1
                late_beats.append(
                    {
                        'beat_index': int(u),
                        'deviation_ms': float(dev * 1000),
                    }
                )

        on_time = len(valid_pairs) - early_count - late_count
        total_pairs = len(valid_pairs)

        return {
            'on_time': int(on_time),
            'early': int(early_count),
            'late': int(late_count),
            'early_ratio': float(early_count / total_pairs) if total_pairs > 0 else 0.0,
            'late_ratio': float(late_count / total_pairs) if total_pairs > 0 else 0.0,
            'early_beats': early_beats,
            'late_beats': late_beats,
        }

    def compare_rhythm(
        self,
        user_beats: List[float],
        ref_beats: List[float],
        user_strengths: Optional[List[float]] = None,
        ref_strengths: Optional[List[float]] = None,
        scoring_model: str = 'balanced',
        language: str = 'en',
    ) -> Dict[str, Any]:
        """Comprehensive rhythm comparison with advanced analysis.
        
        Performs full rhythm evaluation including DTW alignment, error classification,
        consistency analysis, and multi-dimensional scoring.
        
        Args:
            user_beats: User's beat timestamps (seconds).
            ref_beats: Reference beat timestamps (seconds).
            user_strengths: Optional beat strengths (unused, for API consistency).
            ref_strengths: Optional beat strengths (unused, for API consistency).
            scoring_model: 'strict', 'balanced' (default), or 'lenient'.
            language: Language for feedback messages ('en', 'zh'). Default 'en'.
            
        Returns:
            Comprehensive analysis dict with score, deviations, consistency, feedback.
            
        Examples:
            ```python
            # Basic rhythm comparison
            analyzer = AdvancedRhythmAnalyzer()
            user_beats = [0.5, 1.02, 1.48, 2.0, 2.52]  # Slightly off timing
            ref_beats = [0.5, 1.0, 1.5, 2.0, 2.5]      # Perfect timing
            result = analyzer.compare_rhythm(user_beats, ref_beats)
            print(f"Score: {result['score']}/100")
            print(f"Feedback: {result['feedback']['main_issues']}")
            
            # Multilingual feedback (English vs Chinese)
            result_en = analyzer.compare_rhythm(user_beats, ref_beats, language='en')
            result_zh = analyzer.compare_rhythm(user_beats, ref_beats, language='zh')
            
            # English: "Missing 1 beat(s) - focus on beat awareness and tracking"
            print(result_en['feedback']['main_issues'][0])
            
            # Chinese: "缺少1个节拍 - 提高节拍意识和追踪能力"
            print(result_zh['feedback']['main_issues'][0])
            
            # Using formatter for additional language support
            from backend.core.rhythm.i18n import FeedbackFormatter
            formatter = FeedbackFormatter('zh')
            assessment = formatter.format_result(result_en)
            print(assessment['overall_assessment'])  # "优秀 - 专业级表现"
            ```
            
            # Strict scoring for professional evaluation
            result = analyzer.compare_rhythm(
                user_beats, ref_beats, scoring_model='strict'
            )
            
            # Lenient scoring for practice/learning
            result = analyzer.compare_rhythm(
                user_beats, ref_beats, scoring_model='lenient'
            )
            ```
            
        Raises:
            Returns error dict if input is invalid.
        """
        # Input validation
        if not user_beats or not ref_beats:
            return {'score': 0.0, 'error': 'Missing audio data'}

        user_beats = np.array(user_beats, dtype=float)
        ref_beats = np.array(ref_beats, dtype=float)

        if len(user_beats) < 1 or len(ref_beats) < 1:
            return {'score': 0.0, 'error': 'Invalid beat sequences'}

        # Check for NaN or Inf values
        if np.any(~np.isfinite(user_beats)) or np.any(~np.isfinite(ref_beats)):
            return {'score': 0.0, 'error': 'Beat sequence contains invalid values (NaN/Inf)'}

        # Perform DTW alignment
        try:
            distance, path = _compute_dtw_alignment(user_beats, ref_beats)
        except Exception as e:
            return {'score': 0.0, 'error': f'DTW alignment failed: {str(e)}'}

        # Analyze alignment errors
        missing, extra, valid_pairs = self.analyze_errors(path)

        # Calculate timing deviations for valid pairs
        valid_deviations = np.array(
            [
                abs(user_beats[u] - ref_beats[r])
                for u, r in valid_pairs
                if u < len(user_beats) and r < len(ref_beats)
            ],
            dtype=float,
        )

        # Compute statistics with smart handling of edge cases
        if len(valid_deviations) == 0:
            # No valid pairs found → use moderate defaults
            mean_deviation = 0.3
            max_deviation = 0.3
            std_deviation = 0.0
        else:
            mean_deviation = float(np.mean(valid_deviations))
            max_deviation = float(np.max(valid_deviations))
            std_deviation = float(np.std(valid_deviations))

        # Compute auxiliary metrics
        user_consistency = self.compute_interval_consistency(user_beats.tolist())
        ref_consistency = self.compute_interval_consistency(ref_beats.tolist())
        tempo_analysis = self.detect_tempo_changes(user_beats.tolist(), ref_beats.tolist())
        error_classification = self.classify_beat_errors(
            user_beats.tolist(), ref_beats.tolist(), valid_pairs
        )

        # Calculate scores
        base_score, timing_accuracy = self._calculate_score(
            mean_deviation, valid_deviations, missing, extra, scoring_model
        )
        feedback = self._generate_feedback(
            base_score, mean_deviation, missing, extra, error_classification, language
        )

        return {
            'score': round(base_score, 2),
            'timing_accuracy': round(timing_accuracy, 2),
            'mean_deviation_ms': round(mean_deviation * 1000, 2),
            'max_deviation_ms': round(max_deviation * 1000, 2),
            'std_deviation_ms': round(std_deviation * 1000, 2),
            'missing_beats': int(missing),
            'extra_beats': int(extra),
            'valid_matches': len(valid_pairs),
            'total_ref_beats': len(ref_beats),
            'coverage_ratio': float(len(valid_pairs) / len(ref_beats))
            if ref_beats.size > 0
            else 0.0,
            'user_consistency': user_consistency,
            'ref_consistency': ref_consistency,
            'consistency_ratio': round(
                user_consistency['consistency_score']
                / (ref_consistency['consistency_score'] + 1e-8),
                2,
            ),
            'tempo_analysis': tempo_analysis,
            'error_classification': error_classification,
            'feedback': feedback,
            'detailed_assessment': self._generate_detailed_assessment(
                base_score, user_consistency, tempo_analysis, error_classification
            ),
        }

    def _calculate_score(
        self,
        mean_dev: float,
        deviations: np.ndarray,
        missing: int,
        extra: int,
        model: str,
    ) -> Tuple[float, float]:
        """Calculate score based on selected model.
        
        Three scoring strategies:
        - strict: Penalizes deviations and errors heavily (0.8 factor, 15× penalty)
        - balanced: Moderate penalties (0.6 factor, 10× penalty) [default]
        - lenient: Forgiving of small deviations (0.4 factor, 5× penalty)
        
        Args:
            mean_dev: Mean timing deviation (seconds).
            deviations: Array of all timing deviations.
            missing: Count of missing beats.
            extra: Count of extra beats.
            model: 'strict', 'balanced', or 'lenient'.
            
        Returns:
            Tuple of (final_score, timing_accuracy) both 0-100.
        """
        if model == 'strict':
            tolerance_window = 0.20
            error_penalty_factor = 15
        elif model == 'lenient':
            tolerance_window = 0.50
            error_penalty_factor = 5
        else:  # balanced (default)
            tolerance_window = 0.35
            error_penalty_factor = 10

        # Base deviation score
        base_score = max(0, 100 * (1 - mean_dev / tolerance_window))
        
        # Error penalty
        error_penalty = (missing + extra) * error_penalty_factor
        
        # Final score
        final_score = max(0, base_score - error_penalty)

        # Timing accuracy (independent metric)
        timing_accuracy = max(0, 100 * (1 - mean_dev / 0.5))

        return float(final_score), float(timing_accuracy)

    def _generate_detailed_assessment(
        self,
        score: float,
        consistency: Dict,
        tempo_analysis: Dict,
        error_classification: Dict,
    ) -> Dict[str, str]:
        """Generate detailed performance assessment.
        
        Creates natural language qualitative descriptions of performance
        across multiple dimensions.
        
        Args:
            score: Numeric score (0-100).
            consistency: Consistency metrics dict.
            tempo_analysis: Tempo change analysis dict.
            error_classification: Beat error classification dict.
            
        Returns:
            Dict with keys: overall, consistency, tempo, timing.
        """
        assessment = {}

        # Overall score assessment
        if score >= 85:
            assessment['overall'] = 'Excellent - Professional level performance'
        elif score >= 70:
            assessment['overall'] = 'Good - Strong performance with minor issues'
        elif score >= 50:
            assessment['overall'] = 'Fair - Moderate issues that need attention'
        else:
            assessment['overall'] = 'Needs Improvement - Significant rhythm problems'

        # Consistency assessment
        cons_score = consistency['consistency_score']
        if cons_score >= 0.85:
            assessment['consistency'] = 'Very stable beat timing'
        elif cons_score >= 0.70:
            assessment['consistency'] = 'Generally stable with some variation'
        else:
            assessment['consistency'] = 'Inconsistent timing - focus on regularity'

        # Tempo assessment
        if not tempo_analysis['has_tempo_change']:
            assessment['tempo'] = 'Maintained steady tempo'
        else:
            direction = tempo_analysis['drift_detected']
            assessment['tempo'] = f'Detected {direction} tempo during performance'

        # Timing tendency assessment
        on_time = error_classification['on_time']
        early = error_classification['early']
        late = error_classification['late']
        total = on_time + early + late

        if total == 0:
            assessment['timing'] = 'Unable to assess timing'
        elif on_time == total:
            assessment['timing'] = 'All beats well-timed'
        elif early > late * 1.5:  # Significantly more early
            assessment['timing'] = 'Tendency to play ahead of the beat'
        elif late > early * 1.5:  # Significantly more late
            assessment['timing'] = 'Tendency to play behind the beat'
        else:
            assessment['timing'] = 'Balanced timing distribution'

        return assessment

    def _generate_feedback(
        self,
        score: float,
        mean_dev: float,
        missing: int,
        extra: int,
        error_classification: Dict,
        language: str = 'en',
    ) -> Dict[str, Any]:
        """Generate actionable feedback in specified language.
        
        Creates user-facing feedback identifying the main issues
        and suggesting concrete improvements. Supports multiple languages.
        
        Args:
            score: Numeric score (0-100).
            mean_dev: Mean timing deviation (seconds).
            missing: Count of missing beats.
            extra: Count of extra beats.
            error_classification: Beat error classification dict.
            language: Language code ('en' for English, 'zh' for Chinese). Default 'en'.
            
        Returns:
            Dict with accuracy_level and main_issues list (in specified language).
            
        Example:
            ```python
            analyzer = AdvancedRhythmAnalyzer()
            result = analyzer.compare_rhythm(user_beats, ref_beats, language='zh')
            # Feedback is in Chinese:
            # "缺少1个节拍 - 提高节拍意识和追踪能力"
            ```
        """
        formatter = FeedbackFormatter(language)
        feedback = {}

        # Accuracy assessment based on mean deviation (using formatter)
        accuracy_level = formatter.format_accuracy_level(mean_dev)
        feedback['accuracy_level'] = accuracy_level
        feedback['main_issues'] = []

        # Identify and prioritize issues (using formatter for multilingual support)
        early = error_classification['early']
        late = error_classification['late']
        
        issues = formatter.format_main_issues(missing, extra, early, late)
        feedback['main_issues'] = issues
        feedback['language'] = language

        return feedback

    def score_rhythm(
        self, user_beats: List[float], ref_beats: List[float], **kwargs
    ) -> Dict[str, Any]:
        """Alias for compare_rhythm for backward compatibility.
        
        Wrapper that provides old API naming while supporting new parameters
        including language support for internationalization.
        
        Args:
            user_beats: User's beat timestamps (seconds).
            ref_beats: Reference beat timestamps (seconds).
            **kwargs: Additional arguments passed to compare_rhythm
                     (language='en'/'zh', scoring_model, etc).
                     
        Returns:
            Comprehensive analysis result with language-specific feedback.
            
        Example:
            ```python
            analyzer = AdvancedRhythmAnalyzer()
            user_beats = [0.5, 1.02, 1.48, 2.0, 2.52]
            ref_beats = [0.5, 1.0, 1.5, 2.0, 2.5]
            
            # English feedback (default)
            result_en = analyzer.score_rhythm(user_beats, ref_beats)
            
            # Chinese feedback
            result_zh = analyzer.score_rhythm(user_beats, ref_beats, language='zh')
            ```
        """
        return self.compare_rhythm(user_beats, ref_beats, **kwargs)


class RhythmAnalyzer(AdvancedRhythmAnalyzer):
    """Backward-compatible wrapper for legacy RhythmAnalyzer interface.
    
    Maintains API compatibility with older code while delegating to
    the more advanced AdvancedRhythmAnalyzer implementation.
    """

    def __init__(self, threshold_ms: float = 50):
        """Initialize with threshold in milliseconds.
        
        Args:
            threshold_ms: Time window (ms) for on-time classification.
        """
        super().__init__(threshold_ms=threshold_ms)

    def get_rhythm_feedback(self, deviation_ms: float) -> str:
        """Legacy feedback method for backward compatibility.
        
        Simple categorical feedback based on timing deviation.
        This method exists for API compatibility with older versions.
        
        Args:
            deviation_ms: Timing deviation in milliseconds.
            
        Returns:
            Categorical feedback: Perfect, Great, Good, or Needs Improvement.
        """
        if deviation_ms < 30:
            return 'Perfect'
        if deviation_ms < 70:
            return 'Great'
        if deviation_ms < 120:
            return 'Good'
        return 'Needs Improvement'


def score_rhythm(
    user_beats: List[float], ref_beats: List[float], **kwargs
) -> Dict[str, Any]:
    """Wrapper function for backward compatibility.
    
    Convenience function that creates an analyzer and performs comparison.
    Useful for single-shot analysis without reusing the analyzer.
    
    Args:
        user_beats: User's beat timestamps (seconds).
        ref_beats: Reference beat timestamps (seconds).
        **kwargs: Additional arguments passed to compare_rhythm().
        
    Returns:
        Full analysis results from compare_rhythm().
    
    Examples:
        ```python
        # Quick evaluation without creating analyzer
        user_beats = [0.5, 1.02, 1.5, 2.0, 2.52, 3.0]
        ref_beats = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        result = score_rhythm(user_beats, ref_beats)
        print(f"Score: {result['score']}/100")
        print(f"Feedback: {result['feedback']['main_issues']}")
        ```
    """
    threshold_ms = float(kwargs.pop("threshold_ms", 50.0))
    analyzer = AdvancedRhythmAnalyzer(threshold_ms=threshold_ms)
    return analyzer.compare_rhythm(user_beats, ref_beats, **kwargs)
