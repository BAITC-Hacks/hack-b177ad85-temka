"""Pilot-driven tariff campaigns using only the participant's public API.

Historical candidates select experiments, never final lift estimates. All
decision statistics are reset for each act(), so there is no cross-seed state.
"""

from math import ceil, isfinite, sqrt


class Agent:
    PER_CUSTOMER_STD = 0.804
    CONFIDENCE_Z = 1.645  # One-sided 95% bound; heuristic under adaptive selection.
    MAX_CAMPAIGNS = 10
    MAX_CAMPAIGN_SIZE = 5000

    @staticmethod
    def _hypotheses():
        """Asan's candidate_handoff.txt, commit 176723eebe50d36be7596f68201858c3e7fb9ca7.

        Bundle identifiers only so submitting agent.py needs no report file.
        No historical lift, conversion rate or mock effect is encoded here.
        These are experiments, not predetermined winning campaigns.
        All eight priorities and four reserves get an initial pilot; reserves
        are not conditionally activated in this shortlist-only comparison.
        """
        return [
            ("tariff_15", "MID", "tariff_8"),
            ("tariff_4", "MID", "tariff_8"),
            ("tariff_13", "MID", "tariff_8"),
            ("tariff_3", "MID", "tariff_8"),
            ("tariff_8", "MID", "tariff_10"),
            ("tariff_15", "MID", "tariff_10"),
            ("tariff_10", "MID", "tariff_8"),
            ("tariff_12", "MID", "tariff_8"),
            ("tariff_15", "MID", "tariff_4"),
            ("tariff_15", "MID", "tariff_9"),
            ("tariff_11", "HIGH", "tariff_12"),
            ("tariff_13", "MID", "tariff_4"),
        ]

    @staticmethod
    def _slices(frame, filters):
        """Represent smaller audiences using only the allowed campaign filters."""
        yield frame, filters
        columns = [c for c in ("data_segment", "call_segment") if c in frame]
        for col in columns:
            for value, sub in frame.groupby(col, observed=True, sort=True):
                yield sub, dict(filters, **{"filter_" + col: value})
        if len(columns) == 2:
            for values, sub in frame.groupby(columns, observed=True, sort=True):
                yield sub, dict(filters, **dict(zip(("filter_" + c for c in columns), values)))

    def _candidates(self, env):
        profile = env.customer_profile
        known = set(env.tariffs["tariff_plan_code"])
        cells = {key: sub for key, sub in profile.groupby(
            ["current_tariff", "arpu_segment"], observed=True, sort=True)}
        hypotheses = self._hypotheses()
        if not hypotheses:
            # Last-resort experiments, not assertions that higher prices imply lift.
            hypotheses = [(cur, seg, target) for cur, seg in cells
                          for target in sorted(known) if target != cur]
        candidates, seen = [], set()
        for current, segment, target in hypotheses:
            key = (current, segment, target)
            if key in seen or target not in known or target == current or (current, segment) not in cells:
                continue
            seen.add(key)
            filters = {"filter_current_tariff": current, "filter_arpu_segment": segment}
            options = [(sub, fs) for sub, fs in self._slices(cells[current, segment], filters)
                       if 0 < len(sub) <= self.MAX_CAMPAIGN_SIZE]
            if not options:
                continue
            # A single representative subcell if the parent exceeds 5,000.
            sub, filters = max(options, key=lambda item: len(item[0]))
            candidates.append({"cell": (current, segment), "target": target,
                               "frame": sub, "filters": filters, "n": 0,
                               "weighted_sum": 0.0, "runs": 0, "failed": False})
            if len(candidates) == 12:
                break
        return candidates

    def _bounds(self, candidate):
        n = candidate["n"]
        if not n:
            return 0.0, float("inf")
        return candidate["weighted_sum"] / n, self.PER_CUSTOMER_STD / sqrt(n)

    @staticmethod
    def _channel_factor(source_multiplier, target_multiplier):
        # Conversion is capped at 1. For positive lift this is a LOWER bound
        # on the target/source ratio for any underlying probability in [0, 1].
        return min(target_multiplier / source_multiplier,
                   min(target_multiplier, 1.0) / min(source_multiplier, 1.0))

    def _pilot(self, env, candidate, requested):
        if candidate["failed"] or env.pilots_left <= 0 or self._attempts >= 20:
            return False
        channel = env.channels[self._pilot_channel]
        cost = float(channel["cost_per_contact"])
        room = min(env.remaining_contacts - self._reserve_contacts,
                   self._contact_cap - self._pilot_contacts)
        if cost > 0:
            room = min(room, env.remaining_budget // cost,
                       (self._money_cap - self._pilot_cost) // cost)
        n = int(min(200, requested, len(candidate["frame"]), room))
        if n < 10:
            return False
        self._attempts += 1
        before_money, before_contacts = env.remaining_budget, env.remaining_contacts
        try:
            result = env.run_pilot(target_tariff=candidate["target"],
                                   channel=self._pilot_channel, n_customers=n,
                                   **candidate["filters"])
            actual = int(result["n_customers"])
            ratio = float(result["observed_lift_ratio"])
            if not 0 < actual <= n or not isfinite(ratio):
                raise ValueError("Invalid pilot sample size or non-finite lift")
            candidate["weighted_sum"] += actual * ratio
            candidate["n"] += actual
            candidate["runs"] += 1
            return True
        except Exception as exc:
            # API errors may happen AFTER a charge. Read balances, never refund
            # or fabricate an observation, and keep valid earlier measurements.
            candidate["failed"] = True
            self.pilot_errors.append(f"{candidate['cell']} -> {candidate['target']}: {type(exc).__name__}: {exc}")
            return False
        finally:
            self._pilot_cost += max(0, before_money - env.remaining_budget)
            self._pilot_contacts += max(0, before_contacts - env.remaining_contacts)

    def _options(self, env, candidate, money, contacts):
        mean, se = self._bounds(candidate)
        lower = mean - self.CONFIDENCE_Z * se
        if candidate["runs"] < 2 or lower <= 0:
            return []
        source = float(env.channels[self._pilot_channel]["conversion_multiplier"])
        # Subtracting all pilot contacts is conservative when repeated random
        # samples contain the same IDs. Pilot IDs are not exposed by the API.
        covered_fraction = min(1.0, candidate["n"] / len(candidate["frame"]))
        options = []
        for frame, filters in self._slices(candidate["frame"], candidate["filters"]):
            n = len(frame)
            if not 0 < n <= min(self.MAX_CAMPAIGN_SIZE, contacts):
                continue
            arpu = float(frame["predicted_arpu"].sum())
            for name in sorted(env.channels):
                info = env.channels[name]
                cost = n * float(info["cost_per_contact"])
                if cost > money:
                    continue
                factor = self._channel_factor(source, float(info["conversion_multiplier"]))
                # On previously contacted clients only the improvement over the
                # pilot channel counts. Full final contact cost still applies.
                incremental = (1 - covered_fraction) * factor + covered_fraction * max(0, factor - 1)
                gain = lower * arpu * incremental - cost
                if isfinite(gain) and gain > 0:
                    campaign = dict(filters, target_tariff=candidate["target"], channel=name,
                                    campaign_name=f"main_{candidate['cell'][0]}_{candidate['cell'][1]}_{candidate['target']}")
                    options.append((gain, cost, n, campaign))
        return options

    def _fallback(self, env, candidates):
        """A small free campaign to meet the mandatory nonempty-plan contract.

        If every effect is negative, no algorithm can guarantee a profit. This
        fallback limits exposure; it does not pretend that a loss is safe.
        """
        free = [c for c in sorted(env.channels) if env.channels[c]["cost_per_contact"] == 0]
        if not free:
            return []
        free_channel = min(free, key=lambda c: env.channels[c]["conversion_multiplier"])
        ranked = sorted(candidates, key=lambda c: (
            c["n"] > 0, self._bounds(c)[0] - self.CONFIDENCE_Z * self._bounds(c)[1]), reverse=True)
        for candidate in ranked:
            slices = [(sub, filters) for sub, filters in self._slices(candidate["frame"], candidate["filters"])
                      if 0 < len(sub) <= min(self.MAX_CAMPAIGN_SIZE, env.remaining_contacts)]
            if slices:
                _, filters = min(slices, key=lambda item: (len(item[0]), float(item[0]["predicted_arpu"].sum())))
                self.used_fallback = True
                return [dict(filters, campaign_name="limited_fallback",
                             target_tariff=candidate["target"], channel=free_channel)]
        return []  # No nonempty legal audience fits the remaining limits.

    def act(self, env):
        self.pilot_errors = []
        self.used_fallback = False
        self._attempts = self._pilot_contacts = self._pilot_cost = 0
        candidates = self._candidates(env)
        if not candidates:
            return []
        self._reserve_contacts = min(
            len(sub) for c in candidates for sub, _ in self._slices(c["frame"], c["filters"]) if len(sub))
        self._contact_cap = max(0, min(int(env.remaining_contacts * 0.2),
                                      int(env.remaining_contacts) - self._reserve_contacts))
        self._money_cap = max(0, float(env.remaining_budget) * 0.15)
        self._pilot_channel = "sms" if "sms" in env.channels else min(
            env.channels, key=lambda c: env.channels[c]["cost_per_contact"])
        if self._money_cap < 10 * env.channels[self._pilot_channel]["cost_per_contact"]:
            self._pilot_channel = min(env.channels, key=lambda c: env.channels[c]["cost_per_contact"])

        # First-stage exploration of up to 12 historical hypotheses.
        for candidate in candidates:
            self._pilot(env, candidate, 60)

        # Confirm up to four DISTINCT cells. An optimistic bound lets an
        # uncertain but valuable cell earn a confirmation experiment.
        def priority(c):
            mean, se = self._bounds(c)
            return (mean + self.CONFIDENCE_Z * se) * float(c["frame"]["predicted_arpu"].sum())

        confirmed_cells = set()
        for candidate in sorted((c for c in candidates if c["n"]), key=priority, reverse=True):
            if candidate["cell"] in confirmed_cells or len(confirmed_cells) >= 4:
                continue
            mean, se = self._bounds(candidate)
            if mean + self.CONFIDENCE_Z * se <= 0:
                continue
            if self._pilot(env, candidate, 150):
                confirmed_cells.add(candidate["cell"])

        # Repeat positive/ambiguous candidates. Required n targets a positive
        # conservative bound, capped by the API's per-pilot limit.
        while self._attempts < 20 and env.pilots_left > 0:
            pending = []
            for c in candidates:
                if not c["n"] or c["failed"]:
                    continue
                mean, se = self._bounds(c)
                if mean + self.CONFIDENCE_Z * se <= 0:
                    continue
                if c["runs"] >= 2 and mean - self.CONFIDENCE_Z * se > 0:
                    continue
                pending.append(c)
            if not pending:
                break
            candidate = max(pending, key=priority)
            mean, _ = self._bounds(candidate)
            # Compare before dividing: tiny positive means should request the
            # maximum sample, not overflow while computing a target n.
            threshold = self.CONFIDENCE_Z * self.PER_CUSTOMER_STD / sqrt(candidate["n"] + 200)
            wanted = (ceil((self.CONFIDENCE_Z * self.PER_CUSTOMER_STD / mean) ** 2)
                      - candidate["n"]) if mean > threshold else 200
            if not self._pilot(env, candidate, max(100, min(200, wanted))):
                if candidate["failed"]:
                    continue
                break

        money, contacts = float(env.remaining_budget), int(env.remaining_contacts)
        selected, used_cells = [], set()
        while len(selected) < self.MAX_CAMPAIGNS:
            offers = [(option, c["cell"]) for c in candidates if c["cell"] not in used_cells
                      for option in self._options(env, c, money, contacts)]
            if not offers:
                break
            (gain, cost, n, campaign), cell = max(offers, key=lambda item: (item[0][0], -item[0][1]))
            selected.append(campaign)
            used_cells.add(cell)
            money -= cost
            contacts -= n
        return selected or self._fallback(env, candidates)
