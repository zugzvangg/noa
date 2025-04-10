from typing import Any, Dict, Optional, Union

import numba as nb
import numpy as np

from .black_scholes import *
from .common import *
from .svi import *
from .svi import Rho
from .vol_surface import *


@nb.experimental.jitclass([("delta_param", nb.float64)])
class DeltaParam:
    def __init__(self, delta_param: nb.float64):
        self.delta_param = delta_param


@nb.experimental.jitclass([("mu", nb.float64)])
class Mu:
    def __init__(self, mu: nb.float64):
        self.mu = mu


@nb.experimental.jitclass([("theta", nb.float64)])
class Theta:
    def __init__(self, theta: nb.float64):
        if not (theta >= 0):
            raise ValueError("Theta not >= 0")
        self.theta = theta


@nb.experimental.jitclass([("zeta", nb.float64)])
class Zeta:
    def __init__(self, zeta: nb.float64):
        if not (zeta > 0):
            raise ValueError("Zeta not > 0")
        self.zeta = zeta


@nb.experimental.jitclass([("lambda_", nb.float64)])
class Lambda:
    def __init__(self, lambda_: nb.float64):
        if not (lambda_ >= 0):
            raise ValueError("Lambda not >= 0")
        self.lambda_ = lambda_


@nb.experimental.jitclass([("eta", nb.float64)])
class Eta:
    def __init__(self, eta: nb.float64):
        if not (eta >= 0):
            raise ValueError("Eta not >= 0")
        self.eta = eta


@nb.experimental.jitclass([("beta", nb.float64)])
class Beta:
    def __init__(self, beta: nb.float64):
        if not (beta >= 0):
            raise ValueError("Beta not >= 0")
        self.beta = beta


@nb.experimental.jitclass([("alpha", nb.float64)])
class Alpha:
    def __init__(self, alpha: nb.float64):
        self.alpha = alpha


@nb.experimental.jitclass([("gamma_", nb.float64)])
class Gamma_:
    def __init__(self, gamma_: nb.float64):
        self.gamma_ = gamma_


@nb.experimental.jitclass(
    [
        ("delta_param", nb.float64),
        ("mu", nb.float64),
        ("rho", nb.float64),
        ("theta", nb.float64),
        ("zeta", nb.float64),
        ("lambda_", nb.float64),
        ("eta", nb.float64),
        ("beta", nb.float64),
        ("alpha", nb.float64),
        ("gamma_", nb.float64),
    ]
)
class SVINaturalParams:
    def __init__(
        self, delta_param: DeltaParam, mu: Mu, rho: Rho, theta: Theta, zeta: Zeta
    ):
        self.delta_param = delta_param.delta_param
        self.mu = mu.mu
        self.rho = rho.rho
        self.theta = theta.theta
        self.zeta = zeta.zeta

    def array(self) -> nb.float64[:]:
        return np.array([self.delta_param, self.mu, self.rho, self.theta, self.zeta])


