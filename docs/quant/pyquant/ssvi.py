import numba as nb
import numpy as np

from .black_scholes import *
from .common import *
from .svi import *
from .svi import Rho
from .vol_surface import *


@nb.experimental.jitclass([("omega", nb.float64)])
class Omega:
    def __init__(self, omega: nb.float64):
        if not (omega >= 0):
            raise ValueError("Omega not >= 0")
        self.omega = omega


@nb.experimental.jitclass([("zeta", nb.float64)])
class Zeta:
    def __init__(self, zeta: nb.float64):
        if not (zeta > 0):
            raise ValueError("Zeta not > 0")
        self.zeta = zeta


@nb.experimental.jitclass([("mu", nb.float64)])
class Mu:
    def __init__(self, mu: nb.float64):
        self.mu = mu


@nb.experimental.jitclass([("delta_param", nb.float64)])
class DeltaParam:
    def __init__(self, delta_param: nb.float64):
        self.delta_param = delta_param


@nb.experimental.jitclass(
    [
        ("delta_param", nb.float64),
        ("mu", nb.float64),
        ("rho", nb.float64),
        ("omega", nb.float64),
        ("zeta", nb.float64),
    ]
)
class SVINaturalParams:
    def __init__(
        self, delta_param: DeltaParam, mu: Mu, rho: Rho, omega: Omega, zeta: Zeta
    ):
        self.delta_param = delta_param.delta_param
        self.mu = mu.mu
        self.rho = rho.rho
        self.omega = omega.omega
        self.zeta = zeta.zeta

    def array(self) -> nb.float64[:]:
        return np.array([self.delta_param, self.mu, self.rho, self.omega, self.zeta])


class SSVI:
    def __init__(
        self, vol_smile_chain_spaces: list[VolSmileChainSpace], is_log: bool = False
    ) -> None:
        self.is_log = is_log
        self.delta_space_raw_params_list = []
        self.delta_space_natural_params_list = []
        self.vol_smile_chain_spaces = vol_smile_chain_spaces

    def calibrate(self) -> None:
        for vol_smile_chain_space in self.vol_smile_chain_spaces:
            if self.is_log:
                print("\n")
                print(
                    f"======== Get natural params for tau = {vol_smile_chain_space.T} ======== "
                )
                print(f"Market IV {vol_smile_chain_space.sigmas}")
            # 1. for every time to maturity calibrate it's own SVI with raw params
            svi_calc = SVICalc()
            svi_calibrated_params, svi_error = svi_calc.calibrate(
                vol_smile_chain_space,
                CalibrationWeights(np.ones(len(vol_smile_chain_space.Ks))),
                False,
                False,
            )
            if self.is_log:
                print(
                    f"Calibrated to market. Error = {svi_error.v}. Raw params = {svi_calibrated_params.array()}"
                )

                svi_test_iv = svi_calc.implied_vols(
                    vol_smile_chain_space.forward(),
                    Strikes(vol_smile_chain_space.Ks),
                    svi_calibrated_params,
                )

                print(f"Calibrated IV {svi_test_iv.data}")

            # 2. Now get delta-space quotes
            svi_delta_space_chain = svi_calc.delta_space(
                vol_smile_chain_space.forward(),
                svi_calibrated_params,
            ).to_chain_space()
            if self.is_log:
                print(f"Delta-space strikes: {svi_delta_space_chain.strikes().data}")

            # 2. Calibrate to delta-space
            svi_calibrated_params_delta, __ = svi_calc.calibrate(
                svi_delta_space_chain, CalibrationWeights(np.ones(5)), False, True
            )
            if self.is_log:
                print("Delta space params:", svi_calibrated_params_delta.array())
                svi_test_iv_delta = svi_calc.implied_vols(
                    vol_smile_chain_space.forward(),
                    Strikes(vol_smile_chain_space.Ks),
                    svi_calibrated_params_delta,
                )
                print(f"Delta-space market IV: {svi_test_iv_delta.data}")

            self.delta_space_raw_params_list.append(svi_calibrated_params_delta)
            # NOTE: raw SVI from delta or direct market calibration?
            # a, b, rho, m, sigma = svi_calibrated_params_delta.array()
            a, b, rho, m, sigma = svi_calibrated_params.array()
            natural_params = self.raw_to_natural_parametrization(
                SVIRawParams(A(a), B(b), Rho(rho), M(m), Sigma(sigma))
            )
            self.delta_space_natural_params_list.append(natural_params)

            if self.is_log:
                print(
                    f"Raw parametrizarion delta-space params: {svi_calibrated_params_delta.array()}"
                )
                print(
                    f"Natural parametrizarion delta-space params: {natural_params.array()}"
                )

        # 3. Now get atm (K = F) implied total variances for all ttm's chains
        atm_total_variances = []
        for vol_smile_chain_space, delta_space_natural_params_ in zip(
            self.vol_smile_chain_spaces, self.delta_space_natural_params_list
        ):
            F = vol_smile_chain_space.forward().spot().S

            atm_total_variance = self._total_implied_var_ssvi(
                F, F + 1000, delta_space_natural_params_.array()
            )
            atm_total_variances.append(atm_total_variance)
        print("======== ATM total var ========== ", atm_total_variances)
        return atm_total_variances

    def raw_to_natural_parametrization(
        self, svi_raw_params: SVIRawParams
    ) -> SVINaturalParams:
        a, b, rho, m, sigma = svi_raw_params.array()
        sqrt = np.sqrt(1 - rho**2)
        omega = 2 * b * sigma / sqrt
        zeta = sqrt / sigma
        mu = m + rho * sigma / sqrt
        delta_param = a - omega / 2 * (1 - rho**2)
        return SVINaturalParams(
            DeltaParam(delta_param), Mu(mu), Rho(rho), Omega(omega), Zeta(zeta)
        )

    def _total_implied_var_ssvi(
        self,
        F: nb.float64,
        K: nb.float64,
        params: nb.float64[:],
    ) -> nb.float64:
        delta_param, mu, rho, omega, zeta = (
            params[0],
            params[1],
            params[2],
            params[3],
            params[4],
        )
        k = np.log(K / F)
        w = delta_param + omega / 2 * (
            1
            + zeta * rho * (k - mu) * np.sqrt((zeta * (k - mu) + rho) ** 2 + 1 - rho**2)
        )
        return w
