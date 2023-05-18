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
    def __init__(self, implied_vol: ImpliedVol, tenor: Tenor):
        self.sigma = implied_vol.sigma 
        self.T = tenor.T


@nb.experimental.jitclass([
    ("delta", nb.float64),
    ("sigma", nb.float64),
    ("T", nb.float64)
    
])
class RiskReversal:
    def __init__(self, delta: Delta, vol_quote: VolatilityQuote, tenor: Tenor):
        assert delta.pv <=1
        assert delta.pv >= 0
        self.delta = delta.pv
        self.sigma = vol_quote.sigma 
        self.T = tenor.T
        
@nb.experimental.jitclass([
    ("delta", nb.float64),
    ("sigma", nb.float64),
    ("T", nb.float64)
])
class Butterfly:
    def __init__(self, delta: Delta, vol_quote: VolatilityQuote, tenor: Tenor):
        assert delta.pv <=1
        assert delta.pv >= 0
        self.delta = delta.pv
        self.sigma = vol_quote.sigma
        self.T = tenor.T


@nb.experimental.jitclass([
    ("f", nb.float64),
    ("T", nb.float64),
    ("sigma", nb.float64[:]),
    ("K", nb.float64[:]),
])
class VolSmileChain:
    def __init__(self, forward: Forward, strikes: Strikes, implied_vols: ImpliedVols):
        assert strikes.data.shape == implied_vols.data.shape
        self.f = forward.forward_rate().fv
        self.T = forward.T
        self.sigma = implied_vols.data 
        self.K = strikes.data                    
    

@nb.experimental.jitclass([
    ("T", nb.float64),
    ("S", nb.float64),
    ("r", nb.float64),
    ("f", nb.float64),
    ("ATM", nb.float64),
    ("RR25", nb.float64),
    ("BB25", nb.float64),
    ("RR10", nb.float64),
    ("BB10", nb.float64),
    ("strike_lower", nb.float64),
    ("strike_upper", nb.float64),
    ("delta_tol", nb.float64)
]) 
class VolSmileDeltaSpace:
    def __init__(
        self, 
        forward: Forward,
        ATM: Straddle, 
        RR25: RiskReversal, 
        BB25: Butterfly, 
        RR10: RiskReversal, 
        BB10: Butterfly
    ):
        self.T = forward.T
        self.S = forward.S
        self.r = forward.r
        self.f = forward.forward_rate().fv

        assert ATM.T == self.T
        self.ATM = ATM.sigma

        assert RR25.delta == 0.25
        assert RR25.T == self.T
        self.RR25 = RR25.sigma 

        assert BB25.delta == 0.25
        assert BB25.T == self.T
        self.BB25 = BB25.sigma

        assert RR10.delta == 0.1
        assert RR10.T == self.T
        self.RR10 = RR10.sigma

        assert BB10.delta == 0.1
        assert BB10.T == self.T
        self.BB10 = BB10.sigma
        
        self.strike_lower = 0.1
        self.strike_upper = 10.
        self.delta_tol = 10**-12

    def _implied_vols(self, RR: nb.float64, BB: nb.float64) -> tuple[nb.float64]:
        return -RR/2 + (BB + self.ATM), RR/2 + (BB + self.ATM)
    
    def _get_strike(self, sigma: nb.float64, delta: nb.float64) -> nb.float64:
        bs = BlackScholesCalc()
        bs.strike_lower = self.strike_lower
        bs.strike_upper = self.strike_upper
        bs.delta_tol = self.delta_tol
        return bs.strike_from_delta(
            Forward(Spot(self.S), ForwardYield(self.r), Tenor(self.T)), 
            Delta(delta), 
            ImpliedVol(sigma)
        ).K

    def to_chain_space(self):
        ivs = np.zeros(5, dtype=np.float64)
        strikes = np.zeros(5, dtype=np.float64)
        
        ivs[2] = self.ATM     
        ivs[1], ivs[3] = self._implied_vols(self.RR25, self.BB25)
        ivs[0], ivs[4] = self._implied_vols(self.RR10, self.BB10)

        strikes[0] = self._get_strike(ivs[0], -0.1)
        strikes[1] = self._get_strike(ivs[1], -0.25)
        strikes[2] = self.f
        strikes[3] = self._get_strike(ivs[3], 0.25)
        strikes[4] = self._get_strike(ivs[4], 0.1)
        
        return VolSmileChain(
            Forward(Spot(self.S), ForwardYield(self.r), Tenor(self.T)),
            Strikes(strikes),
            ImpliedVols(ivs)
        )   


