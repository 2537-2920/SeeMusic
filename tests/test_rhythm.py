"""
Test cases for the advanced rhythm analyzer
"""

import numpy as np
from backend.core.rhythm.rhythm_analysis import (
    AdvancedRhythmAnalyzer,
    RhythmAnalyzer,
    score_rhythm,
)

def test_backward_compatibility():
    """Test that old code still works"""
    analyzer = RhythmAnalyzer(threshold_ms=50)
    
    user_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    
    result = analyzer.compare_rhythm(user_beats, ref_beats)
    assert 'score' in result
    assert 'timing_accuracy' in result
    assert result['missing_beats'] == 0
    assert result['extra_beats'] == 0
    print("✓ Backward compatibility test passed")


def test_perfect_timing():
    """Test perfect alignment"""
    analyzer = AdvancedRhythmAnalyzer()
    
    beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    
    result = analyzer.compare_rhythm(beats, beats)
    assert result['score'] == 100.0
    assert result['missing_beats'] == 0
    assert result['extra_beats'] == 0
    assert result['mean_deviation_ms'] < 1
    print("✓ Perfect timing test passed")


def test_early_beats():
    """Test beats played early"""
    analyzer = AdvancedRhythmAnalyzer(threshold_ms=50)
    
    user_beats = [0.0, 0.45, 0.95, 1.45, 1.95]
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    
    result = analyzer.compare_rhythm(user_beats, ref_beats)
    errors = result['error_classification']
    assert errors['early'] > 0, "Should detect early beats"
    assert len(errors['early_beats']) > 0
    print("✓ Early beats detection test passed")


def test_late_beats():
    """Test beats played late"""
    analyzer = AdvancedRhythmAnalyzer(threshold_ms=50)
    
    user_beats = [0.0, 0.55, 1.05, 1.55, 2.05]
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    
    result = analyzer.compare_rhythm(user_beats, ref_beats)
    errors = result['error_classification']
    assert errors['late'] > 0, "Should detect late beats"
    assert len(errors['late_beats']) > 0
    print("✓ Late beats detection test passed")


def test_consistency_analysis():
    """Test beat consistency calculation"""
    analyzer = AdvancedRhythmAnalyzer()
    
    # Very consistent beats
    consistent_beats = np.linspace(0, 2, 5)
    result = analyzer.compare_rhythm(consistent_beats.tolist(), consistent_beats.tolist())
    consistent_score = result['user_consistency']['consistency_score']
    
    # Inconsistent beats
    inconsistent_beats = [0.0, 0.4, 1.1, 1.5, 2.3]
    result = analyzer.compare_rhythm(inconsistent_beats, [0, 0.5, 1.0, 1.5, 2.0])
    inconsistent_score = result['user_consistency']['consistency_score']
    
    assert consistent_score > inconsistent_score, "Consistent beats should have higher score"
    print("✓ Consistency analysis test passed")


def test_tempo_change_detection():
    """Test acceleration/deceleration detection"""
    analyzer = AdvancedRhythmAnalyzer()
    
    # Accelerating beats
    accelerating = [0.0, 0.5, 0.95, 1.38, 1.78, 2.15]
    ref_steady = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    
    result = analyzer.compare_rhythm(accelerating, ref_steady)
    assert result['tempo_analysis']['has_tempo_change'] == True
    print("✓ Tempo change detection test passed")


def test_missing_beats():
    """Test detection of missing beats"""
    analyzer = AdvancedRhythmAnalyzer()
    
    user_beats = [0.0, 0.5, 1.5, 2.0]  # Missing beat at 1.0
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    
    result = analyzer.compare_rhythm(user_beats, ref_beats)
    assert result['missing_beats'] > 0
    print("✓ Missing beats detection test passed")


def test_extra_beats():
    """Test detection of extra beats"""
    analyzer = AdvancedRhythmAnalyzer()
    
    user_beats = [0.0, 0.5, 1.0, 1.3, 1.5, 2.0]  # Extra beat at 1.3
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    
    result = analyzer.compare_rhythm(user_beats, ref_beats)
    assert result['extra_beats'] > 0
    print("✓ Extra beats detection test passed")