@nb.experimental.jitclass(
    [
        ("num_iter", nb.int64),
        ("max_mu", nb.float64),
        ("min_mu", nb.float64),
        ("tol", nb.float64),
        ("svi", SVICalc.class_type.instance_type),
    ]
)
class SSVICalc:
    def __init__(
        self,
    ) -> None:
        self.num_iter = 10000
        self.max_mu = 1e4
        self.min_mu = 1e-6
        self.tol = 1e-12
        self.svi = SVICalc()

    def calibrate(
        self,
        vol_surface_delta_space: VolSurfaceDeltaSpace,
        number_of_delta_space_dots: int = 20,
    ):
        zetas, rhos, thetas = (
            np.zeros(number_of_delta_space_dots),
            np.zeros(number_of_delta_space_dots),
            np.zeros(number_of_delta_space_dots),
        )
        # we calibrate SVI with a, m = 0 to the linspace of max and min tenors given in space
        tenors_linspace = np.linspace(
            vol_surface_delta_space.min_T,
            vol_surface_delta_space.max_T,
            number_of_delta_space_dots,
        )
        # calibrate tenor by tenor
        for idx, tenor in enumerate(tenors_linspace):
            vol_smile_chain_space: VolSmileChainSpace = (
                vol_surface_delta_space.get_vol_smile(
                    TimeToMaturity(tenor)
                ).to_chain_space()
            )
            svi_raw_params, _ = self.svi.calibrate(
                vol_smile_chain_space,
                CalibrationWeights(np.ones_like(vol_smile_chain_space.Ks)),
                False,
                False,
                True,
            )
            svi_natural_params_array: SVINaturalParams = (
                self.raw_to_natural_parametrization(svi_raw_params)
            )
            zetas[idx] = svi_natural_params_array.zeta
            thetas[idx] = svi_natural_params_array.theta
            rhos[idx] = svi_natural_params_array.rho

        eta_lambda_, error = self._interpolate_eta_lambda(zetas, thetas)
        print("Eta, Lambda calibration error", error)

        alpha_beta_gamma, error = self._interpolate_alpha_beta_gamma(rhos, thetas)
        print("Alpha, Beta, Gamma calibration error", error)

        return (
            Eta(eta_lambda_[0]),
            Lambda(eta_lambda_[1]),
            Alpha(alpha_beta_gamma[0]),
            Beta(alpha_beta_gamma[1]),
            Gamma_(alpha_beta_gamma[2]),
        )

    def _interpolate_eta_lambda(
        self, zetas: nb.float64[:], thetas: nb.float64[:]
    ) -> Union[nb.float64[:], nb.float64]:

        calibration_weights = CalibrationWeights(np.ones_like(thetas))
        w = calibration_weights.w
        weights = w / w.sum()
        n_points = len(thetas)

        def model(params, thetas):
            eta, lambda_ = params[0], params[1]
            return eta * thetas ** (-lambda_)

        def f(params):
            predictions = model(params, thetas)
            residuals = zetas - predictions

            eta, lambda_ = params[0], params[1]
            J_eta = -(thetas ** (-lambda_))
            J_lambda = -eta * thetas ** (-lambda_) * np.log(thetas)
            J = np.stack((J_eta, J_lambda))
            return residuals * weights, J @ np.diag(weights)

        def proj(params):
            eps = 1e-4
            eta, lambda_ = params[0], params[1]

            lambda_ = np_clip(lambda_, eps, 1.0 - eps)
            eta = np_clip(eta, eps, 1000000.0)
            return np.array([eta, lambda_])

        def levenberg_marquardt(f, proj, x0):
            x = x0.copy()

            mu = 1e-2
            nu1 = 2.0
            nu2 = 2.0

            res, J = f(x)
            F = res.T @ res

            result_x = x
            result_error = F / n_points

            for i in range(self.num_iter):
                if result_error < self.tol:
                    break
                multipl = J @ J.T
                I = np.diag(np.diag(multipl)) + 1e-5 * np.eye(len(x))
                dx = np.linalg.solve(mu * I + multipl, J @ res)
                x_ = proj(x - dx)
                res_, J_ = f(x_)
                F_ = res_.T @ res_
                if F_ < F:
                    x, F, res, J = x_, F_, res_, J_
                    mu = max(self.min_mu, mu / nu1)
                    result_error = F / n_points
                else:
                    i -= 1
                    mu = min(self.max_mu, mu * nu2)
                    continue
                result_x = x
            return result_x, result_error

        optimal_params, calibration_error = levenberg_marquardt(
            f, proj, np.array([1.0, 1.0])
        )
        return optimal_params, calibration_error

    def _interpolate_alpha_beta_gamma(
        self, rhos: nb.float64[:], thetas: nb.float64[:]
    ) -> Union[nb.float64[:], nb.float64]:

        calibration_weights = CalibrationWeights(np.ones_like(thetas))
        w = calibration_weights.w
        weights = w / w.sum()
        n_points = len(thetas)

        def model(params, thetas):
            alpha, beta, gamma = params
            return alpha * np.exp(-beta * thetas) + gamma

        def f(params):
            predictions = model(params, thetas)
            residuals = rhos - predictions

            alpha, beta, gamma = params
            J_alpha = -np.exp(-beta * thetas)
            J_beta = alpha * thetas * np.exp(-beta * thetas)
            J_gamma = -np.ones_like(thetas)
            J = np.stack((J_alpha, J_beta, J_gamma))
            return residuals * weights, J @ np.diag(weights)

        def proj(params):
            eps = 1e-4
            alpha, beta, gamma = params[0], params[1], params[2]
            beta = np_clip(beta, eps, 1000000.0)
            return np.array([alpha, beta, gamma])

        def levenberg_marquardt(f, proj, x0):
            x = x0.copy()

            mu = 1e-2
            nu1 = 2.0
            nu2 = 2.0

            res, J = f(x)
            F = res.T @ res

            result_x = x
            result_error = F / n_points

            for i in range(self.num_iter):
                if result_error < self.tol:
                    break
                multipl = J @ J.T
                I = np.diag(np.diag(multipl)) + 1e-5 * np.eye(len(x))
                dx = np.linalg.solve(mu * I + multipl, J @ res)
                x_ = proj(x - dx)
                res_, J_ = f(x_)
                F_ = res_.T @ res_
                if F_ < F:
                    x, F, res, J = x_, F_, res_, J_
                    mu = max(self.min_mu, mu / nu1)
                    result_error = F / n_points
                else:
                    i -= 1
                    mu = min(self.max_mu, mu * nu2)
                    continue
                result_x = x
            return result_x, result_error

        optimal_params, calibration_error = levenberg_marquardt(
            f, proj, np.array([1.0, 1.0, 1.0])
        )
        return optimal_params, calibration_error

    def _total_implied_var_ssvi(
        self,
        F: nb.float64,
        K: nb.float64,
        params: nb.float64[:],
    ) -> nb.float64:
        delta_param, mu, rho, theta, zeta = (
            params[0],
            params[1],
            params[2],
            params[3],
            params[4],
        )
        k = np.log(K / F)
        w = delta_param + theta / 2 * (
            1
            + zeta * rho * (k - mu) * np.sqrt((zeta * (k - mu) + rho) ** 2 + 1 - rho**2)
        )
        return w

    def raw_to_natural_parametrization(
        self, svi_raw_params: SVIRawParams
    ) -> SVINaturalParams:
        a, b, rho, m, sigma = svi_raw_params.array()
        sqrt = np.sqrt(1 - rho**2)
        theta = 2 * b * sigma / sqrt
        zeta = sqrt / sigma
        mu = m + rho * sigma / sqrt
        delta_param = a - theta / 2 * (1 - rho**2)
        return SVINaturalParams(
            DeltaParam(delta_param), Mu(mu), Rho(rho), Theta(theta), Zeta(zeta)
        )
