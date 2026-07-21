"""Predictable nonlinear certificates maintained from O(d) path state.

The state contains one running parameter mean and scalar accumulators.  Exact
teacher parameters, future rewards, and post-hoc dense diagnostics are not part
of this interface.  A round is opened by :meth:`pre_action_schedule` and closed
only after the reward by :meth:`update_after_reward`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatArray = NDArray[np.float64]
_EPS = np.finfo(np.float64).eps
OPERATOR_MODES = (
    "exact_full",
    "unrescaled_current_subset",
    "certified_approximate",
)


def _integer(value: int, *, name: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer")
    checked = int(value)
    if checked < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return checked


def _finite(value: float, *, name: str, minimum: float | None = None) -> float:
    checked = float(value)
    if not np.isfinite(checked):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and checked < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return checked


def _positive(value: float, *, name: str) -> float:
    checked = _finite(value, name=name)
    if checked <= 0.0:
        raise ValueError(f"{name} must be positive")
    return checked


def _probability(value: float, *, name: str) -> float:
    checked = _finite(value, name=name)
    if not 0.0 < checked < 1.0:
        raise ValueError(f"{name} must lie in (0, 1)")
    return checked


def _failure_probability(value: float, *, name: str) -> float:
    checked = _finite(value, name=name, minimum=0.0)
    if checked >= 1.0:
        raise ValueError(f"{name} must be smaller than one")
    return checked


def _text(value: str, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value.strip()


def _vector(value: ArrayLike, dimension: int, *, name: str) -> FloatArray:
    checked = np.asarray(value, dtype=np.float64)
    if checked.shape != (dimension,):
        raise ValueError(f"{name} must have shape ({dimension},)")
    if not np.all(np.isfinite(checked)):
        raise ValueError(f"{name} must contain only finite values")
    return checked


def _readonly(value: ArrayLike) -> FloatArray:
    result = np.asarray(value, dtype=np.float64).copy()
    result.setflags(write=False)
    return result


def _roundoff_nonnegative(value: float, *, scale: float, name: str) -> float:
    """Clamp only a negative value consistent with float64 roundoff."""

    checked = _finite(value, name=name)
    tolerance = 256.0 * _EPS * max(1.0, abs(float(scale)))
    if checked < -tolerance:
        raise FloatingPointError(
            f"{name} is materially negative ({checked:.17g}; tolerance {tolerance:.3g})"
        )
    return max(0.0, checked)


@dataclass(frozen=True)
class CenteringCertificate:
    """Components of the observable upper bound on ``||M_t||_2``."""

    q_t: float
    residual_path_term: float
    squared_path_term: float
    cubic_path_bound: float
    cubic_bound_mode: str
    m_bar_t: float


@dataclass(frozen=True)
class PathCertificateSnapshot:
    """All policy-available certificate components at one pre-action time."""

    round_number: int
    history_count: int
    q_t: float
    residual_sq_sum_prior: float
    f_bar_prior: float
    e_bar_prior: float
    gamma_hat_prior: float
    chi_bar_t: float
    m_bar_t: float
    psi_bar_t: float
    epsilon_lin_bar_t: float
    beta_bar_t: float
    transfer_factor: float
    kappa_plus_t: float
    optimizer_residual_zeta_t: float
    residual_path_term: float
    squared_path_term: float
    cubic_path_bound: float
    cubic_bound_mode: str
    cg_error_bound: float
    cg_inflation_alpha_t: float
    omega_original_t: float
    omega_corrected_t: float
    L_g: float
    L_mu: float
    G: float
    sigma: float
    lambda_: float
    S: float
    delta: float
    trust_region_radius: float | None
    operator_mode: str
    kappa_plus_source: str
    optimizer_residual_source: str
    cg_certificate_source: str
    smoothness_source: str
    certificate_failure_probability: float
    certificate_probability_type: str

    def as_metrics(self, *, prefix: str = "policy_certificate_") -> dict[str, Any]:
        """Return JSON-compatible per-round fields with an explicit policy tag."""

        return {f"{prefix}{key}": value for key, value in asdict(self).items()}


@dataclass(frozen=True)
class ActionCertificateCommitment:
    """Pre-reward commitment to the selected action's computed CG width."""

    round_number: int
    action: int
    action_count: int
    played_cg_width_squared: float
    all_action_widths_sha256: str
    observable_information_increment: float

    def as_metrics(self, *, prefix: str = "policy_certificate_") -> dict[str, Any]:
        return {f"{prefix}{key}": value for key, value in asdict(self).items()}


