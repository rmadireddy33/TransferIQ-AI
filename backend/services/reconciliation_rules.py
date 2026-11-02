"""Pure deterministic reconciliation. Inputs/outputs are serializable evidence snapshots."""
from collections import defaultdict
from decimal import Decimal, Inexact, InvalidOperation, localcontext

RULE_VERSION = "reconciliation-1"


def decimal_text(value):
    if value is None:
        return None
    text = format(Decimal(value), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def identity_evidence(source, target, security, mappings):
    canonical = security["canonical_identifier"]
    old = source.get("observed_identifier") or canonical
    new = target.get("observed_identifier") or canonical
    if old == new == canonical:
        return [], None
    sd, td = source["snapshot_date"], target.get("snapshot_date")
    if not sd or not td or sd >= td or new != canonical:
        return [], "Identifier change lacks a forward dated comparison to the canonical identifier"
    candidates = [m for m in mappings if m["old_identifier"] == old and m["verified"]
                  and (m.get("evidence_reference") or "").strip() and sd < m["effective_date"] <= td]
    if len(candidates) != 1:
        return [], "Identifier mapping is missing, unverified, or ambiguous"
    mapping = candidates[0]
    if mapping["new_identifier"] != new or mapping["canonical_security_id"] != security["security_id"]:
        return [], "Identifier mapping does not link both observations to this canonical security"
    return [mapping["evidence_reference"]], None


def normalized_quantity(source, target, actions):
    quantity = Decimal(source["quantity"])
    sd, td = source["snapshot_date"], target.get("snapshot_date")
    if not sd or not td:
        return (None if actions else quantity), [], "Snapshot dates are insufficient for corporate-action normalization"
    low, high = sorted((sd, td))
    applicable = sorted([a for a in actions if low < a["effective_date"] <= high],
                        key=lambda a: (a["effective_date"], a["corporate_action_id"]), reverse=sd > td)
    dates = [a["effective_date"] for a in applicable]
    evidence_ids = [a["evidence_reference"] for a in applicable if a.get("evidence_reference")]
    if len(dates) != len(set(dates)) or len(evidence_ids) != len(set(evidence_ids)):
        return None, [], "Duplicate or ambiguous corporate actions on the same effective date"
    refs = []
    try:
        for action in applicable:
            if (not action["verified"] or not (action.get("evidence_reference") or "").strip()
                    or action["action_type"] not in {"SPLIT", "REVERSE_SPLIT"}
                    or action["numerator"] <= 0 or action["denominator"] <= 0):
                return None, [], "Corporate-action reference is unsupported, unverified, or lacks evidence"
            n, d = Decimal(action["numerator"]), Decimal(action["denominator"])
            if sd > td:
                n, d = d, n
            quantity = quantity * n / d
            refs.append(action["evidence_reference"])
        if quantity >= Decimal("1e18") or quantity != quantity.quantize(Decimal("0.00000001")):
            return None, [], "Normalized quantity exceeds supported precision/range; no rounding policy exists"
    except (Inexact, InvalidOperation):
        return None, [], "Split creates unsupported fractional precision; manual investigation required"
    return quantity, refs, None


def evaluate(inputs):
    # Never depend on ambient Decimal settings or silently round financial values.
    with localcontext() as context:
        context.prec = 80
        context.traps[Inexact] = True
        return _evaluate(inputs)


def _evaluate(inputs):
    sources, targets, bases = defaultdict(list), defaultdict(list), defaultdict(list)
    securities = {s["security_id"]: s for s in inputs["securities"]}
    for row in inputs["source"]:
        sources[row["security_id"]].append(row)
    for row in inputs["target"]:
        targets[row["security_id"]].append(row)
    for row in inputs["cost_basis"]:
        bases[row["security_id"]].append(row)
    positions, exceptions = [], []

    def exception(sid, kind, description, source=None, target=None, expected=None,
                  refs=None, status="UNRESOLVED", category="POSITION"):
        difference = None if target is None or expected is None else Decimal(target) - Decimal(expected)
        item = dict(security_id=sid, exception_type=kind, severity="INFO" if status == "EXPLAINED" else "WARNING",
                    source_quantity=decimal_text(source), target_quantity=decimal_text(target),
                    expected_quantity=decimal_text(expected), difference=decimal_text(difference),
                    description=description, evidence_references=sorted(set(refs or [])), resolution_status=status)
        exceptions.append(item)
        if category == "POSITION":
            positions.append({**item, "classification": "EXPLAINED" if status == "EXPLAINED" else "UNRESOLVED"})

    for sid in sorted(sources.keys() | targets.keys()):
        left, right = sources[sid], targets[sid]
        if len(left) > 1 or len(right) > 1:
            exception(sid, "DUPLICATE_POSITION", "Multiple rows identify the same canonical security; aggregation is not supported")
            continue
        if not left:
            exception(sid, "EXTRA_SECURITY", "Security exists only in receiving staging", target=right[0]["quantity"])
            continue
        if not right:
            exception(sid, "MISSING_SECURITY", "Security is absent from receiving staging", source=left[0]["quantity"], expected=left[0]["quantity"])
            continue
        source, target = left[0], right[0]
        sq, tq = Decimal(source["quantity"]), Decimal(target["quantity"])
        if target["status"] != "STAGED":
            exception(sid, "REQUIRES_INVESTIGATION", "Unsupported staging record status", sq, tq)
            continue
        id_refs, id_error = identity_evidence(source, target, securities[sid], inputs["mappings"])
        if id_error:
            exception(sid, "SECURITY_IDENTIFIER_CHANGE", id_error, sq, tq, status="REQUIRES_INVESTIGATION")
            continue
        actions = [a for a in inputs["actions"] if a["security_id"] == sid]
        expected, action_refs, action_error = normalized_quantity(source, target, actions)
        # Missing dates permit raw equality only. They never support normalization.
        if expected is None:
            exception(sid, "REQUIRES_INVESTIGATION", action_error, sq, tq)
        elif expected != tq:
            exception(sid, "QUANTITY_MISMATCH", "Receiving minus expected quantity differs. " +
                      (action_error or "No verified evidence explains the remaining difference."),
                      sq, tq, expected, id_refs + action_refs)
        elif action_refs or id_refs:
            kind = "CORPORATE_ACTION_TIMING" if action_refs else "SECURITY_IDENTIFIER_CHANGE"
            exception(sid, kind, "Verified reference evidence explains the difference; no position was changed",
                      sq, tq, expected, id_refs + action_refs, status="EXPLAINED")
        else:
            positions.append(dict(security_id=sid, classification="MATCHED", source_quantity=decimal_text(sq),
                                  target_quantity=decimal_text(tq), expected_quantity=decimal_text(expected),
                                  difference="0", evidence_references=[]))

    # Basis completeness is independent from quantity reconciliation. No prices or
    # amounts are fabricated; zero documented basis is distinct from missing basis.
    for sid in sorted(targets.keys() | bases.keys()):
        lots = bases[sid]
        target_rows = targets[sid]
        if len(target_rows) != 1:
            if lots:
                exception(sid, "COST_BASIS_INCONSISTENT", "Basis has no unique receiving staging position", category="COST_BASIS")
            continue
        target = target_rows[0]
        if not lots or any(lot["quantity"] is None or lot["cost_basis_amount"] is None
                           or not lot["acquisition_date"] or lot["status"] != "COMPLETE"
                           or not (lot.get("evidence_reference") or "").strip() for lot in lots):
            exception(sid, "COST_BASIS_MISSING", "Cost-basis data is absent or incomplete; quantity outcome is independent",
                      target=target["quantity"], category="COST_BASIS")
        elif (sum((Decimal(lot["quantity"]) for lot in lots), Decimal(0)) != Decimal(target["quantity"])
              or any(target.get("snapshot_date") and lot["acquisition_date"] > target["snapshot_date"] for lot in lots)
              or len({(lot["acquisition_date"], lot["evidence_reference"]) for lot in lots}) != len(lots)):
            exception(sid, "COST_BASIS_INCONSISTENT", "Basis lot quantities, acquisition dates, or duplicate evidence conflict",
                      target=target["quantity"], refs=[lot["evidence_reference"] for lot in lots], category="COST_BASIS")

    direct = sum(p["classification"] == "MATCHED" for p in positions)
    explained = sum(p["classification"] == "EXPLAINED" for p in positions)
    unresolved = len(positions) - direct - explained
    basis_issues = sum(e["exception_type"].startswith("COST_BASIS_") for e in exceptions)
    return dict(total_positions=len(positions), directly_matched=direct, evidence_explained=explained,
                unresolved_count=unresolved, cost_basis_issues=basis_issues, position_results=positions,
                status="EXCEPTIONS_DETECTED" if unresolved or basis_issues else "RECONCILED", exceptions=exceptions)
