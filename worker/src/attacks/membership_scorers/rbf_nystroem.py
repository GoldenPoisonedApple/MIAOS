"""RBF カーネルの Nystroem 近似の特徴写像（svm の rbf カーネル用）。"""

import numpy as np
from scipy.linalg import eigh
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics.pairwise import rbf_kernel
from sklearn.utils import check_random_state

# 基底カーネル行列の固有値の下限（sklearn の Nystroem と同じ。0 除算を防ぐ）
EIGENVALUE_FLOOR: float = 1e-12


class RbfNystroem(TransformerMixin, BaseEstimator):
	"""
	sklearn の Nystroem(kernel="rbf") と同じ特徴写像 φ(x) = k(x, basis) · K_basis^{-1/2}。
	K_basis^{-1/2} は汎用 SVD（gesdd）ではなく対称行列の固有値分解で求める。
	gamma が大きく K_basis が単位行列に近い（特異値が縮退する）と gesdd は収束しないことがあるため。
	精度不足による同様の失敗を避けるため、入力は float64 で計算する。
	"""

	def __init__(self, gamma: float, n_components: int, random_state: int | None = None) -> None:
		self.gamma = gamma
		self.n_components = n_components
		self.random_state = random_state

	def fit(self, x: np.ndarray, y: np.ndarray | None = None) -> "RbfNystroem":
		"""x: (N, D)。N 行から n_components 行（N を超える場合は N 行）を基底として無作為に選ぶ"""
		x = np.asarray(x, dtype=np.float64)
		rng = check_random_state(self.random_state)
		basis_idx = rng.permutation(x.shape[0])[: min(self.n_components, x.shape[0])]
		self.components_ = x[basis_idx]
		# K_basis は対称半正定値。負の固有値は丸め誤差なので下限で切る
		eigenvalues, eigenvectors = eigh(rbf_kernel(self.components_, gamma=self.gamma))
		eigenvalues = np.maximum(eigenvalues, EIGENVALUE_FLOOR)
		self.normalization_ = (eigenvectors / np.sqrt(eigenvalues)) @ eigenvectors.T
		return self

	def transform(self, x: np.ndarray) -> np.ndarray:
		"""x: (N, D) → (N, n_basis)"""
		kernel = rbf_kernel(np.asarray(x, dtype=np.float64), self.components_, gamma=self.gamma)
		return kernel @ self.normalization_.T
