# ADE Config Packages - Research & Refinement

## 1. Executive Summary

**ADE's config package design is solid**, but a few targeted improvements can enhance its **usability, explainability, and safety** without adding complexity. We recommend five subtle changes:

- **Structured Manifest Schema & Versioning (Do Now):** Define a JSON Schema for manifest.json and adopt semantic versioning for the config format. This provides **built-in validation** of configs and clear evolution paths (similar to how dbt and Airbyte attach schemas/versions to their artifacts[\[1\]](https://docs.getdbt.com/reference/artifacts/manifest-json#:~:text=You%20can%20refer%20to%20dbt,and%20consuming%20dbt%20generated%20artifacts)[\[2\]](https://docs.getdbt.com/guides/building-packages#:~:text=just%20created,version%20config)). It improves authoring experience (early error catching) and ensures backward-compatible upgrades.
- **Standard Rule Library & Scoring Conventions (Do Now):** Introduce a lightweight **helper library** for common detector logic (synonym matching, regex patterns, date parsing, etc.) and establish **scoring guidelines** (e.g. score range normalization, use of negative deltas, minimum confidence thresholds). This boosts developer **ergonomics** and consistency - much like Pandera's built-in checks for typical patterns[\[3\]](https://pandera.readthedocs.io/en/stable/checks.html#:~:text=schema%20%3D%20pa.DataFrameSchema%28%7B%20,) - while keeping the "behavior-as-code" flexible. Clear conventions (e.g. treat scores as 0.0-1.0 probabilities) make mapping outcomes more explainable.
- **Enhanced Validation Model (Do Now/Later):** Expand validation capabilities with **standard issue codes/severities** and a path for simple **cross-field checks**. We'll define a canonical set of validation codes (akin to Great Expectations' expectations library) and encourage use of severity = "warning" for non-critical issues. For cross-field rules (e.g. start_date <= end_date), the immediate solution is to leverage the existing hook (e.g. in after_validate) with documented examples. Longer-term, we can consider a dedicated **"table validator"** script pattern for multi-column logic, but only if it can be done without breaking streaming. These steps keep **explainability** first-class by standardizing how issues are reported (similar to how Frictionless Data schemas allow field constraints for validation[\[4\]](https://specs.frictionlessdata.io//table-schema/#:~:text=The%20,updated%20via%20a%20data%20entry)).
- **Config Package Dependencies & Isolation (Do Now):** Allow config authors to include a **requirements.txt** for per-job Python dependencies, installed in an **isolated environment** at runtime. This enables richer logic (e.g. using regex or date libraries) without bloating the base image. The implementation would be a minimal pip install into a sandbox (opt-in via manifest), respecting the runtime_network_access flag. A small **lockfile** (with hashes) can optionally stabilize dependency versions for reproducibility. This approach mirrors best practices in plugin systems (dependency isolation) and Airbyte's connector packaging (each connector declares its own requirements) - all within our single-container constraint.
- **Test Harness and Artifact-Based QA (Do Now):** Develop a basic **config test kit** so authors can validate their packages easily. This includes a manifest linter (JSON Schema validation), the ability to run small sample spreadsheets through ADE in a CLI or CI mode, and **golden artifact** comparisons. We can supply example input files and expected artifact JSONs as a **Compatibility Test Suite**, similar to Airbyte's standard connector acceptance tests (which ensure every connector meets the spec expectations[\[5\]](https://docs.airbyte.com/platform/connector-development/testing-connectors/connector-acceptance-tests-reference#:~:text=To%20ensure%20a%20minimum%20quality,or%20invalid%29%20inputs)). This will raise confidence in config changes and catch regressions early. It's high-benefit for quality, with low complexity (leveraging the existing ADE engine in a test mode).

**Do Now vs. Later:** The first four improvements are feasible in the next 1-2 sprints and largely backward-compatible ("Do Now"). Cross-field validation enhancements and any advanced security features (e.g. code signing) can be phased in "Later" once core usability gains are delivered. Overall, these changes incrementally refine the author experience and trust in ADE's outputs without overhauling the architecture.

## 2. What We Have Today (Short Inventory)

**Current ADE Config Package Design:** An ADE config package is a self-contained folder (or zip) with a manifest and Python modules that define extraction rules. It encapsulates all logic for interpreting raw spreadsheets and producing a normalized output. Key elements of the design include:

- **Manifest (manifest.json):** Declares engine settings, the list of target fields (normalized columns), and references to each field's script. It includes the output column order, display labels, and metadata like synonyms and required/optional flags for each field. The manifest also configures engine behavior (e.g. timeouts, memory limits, whether to append unmapped columns) and optional hook scripts to run at various pipeline stages.
- **Script Modules:** The package has subfolders for different rule types:
- row_types/: Row classification rules for **Pass 1** (e.g. header.py, data.py) to detect header rows vs. data rows. Each defines one or more detect_\* functions that return score deltas for labels like "header" or "data".
- columns/: Column mapping rules for **Pass 2-4**. Each target field has its own &lt;field&gt;.py module containing:
  - detect_\* functions (one or many) for mapping - these examine a raw column's header or sample values and output a score for _that_ field. ADE aggregates these scores across all fields to decide the best mapping for each raw column.
  - An optional transform(values) to clean or standardize the column's values (executed in Pass 3).
  - An optional validate(values) to produce issues/warnings for that column (executed in Pass 4).
- hooks/: Optional lifecycle hooks (on_job_start.py, after_mapping.py, etc.) that run at defined points (before processing, after mapping, after transform, after validate). Hooks have access to the read-only artifact and can be used for custom logging, summary notes, or cross-cutting checks.
- **Pipeline Passes & Determinism:** ADE processes spreadsheets in five passes:
- **Find tables/headers (Pass 1):** Uses row_types detectors to label each row. From these labels, ADE infers table boundaries and header row positions.
- **Map columns (Pass 2):** For each column region in each detected table, ADE calls all columns/&lt;field&gt;.py: detect_\* functions. Each returns a score for its field (positive = evidence the column is that field, negative = evidence it is not). ADE sums scores by field; the highest scorer "wins" and the raw column is mapped to that target field (ties or low-confidence cases can result in an **unmapped** column).
- **Transform values (Pass 3):** For each mapped field, if a transform is defined, ADE applies it to the column's values (one column at a time, streaming rows through). Transforms typically clean data (e.g. trimming strings, parsing dates) and may emit per-column warnings (e.g. "X% of values were truncated").
- **Validate values (Pass 4):** If a validate function is present for the field, ADE invokes it with the (transformed) values. The function returns a list of issues (each with a row index, a code, severity, and message). These issues do **not** stop the pipeline; they are collected for reporting.
- **Write output (Pass 5):** ADE streams rows out to the normalized workbook (e.g. normalized.xlsx) according to the columns.order defined in the manifest. Unmapped columns can be appended (prefixed as raw_&lt;original header&gt;) if configured. At this stage, all decisions about structure and values are finalized.
- **Explainability via Artifact:** Throughout processing, ADE builds an **artifact JSON** - a comprehensive log of actions and decisions. The artifact records table ranges, which raw columns mapped to which fields (with scores and the specific detector rules that fired), any transformations applied, and validation issues (with references to cell locations). Notably, **no raw data values** are stored in the artifact - only references and metadata - for privacy. This artifact provides a transparent audit trail of _why_ each column was mapped a certain way or _why_ a validation error was raised.
- **Safety and Sandboxing:** Config code (the detectors/transforms/validators written by users) runs in an isolated subprocess. By contract, these scripts must be side-effect free (no file I/O, no global state changes). ADE enforces timeouts and memory limits (from engine.defaults in the manifest) to prevent runaway code, and by default disables network access during rule execution for security. The isolation ensures that a buggy or malicious config script cannot crash the main service or access unauthorized resources.
- **Lifecycle & Version Control:** ADE treats config packages as versioned entities. Only one config is "active" (in use for jobs) in a workspace; others remain as editable drafts or archived snapshots. Each update to a config creates a new version (immutable archive of the old state). Users can export a package as a zip (for backup or migration) and import packages - facilitating reuse across projects. Promotion workflow: you develop and test in a draft, then mark it active (which archives the previous active config). This provides traceability of changes and easy rollback by re-activating an archived version if needed.

**In summary,** ADE's current design provides a clear separation of concerns: the manifest as a **declarative spec** of fields and settings, and the Python scripts as **imperative rules** for detection and cleaning. The system achieves flexibility (users can code custom logic) while maintaining determinism and an audit trail. The goal of the following research is to preserve these strengths - simplicity, explainability, single-process deployment - and refine the edges to improve the authoring experience and robustness.

## 3. Survey of Comparable Systems (with citations)

To inform improvements, we surveyed patterns from several analogous systems in data processing, schema packaging, and plugin sandboxing:

- **dbt (Data Build Tool):** dbt treats transformations as code, packaged into **projects** that can be versioned and shared. It uses a central dbt_project.yml manifest to define models, sources, and config. Notably, dbt attaches a **manifest JSON artifact** on each run that fully describes the project state (models, tests, macros) with a versioned JSON Schema[\[1\]](https://docs.getdbt.com/reference/artifacts/manifest-json#:~:text=You%20can%20refer%20to%20dbt,and%20consuming%20dbt%20generated%20artifacts). This ensures that any tooling consuming the manifest knows its schema version and can validate accordingly. dbt also requires packages to declare a range of compatible dbt Core versions (require-dbt-version in the config) to avoid compatibility issues[\[2\]](https://docs.getdbt.com/guides/building-packages#:~:text=just%20created,version%20config). Moreover, dbt packages follow semantic versioning, and there's an official package hub for community macros/models, encouraging reuse. The key takeaways for ADE: adopt a similar rigor in manifest versioning and compatibility declaration, and treat config packages as first-class versioned units of logic.
- **Frictionless Data (Table Schema & Data Package):** The Frictionless standards define a JSON-based **Table Schema** for tabular data, which lists fields with metadata like type, format, and constraints[\[4\]](https://specs.frictionlessdata.io//table-schema/#:~:text=The%20,updated%20via%20a%20data%20entry). For example, a field can have a regex pattern constraint or a "required" flag, and any dataset conforming to this schema can be validated against it. They also allow packaging multiple resources into a **Data Package** with a datapackage.json manifest. This approach is purely declarative (no code), focusing on schema constraints (e.g., uniqueness, foreign keys) and metadata. The concept relevant to ADE is the **embedding of validation rules in the schema**: e.g., Frictionless allows a "constraints" object on each field to declare checks like "required": true or a numeric range. ADE's manifest could similarly incorporate simple validation hints (like required-ness or acceptable patterns) to complement the code-based validators - thereby making certain rules explicit and machine-checkable. Frictionless also exemplifies forward-compatible design: it's designed for extension, and the specs have versioning (the manifest can include a profile/schema reference).
- **Great Expectations (GE):** Great Expectations is a framework for data validation that uses **"Expectation Suites"** to package data quality rules. An expectation suite is basically a collection of assertions (e.g., "column A must not be null", "column B values must be in this set"). GE encourages treating these suites as code: they are often saved in JSON/YAML and checked into version control[\[6\]](https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/expectation_suite/#:~:text=Save%20Expectation%20Suites), and GE has orchestrations (Checkpoints) to apply them to data pipelines. One notable aspect is **rich metadata**: each expectation can have a severity or a meta tag, and GE provides an execution engine that produces detailed results with success/fail and exception info. While GE doesn't inherently classify severities as "warning" vs "error" out of the box, practitioners often add a severity level in the expectation's meta and post-process results accordingly[\[7\]](https://www.startdataengineering.com/post/implement_data_quality_with_great_expectations/#:~:text=Most%20companies%20have%20varying%20levels,of%20severity). This is analogous to ADE's validation issues where we tag severity, and suggests we could standardize issue codes and perhaps allow config-wide settings for which severities should fail a job. GE demonstrates how validation logic can be decoupled from the main code and maintained as a portable artifact. Also, GE's **Data Context** concept centralizes configuration (stores for expectations, validations, etc.), which parallels ADE's concept of a single container housing config plus runtime. GE's approach reinforces the value of **explainability** - their validation results are meant to be human-readable and are often rendered into docs - much like ADE's artifact explaining each mapping decision.
- **Pandera:** Pandera is a Python library for defining DataFrame schemas and validations using a fluent, code-centric API. Developers write Python code to specify schemas (with column types and checks). Pandera offers a bunch of **built-in check helpers** (e.g., Check.less_than(100), Check.str_matches(regex)) so you don't have to manually code common patterns[\[3\]](https://pandera.readthedocs.io/en/stable/checks.html#:~:text=schema%20%3D%20pa.DataFrameSchema%28%7B%20,). It also supports **multi-column validations** by allowing checks at the DataFrame level or grouping by one column to apply checks on another[\[8\]](https://pandera.readthedocs.io/en/stable/checks.html#:~:text=Column%20Check%20Groups%C2%B6). Key insights for ADE: providing a standard utility module for config authors (with common checks or patterns) can drastically simplify writing rules. Instead of each author writing regex matching from scratch, ADE could ship a helper (similar to Pandera's Check) for things like "is value in list", "matches date format", "is unique in column" etc. Additionally, Pandera's multi-column checks highlight a design for cross-field validation: you can pass the whole DataFrame to a check function. In ADE's streaming world, we can't exactly do that, but the idea of having a designated place to implement cross-field logic (perhaps after all columns processed) is inspired by such capabilities.
- **OpenRefine (Data Transform Recipes):** OpenRefine is an interactive data cleaning tool that keeps a log of every transformation applied to a dataset. These transformations can be exported as a JSON **operation history** and re-applied to other datasets[\[9\]](https://carpentry.library.ucsb.edu/2022-04-14-ucsb-openrefine/12-export-transformation/index.html#:~:text=As%20you%20conduct%20your%20data,all%20of%20your%20related%20data). Essentially, OpenRefine lets users script a series of text transformations (splits, merges, edits) without coding, then that script can be reused. This is a very different paradigm (UI-driven rather than code packages), but it underscores the value of **portability of data cleaning logic**. In ADE, the config package plays a role analogous to an OpenRefine recipe: you develop it on sample data, and then you can export it and apply it to many similar files. OpenRefine's JSON format is not directly applicable to ADE (since our transformations are arbitrary Python, not a fixed set of operations), but it validates that storing _the steps to clean data_ in a reusable, shareable form is a proven approach. One idea we can borrow: OpenRefine's operations have a **manifest-like metadata** (each step has a description, maybe an author, etc.), suggesting ADE's artifact could eventually include more narrative or human-friendly descriptions of each rule that was applied.
- **Airbyte (Connector Config & Packaging):** Airbyte is an ELT platform where each source or destination connector is a separate package (often a Docker image) with its own config spec. Connectors declare their configuration requirements in a **JSON Schema** - including UI hints - and Airbyte uses this to render forms and validate user input[\[10\]](https://docs.airbyte.com/platform/connector-development/connector-specification-reference#:~:text=By%20default%2C%20any%20fields%20in,e.g)[\[11\]](https://docs.airbyte.com/platform/connector-development/connector-specification-reference#:~:text=Ordering%20fields%20in%20the%20UI). For example, a source connector might require an API key and output schema; the spec can mark the API key field as airbyte_secret: true to hide it in the UI[\[10\]](https://docs.airbyte.com/platform/connector-development/connector-specification-reference#:~:text=By%20default%2C%20any%20fields%20in,e.g), or use an order attribute to arrange fields logically in the form[\[11\]](https://docs.airbyte.com/platform/connector-development/connector-specification-reference#:~:text=Ordering%20fields%20in%20the%20UI). Connectors also carry their own dependencies and run in isolation (each connector is essentially a self-contained code package), analogous to our config running in a sandbox. Airbyte's approach to versioning is also instructive: connectors have semantic versions and Airbyte can indicate if a new version is breaking. Importantly, Airbyte enforces a **standard test suite for connectors** - every connector must pass a suite of protocol compliance tests (reading, writing, handling schema, etc.)[\[5\]](https://docs.airbyte.com/platform/connector-development/testing-connectors/connector-acceptance-tests-reference#:~:text=To%20ensure%20a%20minimum%20quality,or%20invalid%29%20inputs). This is essentially a TCK (Technology Compatibility Kit) ensuring that all packages meet certain quality standards. For ADE, which similarly lets third-party code (the config rules) dictate behavior, having a lightweight compatibility test (for example, using known input spreadsheets to see if the config maps and validates as expected) would parallel Airbyte's quality checks. Another parallel is **handling of Python dependencies**: Airbyte connectors written in Python often use a base image that includes common libs, and any extra dependencies are listed in a requirements file (which get installed in the container during build). We can emulate this by letting config packages specify their needed libs, which we install at runtime in a sandboxed way (since we don't build separate images per config).
- **Plugin & Sandbox Ecosystems:** More broadly, systems that allow user-contributed code (plugins, hooks, or code challenges platforms) have established patterns for safety and manageability. A common theme is **process isolation** and resource limiting. For instance, online judge systems or sandbox services will run untrusted code in a separate process or container with time and memory limits, rather than trying to restrict Python built-ins (which is known to be bypassable[\[12\]](https://healeycodes.com/running-untrusted-python-code#:~:text=I%20have%20side,to%20parts%20of%20the%20runtime)[\[13\]](https://healeycodes.com/running-untrusted-python-code#:~:text=lookup%20%3D%20lambda%20n%3A%20,0)). They often use OS-level controls like Linux seccomp (to restrict syscalls) and setrlimit (to cap CPU and memory)[\[14\]](https://healeycodes.com/running-untrusted-python-code#:~:text=When%20using%20a%20separate%20process,run%20into%20a%20permissions%20issue)[\[15\]](https://healeycodes.com/running-untrusted-python-code#:~:text=setrlimit%20is%20one%20of%20the,files%20created%20by%20the%20process). ADE's current approach already uses a subprocess with limits, which aligns with best practice (as opposed to attempting "pure" language sandboxing, which is insecure). In terms of plugin architecture, many frameworks offer a clear API for plugins and sometimes a **version handshake** - e.g., a plugin declares which host version it is compatible with. We see this in browser extensions, VSCode plugins, etc., and also in Python (packages specifying dependency version ranges). For ADE, the equivalent is the config manifest declaring the ADE engine version compatibility (so if we introduce a breaking change in how ADE works, config packages could declare which version they need). Code signing is another practice in plugin ecosystems (to ensure a package wasn't tampered with), seen in e.g. Figma plugins or enterprise software. That might be overkill for ADE initially, but recording a hash of the config scripts (and maybe an optional author signature) could be a lightweight step to ensure integrity.

**Summary of Insights:** Other systems reinforce the importance of **strong manifest contracts**, **versioning and compatibility management**, and providing tooling to make user-defined rules both **powerful and safe**. There is a clear trend toward treating configurations/rules as portable code artifacts: from Great Expectations' version-controlled expectation suites to Airbyte's connector packages with JSON specs. We also gleaned that offering **helper utilities and standard patterns** (as Pandera does for common checks, or as Great Expectations does with its library of expectations) can greatly improve the user experience and reduce errors. Finally, the emphasis on **testing and quality** (Airbyte's acceptance tests, GE's validation results) suggests ADE should formalize how config packages are verified and trusted (through test kits and possibly integrity checks). All these lessons inform the options and recommendations below.

## 4. Decision Matrix (by theme)

Below we evaluate options for several key themes in ADE's config package design. Each theme is broken into possible approaches, rated on **complexity** (to implement/maintain), **ergonomics** (developer experience for config authors), **explainability** (impact on traceability/audit), **risk** (of breaking changes or misuse), and **migration effort** for existing configs.

### A. Manifest Design & Evolution

- **Option A: Status Quo (Manual manifest, no schema)** - _Complexity:_ Low (already in place). _Ergonomics:_ Medium - authors rely on docs and runtime errors to catch mistakes (e.g. a typo in a field name might only surface when mapping fails). _Explainability:_ Medium - manifest is simple, but lacks formal structure for new features. _Risk:_ Low immediate risk (no change), but higher risk of user error going uncaught. _Migration Effort:_ None (baseline).  
    _Evaluation:_ This option is the path of least resistance but misses opportunities for validation and controlled evolution.
- **Option B: JSON Schema & Versioning** - Define a JSON Schema for manifest.json and include a schema_version or semver in the manifest. _Complexity:_ Medium - need to create and maintain the schema file and a validation step. _Ergonomics:_ High - tools can validate manifest files against the schema, giving authors immediate feedback; easier onboarding as required fields/allowed values are explicit. _Explainability:_ High - a versioned manifest can be upgraded with clear change logs; the schema doubles as documentation. _Risk:_ Medium - if not managed carefully, a strict schema could reject older manifests (mitigate by making new fields optional and using version flags). _Migration:_ Moderate - existing manifests might need a one-time update to include a version and any new required fields (we can automate or default this).  
    _Evaluation:_ Strongly positive. This option brings ADE in line with best practices (explicit contracts like dbt's manifest artifact[\[1\]](https://docs.getdbt.com/reference/artifacts/manifest-json#:~:text=You%20can%20refer%20to%20dbt,and%20consuming%20dbt%20generated%20artifacts)). The added upfront work is justified by long-term stability.
- **Option C: Split Config (Multiple files or formats)** - For example, have a separate file for field schema (YAML or CSV of fields) and code separately, or store manifest in a database, etc. _Complexity:_ High - major changes to how configs are stored or edited. _Ergonomics:_ Mixed - could simplify one aspect (like editing field list in a spreadsheet) but complicates overall management (multiple sources of truth). _Explainability:_ Medium - splitting might reduce clutter, but links between pieces must be maintained. _Risk:_ High - a redesign can introduce new failure modes, and migration would be significant (all existing packages need refactor). _Migration:_ High - likely manual conversion of manifests.  
    _Evaluation:_ Not worth it. Keeping config packages self-contained in one manifest+scripts is simpler. Option C is too disruptive and against the "no extra infrastructure" constraint.

**Decision:** _Option B - introduce a JSON Schema-backed manifest with versioning - is the recommended path._ It offers the best balance of improved safety and clarity with manageable complexity.

### B. Rule Authoring & Scoring Ergonomics

- **Option A: Freeform Scoring (Current State)** - Detectors assign scores arbitrarily, author by author. No explicit thresholds; tie-breaking is handled by leaving unmapped. _Complexity:_ Low - no change. _Ergonomics:_ Medium/Low - flexible but prone to inconsistency; new authors may be unsure how to scale scores (0.1 vs 10.0?) or how to handle negatives. _Explainability:_ Medium - artifact shows scores, but without a common scale, it's harder to interpret confidence (one field's "5.0" may not equal another's). _Risk:_ Some risk of misuse (e.g., if one script accidentally returns an extreme score, it could dominate mapping). _Migration:_ None.  
    _Evaluation:_ Flexibility is high, but standardization is lacking, which could lead to mapping instability or confusion.
- **Option B: Standardized Score Range & Threshold** - Establish a guideline (e.g., all detector scores should be between -1.0 and +1.0, with 0.0 as neutral). Optionally implement a **global confidence threshold**: if top score < X, do not auto-map (leave column unmapped). _Complexity:_ Low/Medium - mainly documentation and a small change to the mapping logic to apply threshold logic. _Ergonomics:_ High - authors have a clear target range; easier to reason about additive effects. The threshold provides a safety net against spurious low-confidence mappings. _Explainability:_ High - a normalized scale makes artifact scores more meaningful ("score 0.8" clearly high vs "0.1" low). The threshold outcome ("column left unmapped due to low confidence") can be explicitly logged. _Risk:_ Low - if threshold is set conservatively (or default to 0, meaning current behavior), it's backward-compatible. We must fine-tune the default to avoid unmapping things that used to map - likely start with a very low threshold (essentially off) and allow configs to raise it if desired. _Migration:_ Minor - existing packages can continue with default threshold = 0 (no change in behavior), and gradually adopt score normalization in their own rules.  
    _Evaluation:_ This option is a clear improvement. It systematizes scoring without removing flexibility. It's inspired by patterns in information retrieval and ML (treating scores as confidence probabilities) and echoes Great Expectations' concept of mostly thresholds for expectations (e.g., 95% of values should match a rule).
- **Option C: Helper Library & Reusable Rules** - Provide a library module (or base classes) that encapsulate common detection logic, and encourage authors to use them. For example, a function score_by_synonyms(header, synonyms_list) that returns a standardized score (like 0.6 if any synonym matches). Or a regex pattern matcher that returns a score proportional to match frequency. _Complexity:_ Medium - need to develop and maintain this library, but it's within the same codebase (no external service). _Ergonomics:_ High - reduces boilerplate; new authors can pick from a menu of common detectors (much like Pandera's built-in checks[\[3\]](https://pandera.readthedocs.io/en/stable/checks.html#:~:text=schema%20%3D%20pa.DataFrameSchema%28%7B%20,)). Consistency improves (everyone using score_by_regex will behave similarly). _Explainability:_ High - when the artifact logs that a rule fired, if it's a standard library rule, its behavior is known and documented. We can even reference a common rule name in the artifact trace ("applied regex match rule XYZ"). _Risk:_ Low - this doesn't constrain what authors can do; they can still write custom code. The main risk is ensuring the library is correct and doesn't introduce bugs in scoring. _Migration:_ None required - existing detectors keep working; authors can opt into using the library gradually.  
    _Evaluation:_ Strongly positive. This aligns with our goal of making config authoring **safer and faster**. It's essentially packaging best practices (we already have example scripts for synonyms, numeric detection, etc.) into reusable form. Option B and C are complementary - the library can enforce the standardized scoring range internally (option C naturally furthers option B).

_(We treat B and C together in recommendations, as they address the problem from policy vs. tooling angles. Both will be adopted.)_

- **Option D: Automated or Learned Mapping** - (For comparison) Use ML or heuristic algorithms to auto-detect mappings, rather than explicit scoring rules. _Complexity:_ High - introduces model training or complex heuristics; contradicts the lightweight, explainable goal. _Ergonomics:_ Low - would take control away from config authors or require them to tune a model. _Explainability:_ Low - a model's decisions are harder to explain than our current transparent scoring. _Risk:_ High - not deterministic, may require heavy infra (ML libraries, etc.), and hard to rollback. _Migration:_ N/A (not pursuing).  
    _Evaluation:_ Not aligned with ADE's philosophy ("small, pure Python rules; unmapped is OK"). This is not recommended - we note it only as a contrast that we deliberately choose an explainable rule-based system over "magic" automation.

**Decision:** _Adopt Option B + C:_ Establish clear scoring conventions (and a mapping confidence threshold mechanism), and provide a **common rule helper library** to implement these conventions. This combination will make scoring more predictable and rules easier to write, all while maintaining interpretability.

### C. Validation Model & Cross-Field Checks

- **Option A: Field-Only Validation (Current State)** - Validators only see one column's values in isolation. Cross-field logic must be improvised (e.g., via hooks or done upstream in the source data). _Complexity:_ Low. _Ergonomics:_ Medium - simple for single-column rules, but authors have no direct support for relational checks (must write a hook that scans artifact or output, which is advanced). _Explainability:_ High for single-field issues (they're logged per cell with code/severity), but cross-field errors might not be caught at all or are noted in a less structured way (e.g., a hook writing a note). _Risk:_ Low - current approach is stable and keeps things deterministic/streaming. _Migration:_ None.  
    _Evaluation:_ Adequate for many cases (range checks, pattern checks, required fields), but lacks a native solution for multi-column validations (which some users will eventually need, e.g., consistency between two date columns).
- **Option B: Official Cross-Field Validation Phase** - Introduce an explicit phase or mechanism for validations that involve multiple columns or even whole tables. For example, after all column validators run, ADE could invoke a special script (maybe hooks/validate_table.py or a new validators/ directory) that has access to the **full set of columns** or rows. This script could, for instance, iterate through rows (perhaps streaming them again) to check inter-column relations. _Complexity:_ High - this breaks the current streaming assumption (would require buffering a table in memory or re-reading the output). Implementation would need careful resource management. _Ergonomics:_ High for those who need it (makes cross-checks first-class), but for authors who don't, it adds conceptual overhead. _Explainability:_ Medium - if implemented, it should produce issues just like column validators do, which can be logged with row references, so that's fine. But ordering of this new phase and potential interactions (e.g., should these cross-field checks run before writing or after writing?) must be clearly defined. _Risk:_ Medium - could impact performance (reading entire tables) and complicate the pipeline. Also risk of confusion if a user writes a cross-check that contradicts individual field checks. _Migration:_ Moderate - not affecting existing validators, but artifact schema might extend to include cross-table issues; old configs wouldn't use it, which is fine.  
    _Evaluation:_ Powerful but possibly overkill for now. It's a "later" candidate once we have more demand and possibly after optimizing memory usage. We'd need to ensure any such feature doesn't require new infra (sticking to in-memory or file-based checks within the container).
- **Option C: Leverage Hooks (Guidance approach)** - Continue using the after_validate hook for cross-field logic, but improve support via documentation or minor enhancements. For example, we can pass the **normalized output path** or a summary of field values into the hook context. An after_validate script could then open the output (as CSV/Excel) or iterate through artifact structures to perform checks like "if column X < column Y for any row, log an issue". We could provide utility functions to help read the output in a memory-efficient way (e.g., streaming row by row using our internal reader). _Complexity:_ Low/Medium - no new pipeline phase, just augmenting what the hook can do (passing file path or a helper to get combined row data). _Ergonomics:_ Medium - writing such a hook is less straightforward than a dedicated validator, but we can supply examples to make it easier. _Explainability:_ Medium/High - any issues the hook creates can still be added to artifact (the hook can return a structured note or even inject issues if we design it so). However, since it's not a formal part of Pass 4, we'd likely log cross-field findings as **notes or global issues** rather than cell-specific errors (unless the hook mimics the artifact format exactly). _Risk:_ Low - it doesn't disrupt existing flow; worst case the hook approach is clunky but doesn't affect those who don't use it. _Migration:_ None.  
    _Evaluation:_ This is a pragmatic interim solution. It uses existing extension points to handle a subset of cross-field needs. For example, a hook could aggregate all validation issues and perhaps add a summary, or perform a simple relation check by scanning the output file.
- **Option D: Schema-driven Constraints in Manifest** - Another angle: allow declaring simple cross-field constraints declaratively (e.g., mark two fields as a unique compound key, or one field must be <= another). ADE could then auto-generate validation logic for these. _Complexity:_ High - this would require a mini-language or set of manifest rules that ADE engine interprets. _Ergonomics:_ Medium - nice for very common constraints, but anything complex would still need custom code, so it only covers partial use cases. _Explainability:_ High - the manifest could clearly state the constraint (good for understanding), and the artifact could reference it by name if violated. _Risk:_ Medium - adds complexity to manifest and engine; risk of overlapping with custom validators. _Migration:_ Moderate - existing configs would ignore this feature, no breakage; but it increases manifest complexity overall.  
    _Evaluation:_ Not immediate priority. Could consider in future when we have enough patterns to justify formalizing them. For now, code-based approaches are more flexible.

**Decision:** _Proceed with Option C (improve hook usage) now, and revisit Option B (formal cross-field validators) later._ In the short term, we will document how to do cross-field checks in after_validate (and possibly provide a small helper to fetch needed data). This addresses urgent needs without major changes. We will also standardize **validation issue reporting** (common codes and severity usage) under the current per-field model. A formal multi-column validation interface can be designed in a future version once we gather more requirements, keeping in mind the streaming constraints.

### D. Packaging & Dependencies

- **Option A: No External Dependencies (Status Quo)** - Config scripts can only use Python's standard library (and whatever limited packages are pre-installed in the ADE container). _Complexity:_ Low. _Ergonomics:_ Medium/Low - simple in that authors don't worry about dependency management, but limiting if a needed library isn't available. They might end up writing more code from scratch (e.g., custom CSV parsing or regex), or we bloat the base image with many libraries just in case. _Explainability:_ High - fewer moving parts, easier to reproduce environment. _Risk:_ Low - no additional security concerns from pip installations, no version mismatch issues. _Migration:_ None.  
    _Evaluation:_ This is the most restrictive. It aligns with security (reducing attack surface) but at a cost to flexibility. As ADE grows, not having a sanctioned way to use external libs could be a bottleneck for complex data extraction logic.
- **Option B: Vendored Libraries in Package** - Allow authors to include a vendor/ directory inside the config package with any pip modules they need (by manually downloading wheels or using pip install -t vendor). ADE's sandbox process would add this vendor/ to PYTHONPATH so the scripts can import those modules. _Complexity:_ Low/Medium - no internet needed at runtime, just adjust path. But requires authors to manage and package those files, and possibly deal with platform-specific binaries if any. _Ergonomics:_ Medium - it gives freedom to use libraries, but managing them manually is technical. For pure Python deps it's okay; compiled deps could be tricky (must match the runtime environment). _Explainability:_ Medium - the artifact could list what packages were loaded (we might log module versions for traceability). Vendoring keeps everything self-contained, which is good for reproducibility. _Risk:_ Medium - larger packages mean bigger config zip and potentially memory overhead. There's also a security aspect: we'd be executing third-party code; however, it's code the config author provided, so not fundamentally different from their own scripts. _Migration:_ None - existing configs unaffected; new ones can opt to include vendor libs.  
    _Evaluation:_ This option empowers advanced use cases (e.g., use pandas or openpyxl for complex parsing within a transform). But it's somewhat clunky for authors and doesn't automatically resolve dependencies (they must gather them).
- **Option C: Requirements.txt + Automated Install** - Authors declare needed libraries and versions in a requirements.txt (or similar manifest key). When a job starts, ADE's sandbox process creates an **isolated environment** (e.g., a venv or simply by pointing pip at a target directory) and installs the requirements. After installation, the job runs with those packages available. The environment is destroyed or wiped after the job to avoid leakage. _Complexity:_ Medium - we need to invoke pip reliably, handle failures (network issues, install errors), and cache or isolate the installed files. Also need to respect runtime_network_access: if network is disallowed but dependencies are requested, we either fail the job or require an offline installation mechanism (like pre-bundled wheels). _Ergonomics:_ High - very convenient for authors: just list packages, similar to how Airbyte connectors or dbt packages declare their dependencies. They don't have to manually bundle files. _Explainability:_ Medium/High - we can capture the list of installed versions in the artifact or logs, so runs are auditible (e.g., "installed pandas 1.5.3 for this job"). With an optional lockfile (hashes of wheels), runs become deterministic and verify package integrity (pip can check hashes). _Risk:_ Medium - pip installing on the fly introduces points of failure and slight startup latency. There's a security consideration: opening network access to PyPI (if runtime_network_access is true) - we should encourage locking versions and possibly hosting an internal PyPI mirror for air-gapped deployments. Also, different config packages might use conflicting versions if run concurrently (though each job would isolate its venv, so that's fine but uses more disk). _Migration:_ None for existing configs (they'll have no requirements and skip this step).  
    _Evaluation:_ This is a balanced approach that we lean toward. It leverages well-known tooling (pip/venv) and aligns with how many projects handle deps. The key is implementing it in a lightweight way (e.g., use pip install --target job_temp_dir and PYTHONPATH rather than heavy virtualenv creation). For better performance, we might cache wheels or virtualenvs keyed by requirements hash between runs, but that can be an optimization later.
- **Option D: Global or Pre-Installed Dependencies** - Another approach could be "just install everything in the base container" (or mount common libraries) so that most configs find what they need. _Complexity:_ Low to implement (just bake into image). _Ergonomics:_ Low - it's unpredictable what's available, and if two configs need different versions of a lib, we're stuck. _Explainability:_ Low - the environment could drift across releases, causing different behavior without the config author knowing. _Risk:_ High - increases the attack surface (many libraries, possibly with vulnerabilities, in the runtime even if not used). _Migration:_ N/A (not a controlled approach).  
    _Evaluation:_ Not desirable. It undermines the isolation goal and doesn't scale well.

**Decision:** _Implement Option C (requirements.txt with on-demand install), and allow Option B (vendoring) as an alternative for offline cases._ Specifically, we'll support a requirements.txt in the config package - if present, and if engine.defaults.runtime_network_access is true or an offline wheel source is configured, the sandbox will install those packages into an isolated directory for that job. We will also document how to vendor packages for environments with no internet access or strict reproducibility requirements. This gives config authors flexibility while preserving our single-container deployment (no new long-running services needed). The overhead is manageable and contained within the job's lifecycle.

### E. Testability and Quality Assurance

- **Option A: Ad-Hoc Testing (Status Quo)** - Authors test configurations by running actual ADE jobs on sample files and inspecting the output and artifact manually. No dedicated test framework. _Complexity:_ Low (no changes). _Ergonomics:_ Low - very manual; difficult to do automated regression tests. If ADE's engine changes, authors might not know if their config still behaves the same except by re-running everything. _Explainability:_ Medium - the artifact provides info to verify each run, but comparing artifacts between versions is cumbersome without tools. _Risk:_ Medium - bugs or breaking changes can slip in unnoticed until production since there's no systematic testing. _Migration:_ None.  
    _Evaluation:_ This is insufficient as the ecosystem grows. Relying on human, manual testing is slow and error-prone.
- **Option B: Config Compatibility Test Kit (TCK)** - Provide a standardized **test harness** for config packages. This could include:
- A set of small **sample input spreadsheets** covering diverse scenarios (edge cases like missing headers, additional irrelevant columns, tricky date formats, etc.).
- Expected outputs or artifact snippets for those inputs (which a "known good" config should produce if it follows our default practices).
- A command-line tool or script (e.g., ade test config_package.zip) that runs these inputs through the package and reports any mismatches or errors.
- Optionally, allow config authors to add their own unit tests: e.g., we could allow them to include a tests/ folder with simple assertions (perhaps using a lightweight testing library or just a script that calls their detector functions with example data). _Complexity:_ Medium - requires writing the harness and maintaining some test files, and possibly updating expected outputs as the engine evolves. _Ergonomics:_ High - gives authors confidence; they can run ade test during development or CI pipelines to catch issues. It's similar to Airbyte's acceptance tests which ensure connectors meet the spec[\[5\]](https://docs.airbyte.com/platform/connector-development/testing-connectors/connector-acceptance-tests-reference#:~:text=To%20ensure%20a%20minimum%20quality,or%20invalid%29%20inputs), thereby increasing overall quality. _Explainability:_ High - when tests fail, it would pinpoint which field or rule didn't behave as expected. Could also double as documentation (the sample files illustrate common patterns). _Risk:_ Low - this doesn't affect runtime behavior, only adds a layer of validation. The main risk is maintenance burden for us (keeping the test expectations in sync with intended behavior). _Migration:_ Low - it's an additive tool; existing packages are not forced to use it, though we'd encourage them to.  
    _Evaluation:_ Very beneficial. This fosters a community norm of testing config logic thoroughly before production use. It also helps our team verify that changes in the ADE engine don't break existing configs (we can run the TCK on a suite of packages).
- **Option C: In-Engine Assertions and Debug Modes** - Another approach is to build more debugging facilities into ADE itself. For example, a "dry run" mode that goes through mapping without writing output, or a verbose logging mode for rules. Or even allowing config authors to specify assert statements in their code (like "assert value conforms to X during transform" to fail the job if an invariant is broken). _Complexity:_ Medium - would require adding flags and more logging pathways. _Ergonomics:_ Medium - could help during development (more insight in logs), but not a replacement for systematic tests. _Explainability:_ Medium - might clutter the artifact or logs with debug info not relevant in production. _Risk:_ Low/Medium - debug features are optional, but need to be careful they don't accidentally remain on in prod (affecting performance or behavior). _Migration:_ N/A (additive).  
    _Evaluation:_ Some of these could be useful (e.g., a --validate-manifest command or an environment variable to dump more details for a single job). But they complement rather than replace an external test harness. We'll incorporate a manifest validator by default (via JSON Schema), and possibly a debug log flag, but focus on Option B for structured testing.
- **Option D: Continuous Compatibility Suite (for ADE maintainers)** - Internally maintain a set of archived real-world config packages and run them on known inputs with each release to ensure no regressions. _Complexity:_ Medium - this is essentially our own regression test harness, possibly using the same tools as Option B. _Ergonomics:_ N/A for users (this is internal QA). _Explainability:_ N/A (ensures our explainability isn't broken inadvertently). _Risk:_ Low - just needs upkeep of test cases. _Migration:_ N/A.  
    _Evaluation:_ We should do this as part of release process. It's an extension of Option B, with broader and maybe private test cases.

**Decision:** _Adopt Option B - a Config Package Test Kit - and integrate it into our development workflow._ We will create a minimal framework where each config package can be quickly validated. This includes a manifest schema validation (to catch mistakes in config definition) and the ability to run the package against sample data. For now, this will be a manual or CLI-invoked process (no new service), possibly integrated with CI for those who version control their config packages. We will also use this framework internally for regression tests (Option D). Debugging aids (Option C) will be considered as needed - e.g., we'll certainly implement manifest validation, and we might allow a verbosity flag that prints each rule's score contribution for troubleshooting a mapping issue.

### F. Security & Isolation

- **Option A: Current Sandbox (Subprocess + rlimits)** - Continue with the existing model: run config code in a subprocess inside the container, limit CPU time and memory via the OS (and perhaps thread count, etc.), and keep network disabled unless explicitly allowed. This already aligns with known safe practices (segregating untrusted code)[\[16\]](https://healeycodes.com/running-untrusted-python-code#:~:text=How%20it%20works). _Complexity:_ Low (status quo). _Security:_ Medium - this is a decent baseline. It doesn't yet restrict filesystem access beyond what the container user permissions enforce (currently, config code could potentially read/write files in the working directory - though by convention they shouldn't, and container user may be non-privileged). _Ergonomics:_ N/A to config authors (translucent to them). _Risk:_ Some risk remains if, say, a malicious config tried to abuse the file system or CPU in ways not caught by simple limits. _Migration:_ None.  
    _Evaluation:_ The baseline is okay, but we can bolster it with minimal effort.
- **Option B: Hardened Sandbox (Seccomp, Import Restrictions)** - Enhance the subprocess by using Linux seccomp to block dangerous syscalls (no file creation, no exec, etc.) and possibly a chroot or working directory jail so the config code cannot see anything outside its job folder. Additionally, explicitly restrict which modules can be imported - for example, by pre-populating sys.modules with allowed ones or running the subprocess with Python's -I -s -S flags (isolated mode: ignore user site-packages and PYTHONPATH)[\[12\]](https://healeycodes.com/running-untrusted-python-code#:~:text=I%20have%20side,to%20parts%20of%20the%20runtime). We might also intercept imports to prevent certain modules like os or subprocess unless needed. _Complexity:_ Medium - seccomp requires native extensions or use of a library like pyseccomp[\[17\]](https://healeycodes.com/running-untrusted-python-code#:~:text=For%20my%20sandbox%2C%20the%20layer,to%20already%20open%20file%20descriptors); managing allowed syscalls can be tricky to get right (need to allow reading the spreadsheet file descriptor, etc.). Import filtering in Python is also not foolproof unless done at process start. _Security:_ High - would significantly reduce the attack surface (process can't open network sockets or new files unless permitted, etc.). _Ergonomics:_ Mostly invisible to config authors, unless they try something disallowed (in which case they get a clear error). It might mean some legitimate actions (like opening a small lookup file shipped in the config) would be blocked unless we explicitly permit read access to the config folder. We'd have to document these limitations. _Risk:_ Medium - could inadvertently break some existing config script that, for instance, tries to open a file (though they're not supposed to). Also, implementing seccomp incorrectly could cause the sandbox to block needed operations (like loading dynamic libraries for a dependency). _Migration:_ Low - likely backward-compatible for well-behaved configs; potential minor tweaks needed if a config relied on something now disallowed.  
    _Evaluation:_ This is worth doing incrementally. We can start by using safer Python flags (-I etc.) to prevent rogue imports from outside. Then evaluate seccomp - perhaps have it off by default, toggleable for high-security mode, until it's proven. The sandbox already limits CPU/memory via rlimits (we'll continue that)[\[15\]](https://healeycodes.com/running-untrusted-python-code#:~:text=setrlimit%20is%20one%20of%20the,files%20created%20by%20the%20process), which is crucial to kill infinite loops.
- **Option C: Out-of-Process Isolation (Container or MicroVM per Job)** - Run each config job in a separate Docker container or micro-VM, fully isolated from the main ADE process. This is the ultimate sandbox but violates our "no new infrastructure" rule (would require container orchestration or VM management). _Complexity:_ High - essentially running a mini environment per job. _Security:_ Very high - strong isolation, but we already have containerization at the app level; doing it per job is likely overkill given our threat model (configs are authored by users of the system, not arbitrary anonymous code). _Ergonomics:_ Low - would add overhead for deployment (DinD or similar) and possibly slow startup. _Risk:_ High - lots of moving parts; potential to introduce failures in orchestrating containers/VMs. _Migration:_ High - a big change in how jobs run.  
    _Evaluation:_ Not justified for our scope. We can achieve sufficient safety with Option B within the single container model.
- **Option D: Integrity Verification (Code Signing/Hashing)** - Complement runtime security with integrity checks. For example, compute a hash (e.g., SHA-256) of each script in the config package when it's activated. Store these hashes in the manifest or artifact. Then:
- At job start, verify the on-disk scripts match the recorded hash (to detect tampering of an active config).
- In the artifact, log the hash of each rule's code (so one can later prove which version of code ran for a given job).
- Optionally, allow config packages to be signed by an author or trusted authority. This is more of an enterprise feature (ensuring configs weren't modified by unauthorized parties). _Complexity:_ Low/Medium - computing and comparing hashes is straightforward. Implementing a full signing workflow is more work (key management, etc.), so likely we'd start with just hashing. _Security:_ Medium/High - ensures **integrity** (detects changes or corruption) but not confidentiality or full trust (a malicious author can still write malicious code - signing just authenticates authorship). It's still a valuable audit feature. _Ergonomics:_ Medium - mostly transparent, though if a hash mismatch occurs, we'd have to present a clear error ("Config may have been modified outside of ADE"). _Risk:_ Low - doesn't affect runtime unless a check fails. _Migration:_ Low - we can introduce this in a backward-compatible way (existing configs just get hashed upon activation).  
    _Evaluation:_ A good incremental safety measure. It adds to explainability too: the artifact registering a rule's hash means the execution can be tied to a specific version of the code. This option is worth doing alongside runtime sandbox hardening.

**Decision:** _Continue with Option A as baseline, implement parts of Option B and Option D for additional safety._ Concretely, we will run the sandbox process in isolated mode (no unintended imports) and consider a minimal seccomp profile to block egregious system calls (at least on Linux deployments)[\[14\]](https://healeycodes.com/running-untrusted-python-code#:~:text=When%20using%20a%20separate%20process,run%20into%20a%20permissions%20issue). We will also start logging script hashes in the artifact and detecting unexpected modifications to active configs. These changes strengthen security without requiring new infrastructure or impacting normal usage. Option C (full container per job) is not pursued. Full code signing (Option D extended) can be tabled until a customer needs that level of assurance, but our hashing mechanism will lay the groundwork.

## 5. Recommendations (Manifest, Rules, Validation, Packaging, Artifact)

Based on the analysis above, we propose a set of concrete changes and best practices for the next iteration of ADE config packages. Each recommendation is **incremental** (building on the current design), maintains or improves explainability, and aims to be backward-compatible. We indicate the rationale, an example or snippet if applicable, acceptance criteria (what tests/behavior should result), and notes on any risks or rollbacks.

### 5.1 Manifest & Metadata

**Introduce a Versioned JSON Schema for manifest.json**  
_Rationale:_ Formalizing the manifest structure will catch errors early and guide future enhancements in a compatible way. By versioning the schema (e.g., ade.manifest/v1.0), we can evolve the manifest gradually, and the engine can validate which versions it supports. This is akin to dbt's manifest versioning and JSON schema approach[\[1\]](https://docs.getdbt.com/reference/artifacts/manifest-json#:~:text=You%20can%20refer%20to%20dbt,and%20consuming%20dbt%20generated%20artifacts), ensuring that producers and consumers of config packages share a clear contract.  
_Implementation:_ Develop a JSON Schema (e.g., ade_manifest_schema_v1.json) that describes the manifest. Include definitions for engine.defaults (with properties like timeout_ms, etc.), columns.order (array of field keys), columns.meta (map of field key to object with required props like label and script, and optional props like synonyms, required, etc.), and hooks (mapping of hook name to list of scripts). The manifest file itself will include a top-level identifier of the schema version, for example:

```json
{
  "info": {
    "schema": "ade.manifest/v1.0",
    "version": "1.3.0",
    "title": "Membership Rules"
  },
  "...": "engine, hooks, columns as before"
}
```

Here info.schema is our manifest format version, and info.version is a user-defined package version (semantic version of their config content). The JSON Schema file can be published with our docs so authors or tools can validate without running ADE.  
_Acceptance Criteria:_ ADE on startup (or when loading a config) validates manifest.json against the schema. If invalid, it produces a clear error pointing to the issue (e.g., "manifest.json: 'columns.meta.department.script' is required"). The manifest still supports older versions (we can initially mark new fields as optional and accept schema: ade.manifest/v0.6 for legacy). We should test loading a known-good manifest (passes validation) and a known-bad one (missing a required field, see that it fails with a useful message).  
_Risk/Mitigation:_ The main risk is rejecting a manifest that ADE _used to_ accept (if, say, some packages had slight irregularities). To mitigate, we can start in a non-fatal "warn" mode: log schema validation issues but still attempt to run (for one version), then enforce strictly in the next version once people adjust. Rollback is simple: if any unforeseen problem, we could disable the validation step or allow a flag to skip it.

**Semantic Versioning & Compatibility Flags:**  
In the info section of the manifest, encourage usage of a version (for the config package's own version) and possibly ade_version or requires_engine field. For example:

```json
"info": {
  "schema": "ade.manifest/v1.0",
  "version": "1.2.0",
  "requires_engine": ">=0.6.0"
}
```

_Rationale:_ This communicates which ADE engine versions the package was designed for, similar to dbt's require-dbt-version config[\[2\]](https://docs.getdbt.com/guides/building-packages#:~:text=just%20created,version%20config). Initially, we can set requires_engine automatically on export (e.g., to the current ADE version) so it's mostly informational. In future, if a package is imported into an incompatible ADE version, the system can detect that and warn/refuse. This prevents subtle errors from version mismatches.  
_Acceptance Criteria:_ The manifest schema includes an optional requires_engine (string). ADE's import or activation logic checks it against its own version and logs a warning if not satisfied ("This config was built for ADE 0.6+, you are running 0.5.2; behavior might differ."). We don't have multiple major versions of ADE yet, but this is future-proofing.  
_Risk:_ Minimal, since it's advisory at this point. We just need to parse semantic version strings correctly. Rollback is as simple as ignoring that field if something goes wrong.

**Enrich Field Metadata (synonyms, patterns, privacy):**  
We will extend `columns.meta[field]` objects with a few new optional properties:

- `synonyms`: already in use (list of alternative header names) and now documented as first-class detection hints.
- `pattern` or `regex`: string pattern that field values should match, for example `"pattern": "^[A-Z]{3}\\d{3}$"` for an ID format.
- `type_hint`: a simple data type tag (e.g., `"integer"`, `"date"`) used for both detection hints and validation.
- `privacy`: a classification such as `"personal_data"` or `"sensitive"` so artifacts can highlight sensitive fields.

_Rationale:_ These additions make the manifest a richer schema descriptor, closer to concepts in Table Schema (which has patterns and constraints for fields)[\[4\]](https://specs.frictionlessdata.io//table-schema/#:~:text=The%20,updated%20via%20a%20data%20entry). They remain optional to keep things light, but provide hooks for both user logic and potential ADE engine use. For example, an email field could specify a regex and a privacy flag. The config's detector code can reference field_meta\["pattern"\] to score regex matches (we'll provide a helper for that). The validator can similarly use it to flag any value that doesn't match. In short, it avoids hard-coding patterns in multiple places; it's part of the package's declarative knowledge.  
_Snippet Example:_

```json
"columns": {
  "order": ["member_id", "email"],
  "meta": {
    "member_id": {
      "label": "Member ID",
      "required": true,
      "script": "columns/member_id.py",
      "synonyms": ["member number", "ID#"],
      "pattern": "^[A-Z]{2}\\d{4}$"
    },
    "email": {
      "label": "Email Address",
      "required": false,
      "script": "columns/email.py",
      "type_hint": "email",
      "privacy": "personal"
    }
  }
}
```

In this example, member_id values should be 2 letters followed by 4 digits (the transform/validate logic can use this), and email is marked as a personal identifier with an implicit pattern of what an email looks like (the type_hint: "email" we could interpret via a built-in regex in the helper library).  
_Acceptance Criteria:_ The manifest accepts these new fields (schema updated). They are exposed to detector/validator functions via the field_meta dict. We should update our example detectors to utilize them (e.g., a generic detect_by_pattern function that reads field_meta.get("pattern")). If a privacy is set, ensure it's recorded somewhere in the artifact (for future auditing; e.g., artifact's field metadata could carry it). This doesn't directly change engine behavior beyond making the data available. We consider it a success if authors can remove some hard-coded regexes in their code and instead rely on manifest config, improving clarity.  
_Risk:_ Very low - these are optional and non-functional unless used. Even if someone sets a pattern, it's up to their rules or future engine updates to act on it. We will clearly document that these are hints, not enforced by ADE unless the rules enforce them. Rollback: if any issue, ignoring these fields would revert behavior to current state.

### 5.2 Rule Library & Scoring Conventions

**Provide ade_rules Helper Module:**  
Create a built-in Python module (perhaps ade.rules or a util file that config scripts can import) containing common functions for detectors, transforms, and validators. Examples of initial helpers:

- `match_synonyms(header: str, synonyms: list[str]) -> float`: returns a standardized score (e.g., +0.5) if any synonym substring is found in the header (case-insensitive), else 0.0; possibly weight by exact match vs partial.
- `match_regex(values: list, pattern: str) -> float`: checks what fraction of non-empty values match the regex and returns a score scaled to that fraction (e.g., if 80% match, score 0.8); cap or threshold it within [0,1].
- `contains_numbers(values: list) -> float`: simple heuristic to detect numeric-looking columns.
- `date_format_score(values: list) -> float`: identifies whether values look like dates.
- `to_number(value)`, `to_string(value)`, `normalize_whitespace(value)`: utility transforms.
- Validation helpers like `find_required_missing(values) -> list[issue]`, which returns an issue dict for each missing required value using manifest info such as `field_meta["label"]`.
- Standard issue code constants or enums, e.g., `ISSUE_REQUIRED_MISSING = "required_missing"` or `ISSUE_PATTERN_MISMATCH = "pattern_mismatch"`, so authors use consistent codes.

_Rationale:_ This reduces duplication and errors. Many config packages will independently write similar logic (we already see patterns: checking synonyms in header, checking email format, etc.). By centralizing these, we ensure a consistent scoring scale. It also makes user scripts shorter and more readable (improving maintainability). For example, a detector can be one line calling ade_rules.match_synonyms(header, field_meta.get("synonyms", \[\])) to get a score contribution[\[11\]](https://docs.airbyte.com/platform/connector-development/connector-specification-reference#:~:text=Ordering%20fields%20in%20the%20UI), instead of 10 lines of looping and lowercasing.  
_Snippet Example:_

```python
# columns/email.py (detector using new library)
import ade_rules as rules

def detect_email_format(*, header, values_sample, field_name, field_meta, **_):
    score = 0.0
    # Boost if header has typical email keywords
    score += rules.match_synonyms(header or "", ["email", "e-mail"])
    # Boost proportional to fraction of values matching email regex
    score += rules.match_regex(values_sample, rules.PATTERN_EMAIL)  # assume ade_rules provides a standard email regex
    return {"scores": {field_name: round(min(score, 1.0), 2)}}
```

Another example for validation:

```python
# columns/member_id.py (validator using library)
import ade_rules as rules

def validate(*, values, field_meta, **_):
    issues = []
    if field_meta.get("required"):
        issues += rules.find_required_missing(values, field_name="member_id")
    pattern = field_meta.get("pattern")
    if pattern:
        issues += rules.find_pattern_violations(values, pattern, field_name="member_id")
    return {"issues": issues}
```

Here find_required_missing would create an issue for each blank value (with code "required_missing" and severity "error"), and find_pattern_violations would create issues for values not matching the given regex (with code "pattern_mismatch", maybe severity "warning" by default). These functions inside ade_rules know how to format the issue dictionary according to our conventions (populating row_index, message with the field label, etc.), saving the author from boilerplate.  
_Acceptance Criteria:_ The ade_rules (or similarly named) module is packaged with ADE and accessible to config scripts. We'll test that a simple config using these helpers runs successfully. We should also ensure the helpers themselves are well-tested (unit tests for match_synonyms, etc., on sample inputs). Additionally, verify that using them indeed produces consistent scoring (e.g., two different fields both using match_regex will yield comparable 0-1 scores for similar match fractions). For validation, ensure that the issues generated align with artifact expectations (correct row indices and messages).  
_Risk:_ Minimal functionality risk, as this is additive. Authors are free to ignore these and continue writing raw Python if they prefer. However, there's a design risk that we must keep the helpers up-to-date with any changes in scoring philosophy. We mitigate that by making the helpers relatively simple (just encapsulating current best practice). Rollback is simply advising authors not to use a buggy helper or patching the helper in a hotfix. Since this is internal to our container, we can fix and deploy improvements easily without breaking the config package interface.

**Score Normalization & Threshold Implementation:**  
We will adopt a convention that detector scores should generally be in the range **\-1.0 to +1.0**, and we will clamp or scale where appropriate. This doesn't mean all scores are probabilities, but it avoids extreme values. We'll update documentation accordingly and adjust our example scripts (and ade_rules functions) to adhere to this range. Additionally, implement a **mapping confidence threshold** in the mapping logic: a configurable value mapping_score_threshold (perhaps in engine.defaults or columns config). If the highest field score for a column is below this threshold, ADE will refrain from mapping that column (treat it as unmapped). The default can be 0.0 (effectively no threshold, preserving current behavior), but users or future versions can set e.g. 0.5 if they want only strong matches to auto-map. We can also allow per-field thresholds in columns.meta\[field\].min_confidence if some fields require a higher bar (though this might be over-engineering initially).

_Rationale:_ This directly addresses edge cases where a column might accidentally get mapped to a field with a weak score just because it's slightly higher than others. With a threshold, config authors have more control to say "if in doubt, leave it unmapped" which is safer. It aligns with the "unmapped is OK" philosophy - we prefer to be unsure rather than confidently wrong. Other systems have analogous ideas (e.g., Great Expectations has the concept of mostly and can treat a validation as failed only beyond a threshold; here we treat mapping as "pass/fail" based on a threshold of confidence). From an explainability perspective, this threshold will be documented and its effect clearly logged (e.g., artifact could mark "Column X was not mapped to any field (highest score 0.3 below threshold 0.5)"). Users reviewing the artifact then know it wasn't an oversight, but an intentional low-confidence skip.

_Implementation:_ - Add a new manifest setting: engine.defaults.mapping_score_threshold (float, default 0.0 for backward compatibility). Or incorporate it under a columns: setting. - When computing mapping for each raw column, after summing scores for each candidate field, determine the max score and the winner field. If max_score >= threshold, proceed as today (map to winner, log the mapping with that score). If max_score < threshold, then set the column as unmapped (possibly logged as mapping to None). Unmapped columns can still be output as raw if append_unmapped_columns is true. - Also, ensure tie-breaking logic remains: if two fields tie exactly and above threshold, currently we leave unmapped (to avoid arbitrary pick). That rule stays. - Possibly store the actual confidence (max score) in artifact for each column mapping for transparency.

_Snippet Change:_ In pseudo-code, where mapping is determined:

max_field, max_score = None, 0.0  
for field in target_fields:  
if scores\[field\] > max_score:  
max_field, max_score = field, scores\[field\]  
\# after loop:  
if max_field is not None and max_score >= manifest\["engine"\]\["defaults"\].get("mapping_score_threshold", 0.0):  
assign_column_to_field(column, max_field)  
else:  
leave_column_unmapped(column)

The artifact entry for that column might then look like:

{  
"column_index": 5,  
"header": "ID No.",  
"field": null,  
"confidence": 0.3,  
"decision": "unmapped_low_confidence",  
"scores": { "member_id": 0.3, "first_name": 0.0, ... }  
}

This example shows an unmapped column with highest score 0.3 for member_id but below threshold 0.5, so field is null and we note the reason. (We'll adjust actual artifact schema accordingly.)

_Acceptance Criteria:_ When the threshold remains at the default 0.0, behavior is identical to today (we should confirm with a regression test: same mappings and artifacts for a known input). When a higher threshold is configured, validate that:

- A column with a low score (below threshold) ends up unmapped and the artifact clearly reflects that state.
- A strongly matching column (above threshold) continues to map normally.
- Ties are still resolved as "unmapped" regardless of the threshold.

Also confirm that any per-field `min_confidence` override supersedes the global value. For instance, `member_id.min_confidence = 0.8` should enforce stricter mapping for that field while others still respect the global 0.5.

_Risk:_ If a user sets the threshold unwisely high, many columns might remain unmapped, potentially dropping data that used to flow through. However, since default is 0.0, existing configs won't be affected. We will clearly document this setting and perhaps caution that anything above, say, 0.5 should be used with care. Rollback is straightforward: if something goes wrong, the threshold can be turned back to 0 (effectively disabling it).

**Standardize Issue Codes and Severity Usage:**  
While not exactly scoring, as part of rule ergonomics we want to ensure **validation issues** are reported consistently:

- Define a recommended set of code strings for common validation errors (e.g., `"required_missing"`, `"pattern_mismatch"`, `"out_of_range"`, `"invalid_format"`). Document them and expose constants in the `ade_rules` library.
- Encourage meaningful severity levels: use `"error"` for data that breaks downstream expectations, `"warning"` for issues that still allow output, and `"info"` for minor notes.
- Have the `ade_rules` helpers default each issue code to an appropriate severity while allowing overrides (e.g., `required_missing -> error`, `pattern_mismatch -> warning`).

_Rationale:_ This doesn't change any functionality but improves the _interpretability_ of validation results. If every config author uses different codes for the same concept ("null_found", "blank_field", etc. for missing values), it's hard for users (and our UI) to aggregate or understand. A consistent taxonomy (inspired by Great Expectations or data quality frameworks) makes it easier to filter issues and create summaries. Severities in ADE already exist; we just want to ensure they are used consistently (we might also consider adding a numeric ranking behind the scenes: e.g., treat "error" as 3, "warning" as 2, "info" as 1 for sorting).

_Implementation:_ Document a table of standard issue codes. Update our example validators to use them. Possibly have the artifact or UI group issues by severity and code. No code changes needed except maybe adding a check: if an issue's code is not provided by the validator, perhaps we require it or fill a default like "custom_issue". (It might be good to enforce that code is not empty for any issue - we can validate that in tests.)

_Acceptance Criteria:_ Review a sample artifact from a config with validations - ensure the codes are from the standard set. For internal consistency, run our own configs to see if any non-standard codes appear and update them. It's okay to allow custom codes (some users might define very specific ones), but the common ones should be unified. Perhaps acceptance is that our documentation lists at least 5 common codes and any issues produced by our provided rule library use those codes.

_Risk:_ Very low. It's mostly a convention. We will not break if someone uses a different code, but we'll nudge them towards consistency. If in future we plug these into UI or reporting, having them consistent will pay off.

### 5.3 Validation & Cross-Field Strategy

**Implement Cross-Field Checks via Hooks (Now) and Plan for Table Validator (Future):**  
We recommend an immediate solution to empower cross-field validation using the existing hook system:

- **Now:** document and exemplify using the `after_validate` hook to perform table-level checks. Provide a template `hooks/after_validate.py` showing how to iterate over artifact tables and compare fields. As an alternative, consider a helper such as `ade_rules.check_relations(artifact, rules)`-though simple examples may be sufficient for now.
- Ensure that the hook can report its findings. Extend the hook return format to allow `{"issues": [...]}` in addition to `{"notes": "..."}` and merge those issues into the artifact, flagged as cross-field checks.
- If feasible, pass the normalized output path or an easy-to-consume data structure into the hook. After validation, the normalized spreadsheet exists on disk; supplying the path lets authors load the data with `openpyxl` or `pandas` when necessary.
- Consider (but likely defer) running the hook just before writing so data remains in memory. Because ADE streams rows, reopening the output file is often simpler and keeps the writer pipeline unchanged.

_Rationale:_ This leverages what we have to solve immediate needs, without altering pipeline structure. It's slightly hacky (reading your own output to validate it), but since we forbid raw data in artifact, the output file is the only complete source of data. Many users might not need this, but offering a path is better than nothing.

_Future:_ Design a formal validate_table.py script interface (Option B earlier). This would run after all per-column validations, with access to either an in-memory table or an iterator of rows. It would produce issues similar to column validators but could reference multiple fields in the message (maybe using a special code like "cross_field_error"). This likely requires buffering the table's data in memory (violating streaming), or performing a second pass on the file. We might delay this until we have a mechanism to handle large data (maybe limit cross-field checks to smaller sample or something). So we propose to **mark this as a roadmap item** with a capability flag like: in manifest info we could add "capabilities": \["cross_field_validation"\] when it's ready, and engine checks if it supports it.

_Acceptance Criteria (Now):_ Provide an example hook that checks a simple rule (like "if start_date and end_date are both mapped, ensure start <= end for each row"). Run it on a sample dataset to see that it correctly identifies any violations and that those appear in the artifact (perhaps as a note or as synthetic issues). For instance, the hook could append to artifact\["tables"\]\[i\]\["validation"\]\["issues"\]. We need to confirm that modifying artifact in hook is safe or provide an official API (maybe return issues and let the engine merge them). We should also verify performance on a moderately large file, to ensure reading it in hook doesn't blow memory or time budget (and note in docs that such hooks should be used judiciously).

_Risk:_ Using hooks for this is advanced and not foolproof - a poorly written cross-check hook could slow down the job or run out of memory. We mitigate by guiding best practices (e.g., if possible, only read needed columns, or break as soon as one violation found, etc.). Since this is optional, the risk is isolated to those who use it. In worst case, we roll back by advising against cross-field checks on huge data, or eventually implementing the formal solution which can be optimized internally.

**Aggregate Validation Summary:**  
As a minor recommendation to complement validation, we suggest adding an automatic summary of validation results at the end of a job. Possibly via the after_validate hook (we can provide a default one that counts errors/warnings). For example, after Pass 4, we could log: "Validation complete: 3 errors, 5 warnings found across 2 tables." This could go in artifact summary or logs. It's a small UX improvement so users don't have to scroll through possibly thousands of row-level issues to know the high-level outcome.

_Rationale:_ Clarity and quick feedback. Similar to how Great Expectations prints a summary of how many expectations passed/failed.

_Implementation:_ Could be done by always invoking a built-in piece of code in after_validate (in addition to user hook, not overriding it) that simply looks at artifact issues and tallies them. Or incorporate into the artifact structure (like an artifact\["validation_summary"\]).

_Acceptance Criteria:_ On running a job with some validation issues, the artifact or logs clearly show a one-line summary. E.g., in artifact JSON:

"summary": { "errors": 3, "warnings": 5, "info": 0 }

Test with and without any issues to ensure it handles zero-case.

_Risk:_ None really. If an error, we can remove it. If users find it unnecessary, it's just a small entry.

### 5.4 Packaging & Dependencies

**Support requirements.txt in Config Package:**  
Implement logic to detect a `requirements.txt` file at the root of the config package (or a manifest field listing dependencies). If present, on job start:

- When `runtime_network_access` is true (or offline sources are configured), run `pip install --target <temp_dir> -r requirements.txt` to install packages into an isolated directory.
- Add that directory to `PYTHONPATH` for the sandboxed subprocess (or create and activate a venv).
- Preserve sandboxing: use `--no-warn-script-location`, avoid global installs, and consider `--no-deps` if we require explicit dependency pins.
- Optionally cache environments keyed by the requirements hash to avoid reinstalling.
- After the job, delete the temporary installation (or keep the cache if in use).
- If installation fails, abort the job and surface the pip log for debugging.

_Rationale:_ as discussed, this dramatically improves flexibility (authors can leverage PyPI ecosystem). We model this after the convenience of Airbyte's connector development, where dependencies are just part of the connector spec. It avoids complicating the Docker image or requiring the user to do out-of-band prep.

_Acceptance Criteria:_

- Unit test: with a simple `requirements.txt` (for example `python-dateutil==2.8.2`), verify that the module is importable during a job run and that a detector using `dateutil.parser.parse` succeeds.
- If `runtime_network_access` is false and a requirements file exists, ADE should fail fast with a clear message (preferred) or skip installation with an explicit warning, avoiding a later import error.
- Try installing a dependency with compiled wheels (e.g., `xlrd`) to confirm the sandbox handles non-trivial packages and to observe startup overhead.
- Update documentation to explain how to add `requirements.txt`, remind authors to pin versions, and reiterate the `runtime_network_access` requirement or the vendoring alternative.

_Risk:_ The runtime of pip install could be significant for large packages - we will document that heavy dependencies should be used sparingly. We could mitigate by recommending using pandas or numpy only if absolutely needed because those can be 10s of MB. Also dependency conflicts: since each config's environment is separate, one config's dependencies won't conflict with another's, so that's fine. If a dependency fails to install (maybe platform issue), the job fails - which is correct behavior (the config essentially can't run). Rollback plan if this feature is problematic: since it's opt-in (only if requirements.txt exists), worst case we tell users to vendor libs manually and disable the auto-install. We should also be mindful of security: pip will run setup scripts of packages. Running that inside our sandbox process is safer than in the main process. We might even do the install in a yet another process to keep the sandbox clean. But probably okay to do in sandbox before dropping privileges (pip might need to compile, etc., though target directory approach shouldn't require special privileges).

**Optional Requirements Lockfile:**  
As an extension, encourage (but don't require initially) authors to include a requirements-lock.txt with pinned versions and hashes (output of pip freeze or pip-tools). If present, we use it to install with --no-deps (ensuring exact versions and verified hashes). This adds determinism. We won't implement a full resolver - this is just if they supply it. If not, pip's normal resolution is used.

_Rationale:_ In regulated environments, they might want to guarantee the same versions are used each run, and guard against supply-chain attacks by verifying hashes.

_Acceptance:_ Not a separate feature to test beyond what above; just mention in docs that if you need strict reproducibility, include exact pins and we will honor them. Possibly in the artifact or logs, list the installed package versions so there's a record.

**Allow Library Bundling as Alternative:**  
Document that if `runtime_network_access` is false (no internet) or if teams prefer offline installs, they can bundle dependencies by:

- Including a `vendor/` folder with `.whl` or `.py` files and adding a manifest entry such as `"requirements": {"vendor_dir": "vendor/"}` so ADE adds it to `PYTHONPATH`.
- Pre-installing shared libraries in the ADE image (only for universally needed packages).

We won't implement anything heavy for this; just ensure our sandbox's Python path automatically includes the config package root, so if they have pure python modules in columns/ or subfolders, they're importable.

_Acceptance:_ If a user drops a simple module file in the config and imports it from another, it should work (this might already be the case since all scripts are in one package directory). Test by creating columns/helpers.py and using import columns.helpers in another script, see that it works.

**Artifact Annotation of Dependencies:**  
To maintain explainability and an audit trail, add an artifact entry listing dependencies installed for the job, for example:

```json
"environment": {
  "dependencies": ["python-dateutil 2.8.2", "numpy 1.21.0"]
}
```

This could live within the artifact's `config` section. It ensures that two runs of the same config can be differentiated if, say, a dependency version changed (though pinning should keep versions stable).

_Acceptance:_ After a job with requirements runs, artifact JSON contains a list of resolved packages with versions. We verify that is correct and complete.

_Risk:_ Minimal. If something goes wrong (like artifact too large with many deps), we can truncate or remove this detail. But likely fine as the number of deps for a config is small (a handful at most, not hundreds like a whole app).

### 5.5 Artifact & Explainability Enhancements

**Record Mapping Confidence and Rule Traces:**  
We will augment the artifact JSON to include:

- The final score (confidence) for each mapped column, along with the threshold that applied.
- The contribution from each detector rule (function name + score) so users understand how the final confidence was assembled.

For example:

```json
"mapping": {
  "field": "member_id",
  "confidence": 0.87,
  "rules": [
    { "rule": "detect_synonyms", "score": 0.60 },
    { "rule": "detect_email_shape", "score": 0.27 }
  ]
}
```

(for a column that partially matched two rules). If a rule didn't run (maybe logic skipped), it would not appear.

This detailed trace makes the artifact even more useful to debug why ADE chose a certain mapping. It aligns with our emphasis on explainability - users can see not just the final winner but _why_ it won (which clues contributed). Some of this might already be in artifact as "rule traces", but we'll ensure completeness and standardized format.

**Hash of Scripts in Artifact:**  
As discussed in security, compute a hash (say SHA256 truncated for display) for each script file and include that in the artifact's metadata. For example:

```json
"config_package": {
  "id": "my-config:1.2.0",
  "scripts_hash": "e3b0c44298fc...",
  "fields": {
    "member_id": { "script": "columns/member_id.py", "hash": "abc123..." }
  }
}
```

Alternatively, a simpler approach: one overall package hash (perhaps hash of the zip or concatenation of files). The goal is to later verify if needed that the code that ran is exactly what was expected when the config was activated. This also helps identify if two artifacts were produced by the exact same config version (the hash would match).

**Signature Placeholder:**  
If in future we implement signing, we could have manifest contain something like "signature": "&lt;base64sig&gt;" and artifact could note "signature_verified": true/false. But for now, we won't implement that; just keep the structure in mind.

**Acceptance Criteria for Artifact changes:** Run a job and inspect the artifact; verify that:

- Each column entry shows its mapping confidence and, when unmapped, clearly states the reason (e.g., `"decision": "unmapped_low_confidence"`).
- For mapped columns, the sum of rule scores equals the confidence (allowing for rounding).
- Rule entries reference detector function names so contributors can trace the decision path.
- The artifact includes the config package hash; compute it independently to confirm it matches.
- Editing a script after activation triggers a mismatch warning or failure due to hash differences, ensuring tamper detection.

_Risk:_ Adding more data to artifact could increase its size slightly, but should be negligible in comparison to not including cell values. We should ensure the artifact format version is bumped if needed (so that any consumer of artifact can handle new fields). If issues arise (like performance logging every rule score), we could make the detailed rule trace optional or capped. However, given our design (few detectors per field, few fields), this is fine. Rollback would be to drop or reduce the detail if found too verbose.

**Documentation & Guides Updates:**  
Finally, ensure our **Config Package Author Guide** is updated with these changes:

- Show the new manifest fields (pattern, etc.) and explain how to use them.
- Explain how to add dependencies and the implications.
- Provide examples of using the `ade_rules` library in detectors/transforms/validators.
- Offer a checklist for authors (e.g., "Did you specify required fields? Did you set a reasonable confidence threshold? Did you test with the provided kit?") to reinforce best practices.

Each recommendation above comes with a documentation snippet or code example we will integrate into the official docs. We will also highlight that these new features are optional and backward-compatible: older configs will run as before, but can be enhanced by adopting these improvements.

## 6. Minimal Patch Plan (file-by-file)

To implement the recommendations, we outline a minimal set of changes in the codebase (assuming a typical project structure for ADE). This is a high-level plan indicating which files/modules to modify or add:

- **manifest_schema.json (new):** Create the JSON Schema for manifest v1.0 with required keys and types. Store it in the ADE codebase (and optionally expose it in docs). Add a constant such as `CURRENT_MANIFEST_VERSION = "ade.manifest/v1.0"`.
- **ade/config_loader.py** (or similar):
  - Validate `manifest.json` against the schema (using a JSON Schema library).
  - Handle new manifest fields (`requires_engine`, `pattern`, etc.), storing them in an internal config object.
  - Perform version checks when `requires_engine` is present.
  - On validation errors, emit clear messages (initially warnings if we choose a soft rollout).
  - Compute script hashes during package load for later artifact use or integrity checks.
- **ade/rule_executor.py** (pipeline orchestration):
  - **Pass 2 (mapping):** apply `mapping_score_threshold`, leaving ties or low scores unmapped and capturing sorted scores for artifact output.
  - Collect detector function names and their returned scores for rule tracing.
  - **Pass 3 & 4 (transform, validate):** integrate the helper library (ensure `ade_rules` is importable inside the sandbox).
  - **Between Pass 4 and 5:** summarize issues and merge hook returns (including `issues`) into the artifact.
  - **Pass 5 (writing):** optionally provide the output file path to hooks if they need to open the written file.
- **ade/hooks.py** - Update hook invocation:
  - Pass extra context (e.g., output file path) when helpful.
  - Merge hook-returned `issues` or `notes` into the artifact with provenance metadata.
  - Extend the manifest schema only if we later need to declare hook capabilities.
- **ade/artifact_builder.py** - Extend artifact assembly:
  - Record mapping confidences, individual rule contributions, and the winning field for each column.
  - Add config package metadata such as version, script hashes, and installed dependencies.
  - Summarize validation issues by severity.
  - Ensure compatibility with the existing artifact schema or bump the version if needed.
- **ade/security.py** (or the job runner):
  - Compute hashes for scripts and other config files.
  - Optionally apply a seccomp filter when supported; otherwise fall back gracefully.
  - Launch sandboxed processes with hardened Python flags (`-I -B -s -S`) and verify scripts still run.
- **ade/requirements_installer.py** (new, or part of job initialization):
  - When `requirements.txt` is present, install dependencies into a temporary target directory (e.g., via `pip install --target ...`).
  - Respect `runtime_network_access`; fail fast or skip installation if networking is disallowed.
  - Optionally add a simple cache keyed by the requirements hash to avoid reinstalling.
  - Capture the final dependency list (using `pip` output or `importlib.metadata`) and clean up temporary directories.
- **ade_rules.py** (new helper module):
  - Implement the shared detector and validator helpers described above.
  - Pre-compile common patterns (email regex, etc.) as constants.
  - Provide helper functions for validation issue formatting.
  - Make the module importable from sandboxed scripts and add regression tests for the helpers.
- **Docs & Examples:**
  - Update the configuration authoring docs to mention new manifest fields and thresholds.
  - Provide "before and after" illustrations of using the helper library.
  - Document how to ship dependencies with `requirements.txt` or vendored modules.
  - Add guidance for cross-field validation via hooks and highlight the new artifact insights.
  - Prepare a migration note explaining how existing packages continue to work and how to opt into schema validation (`"schema": "ade.manifest/v1.0"` followed by `ade validate`).

Given the modularity, these changes are localized and can be developed and tested in parallel:

- Manifest schema and validation (`config_loader`)
- Scoring changes and artifact enhancements (`rule_executor` / `artifact_builder`)
- Helper library work (`ade_rules`)
- Dependency installation flow (`requirements_installer`)
- Hook and cross-field adjustments (hook system)
- Security hardening (sandbox launch configuration)

We expect implementing and unit-testing each of these to be achievable within one sprint, with perhaps another sprint for integration testing and documentation polish.

## 7. Example Config Package v1.0 (manifest + scripts)

To illustrate the refined design, below is a mini example of a config package (manifest and a couple of scripts) incorporating the recommendations. This example assumes an organization that wants to extract member data with an email, and demonstrates use of synonyms, pattern, transform, validate, and even a cross-field check via hook.

**manifest.json:**

```json
{
  "info": {
    "schema": "ade.manifest/v1.0",
    "title": "Membership Data Config",
    "version": "1.0.0",
    "requires_engine": ">=0.6.0"
  },
  "engine": {
    "defaults": {
      "timeout_ms": 60000,
      "memory_mb": 128,
      "runtime_network_access": false,
      "mapping_score_threshold": 0.5
    },
    "writer": {
      "mode": "row_streaming",
      "append_unmapped_columns": true,
      "unmapped_prefix": "raw_"
    }
  },
  "hooks": {
    "after_validate": [
      { "script": "hooks/after_validate.py" }
    ]
  },
  "columns": {
    "order": ["member_id", "email", "join_date"],
    "meta": {
      "member_id": {
        "label": "Member ID",
        "required": true,
        "script": "columns/member_id.py",
        "synonyms": ["member number", "member #", "ID"],
        "pattern": "^[A-Z]{2}\\d{4}$"
      },
      "email": {
        "label": "Email",
        "required": false,
        "script": "columns/email.py",
        "synonyms": ["email", "e-mail", "email address"],
        "type_hint": "email",
        "privacy": "personal"
      },
      "join_date": {
        "label": "Join Date",
        "required": false,
        "script": "columns/join_date.py",
        "synonyms": ["start date", "date joined", "membership date"],
        "type_hint": "date"
      }
    }
  }
}
```

Key points in this manifest:

- It uses `schema: ade.manifest/v1.0` and has a package version.
- It sets a `mapping_score_threshold` of 0.5, mapping columns only when at least 50% confident.
- `member_id` is required, with synonyms and a specific pattern (two letters + four digits).
- `email` is marked as personal data with common header synonyms.
- `join_date` is optional but type-hinted as `date`, which detection logic can use.
- The configuration includes an `after_validate` hook script.

**requirements.txt:** (not shown above but let's assume it exists if needed)  
For this example, maybe no external requirements are needed, as we can rely on Python stdlib for regex and date parsing. If we wanted to use python-dateutil for date parsing, we'd add it here and set runtime_network_access: true or vendor it.

**columns/member_id.py:**

```python
import re
import ade_rules as rules

# Pre-compile the pattern from manifest for efficiency
PATTERN = re.compile(r"^[A-Z]{2}\d{4}$")

def detect_id_pattern(*, header, values_sample, field_name, field_meta, **_):
    """Detect member ID by header keywords and value pattern."""
    score = 0.0
    score += rules.match_synonyms(header or "", field_meta.get("synonyms", []))
    if values_sample:
        match_fraction = sum(1 for value in values_sample if value and PATTERN.match(str(value))) / len(values_sample)
        if match_fraction > 0.0:
            score += 0.9 * match_fraction  # leave room for header boost
    return {"scores": {field_name: round(score, 2)}}

def transform(*, values, **_):
    # Normalize ID format: remove non-alphanumeric characters and uppercase it
    cleaned = []
    for value in values:
        if value is None:
            cleaned.append(None)
            continue
        normalized = "".join(ch for ch in str(value) if ch.isalnum()).upper()
        cleaned.append(normalized or None)
    return {"values": cleaned, "warnings": []}

def validate(*, values, field_meta, **_):
    issues = []
    if field_meta.get("required"):
        issues += rules.find_required_missing(values, field_name="member_id")
    for index, value in enumerate(values, start=1):
        if value and not PATTERN.match(str(value)):
            issues.append({
                "row_index": index,
                "code": "pattern_mismatch",
                "severity": "warning",
                "message": f"Member ID '{value}' does not match expected format (AA9999)."
            })
    return {"issues": issues}
```

**columns/email.py:**

```python
import re
import ade_rules as rules

# Standard email regex (simplified version)
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

def detect_email(*, header, values_sample, field_name, field_meta, **_):
    score = 0.0
    score += rules.match_synonyms(header or "", field_meta.get("synonyms", []))
    if values_sample:
        match_fraction = sum(1 for value in values_sample if value and EMAIL_REGEX.match(str(value))) / len(values_sample)
        score += round(match_fraction, 2)  # e.g. 0.75 if 75% look like emails
    return {"scores": {field_name: score}}

def transform(*, values, **_):
    # Simple normalization: lower-case all emails
    normalized = [value.lower() if isinstance(value, str) else value for value in values]
    return {"values": normalized, "warnings": []}

def validate(*, values, **_):
    issues = []
    for index, value in enumerate(values, start=1):
        if value and not EMAIL_REGEX.match(str(value)):
            issues.append({
                "row_index": index,
                "code": "invalid_format",
                "severity": "warning",
                "message": f"Value '{value}' is not a valid email address."
            })
    return {"issues": issues}
```

**columns/join_date.py:**

```python
from datetime import datetime
import ade_rules as rules

def detect_date(*, header, values_sample, field_name, field_meta, **_):
    score = 0.0
    score += rules.match_synonyms(header or "", field_meta.get("synonyms", []))
    if values_sample:
        date_count = 0
        for value in values_sample:
            if isinstance(value, str) and "/" in value:
                date_count += 1  # simple heuristic for date-like strings
            elif isinstance(value, (int, float)) and value > 1000:
                date_count += 0.5  # possible Excel serial or year
        fraction = date_count / len(values_sample)
        if fraction > 0.5:
            score += 0.5  # moderate boost if majority look like dates
    return {"scores": {field_name: round(score, 2)}}

def transform(*, values, **_):
    normalized = []
    warnings = []
    for value in values:
        if not value:
            normalized.append(None)
            continue
        text = str(value).strip()
        try:
            parsed = datetime.strptime(text, "%m/%d/%Y")
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                normalized.append(text)  # leave as-is
                warnings.append(f"Unrecognized date format: '{text}'")
                continue
        normalized.append(parsed.strftime("%Y-%m-%d"))
    return {"values": normalized, "warnings": warnings}

def validate(*, values, **_):
    # No additional rules for the example
    return {"issues": []}
```

**hooks/after_validate.py:**

```python
def run(*, artifact, **_):
    # Example cross-field check: ensure join_date is not present without email
    notes = []
    for sheet in artifact.get("sheets", []):
        for table in sheet.get("tables", []):
            fields = table.get("fields", {})
            if "email" not in fields or "join_date" not in fields:
                continue
            email_col = fields["email"]
            date_col = fields["join_date"]
            email_issues = 0
            for row_index, (email_value, date_value) in enumerate(
                zip(email_col.get("values", []), date_col.get("values", [])),
                start=1,
            ):
                if date_value and not email_value:
                    notes.append(f"Row {row_index}: Join Date is present but Email is missing.")
                    email_issues += 1
            if email_issues:
                notes.append(f"Found {email_issues} cases where join_date had no corresponding email.")
    return {"notes": " ; ".join(notes) if notes else None}
```

_Explanation:_ The hook above is contrived; it demonstrates accessing artifact data. We assume the artifact structure has actual values accessible - which it normally wouldn't (only references). In a real scenario, since raw values aren't stored, this hook might not work unless we adjust the artifact to include transformed values for each field (which might be a new feature we'd implement for cross-field logic). If that's not the case, the hook could instead read the output file. For brevity, we showed artifact use.

**Running this Example:**  
Suppose we have an input spreadsheet with columns "Member Number", "Email Address", "Notes", and "Date Joined". ADE would:

- **Pass 1:** detect the header row (likely by density; assume default behavior).
- **Pass 2:**
  - `member_id.detect_id_pattern` finds the "Member Number" column via synonyms and value pattern, mapping it to `member_id`.
  - `email.detect_email` recognizes "Email Address" through header keywords and `@` symbols, mapping to `email`.
  - `join_date.detect_date` matches "Date Joined" via synonyms and date-like values, mapping to `join_date`.
  - "Notes" stays unmapped; with a `mapping_score_threshold` of 0.5, it remains as `raw_Notes`.
- **Pass 3:**
  - `member_id.transform` normalizes IDs (e.g., `ab-1234` -> `AB1234`).
  - `email.transform` lowercases addresses.
  - `join_date.transform` normalizes dates to `YYYY-MM-DD`.
- **Pass 4:**
  - `member_id.validate` flags missing or malformed IDs.
  - `email.validate` warns on invalid email formats.
  - `join_date.validate` emits no issues in this scenario.
- **after_validate hook:** logs rows where `join_date` exists but `email` is missing, e.g., "Row 5: Join Date present but Email missing." The note appears in the artifact for auditing.

**Expected Artifact Excerpts:**  
\- Mapping decisions with confidences, e.g.:

"column_2": {  
"header": "Email Address",  
"field": "email",  
"confidence": 0.85,  
"rules": \[  
{"rule": "detect_email", "score": 0.85}  
\]  
}

\- Validation issues example:

"issues": \[  
{"cell": "B10", "code": "invalid_format", "severity": "warning", "message": "Value 'abc@com' is not a valid email address."},  
{"cell": "A15", "code": "required_missing", "severity": "error", "message": "Member ID is required."}  
\]

\- Hook notes in artifact history:

"notes": "Row 5: Join Date present but Email missing. ; Found 1 cases where join_date had no corresponding email."

\- Package info:

"config_package": {  
"name": "Membership Data Config",  
"version": "1.0.0",  
"manifest_schema": "ade.manifest/v1.0",  
"script_hashes": {  
"columns/member_id.py": "&lt;hash1&gt;",  
"columns/email.py": "&lt;hash2&gt;",  
...  
}  
}

This example, while simplified, demonstrates how the refined config design is used in practice. The manifest is richer but still human-editable. The code is shorter and clearer thanks to helper usage (rules.match_synonyms, etc.). The outcome is more robust (e.g., notes for cross-field conditions, unmapped unexpected columns, etc.), and everything is recorded for traceability.

## 8. Testing & Release Notes

To validate these changes and ensure a smooth transition, we will employ a combination of automated tests, manual testing on sample configs, and clear communication in release notes.

**Automated Testing Plan:**

- **Unit tests for new components:** develop focused tests for:
  - Manifest schema validation (accept valid manifests, reject invalid ones with clear errors).
  - Scoring logic (threshold behavior, tie handling, and rounding).
  - `ade_rules` helpers (synonym matching, regex scoring, missing-value detection).
  - Dependency installation (simulate or mock pip installs to ensure isolation logic).
  - Security flags (ensure sandboxed code cannot invoke blocked operations).
  - Hook integration (confirm `after_validate` issues propagate to the artifact).
- **Integration tests with sample configs:** build end-to-end scenarios:
  - A **basic config** (no new features) to verify backward compatibility with threshold = 0.0.
  - A **feature-rich config** (section 7 example) to validate confidence thresholds, issue codes, rule traces, warnings, hook notes, and dependency handling.
  - A **performance regression** case using a moderate dataset (~10k rows x 20 columns) to ensure runtime remains acceptable.
- **Negative tests:** provide malformed manifests and confirm immediate, descriptive errors. Combine `runtime_network_access: false` with `requirements.txt` to ensure we fail fast with guidance to enable networking or vendor packages.
- **Backward compatibility check:** run archived real-world configs and investigate any deviations. Defaults should yield identical behavior; only intentional fixes should change results.
- **Security tests:** attempt disallowed operations (e.g., `open("/etc/passwd")`) and deliberate sandbox escapes such as the `__builtins__` trick[\[18\]](https://healeycodes.com/running-untrusted-python-code#:~:text=__builtins__%20%3D%20), confirming hardened interpreters block them.

**User Acceptance Testing:** Before release, create a release candidate build and exercise it with a friendly user or staging environment:

- Import existing configs, run representative jobs, and confirm behavior matches expectations.
- Try new features individually with real data:
  - Use manifest synonyms/pattern fields and observe improved mapping.
  - Enable a mapping threshold and verify low-confidence columns remain unmapped (emitted as `raw_*`).
  - Add a known library via `requirements.txt` (e.g., `phonenumbers`) and confirm detection logic can import it.
  - Run the test kit CLI (if available) to validate the config and ensure all checks pass.

**Release Notes:**

Draft a section in the release notes (and communicate via an upgrade guide) highlighting:

- **Manifest Schema & Validation:** "ADE now validates config manifest files against a schema. Include `info.schema` (ADE auto-fills v1.0 on save). Non-conforming entries raise warnings/errors so you can fix issues early."
- **New Manifest Options:** Describe optional fields (`pattern`, `type_hint`, etc.), emphasizing that they are opt-in enhancements.
- **Scoring and Mapping:** Introduce `mapping_score_threshold` (default 0) with an example of avoiding dubious mappings by raising the threshold.
- **Helper Library:** "We added an `ade_rules` module with helper functions for detectors/validators (synonym matching, regex checks, etc.). Existing configs keep working; adopt helpers at your pace."
- **Validation Enhancements:** Highlight standard issue codes and cross-field checks via hooks; note that reading the output file may be required initially.
- **Dependencies in Configs:** Explain `requirements.txt` support, when to set `runtime_network_access: true`, and how to vendor libraries or pin versions. Note that installs are per-job and cleaned up.
- **Security Updates:** Mention sandbox tightening (isolated mode, potential seccomp). Warn that previously permissive scripts might now fail if they attempt disallowed operations.
- **Artifact Changes:** Inform users that artifact JSON now includes mapping confidences, rule traces, and config metadata. Encourage tooling updates to handle new fields; artifact version is bumped accordingly.
- **Backward Compatibility:** Assure users that existing config packages still run unless manifest validation exposes latent errors. Recommend re-running critical configs in a staging environment.
- **Testing Tools:** If a CLI/test kit ships, point to `ade validate` and `ade test` for quick checks; otherwise clarify that it remains internal for now.

**Documentation and Training:** The release notes will point to the updated documentation sections for details. We may also host a short webinar or write a blog post ("Writing Safer ADE Configs with the new v1.0 manifest") to walk through these improvements for our user community, making adoption smoother.

## 9. Risks, Trade-offs, and Rollback

While these refinements are designed to be incremental and low-risk, we acknowledge potential trade-offs and have considered rollback strategies:

- **Backward Compatibility Risk:** There's a small chance that by enforcing manifest validation, some legacy config might break (e.g., if it had a subtle error that previously was ignored). Trade-off: catching errors is usually good, but if a config can't be loaded, that's a disruption. _Mitigation:_ We can start by logging a warning for schema violations rather than failing outright, in the first release. Give users time to adjust. If something catastrophic occurs (many configs failing validation unexpectedly), we could roll back to non-strict mode quickly via a patch.
- **User Learning Curve:** Authors will need to learn the new manifest fields and helper library. If not, they might be confused by warnings or changes (like "What is this schema version thing?"). Trade-off: Slight upfront effort vs. long-term benefit of clarity. _Mitigation:_ Provide clear docs, examples (like the one above), and possibly deprecate slowly. We intentionally kept all new features optional. If a user does nothing differently, their config should behave the same (no threshold by default, etc.). We will monitor support channels for any confusion and be ready to clarify. Rollback isn't needed for this, but we might refine documentation or provide a quick cheat-sheet if multiple users stumble.
- **Confidence Threshold Impact:** If a user sets a threshold without fully understanding it, they might end up with lots of unmapped columns and incomplete outputs. Trade-off: flexibility vs. risk of misconfiguration. _Mitigation:_ Default is no threshold. We'll document it as an advanced feature. Also, the artifact explicitly shows when threshold prevented a mapping, so if they see many unmapped columns, they can adjust. If threshold concept proves problematic, we could disable it or leave it experimental (but since default is off, the risk is contained).
- **Performance Overhead:** Additional validation, logging, and dependency installation could slow down jobs. For instance, computing hashes or installing packages takes time. Trade-off: richer functionality vs. speed. _Mitigation:_
- Manifest validation and hashing happen once per job, which is negligible compared to reading a spreadsheet.
- Logging a bit more info to artifact is trivial overhead.
- The biggest hit is dependency installation: downloading and installing libs could add seconds or minutes if large. We will emphasize using that feature only when needed and maybe suggest caching layers. If a particular config's dependencies are static, an admin might even pre-install them in the container to avoid runtime cost (we can mention that).
- We plan to add caching of venvs if needed to reuse installations across jobs (but not in initial release). If performance issues are reported, we can optimize in subsequent releases. Rollback scenario: in worst case, if auto-pip proves too slow/unreliable, we could disable it and require vendoring, but that's unlikely if used properly.
- **Sandbox Hardening Issues:** Introducing seccomp or stricter import rules might have unforeseen side effects (maybe a library tries to open a file in temp and fails, or a harmless syscall gets blocked). Trade-off: security vs. possible breakage of legitimate code. _Mitigation:_
- We'll test common operations. Seccomp filters will be set carefully (e.g., allow read, write on already open fds, disallow exec).
- We might initially put seccomp behind a feature flag or environment variable so we can turn it off quickly if needed.
- If an issue arises (e.g., a user says "my transform uses pandas and now it crashes"), we can investigate which syscall was blocked and adjust the filter or disable seccomp in a hotfix. The rlimits and Python -I flags are safer changes (shouldn't break code that follows rules).
- Rollback: can ship a patch that removes or loosens the sandbox restrictions if absolutely necessary.
- Code signing (which we didn't fully implement) has no risk since it's not there yet; hashing has little risk.
- **User Adoption of Helper Library:** There's a risk that some authors won't use the new ade_rules and continue writing their own (maybe because they trust their code more or don't know about it). That's fine, but then we lose some consistency benefits. Trade-off: we can't force style, only encourage. _Mitigation:_ We'll showcase the convenience of the library in examples and maybe gradually move all official sample configs to use it, signaling it's the preferred method. If any critical bug is found in a helper function, worst-case authors can revert to custom code until we fix it - the architecture allows that flexibility. Rollback isn't needed since it's optional; we just maintain it actively.
- **Complexity vs. Simplicity:** Adding these features slightly increases the complexity of the system. There's a risk we drift from "lightweight" if we're not careful (especially with dependency management and cross-field checks). Trade-off: added capability vs. simplicity. We deliberately kept heavy things (like ML or external services) out. The added complexity is mostly internal (manifest validation, etc.) and hidden behind the scenes or optional. We will monitor whether these changes cause any maintenance burden - e.g., does maintaining the manifest JSON Schema create friction if we change something? We'll manage that by versioning the schema properly. If at some point we find a feature is not worth its complexity (for instance, if cross-field checks via hooks prove too confusing and a better design emerges), we can deprecate that approach and introduce a more streamlined one.

In summary, each improvement has been weighed for risk. Our strategy is to **implement conservatively, test thoroughly, and introduce changes in a backward-compatible manner**. If any recommendation proves problematic in real-world use, we have fallbacks: e.g., disable strict validation, toggle sandbox features, or simply not enforce new options. The final safety net is that we can always allow users to stick with their previous active config (since one active config remains in place until a new one is explicitly activated), but since the engine changes apply to all, we'd rather fix issues than require rolling back the whole application. We will plan a minor version release (e.g., ADE 0.6.0 to 0.6.1) shortly after, to address any post-release findings quickly.

The overall goal is that after these changes, users feel the system is **even more robust and user-friendly** without feeling it became a different product. We will closely watch for feedback and be ready to make quick adjustments as needed.

## 10. References

- **dbt Package Versioning and Compatibility** - _dbt's documentation on package config and versioning._ Demonstrates how dbt projects declare allowed dbt engine versions (via require-dbt-version) and use semantic versioning for packages[\[2\]](https://docs.getdbt.com/guides/building-packages#:~:text=just%20created,version%20config). This informed our approach to add a requires_engine field and semver to ADE's manifest for safe upgrades.
- **dbt Manifest Artifact JSON Schema** - _dbt Developer Hub: Manifest JSON file reference._ Describes how each dbt run produces a manifest.json with a defined schema and version mapping to dbt versions[\[1\]](https://docs.getdbt.com/reference/artifacts/manifest-json#:~:text=You%20can%20refer%20to%20dbt,and%20consuming%20dbt%20generated%20artifacts). Validating against such a schema is a best practice we adopted for ADE's manifest to ensure config integrity and clarity.
- **Frictionless Table Schema** - _Frictionless Data Table Schema specification._ Provides a JSON format for table schemas, including field constraints (required, pattern matching, etc.)[\[4\]](https://specs.frictionlessdata.io//table-schema/#:~:text=The%20,updated%20via%20a%20data%20entry). This influenced our decision to enrich ADE's manifest with field-level metadata like regex patterns and required flags, enabling built-in validation akin to frictionless's approach to declarative data checks.
- **Great Expectations - Storing Expectations as Code** - _Great Expectations documentation (v0.18) on Expectation Suites._ Emphasizes that expectation suites (data validation rules) are saved as JSON and version-controlled just like code[\[6\]](https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/expectation_suite/#:~:text=Save%20Expectation%20Suites). This parallels our treatment of ADE config packages as versioned artifacts and inspired our test harness idea (similar to GE's checkpoints to regularly validate data against expectations).
- **Great Expectations - Severity Metadata** - _Data quality blog (StartDataEngineering) on using Great Expectations._ Explains how teams add severity levels in expectation metadata and handle them (e.g., only alert on certain severities)[\[7\]](https://www.startdataengineering.com/post/implement_data_quality_with_great_expectations/#:~:text=Most%20companies%20have%20varying%20levels,of%20severity). This guided us to standardize issue codes and severities in ADE, so validation results can be categorized (error vs warning) consistently for downstream action.
- **Pandera - Built-in Validation Checks** - _Pandera documentation on checks._ Shows examples of Pandera's built-in check helpers like Check.less_than(100) and Check.str_matches(regex)[\[3\]](https://pandera.readthedocs.io/en/stable/checks.html#:~:text=schema%20%3D%20pa.DataFrameSchema%28%7B%20,). This reinforced the value of providing a library of common rule functions in ADE (for scoring and validation) to avoid reinventing the wheel for each config.
- **Airbyte Connector Spec & UI Annotations** - _Airbyte docs: Connector Specification Reference._ Details how connectors declare config in JSON Schema and use special fields like airbyte_secret to mark sensitive fields and order to arrange fields in UI[\[10\]](https://docs.airbyte.com/platform/connector-development/connector-specification-reference#:~:text=By%20default%2C%20any%20fields%20in,e.g)[\[11\]](https://docs.airbyte.com/platform/connector-development/connector-specification-reference#:~:text=Ordering%20fields%20in%20the%20UI). This influenced our addition of a privacy flag for fields and considering manifest metadata that could hint at UI (though ADE's UI is simpler, the concept of including these in the spec is adopted).
- **Airbyte Connector Acceptance Tests** - _Airbyte docs: Acceptance Tests Reference._ Describes Airbyte's standard test suite for connectors to ensure each meets protocol requirements[\[5\]](https://docs.airbyte.com/platform/connector-development/testing-connectors/connector-acceptance-tests-reference#:~:text=To%20ensure%20a%20minimum%20quality,or%20invalid%29%20inputs). This motivated our recommendation to create a config package test kit (TCK) for ADE, to similarly enforce a quality baseline and catch issues early for any custom config logic.
- **OpenRefine Transformation History** - _OpenRefine tutorial (Library Carpentry) on exporting and reusing scripts._ Explains that OpenRefine records every data cleaning step in a JSON file that can be reapplied to other datasets[\[9\]](https://carpentry.library.ucsb.edu/2022-04-14-ucsb-openrefine/12-export-transformation/index.html#:~:text=As%20you%20conduct%20your%20data,all%20of%20your%20related%20data). This validated our approach of treating ADE's config + artifact as a complete record of "what happened", and inspired us to ensure portability (export/import) and traceability (detailed artifact logging of each rule's effect).
- **Sandboxing Untrusted Code (Security)** - _Andrew Healey's blog "Running Untrusted Python Code"._ Outlines best practices for sandboxing: run code in a separate process, drop permissions with seccomp, apply resource limits, and avoid relying solely on Python-level restrictions[\[16\]](https://healeycodes.com/running-untrusted-python-code#:~:text=How%20it%20works)[\[15\]](https://healeycodes.com/running-untrusted-python-code#:~:text=setrlimit%20is%20one%20of%20the,files%20created%20by%20the%20process). This strongly guided ADE's sandbox hardening: we continue using subprocess isolation and have implemented OS-level safeguards (CPU/memory limits, and planning seccomp) to safely execute user-provided config code. The blog also shows how simply removing builtins is insufficient[\[18\]](https://healeycodes.com/running-untrusted-python-code#:~:text=__builtins__%20%3D%20), reinforcing our approach to use true OS isolation.

[\[1\]](https://docs.getdbt.com/reference/artifacts/manifest-json#:~:text=You%20can%20refer%20to%20dbt,and%20consuming%20dbt%20generated%20artifacts) Manifest JSON file | dbt Developer Hub

<https://docs.getdbt.com/reference/artifacts/manifest-json>

[\[2\]](https://docs.getdbt.com/guides/building-packages#:~:text=just%20created,version%20config) Building dbt packages | dbt Developer Hub

<https://docs.getdbt.com/guides/building-packages>

[\[3\]](https://pandera.readthedocs.io/en/stable/checks.html#:~:text=schema%20%3D%20pa.DataFrameSchema%28%7B%20,) [\[8\]](https://pandera.readthedocs.io/en/stable/checks.html#:~:text=Column%20Check%20Groups%C2%B6) Validating with Checks - pandera documentation

<https://pandera.readthedocs.io/en/stable/checks.html>

[\[4\]](https://specs.frictionlessdata.io//table-schema/#:~:text=The%20,updated%20via%20a%20data%20entry) Table Schema | Data Package (v1)

<https://specs.frictionlessdata.io//table-schema/>

[\[5\]](https://docs.airbyte.com/platform/connector-development/testing-connectors/connector-acceptance-tests-reference#:~:text=To%20ensure%20a%20minimum%20quality,or%20invalid%29%20inputs) Acceptance Tests Reference | Airbyte Docs

<https://docs.airbyte.com/platform/connector-development/testing-connectors/connector-acceptance-tests-reference>

[\[6\]](https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/expectation_suite/#:~:text=Save%20Expectation%20Suites) Expectation Suite | Great Expectations

<https://docs.greatexpectations.io/docs/0.18/reference/learn/terms/expectation_suite/>

[\[7\]](https://www.startdataengineering.com/post/implement_data_quality_with_great_expectations/#:~:text=Most%20companies%20have%20varying%20levels,of%20severity) How to implement data quality checks with greatexpectations - Start Data Engineering

<https://www.startdataengineering.com/post/implement_data_quality_with_great_expectations/>

[\[9\]](https://carpentry.library.ucsb.edu/2022-04-14-ucsb-openrefine/12-export-transformation/index.html#:~:text=As%20you%20conduct%20your%20data,all%20of%20your%20related%20data) Exporting Transformed Data, Saving and Reusing Scripts - Introduction to OpenRefine

<https://carpentry.library.ucsb.edu/2022-04-14-ucsb-openrefine/12-export-transformation/index.html>

[\[10\]](https://docs.airbyte.com/platform/connector-development/connector-specification-reference#:~:text=By%20default%2C%20any%20fields%20in,e.g) [\[11\]](https://docs.airbyte.com/platform/connector-development/connector-specification-reference#:~:text=Ordering%20fields%20in%20the%20UI) Connector Specification Reference | Airbyte Docs

<https://docs.airbyte.com/platform/connector-development/connector-specification-reference>

[\[12\]](https://healeycodes.com/running-untrusted-python-code#:~:text=I%20have%20side,to%20parts%20of%20the%20runtime) [\[13\]](https://healeycodes.com/running-untrusted-python-code#:~:text=lookup%20%3D%20lambda%20n%3A%20,0) [\[14\]](https://healeycodes.com/running-untrusted-python-code#:~:text=When%20using%20a%20separate%20process,run%20into%20a%20permissions%20issue) [\[15\]](https://healeycodes.com/running-untrusted-python-code#:~:text=setrlimit%20is%20one%20of%20the,files%20created%20by%20the%20process) [\[16\]](https://healeycodes.com/running-untrusted-python-code#:~:text=How%20it%20works) [\[17\]](https://healeycodes.com/running-untrusted-python-code#:~:text=For%20my%20sandbox%2C%20the%20layer,to%20already%20open%20file%20descriptors) [\[18\]](https://healeycodes.com/running-untrusted-python-code#:~:text=__builtins__%20%3D%20) Running Untrusted Python Code - Andrew Healey

<https://healeycodes.com/running-untrusted-python-code>
