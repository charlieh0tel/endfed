"""The shape of the tabulated model: what is tabulated, over what, and how far.

These are the constants the shipped table is built to, shared by the fit
(`fit.py`), the tabulation (`table2d.py`) and the generator that writes the
page (`coefficients2d.py`).  They live apart from any one of those because
they are the specification rather than a step in it: change a node here and
every stage moves together.

Coefficients are tabulated against log10(h/lambda), which is the variable they
actually move with, and against soil.  `vf_a` is not tabulated: it fits to
1.000 in every bin, so it ships as a constant.
"""

import numpy as np

#: Below this the model is not fitted at all.  Two independent failures
#: live there and neither is the model's: NEC returns non-physical negative
#: resistances, and the per-wire segment floor puts 12:1 grading on the
#: junction carrying the source, which does not converge away.  Both are
#: h/lambda is.  Fitting through them was making the coefficients describe
#: the solver rather than the antenna.
#:
#: The floor is 0.05 because that is where the page already stops claiming
#: accuracy, and because it is exactly where the bad data ends: at 0.02 some
#: 327 non-physical points survive, 23 percent of one group at 1.9 MHz over
#: poor ground, while at 0.05 there are none.  Fitting where the page claims
#: accuracy and extrapolating flat below it is the same statement made once
#: instead of twice.
MIN_H_OVER_LAMBDA = 0.05

#: Nodes in h/lambda.  Spaced logarithmically over the range a real
#: installation reaches, from the exclusion floor to 25 m on 10 m.  Below
#: the first node the table is held flat, which is honest extrapolation
#: rather than a fit to points NEC could not solve.
NODES = np.array([0.05, 0.09, 0.16, 0.28, 0.5, 0.9, 1.6, 2.5])

#: Tabulated per soil per node.  vf_a is constant, see the module docstring.
TABLE_PARAMS = ("alpha_a_lam", "ka", "alpha_r_lam", "vf_r", "kr")

#: Bounds for the joint refinement, in TABLE_PARAMS order, taken from the span
#: the per-group fits reach and rounded outwards.  Left at fit.py's much looser
#: search bounds the refinement buys accuracy by pushing a Z0 scale to 2.7,
#: which is a line form that has stopped describing a wire: the table would be
#: compensating for the model rather than fitting the antenna.  Plausibility is
#: asserted again on the far side, in docs/tools/model.test.mjs.
REFINE_BOUNDS = (
    (0.02, 0.4, 0.05, 0.35, 0.4),
    (0.40, 1.6, 3.00, 1.00, 1.6),
)

#: The antenna line's velocity factor, constant rather than tabulated.
VF_A = 1.0

#: Nodes in counterpoise height over wavelength, the table's second axis.
#: Log spaced over what a real installation reaches, held flat outside them
#: as h/lambda is.  Both axes divide by the same wavelength, so a counterpoise
#: fixed in metres cannot span this one at a short wavelength.
Z_NODES = np.array([1e-4, 1e-3, 8e-3, 6e-2])

#: Fitted-parameter index of each tabulated name, into fit.PARAM_NAMES.
SOURCE_INDEX = (0, 2, 3, 4, 5)
