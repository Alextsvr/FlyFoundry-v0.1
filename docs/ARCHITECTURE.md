# Architecture

`environments/` hidden benchmark + budgeted Evaluator · `agents/` arms (controller population, GA, random, LLM adapter) · `biology/` mushroom-body
model · `evolution/` MAP-Elites archive, lineage · `evaluation/` fitness sharing, diversity, bootstrap stats · `research/` runner, experiment,
analysis, opportunities, provenance · `storage/` exact serialisation + checkpoints · `reporting/` SVG charts + HTML/markdown/CSV/JSON · `cli/`.
Data flow: Experiment → ArmRunner(arm, seed) → arm.step(Evaluator) → history → checkpoint payload → analysis → report.
Genealogy: each agent has id, parents, birth/death generation, operator, #mutations, best/last fitness; pruned to the ancestry of living agents,
archive elites and recent champions; hypotheses carry arm, seed, agent id, parent and ancestry chain.
