"""Replayable genealogy: every agent has id, parents, birth/death generation, operator, fitness.

op codes: 0 = founder (random init), 1 = clone + mutation, 2 = crossover + mutation.
Old branches are pruned to the ancestry closure of living agents, archive elites
and recent champions so checkpoints stay bounded.
"""
from __future__ import annotations

import numpy as np

OP_NAMES = {0: "founder", 1: "clone+mutation", 2: "crossover+mutation"}


class Lineage:
    # row: [parent1, parent2, born, op, n_mut, died, best_f, last_f]
    def __init__(self):
        self.rows: dict[int, list] = {}
        self.next_id = 0
        self.pruned = 0

    def new_ids(self, n: int) -> np.ndarray:
        ids = np.arange(self.next_id, self.next_id + n, dtype=np.int64)
        self.next_id += n
        return ids

    def birth(self, ids, p1, p2, gen, op, nmut):
        for i in range(len(ids)):
            self.rows[int(ids[i])] = [int(p1[i]), int(p2[i]), int(gen), int(op[i]), int(nmut[i]), -1, -9.0, -9.0]

    def observe(self, ids, f):
        for i, x in zip(ids, f):
            r = self.rows.get(int(i))
            if r is not None:
                r[7] = float(x)
                if x > r[6]:
                    r[6] = float(x)

    def death(self, ids, gen):
        for i in ids:
            r = self.rows.get(int(i))
            if r is not None and r[5] < 0:
                r[5] = int(gen)

    def ancestry(self, agent_id: int, max_depth: int = 10_000) -> list[int]:
        """Primary-parent chain from agent back to a founder (or pruned stub)."""
        chain, cur = [], int(agent_id)
        while cur in self.rows and len(chain) < max_depth:
            chain.append(cur)
            p1 = self.rows[cur][0]
            if p1 < 0:
                break
            cur = p1
        return chain

    def closure(self, roots) -> set[int]:
        keep, stack = set(), [int(r) for r in roots if int(r) >= 0]
        while stack:
            i = stack.pop()
            if i in keep or i not in self.rows:
                continue
            keep.add(i)
            stack.extend(p for p in self.rows[i][:2] if p >= 0)
        return keep

    def prune(self, roots):
        keep = self.closure(roots)
        before = len(self.rows)
        self.rows = {i: r for i, r in self.rows.items() if i in keep}
        self.pruned += before - len(self.rows)

    def founder_of(self, agent_id: int) -> int:
        chain = self.ancestry(agent_id)
        return chain[-1] if chain else int(agent_id)

    def get_state(self):
        ids = np.array(sorted(self.rows), dtype=np.int64)
        tab = np.array([self.rows[int(i)] for i in ids], dtype=np.float64).reshape(len(ids), 8)
        return {"ids": ids, "table": tab, "next_id": self.next_id, "pruned": self.pruned}

    def set_state(self, s):
        ids, tab = np.asarray(s["ids"]), np.asarray(s["table"])
        self.rows = {}
        for i, r in zip(ids, tab):
            self.rows[int(i)] = [int(r[0]), int(r[1]), int(r[2]), int(r[3]), int(r[4]), int(r[5]),
                                 float(r[6]), float(r[7])]
        self.next_id = int(s["next_id"])
        self.pruned = int(s["pruned"])
