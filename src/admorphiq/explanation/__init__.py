"""R58 EXPLANATION layer — harness-enforced protocol compiler (Navigation Vertical
Slice v0).

See ``docs/r58_codex_explanation_layer_20260715.md`` for the design verdict
this package implements. Deliberately separate from
:mod:`admorphiq.repl_agent` (that harness is running live experiments; this
package is built to plug into it later, not to replace it mid-flight).
"""

from admorphiq.explanation.protocol import (
    CONSUME,
    FILL,
    FUNNEL_INTENT_ABANDONED,
    FUNNEL_INTENT_SELECTED,
    FUNNEL_KERNEL_INVOKED,
    FUNNEL_OPPORTUNITY,
    FUNNEL_PREDICTION_VERIFIED,
    FUNNEL_RESULT_CONSUMED,
    FUNNEL_SLOTS_VALID,
    SELECT,
    VERIFY,
    ExplanationProtocol,
    HandleStore,
    compute_navigation,
    validate,
)

__all__ = [
    "CONSUME",
    "FILL",
    "FUNNEL_INTENT_ABANDONED",
    "FUNNEL_INTENT_SELECTED",
    "FUNNEL_KERNEL_INVOKED",
    "FUNNEL_OPPORTUNITY",
    "FUNNEL_PREDICTION_VERIFIED",
    "FUNNEL_RESULT_CONSUMED",
    "FUNNEL_SLOTS_VALID",
    "SELECT",
    "VERIFY",
    "ExplanationProtocol",
    "HandleStore",
    "compute_navigation",
    "validate",
]