def test_scoring_models():
    """Test different scoring models"""
    analyzer = AdvancedRhythmAnalyzer()
    
    user_beats = [0.0, 0.48, 1.02, 1.5, 2.05, 2.48]
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    
    strict = analyzer.compare_rhythm(user_beats, ref_beats, scoring_model='strict')
    balanced = analyzer.compare_rhythm(user_beats, ref_beats, scoring_model='balanced')
    lenient = analyzer.compare_rhythm(user_beats, ref_beats, scoring_model='lenient')
    
    # Strict should penalize more than balanced than lenient
    assert strict['score'] <= balanced['score']
    assert balanced['score'] <= lenient['score']
    print("✓ Scoring models test passed")


def test_function_compatibility():
    """Test score_rhythm function"""
    user_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    
    result = score_rhythm(user_beats, ref_beats)
    assert 'score' in result
    assert result['score'] == 100.0
    print("✓ Function compatibility test passed")


def test_threshold_customization():
    """Test custom threshold setting"""
    user_beats = [0.0, 0.48, 1.0, 1.5, 2.0]
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    
    # With 40ms threshold (stricter)
    strict = AdvancedRhythmAnalyzer(threshold_ms=40)
    result_strict = strict.compare_rhythm(user_beats, ref_beats)
    
    # With 100ms threshold (lenient)
    lenient = AdvancedRhythmAnalyzer(threshold_ms=100)
    result_lenient = lenient.compare_rhythm(user_beats, ref_beats)
    
    # Strict should have more early beats detected
    assert result_strict['error_classification']['early'] >= result_lenient['error_classification']['early']
    print("✓ Threshold customization test passed")


def test_score_rhythm_function_honors_threshold_kwarg():
    """Test score_rhythm forwards threshold_ms into analyzer construction."""
    user_beats = [0.0, 0.45, 0.95, 1.45, 1.95]
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0]

    strict_result = score_rhythm(user_beats, ref_beats, threshold_ms=40)
    lenient_result = score_rhythm(user_beats, ref_beats, threshold_ms=100)

    assert strict_result['error_classification']['early'] > lenient_result['error_classification']['early']
    print("✓ score_rhythm threshold kwarg test passed")


def test_empty_input_handling():
    """Test handling of empty or invalid input"""
    analyzer = AdvancedRhythmAnalyzer()
    
    # Empty input
    result = analyzer.compare_rhythm([], [])
    assert 'error' in result
    
    # One empty
    result = analyzer.compare_rhythm([0, 1, 2], [])
    assert 'error' in result
    
    print("✓ Empty input handling test passed")


def test_detailed_assessment():
    """Test detailed assessment generation"""
    analyzer = AdvancedRhythmAnalyzer()
    
    user_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0]
    
    result = analyzer.compare_rhythm(user_beats, ref_beats)
    assessment = result['detailed_assessment']
    
    assert 'overall' in assessment
    assert 'consistency' in assessment
    assert 'tempo' in assessment
    assert 'timing' in assessment
    
    print("✓ Detailed assessment test passed")


def test_feedback_generation():
    """Test feedback generation"""
    analyzer = AdvancedRhythmAnalyzer()
    
    user_beats = [0.0, 0.48, 1.02, 1.5, 2.05, 2.48]
    ref_beats = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    
    result = analyzer.compare_rhythm(user_beats, ref_beats)
    feedback = result['feedback']
    
    assert 'accuracy_level' in feedback
    assert 'main_issues' in feedback
    assert isinstance(feedback['main_issues'], list)
    
    print("✓ Feedback generation test passed")


if __name__ == '__main__':
    print("Running Advanced Rhythm Analyzer Tests...\n")
    
    test_backward_compatibility()
    test_perfect_timing()
    test_early_beats()
    test_late_beats()
    test_consistency_analysis()
    test_tempo_change_detection()
    test_missing_beats()
    test_extra_beats()
    test_scoring_models()
    test_function_compatibility()
    test_threshold_customization()
    test_empty_input_handling()
    test_detailed_assessment()
    test_feedback_generation()
    
    print("\n✅ All tests passed!")