@nb.experimental.jitclass([
    ("sigma", nb.float64[:]),
    ("T", nb.float64[:])
])
class Straddles:
    def __init__(self, implied_vols: ImpliedVols, tenors: Tenors):
        assert implied_vols.data.shape == tenors.data.shape
        assert is_sorted(tenors.data)
        self.sigma = implied_vols.sigma 
        self.T = tenors.T


@nb.experimental.jitclass([
    ("delta", nb.float64),
    ("sigma", nb.float64[:]),
    ("T", nb.float64[:])
    
])
class RiskReversals:
    def __init__(self, delta: Delta, volatility_quotes: VolatilityQuotes, tenors: Tenors):
        assert delta.pv <=1
        assert delta.pv >= 0
        assert volatility_quotes.data.shape == tenors.data.shape
        assert is_sorted(tenors.data)
        self.delta = delta.pv
        self.sigma = volatility_quotes.data 
        self.T = tenors.data  


@nb.experimental.jitclass([
    ("delta", nb.float64),
    ("sigma", nb.float64[:]),
    ("T", nb.float64[:])
])
class Butterflies:
    def __init__(self, delta: Delta, volatility_quotes: VolatilityQuotes, tenors: Tenors):
        assert delta.pv <=1
        assert delta.pv >= 0
        assert volatility_quotes.data.shape == tenors.data.shape
        assert is_sorted(tenors.data)
        self.delta = delta.pv
        self.sigma = volatility_quotes.data 
        self.T = tenors.data 


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
            np.append(np.array([0.]), forward_curve.forward_rates())
        )

        self.ATM = CubicSpline(
            np.append(np.array([0.]), straddles.T),
            np.append(np.array([0.]), straddles.sigma)
        )

        self.RR25 = CubicSpline(
            np.append(np.array([0.]), risk_reversals_25.T),
            np.append(np.array([0.]), risk_reversals_25.sigma)
        )

        self.BB25 = CubicSpline(
            np.append(np.array([0.]), butterflies_25.T),
            np.append(np.array([0.]), butterflies_25.sigma)
        )

        self.RR10 = CubicSpline(
            np.append(np.array([0.]), risk_reversals_10.T),
            np.append(np.array([0.]), risk_reversals_10.sigma)
        )

        self.BB10 = CubicSpline(
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
        
    def get_vol_smile(self, tenor: Tenor) -> VolSmileDeltaSpace:
        T = tenor.T
        assert T > 0 and T <= self.max_T
    
        return VolSmileDeltaSpace(
            Forward.from_forward_rate(
                Spot(self.S),
                ForwardRate(self.f(T)),
                tenor
            ),
            Straddle(
                ImpliedVol(self.ATM(T)),
                tenor
            ),
            RiskReversal(
                Delta(.25),
                VolatiltyQuote(self.RR25(T)),
                tenor
            ),
            Butterfly(
                Delta(.25),
                VolatiltyQuote(self.BB25(T)),
                tenor
            ),
            RiskReversal(
                Delta(.1),
                VolatiltyQuote(self.RR10(T)),
                tenor
            ),
            Butterfly(
                Delta(.1),
                VolatiltyQuote(self.BB10(T)),
                tenor
            )
        )