@dataclass(frozen=True)
class PathCertificateUpdate:
    """Post-reward state values committed for the next round."""

    round_number: int
    history_count_after_update: int
    collection_residual: float
    residual_sq_sum_after_update: float
    f_bar_after_update: float
    e_bar_after_update: float
    gamma_hat_after_update: float
    observable_information_increment: float
    theta_scatter_after_update: float

    def as_metrics(self, *, prefix: str = "policy_certificate_") -> dict[str, Any]:
        return {f"{prefix}{key}": value for key, value in asdict(self).items()}


class PathCertificateState:
    """O(d)-state predictable certificates for a nonlinear CC-UCB policy.

    The Welford state represents ``theta_1, ..., theta_{t-1}`` before round
    ``t``.  Its scalar scatter is

    ``sum_{s<t} ||theta_s - mean_{s<t}||_2^2``.

    Therefore ``compute_Q(theta_t)`` evaluates exactly

    ``scatter + (t-1) ||theta_t-mean||_2^2
      = sum_{s<t} ||theta_t-theta_s||_2^2``.
    """

    def __init__(self, dimension: int) -> None:
        self._dimension = _integer(dimension, name="dimension", minimum=1)
        self._count = 0
        self._mean_theta = _readonly(np.zeros(self._dimension, dtype=np.float64))
        self._theta_scatter = 0.0
        self._residual_sq_sum = 0.0
        self._f_bar = 0.0
        self._e_bar = 0.0
        self._gamma_hat = 0.0
        self._max_theta_norm = 0.0
        self._pending_snapshot: PathCertificateSnapshot | None = None
        self._pending_theta: FloatArray | None = None
        self._pending_action: ActionCertificateCommitment | None = None
        self._fixed_constants: tuple[float | None, ...] | None = None

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def count(self) -> int:
        return self._count

    @property
    def mean_theta(self) -> FloatArray:
        return self._mean_theta

    @property
    def theta_scatter(self) -> float:
        return self._theta_scatter

    @property
    def residual_sq_sum(self) -> float:
        return self._residual_sq_sum

    @property
    def F_bar(self) -> float:
        return self._f_bar

    @property
    def E_bar(self) -> float:
        return self._e_bar

    @property
    def gamma_hat(self) -> float:
        return self._gamma_hat

    @property
    def has_pending_round(self) -> bool:
        return self._pending_snapshot is not None

    @property
    def has_action_commitment(self) -> bool:
        return self._pending_action is not None

    def compute_Q(self, theta_t: ArrayLike) -> float:
        current = _vector(theta_t, self._dimension, name="theta_t")
        displacement = current - self._mean_theta
        between = float(self._count) * float(displacement @ displacement)
        raw = self._theta_scatter + between
        return _roundoff_nonnegative(
            raw,
            scale=abs(self._theta_scatter) + abs(between),
            name="Q_t",
        )

    def compute_chi_bar(
        self,
        theta_t: ArrayLike,
        L_g: float,
        sigma: float,
        lambda_: float,
    ) -> float:
        lipschitz = _finite(L_g, name="L_g", minimum=0.0)
        noise = _positive(sigma, name="sigma")
        damping = _positive(lambda_, name="lambda_")
        return float(
            lipschitz
            * math.sqrt(self.compute_Q(theta_t))
            / (noise * math.sqrt(damping))
        )

    def _centering_certificate(
        self,
        theta_t: ArrayLike,
        L_g: float,
        G: float,
        sigma: float,
        *,
        trust_region_radius: float | None = None,
    ) -> CenteringCertificate:
        lipschitz = _finite(L_g, name="L_g", minimum=0.0)
        gradient_bound = _finite(G, name="G", minimum=0.0)
        noise = _positive(sigma, name="sigma")
        current = _vector(theta_t, self._dimension, name="theta_t")
        q_t = self.compute_Q(current)

        if trust_region_radius is None:
            cubic_path_bound = q_t ** 1.5
            cubic_bound_mode = "holder_Q_to_three_halves"
        else:
            radius = _finite(
                trust_region_radius, name="trust_region_radius", minimum=0.0
            )
            tolerance = 256.0 * _EPS * max(1.0, radius)
            if self._max_theta_norm > radius + tolerance:
                raise ValueError("a stored parameter lies outside the trust region")
            if float(np.linalg.norm(current)) > radius + tolerance:
                raise ValueError("theta_t lies outside the trust region")
            cubic_path_bound = 2.0 * radius * q_t
            cubic_bound_mode = "trust_region_2R_Q"

        residual_path_term = math.sqrt(self._residual_sq_sum * q_t)
        squared_path_term = q_t
        # ||M_t|| <= sigma^-2 [
        #   L_g sqrt(R_t Q_t) + (3 G L_g / 2) Q_t
        #   + (L_g^2 / 2) sum_{s<t} ||theta_t-theta_s||^3 ].
        # The final sum is bounded by Q_t^(3/2), or by 2 R Q_t when all
        # iterates lie in the radius-R trust region.
        m_bar_t = (
            lipschitz * residual_path_term
            + 1.5 * gradient_bound * lipschitz * squared_path_term
            + 0.5 * lipschitz * lipschitz * cubic_path_bound
        ) / (noise * noise)
        return CenteringCertificate(
            q_t=q_t,
            residual_path_term=_finite(
                residual_path_term, name="residual_path_term", minimum=0.0
            ),
            squared_path_term=_finite(
                squared_path_term, name="squared_path_term", minimum=0.0
            ),
            cubic_path_bound=_finite(
                cubic_path_bound, name="cubic_path_bound", minimum=0.0
            ),
            cubic_bound_mode=cubic_bound_mode,
            m_bar_t=_finite(m_bar_t, name="M_bar_t", minimum=0.0),
        )

    def compute_M_bar(
        self,
        theta_t: ArrayLike,
        L_g: float,
        G: float,
        sigma: float,
        *,
        trust_region_radius: float | None = None,
    ) -> float:
        return self._centering_certificate(
            theta_t,
            L_g,
            G,
            sigma,
            trust_region_radius=trust_region_radius,
        ).m_bar_t

    def compute_psi_bar(
        self,
        theta_t: ArrayLike,
        zeta_t: float,
        L_g: float,
        G: float,
        sigma: float,
        lambda_: float,
        *,
        trust_region_radius: float | None = None,
    ) -> float:
        optimizer_residual = _finite(zeta_t, name="zeta_t", minimum=0.0)
        damping = _positive(lambda_, name="lambda_")
        m_bar = self.compute_M_bar(
            theta_t,
            L_g,
            G,
            sigma,
            trust_region_radius=trust_region_radius,
        )
        return float((optimizer_residual + m_bar) / math.sqrt(damping))

    def compute_epsilon_lin_bar(
        self,
        theta_t: ArrayLike,
        L_mu: float,
        S: float,
    ) -> float:
        current = _vector(theta_t, self._dimension, name="theta_t")
        lipschitz = _finite(L_mu, name="L_mu", minimum=0.0)
        radius = _finite(S, name="S", minimum=0.0)
        return float(0.5 * lipschitz * (radius + np.linalg.norm(current)) ** 2)

    def compute_beta_bar(
        self,
        *,
        delta: float,
        lambda_: float,
        S: float,
        sigma: float,
    ) -> float:
        failure_probability = _probability(delta, name="delta")
        damping = _positive(lambda_, name="lambda_")
        radius = _finite(S, name="S", minimum=0.0)
        noise = _positive(sigma, name="sigma")
        return float(
            math.sqrt(self._gamma_hat + 2.0 * math.log(1.0 / failure_probability))
            + math.sqrt(damping) * radius
            + math.sqrt(self._f_bar) / noise
        )

    def compute_transfer_factor(
        self,
        theta_t: ArrayLike,
        L_g: float,
        sigma: float,
        lambda_: float,
        *,
        kappa_plus_t: float = 1.0,
    ) -> float:
        kappa = _finite(kappa_plus_t, name="kappa_plus_t", minimum=1.0)
        chi_bar = self.compute_chi_bar(theta_t, L_g, sigma, lambda_)
        return float(kappa * (1.0 + chi_bar) ** 2)

    def _bind_fixed_constants(
        self,
        *,
        L_g: float,
        L_mu: float,
        G: float,
        sigma: float,
        lambda_: float,
        S: float,
        delta: float,
        trust_region_radius: float | None,
    ) -> tuple[float, float, float, float, float, float, float, float | None]:
        constants = (
            _finite(L_g, name="L_g", minimum=0.0),
            _finite(L_mu, name="L_mu", minimum=0.0),
            _finite(G, name="G", minimum=0.0),
            _positive(sigma, name="sigma"),
            _positive(lambda_, name="lambda_"),
            _finite(S, name="S", minimum=0.0),
            _probability(delta, name="delta"),
            (
                None
                if trust_region_radius is None
                else _finite(
                    trust_region_radius,
                    name="trust_region_radius",
                    minimum=0.0,
                )
            ),
        )
        if self._fixed_constants is None:
            self._fixed_constants = constants
        elif constants != self._fixed_constants:
            raise ValueError(
                "the fixed theorem constants changed after the certificate state "
                "was initialized"
            )
        return constants

    def pre_action_schedule(
        self,
        theta_t: ArrayLike,
        *,
        L_g: float,
        L_mu: float,
        G: float,
        sigma: float,
        lambda_: float,
        S: float,
        delta: float,
        zeta_t: float,
        operator_mode: str,
        optimizer_residual_source: str,
        cg_certificate_source: str,
        smoothness_source: str,
        kappa_plus_t: float | None = None,
        kappa_plus_source: str | None = None,
        cg_error_bound: float = 0.0,
        trust_region_radius: float | None = None,
        certificate_failure_probability: float = 0.0,
    ) -> PathCertificateSnapshot:
        """Open round ``count+1`` and return its policy-available schedule."""

        if self._pending_snapshot is not None:
            raise RuntimeError("the previous pre-action round has not been updated")
        current = _vector(theta_t, self._dimension, name="theta_t")
        if operator_mode not in OPERATOR_MODES:
            raise ValueError(f"operator_mode must be one of {OPERATOR_MODES}")
        if operator_mode in {"exact_full", "unrescaled_current_subset"}:
            kappa = 1.0 if kappa_plus_t is None else _finite(
                kappa_plus_t, name="kappa_plus_t", minimum=1.0
            )
            if kappa != 1.0:
                raise ValueError(f"{operator_mode} requires kappa_plus_t=1")
            kappa_source = (
                "analytic_exact_full_identity"
                if operator_mode == "exact_full"
                else "analytic_unrescaled_subset_Loewner_order"
            )
            if kappa_plus_source is not None and kappa_plus_source != kappa_source:
                raise ValueError("kappa_plus_source disagrees with operator_mode")
        else:
            if kappa_plus_t is None or kappa_plus_source is None:
                raise ValueError(
                    "certified_approximate requires kappa_plus_t and its source"
                )
            kappa = _finite(kappa_plus_t, name="kappa_plus_t", minimum=1.0)
            kappa_source = _text(kappa_plus_source, name="kappa_plus_source")
        zeta_source = _text(
            optimizer_residual_source, name="optimizer_residual_source"
        )
        cg_source = _text(cg_certificate_source, name="cg_certificate_source")
        smooth_source = _text(smoothness_source, name="smoothness_source")
        cert_failure = _failure_probability(
            certificate_failure_probability,
            name="certificate_failure_probability",
        )
        optimizer_residual = _finite(zeta_t, name="zeta_t", minimum=0.0)
        cg_bound = _finite(cg_error_bound, name="cg_error_bound", minimum=0.0)
        if cg_bound >= 1.0:
            raise ValueError("cg_error_bound must be smaller than one")
        (
            checked_L_g,
            checked_L_mu,
            checked_G,
            checked_sigma,
            checked_lambda,
            checked_S,
            checked_delta,
            checked_trust_radius,
        ) = self._bind_fixed_constants(
            L_g=L_g,
            L_mu=L_mu,
            G=G,
            sigma=sigma,
            lambda_=lambda_,
            S=S,
            delta=delta,
            trust_region_radius=trust_region_radius,
        )

        centering = self._centering_certificate(
            current,
            checked_L_g,
            checked_G,
            checked_sigma,
            trust_region_radius=checked_trust_radius,
        )
        chi_bar = self.compute_chi_bar(
            current, checked_L_g, checked_sigma, checked_lambda
        )
        epsilon_lin_bar = self.compute_epsilon_lin_bar(
            current, checked_L_mu, checked_S
        )
        beta_bar = self.compute_beta_bar(
            delta=checked_delta,
            lambda_=checked_lambda,
            S=checked_S,
            sigma=checked_sigma,
        )
        psi_bar = float(
            (optimizer_residual + centering.m_bar_t)
            / math.sqrt(checked_lambda)
        )
        transfer = float(kappa * (1.0 + chi_bar) ** 2)
        alpha = float(math.sqrt((1.0 + cg_bound) / (1.0 - cg_bound)))
        snapshot = PathCertificateSnapshot(
            round_number=self._count + 1,
            history_count=self._count,
            q_t=centering.q_t,
            residual_sq_sum_prior=self._residual_sq_sum,
            f_bar_prior=self._f_bar,
            e_bar_prior=self._e_bar,
            gamma_hat_prior=self._gamma_hat,
            chi_bar_t=chi_bar,
            m_bar_t=centering.m_bar_t,
            psi_bar_t=psi_bar,
            epsilon_lin_bar_t=epsilon_lin_bar,
            beta_bar_t=beta_bar,
            transfer_factor=transfer,
            kappa_plus_t=kappa,
            optimizer_residual_zeta_t=optimizer_residual,
            residual_path_term=centering.residual_path_term,
            squared_path_term=centering.squared_path_term,
            cubic_path_bound=centering.cubic_path_bound,
            cubic_bound_mode=centering.cubic_bound_mode,
            cg_error_bound=cg_bound,
            cg_inflation_alpha_t=alpha,
            omega_original_t=beta_bar + psi_bar,
            omega_corrected_t=beta_bar,
            L_g=checked_L_g,
            L_mu=checked_L_mu,
            G=checked_G,
            sigma=checked_sigma,
            lambda_=checked_lambda,
            S=checked_S,
            delta=checked_delta,
            trust_region_radius=checked_trust_radius,
            operator_mode=operator_mode,
            kappa_plus_source=kappa_source,
            optimizer_residual_source=zeta_source,
            cg_certificate_source=cg_source,
            smoothness_source=smooth_source,
            certificate_failure_probability=cert_failure,
            certificate_probability_type=(
                "deterministic" if cert_failure == 0.0 else "probabilistic"
            ),
        )
        self._pending_snapshot = snapshot
        self._pending_theta = _readonly(current)
        return snapshot

    def commit_action_selection(
        self,
        action: int,
        all_action_cg_widths_squared: ArrayLike,
    ) -> ActionCertificateCommitment:
        """Commit the selected pre-action width before any reward is supplied."""

        if self._pending_snapshot is None:
            raise RuntimeError("pre_action_schedule must precede action commitment")
        if self._pending_action is not None:
            raise RuntimeError("the action for this round is already committed")
        widths = np.asarray(all_action_cg_widths_squared, dtype=np.float64)
        if widths.ndim != 1 or widths.size == 0:
            raise ValueError("all_action_cg_widths_squared must be a nonempty vector")
        if not np.all(np.isfinite(widths)) or np.any(widths < 0.0):
            raise ValueError("all action CG widths must be finite and nonnegative")
        selected = _integer(action, name="action")
        if selected >= widths.size:
            raise ValueError("action lies outside the width vector")
        played_width = float(widths[selected])
        snapshot = self._pending_snapshot
        information_increment = _finite(
            math.log1p(
                snapshot.transfer_factor
                * played_width
                / (
                    snapshot.sigma**2
                    * (1.0 - snapshot.cg_error_bound)
                )
            ),
            name="observable_information_increment",
            minimum=0.0,
        )
        commitment = ActionCertificateCommitment(
            round_number=snapshot.round_number,
            action=selected,
            action_count=int(widths.size),
            played_cg_width_squared=played_width,
            all_action_widths_sha256=hashlib.sha256(
                np.ascontiguousarray(widths).tobytes()
            ).hexdigest(),
            observable_information_increment=information_increment,
        )
        self._pending_action = commitment
        return commitment

    def update_after_reward(
        self,
        theta_t: ArrayLike,
        collection_residual: float,
        epsilon_lin_bar: float,
    ) -> PathCertificateUpdate:
        """Close the open round and update all summaries for round ``t+1``.

        The observable information increment is

        ``log(1 + sigma^-2 u_t(a_t) tilde_s_t^2(a_t)/(1-epsilon_CG_t))``.
        """

        if self._pending_snapshot is None or self._pending_theta is None:
            raise RuntimeError("pre_action_schedule must be called before reward update")
        if self._pending_action is None:
            raise RuntimeError("commit_action_selection must be called before reward update")
        current = _vector(theta_t, self._dimension, name="theta_t")
        if not np.array_equal(current, self._pending_theta):
            raise ValueError("theta_t changed between action selection and reward update")
        residual = _finite(collection_residual, name="collection_residual")
        epsilon = _finite(
            epsilon_lin_bar, name="epsilon_lin_bar", minimum=0.0
        )
        expected_epsilon = self._pending_snapshot.epsilon_lin_bar_t
        epsilon_tolerance = 256.0 * _EPS * max(1.0, expected_epsilon)
        if abs(epsilon - expected_epsilon) > epsilon_tolerance:
            raise ValueError("epsilon_lin_bar differs from the pre-action certificate")
        information_increment = self._pending_action.observable_information_increment

        # Vector Welford update.  With n=self.count and x=theta_t:
        # mean' = mean + (x-mean)/(n+1),
        # scatter' = scatter + (x-mean)^T(x-mean').
        next_count = self._count + 1
        delta = current - self._mean_theta
        next_mean = self._mean_theta + delta / float(next_count)
        delta_after = current - next_mean
        scatter_increment = float(delta @ delta_after)
        next_scatter = _roundoff_nonnegative(
            self._theta_scatter + scatter_increment,
            scale=abs(self._theta_scatter) + abs(scatter_increment),
            name="theta_scatter",
        )

        next_residual_sq_sum = _finite(
            self._residual_sq_sum + residual * residual,
            name="residual_sq_sum",
            minimum=0.0,
        )
        next_f_bar = _finite(
            self._f_bar + epsilon * epsilon, name="F_bar", minimum=0.0
        )
        next_e_bar = _finite(self._e_bar + epsilon, name="E_bar", minimum=0.0)
        next_gamma_hat = _finite(
            self._gamma_hat + information_increment,
            name="gamma_hat",
            minimum=0.0,
        )

        self._count = next_count
        self._mean_theta = _readonly(next_mean)
        self._theta_scatter = next_scatter
        self._residual_sq_sum = next_residual_sq_sum
        self._f_bar = next_f_bar
        self._e_bar = next_e_bar
        self._gamma_hat = next_gamma_hat
        self._max_theta_norm = max(self._max_theta_norm, float(np.linalg.norm(current)))
        update = PathCertificateUpdate(
            round_number=self._pending_snapshot.round_number,
            history_count_after_update=next_count,
            collection_residual=residual,
            residual_sq_sum_after_update=next_residual_sq_sum,
            f_bar_after_update=next_f_bar,
            e_bar_after_update=next_e_bar,
            gamma_hat_after_update=next_gamma_hat,
            observable_information_increment=information_increment,
            theta_scatter_after_update=next_scatter,
        )
        self._pending_snapshot = None
        self._pending_theta = None
        self._pending_action = None
        return update


__all__ = [
    "ActionCertificateCommitment",
    "CenteringCertificate",
    "OPERATOR_MODES",
    "PathCertificateSnapshot",
    "PathCertificateState",
    "PathCertificateUpdate",
]
