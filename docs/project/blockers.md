# Cateniq blockers and open questions

Updated: 2026-10-22

These are scoped implementation gates, not evidence that the project is currently blocked. Documentation setup and planning are complete. Task execution status belongs in the [backlog](backlog.md).

<a id="blk-001"></a>

## BLK-001 — Numerical profile and independent validation

- Identified: 2026-10-22
- Status: Resolved (2026-10-22)
- Affected tasks/milestones: [CAT-004](backlog.md#cat-004), CAT-005, CAT-007; M1/M2.
- Question: Which bounded catenary parameterisation and residual/support checks reliably distinguish the initial endpoint-error scenario from sparse or unsupported evidence?
- Impact: No numerical implementation can be called correct until units, constraints, conditioning checks and error tolerances are specified and independently evaluated.
- Blocking scope: Gates dependent fixture/fitter acceptance, not workspace bootstrap or the profile investigation itself.
- Evidence: The concept proposes catenary geometry; no numerical code or benchmark exists. This is a planning gate, not a failed solver attempt.
- Next action / owner: Implementing agent completes CAT-004 using primary mathematical references and hand-checkable/independently derived fixtures; freeze the supported domain and limitations.
- Resolution: Profile frozen in `backend/src/cateniq/geometry/profile.py` (vertex-form catenary, a in [3, 5000] m, spans 10–120 m, sag/span <= 0.20, evidence gates and tolerances). Feasibility validated by 19 independently derived reference checks; measured errors sit orders of magnitude inside the frozen tolerances. See `docs/project/evidence/geometry-profile.md`; vertex-bracketing gate was dropped after it rejected a supported unequal-height case.

<a id="blk-002"></a>

## BLK-002 — Endpoint interaction and performance budgets

- Identified: 2026-10-22
- Status: Resolved (re-verified 2026-10-23)
- Affected tasks/milestones: [CAT-006](backlog.md#cat-006), CAT-008, CAT-012; M1 interaction and M4 performance acceptance.
- Question: Which constrained editing/snapping interaction is usable with occluded points, and what measured budgets fit the chosen reference machine and workload?
- Impact: A nominal frame-rate claim cannot establish selection/edit usability or memory behaviour.
- Blocking scope: Gates interaction/performance acceptance, not the initial prototype. No user answer is currently required.
- Evidence: Roughly 100,000 points is an initial representative workload; no Cateniq browser measurements exist.
- Next action / owner: CAT-006 implementing agent corrects occlusion regression assertions and performance sampling; see [independent review](evidence/m1-exit-review.md) and [interaction evidence](evidence/endpoint-interaction.md).
- Prior resolution (follow-up verification corrections outstanding): Plane-constrained endpoint drag with 0.6 m snap to declared attachment candidates, plus numeric editing; selected-span handles, blocker-aware pick ordering (nearest visible hit; occluded handles unreachable), co-located-handle and bird's-eye occlusion verified in-browser. Budgets frozen on the named reference machine at the 100,200-point workload: load ≤5 s, select ≤1 s, edit ≤1 s, commit ≤1 s, frame p50 ≤50 ms / p95 ≤150 ms; resource observations recorded (flat heap, identical rebuild). Evidence: `docs/project/evidence/endpoint-interaction.md` (Playwright-measured).
