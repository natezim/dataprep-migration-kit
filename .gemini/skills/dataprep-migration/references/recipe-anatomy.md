# Recipe anatomy — reading exported Dataprep flow packages

How Dataprep exports a flow, so `@flow-inventory` and `@recipe-translator` can parse it.

## Getting the package — API-optional

Two routes produce the **identical ZIP** of JSON descriptors; everything downstream is the same:
- **API (fast path):** `GET /v4/flows/{id}/package` (auth: API access token in the Authorization
  header). Catalog can be seeded from an API sweep of `GET /v4/flows`. Best for repeatability
  across ~100 flows.
- **UI (no API needed):** Flow menu → **"Export Flow"** downloads the same ZIP. Some LOBs have no
  API access — this route is fully supported, and the catalog can instead be seeded from a pasted
  flow list.

## Flow package directory schema

| Path | Format | What it holds |
|---|---|---|
| `flow.json` | JSON | Master metadata: node IDs, ownership, environment parameters, global config |
| `recipes/` | dir of JSON | One structure per recipe — the ordered, raw **Wrangle DSL** commands (the logic to translate) |
| `inputs/` | dir of JSON | Upstream source mappings (BigQuery tables, GCS URIs, relational connections) |
| `outputs/` | dir of JSON | Publish destinations: target format (CSV/JSON/Avro/Parquet), compression, ingestion pattern (New/Update/Truncate/Load) |
| `webhooks/` | dir of JSON | Event-driven tasks on pipeline state transitions (usually not migrated) |
| `*.data` | binary/CSV | Artifacts for Transformation-by-Example (TBE) steps and manual cluster clean-value overrides — **flag these: they don't transpile cleanly** |

## The DAG: nodes + edges

The flow is a Directed Acyclic Graph. **Flow nodes** = unique immutable IDs for every object
(imported datasets, recipes, outputs). **Flow edges** map direction by linking
`inputFlownode.id → outputFlownode.id`. To resolve dependencies (and detect flow→flow links):

1. `getFlowInputs` → collect source metadata; grab each dataset's `parsingRecipe.id`.
2. `listFlows` with `?embed=flownodes` → find the node whose nested `recipe.id` matches that
   `parsingRecipe.id`; take that node's `id`.
3. `?embed=flowEdges` → find the edge whose `inputFlownode.id` matches; its `outputFlownode.id`
   is the downstream target. These edges are the dependency graph → `ref()` / read order.

> A flow whose **input** resolves to another flow's **output** is an inter-flow dependency.
> Migrate upstream flows first.

## What to extract per flow

`{ flow_id, name, inputs[], outputs[], recipes:[{order, verb, params, original_wrangle}],
   edges[], output_format, ingestion_pattern, has_tbe_or_cluster_overrides }`

- Source/target table names → `ref()` / `read_gbq` / `to_gbq`.
- Each recipe step's raw Wrangle text → quote verbatim in the output comment.
- `*.data` presence, nested types, non-CSV inputs, multi-dataset joins/unions → these disqualify
  the rare native code-gen accelerator (CSV-only, no multi-dataset; see `wrangle-to-python.md`
  → *Path A*); transpile instead.

## TODO on first real export

- [ ] Confirm exact JSON keys inside `recipes/*.json` for step type + params (versions vary).
- [ ] Note how multi-output flows and parameterized datasets are represented.
- [ ] Capture a real `flow.json` sample into `context/` as the reference fixture.
