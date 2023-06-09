import numpy as np
import numba as nb
from scipy.interpolate import CubicSpline

from .common import *
from .black_scholes import *


@nb.experimental.jitclass([
    ("sigma", nb.float64),
    ("T", nb.float64)
])
class Straddle:
    def __init__(self, implied_vol: ImpliedVol, time_to_maturity: TimeToMaturity):
        self.sigma = implied_vol.sigma 
        self.T = time_to_maturity.T

@nb.experimental.jitclass([
    ("delta", nb.float64),
    ("sigma", nb.float64),
    ("T", nb.float64)
    
])
class RiskReversal:
    def __init__(self, delta: Delta, vol_quote: VolatilityQuote, time_to_maturity: TimeToMaturity):
        if not (delta.pv <=1 and delta.pv >= 0):
            raise ValueError('Delta expected within [0,1]')
        self.delta = delta.pv
        self.sigma = vol_quote.sigma 
        self.T = time_to_maturity.T
        
@nb.experimental.jitclass([
    ("delta", nb.float64),
    ("sigma", nb.float64),
    ("T", nb.float64)
])
class Butterfly:
    def __init__(self, delta: Delta, vol_quote: VolatilityQuote, time_to_maturity: TimeToMaturity):
        if not (delta.pv <=1 and delta.pv >= 0):
            raise ValueError('Delta expected within [0,1]')
        self.delta = delta.pv
        self.sigma = vol_quote.sigma
        self.T = time_to_maturity.T


@nb.experimental.jitclass([
    ("T", nb.float64),
    ("S", nb.float64),
    ("r", nb.float64),
    ("f", nb.float64),
    ("sigmas", nb.float64[:]),
    ("strikes", nb.float64[:]),
])
class VolSmileChain:
    bs_calc: BSCalc
    def __init__(self, forward: Forward, strikes: Strikes, implied_vols: ImpliedVols):
        if not strikes.data.shape == implied_vols.data.shape:
            raise ValueError('Inconsistent data between strikes and implied vols')
        if not is_sorted(strikes.data):
            raise ValueError('Strikes are not in order')

        self.T = forward.T
        self.S = forward.S
        self.r = forward.r
        self.f = forward.forward_rate().fv

        self.sigmas = implied_vols.data 
        self.strikes = strikes.data
        
        self.bs_calc = BSCalc()

    def premiums(self) -> Premiums:
        res = np.zeros_like(self.sigmas)
        forward = Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T))
        n = len(self.sigmas)
        for i in range(n):
            K = self.strikes[i]
            sigma = self.sigmas[i]
            res[i] = self.bs_calc.premium(forward, Strike(K), ImpliedVol(sigma), OptionType(K >= self.f)).pv
        return Premiums(res)
    
    def forward(self) -> Forward:
        return Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T))

    def deltas(self) -> Deltas:
        res = np.zeros_like(self.strikes)
        n = len(self.strikes)
        forward = Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T))
        for i in range(n):
            res[i] = self.bs_calc.delta(
                forward,
                Strike(self.strikes[i]),
                ImpliedVol(self.sigmas[i]),
                OptionType(self.strikes[i] >= self.f)
            ).pv 
        return Deltas(res) 
    
    def gammas(self) -> Gammas:
        res = np.zeros_like(self.strikes)
        n = len(self.strikes)
        forward = Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T))
        for i in range(n):
            res[i] = self.bs_calc.gamma(
                forward,
                Strike(self.strikes[i]),
                ImpliedVol(self.sigmas[i])
            ).pv 
        return Gammas(res) 
    
    def vegas(self) -> Vegas:
        res = np.zeros_like(self.strikes)
        n = len(self.strikes)
        forward = Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T))
        for i in range(n):
            res[i] = self.bs_calc.vega(
                forward,
                Strike(self.strikes[i]),
                ImpliedVol(self.sigmas[i])
            ).pv 
        return Vegas(res) 
    
    def vannas(self) -> Vannas:
        res = np.zeros_like(self.strikes)
        n = len(self.strikes)
        forward = Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T))
        for i in range(n):
            res[i] = self.bs_calc.vanna(
                forward,
                Strike(self.strikes[i]),
                ImpliedVol(self.sigmas[i])
            ).pv 
        return Vannas(res) 
    
    def volgas(self) -> Volgas:
        res = np.zeros_like(self.strikes)
        n = len(self.strikes)
        forward = Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T))
        for i in range(n):
            res[i] = self.bs_calc.volga(
                forward,
                Strike(self.strikes[i]),
                ImpliedVol(self.sigmas[i])
            ).pv 
        return Volgas(res) 


