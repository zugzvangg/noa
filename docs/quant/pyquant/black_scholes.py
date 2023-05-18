import numpy as np
import numba as nb

from .utils import *
from .common import *


@nb.experimental.jitclass([
    ("S", nb.float64),
    ("r", nb.float64),
    ("T", nb.float64),
    ("K", nb.float64),
    ("is_call", nb.boolean),
    ("tol", nb.float64),
    ("sigma_lower", nb.float64),
    ("sigma_upper", nb.float64),
    ("strike_lower", nb.float64),
    ("strike_upper", nb.float64),
    ("delta_tol", nb.float64)
])
class BlackScholesCalc:
    def __init__(self):
        self.tol = 10**-6
        self.sigma_lower = 10**-3
        self.sigma_upper = 3
        self.strike_lower = 0.1
        self.strike_upper = 10.
        self.delta_tol = 10**-12
        
    def strike_from_delta(self, forward: Forward, delta: Delta, implied_vol: ImpliedVol) -> Strike:
        K_l = self.strike_lower*forward.S
        K_r = self.strike_upper*forward.S
        option_type = OptionType(delta.pv >= 0.)
        
        def g(K):
            return self.delta(forward, Strike(K), implied_vol, option_type).pv - delta.pv

        def g_prime(K):
            return self._dDelta_dK(forward, Strike(K), implied_vol)
        
        assert g(K_l) * g(K_r) <= 0
        
        K = (K_l+K_r) / 2
        epsilon = g(K)
        grad = g_prime(K)
        i = 0
        while abs(epsilon) > self.delta_tol and i < 10: 
            if abs(grad) > 1e-4:
                K -= epsilon / grad
                if K > K_r or K < K_l: 
                    K = (K_l + K_r) / 2
                    if g(K_l)*epsilon > 0:
                        K_l = K
                    else:
                        K_r = K
                    K = (K_l + K_r) / 2
            else:
                if g(K_l)*epsilon > 0:
                    K_l = K
                else:
                    K_r = K
                K = (K_l + K_r) / 2
            epsilon = g(K)
            grad = g_prime(K)
            i += 1

        return Strike(K)
        
    def implied_vol(self, forward: Forward, strike: Strike, premium: Premium, option_type: OptionType) -> ImpliedVol:
        pv = premium.pv

        def g(sigma):
            return pv - self.premium(forward, strike, ImpliedVol(sigma), option_type).pv

        def g_prime(sigma):
            return -self.vega(forward, strike, ImpliedVol(sigma)).pv 
        
        sigma_l = self.sigma_lower
        sigma_r = self.sigma_upper
        
        assert g(sigma_l) * g(sigma_r) <= 0
        
        sigma = (sigma_l + sigma_r) / 2
        epsilon = g(sigma)
        grad = g_prime(sigma)
        while abs(epsilon) > self.tol:   
            if abs(grad) > 1e-6:
                sigma -= epsilon / grad
                if sigma > sigma_r or sigma < sigma_l:
                    sigma = (sigma_l + sigma_r) / 2
                    if g(sigma_l)*epsilon > 0:
                        sigma_l = sigma
                    else:
                        sigma_r = sigma
                    sigma = (sigma_l + sigma_r) / 2
            else:
                if g(sigma_l)*epsilon > 0:
                    sigma_l = sigma
                else:
                    sigma_r = sigma
                sigma = (sigma_l + sigma_r) / 2
            
            epsilon = g(sigma)
            grad = g_prime(sigma) 
        return ImpliedVol(sigma)
       
    def premium(self, forward: Forward, strike: Strike, implied_vol: ImpliedVol, option_type: OptionType) -> Premium:
        pm = 1 if option_type.is_call else -1
        d1 = self._d1(forward, strike, implied_vol)
        d2 = self._d2(d1, forward, implied_vol)
        return Premium(
            pm * forward.S * normal_cdf(pm * d1) - pm * strike.K * \
            np.exp(-forward.r * forward.T) * normal_cdf(pm * d2)
        )
    
    def delta(self, forward: Forward, strike: Strike, implied_vol: ImpliedVol, option_type: OptionType) -> Delta:
        d1 = self._d1(forward, strike, implied_vol)
        return Delta(
            normal_cdf(d1) if option_type.is_call else normal_cdf(d1) - 1.0
        )
    
    def gamma(self, forward: Forward, strike: Strike, implied_vol: ImpliedVol) -> Gamma:
        d1 = self._d1(forward, strike, implied_vol) 
        return Gamma(
            normal_pdf(d1) / (forward.S * implied_vol.sigma * np.sqrt(forward.T))
        )
    
    def vega(self, forward: Forward, strike: Strike, implied_vol: ImpliedVol) -> Vega:
        return Vega(
            forward.S * np.sqrt(forward.T) * normal_pdf(self._d1(forward, strike, implied_vol))
        )
    
    def vanna(self, forward: Forward, strike: Strike, implied_vol: ImpliedVol) -> Vanna:
        d2 = self._d2(self._d1(forward, strike, implied_vol), forward, implied_vol)
        return Vanna(
            self.vega(forward, strike, implied_vol).pv * d2 / (implied_vol.sigma * forward.S)
        )
    
    def volga(self, forward: Forward, strike: Strike, implied_vol: ImpliedVol) -> Volga:
        d1 = self._d1(forward, strike, implied_vol)
        d2 = self._d2(d1, forward, implied_vol)
        return Volga(
            self.vega(forward, strike, implied_vol).pv * d1 * d2 / implied_vol.sigma
        )
    
    def _d1(self, forward: Forward, strike: Strike, implied_vol: ImpliedVol) -> nb.float64:
        d1 = (np.log(forward.S / strike.K) + (forward.r + implied_vol.sigma**2 / 2)\
               * forward.T) / (implied_vol.sigma * np.sqrt(forward.T))
        return d1
    
    def _d2(self, d1: nb.float64, forward: Forward, implied_vol: ImpliedVol) -> nb.float64:
        return d1 - implied_vol.sigma * np.sqrt(forward.T)
    
    def _dDelta_dK(self, forward: Forward, strike: Strike, implied_vol: ImpliedVol) -> nb.float64:
        d1 = self._d1(forward, strike, implied_vol)
        return - normal_pdf(d1) / (strike.K * np.sqrt(forward.T) * implied_vol.sigma)
    