"""Deterministic full sequence comparison. No timing, result or AI weighting."""
from copy import deepcopy


def normalized(event):
    return {key: deepcopy(event.get(key)) for key in
            ('action', 'button_id', 'target_id', 'parameters')}


def compare(standard, actual):
    expected, received = list(map(normalized, standard)), list(map(normalized, actual))
    first = next((index for index in range(max(len(expected), len(received)))
                  if (expected[index] if index < len(expected) else None) !=
                     (received[index] if index < len(received) else None)), None)
    return {'status': 'correct' if first is None else 'error',
            'score': 100 if first is None else None,
            'standard_count': len(expected), 'actual_count': len(received),
            'first_difference': None if first is None else {
                'sequence': first + 1,
                'expected': expected[first] if first < len(expected) else None,
                'actual': received[first] if first < len(received) else None},
            'comparison_version': 1}