@nb.experimental.jitclass([
    ("T", nb.float64),
    ("S", nb.float64),
    ("r", nb.float64),
    ("f", nb.float64),
    ("ATM", nb.float64),
    ("RR25", nb.float64),
    ("BF25", nb.float64),
    ("RR10", nb.float64),
    ("BF10", nb.float64),
    ("atm_blip", nb.float64),
    ("rr25_blip", nb.float64),
    ("bf25_blip", nb.float64),
    ("rr10_blip", nb.float64),
    ("bf10_blip", nb.float64),
    ("strike_lower", nb.float64),
    ("strike_upper", nb.float64),
    ("delta_tol", nb.float64),
    ("delta_grad_eps", nb.float64)
]) 
class VolSmileDeltaSpace:
    bs_calc: BSCalc
    def __init__(
        self, 
        forward: Forward,
        ATM: Straddle, 
        RR25: RiskReversal, 
        BF25: Butterfly, 
        RR10: RiskReversal, 
        BF10: Butterfly
    ):
        self.T = forward.T
        self.S = forward.S
        self.r = forward.r
        self.f = forward.forward_rate().fv

        if not ATM.T == self.T:
            raise ValueError('Inconsistent time_to_maturity for ATM')
        self.ATM = ATM.sigma

        if not RR25.delta == 0.25:
            raise ValueError('Inconsistent delta for 25RR')
        if not RR25.T == self.T:
            raise ValueError('Inconsistent time_to_maturity for 25RR')
        self.RR25 = RR25.sigma 

        if not BF25.delta == 0.25:
            raise ValueError('Inconsistent delta for 25BF')
        if not BF25.T == self.T:
            raise ValueError('Inconsistent time_to_maturity for 25BF')
        self.BF25 = BF25.sigma

        if not RR10.delta == 0.1:
            raise ValueError('Inconsistent delta for 10RR')
        if not RR10.T == self.T:
            raise ValueError('Inconsistent delta for 10RR')
        self.RR10 = RR10.sigma

        if not BF10.delta == 0.1:
            raise ValueError('Inconsistent delta for 10BF')
        if not BF10.T == self.T:
            raise ValueError('Inconsistent time to maturity for 10BF')
        self.BF10 = BF10.sigma

        self.atm_blip = 0.0025
        self.rr25_blip = 0.001
        self.bf25_blip = 0.001
        self.rr10_blip = 0.0016
        self.bf10_blip = 0.00256
        
        self.strike_lower = 0.1
        self.strike_upper = 10.
        self.delta_tol = 10**-12
        self.delta_grad_eps = 1e-4
        
        self.bs_calc = BSCalc()
        self.bs_calc.strike_lower = self.strike_lower
        self.bs_calc.strike_upper = self.strike_upper
        self.bs_calc.delta_tol = self.delta_tol
        self.bs_calc.delta_grad_eps = self.delta_grad_eps

    def _implied_vols(self, RR: nb.float64, BB: nb.float64) -> tuple[nb.float64]:
        return -RR/2 + (BB + self.ATM), RR/2 + (BB + self.ATM)
    
    def _get_strike(self, sigma: nb.float64, delta: nb.float64) -> nb.float64:
        return self.bs_calc.strike_from_delta(
            Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T)), 
            Delta(delta), 
            ImpliedVol(sigma)
        ).K

    def to_chain_space(self) -> VolSmileChain:
        ivs = np.zeros(5, dtype=np.float64)
        strikes = np.zeros(5, dtype=np.float64)
           
        ivs[2] = self.ATM     
        ivs[1], ivs[3] = self._implied_vols(self.RR25, self.BF25)
        ivs[0], ivs[4] = self._implied_vols(self.RR10, self.BF10)

        strikes[0] = self._get_strike(ivs[0], -0.1)
        strikes[1] = self._get_strike(ivs[1], -0.25)
        strikes[2] = self.f
        strikes[3] = self._get_strike(ivs[3], 0.25)
        strikes[4] = self._get_strike(ivs[4], 0.1)
        
        return VolSmileChain(
            Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T)),
            Strikes(strikes),
            ImpliedVols(ivs)
        ) 
    
    def forward(self) -> Forward:
        return Forward(Spot(self.S), ForwardYield(self.r), TimeToMaturity(self.T))
    
    def blip_ATM(self):
        self.ATM += self.atm_blip
        return self

    def blip_25RR(self):
        self.RR25 += self.rr25_blip
        return self

    def blip_25BF(self):
        self.BF25 += self.bf25_blip
        return self

    def blip_10RR(self):
        self.RR10 += self.rr10_blip
        return self

    def blip_10BF(self):
        self.BF10 += self.bf10_blip
        return self


