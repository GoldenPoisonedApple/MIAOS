from __future__ import annotations

import numpy as np
from sklearn.model_selection import train_test_split


def decoration_random_state(experiment_seed: int, seed_offset: int) -> int:
    return experiment_seed + seed_offset


def select_indices_by_fraction(
    pool_indices: np.ndarray,
    fraction: float,
    random_state: int,
) -> set[int]:
    # validation
    if fraction <= 0.0 or len(pool_indices) == 0:
        return set()
    if fraction >= 1.0:
        return set(int(idx) for idx in pool_indices)

    # train_size: floatを渡すと割合分割となる
    selected, _ = train_test_split(
        pool_indices,
        train_size=fraction,
        random_state=random_state,
    )
    # numpy arrayをset[int]に変換
    return set(int(idx) for idx in selected)