@nb.experimental.jitclass([
    ("sigma", nb.float64[:]),
    ("T", nb.float64[:])
])
class Straddles:
    def __init__(self, implied_vols: ImpliedVols, times_to_maturity: TimesToMaturity):
        if not implied_vols.data.shape == times_to_maturity.data.shape:
            raise ValueError('Inconsistent data between implied vols and times to maturity')
        if not is_sorted(times_to_maturity.data):
            raise ValueError('Times to maturity are not in order')
        self.sigma = implied_vols.data 
        self.T = times_to_maturity.data


@nb.experimental.jitclass([
    ("delta", nb.float64),
    ("sigma", nb.float64[:]),
    ("T", nb.float64[:])
    
])
class RiskReversals:
    def __init__(self, delta: Delta, volatility_quotes: VolatilityQuotes, times_to_maturity: TimesToMaturity):
        if not (delta.pv <=1 and delta.pv >= 0):
            raise ValueError('Delta expected within [0,1]')
        if not volatility_quotes.data.shape == times_to_maturity.data.shape:
            raise ValueError('Inconsistent data between quotes and times to maturity')
        if not is_sorted(times_to_maturity.data):
            raise ValueError('Times to maturity are not in order')
        self.delta = delta.pv
        self.sigma = volatility_quotes.data 
        self.T = times_to_maturity.data  


@nb.experimental.jitclass([
    ("delta", nb.float64),
    ("sigma", nb.float64[:]),
    ("T", nb.float64[:])
])
class Butterflies:
    def __init__(self, delta: Delta, volatility_quotes: VolatilityQuotes, times_to_maturity: TimesToMaturity):
        if not (delta.pv <=1 and delta.pv >= 0):
            raise ValueError('Delta expected within [0,1]')
        if not volatility_quotes.data.shape == times_to_maturity.data.shape:
            raise ValueError('Inconsistent data between quotes and times to maturity')
        if not is_sorted(times_to_maturity.data):
            raise ValueError('Times to maturity are not in order')
        self.delta = delta.pv
        self.sigma = volatility_quotes.data 
        self.T = times_to_maturity.data 


class VolSurface:

    def __init__(
        self, 
        forward_curve: ForwardCurve, 
        straddles: Straddles,
        risk_reversals_25: RiskReversals,
        butterflies_25: Butterflies,
        risk_reversals_10: RiskReversals,
        butterflies_10: Butterflies
    ): 
        self.S = forward_curve.S

        self.f = CubicSpline(
            np.append(np.array([0.]), forward_curve.T),
            np.append(np.array([0.]), forward_curve.forward_rates().data)
        )

        self.ATM = CubicSpline(
            np.append(np.array([0.]), straddles.T),
            np.append(np.array([0.]), straddles.sigma)
        )

        self.RR25 = CubicSpline(
            np.append(np.array([0.]), risk_reversals_25.T),
            np.append(np.array([0.]), risk_reversals_25.sigma)
        )

        self.BF25 = CubicSpline(
            np.append(np.array([0.]), butterflies_25.T),
            np.append(np.array([0.]), butterflies_25.sigma)
        )

        self.RR10 = CubicSpline(
            np.append(np.array([0.]), risk_reversals_10.T),
            np.append(np.array([0.]), risk_reversals_10.sigma)
        )

        self.BF10 = CubicSpline(
            np.append(np.array([0.]), butterflies_10.T),
            np.append(np.array([0.]), butterflies_10.sigma)
        )

        self.max_T = np.min(np.array([
            forward_curve.T[-1], 
            straddles.T[-1],
            risk_reversals_25.T[-1],
            butterflies_25.T[-1],
            risk_reversals_10.T[-1],
            butterflies_10.T[-1]
        ]))
        
    def get_vol_smile(self, time_to_maturity: TimeToMaturity) -> VolSmileDeltaSpace:
        T = time_to_maturity.T
        if not (T > 0 and T <= self.max_T):
            raise ValueError('TimeToMaturity outside available bounds')
    
        return VolSmileDeltaSpace(
            Forward.from_forward_rate(
                Spot(self.S),
                ForwardRate(self.f(T)),
                time_to_maturity
            ),
            Straddle(
                ImpliedVol(self.ATM(T)),
                time_to_maturity
            ),
            RiskReversal(
                Delta(.25),
                VolatilityQuote(self.RR25(T)),
                time_to_maturity
            ),
            Butterfly(
                Delta(.25),
                VolatilityQuote(self.BF25(T)),
                time_to_maturity
            ),
            RiskReversal(
                Delta(.1),
                VolatilityQuote(self.RR10(T)),
                time_to_maturity
            ),
            Butterfly(
                Delta(.1),
                VolatilityQuote(self.BF10(T)),
                time_to_maturity
            )
        )