# ComponentSpec Source Annotations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a source-preserving, line-by-line annotated copy of the ComponentSpec YAML and verify annotation coverage and YAML equivalence.

**Architecture:** A small deterministic text transformer tracks YAML section and parameter context, appends one of four approved source classifications to every data-bearing line, and preserves existing comments. A separate verification pass checks coverage, parseability, and structural equivalence.

**Tech Stack:** Python 3 standard library, PyYAML when available, pytest-style command-line assertions.

## Global Constraints

- Do not modify `D:/ragxinchuang/component-spec-v1.2-template.yaml`.
- Annotate only YAML data-bearing lines; preserve blank and comment-only lines.
- Every annotation must use `@：<one of four categories>；<reason>`.
- Preserve YAML semantics by placing annotations inside line comments.

---

### Task 1: Deterministic Annotation Generator

**Files:**
- Create: `tools/annotate_component_spec.py`
- Create: `docs/component-spec-v1.2-template.annotated.yaml`

**Interfaces:**
- Consumes: UTF-8 YAML source path and output path.
- Produces: annotated YAML with one source classification per data line.

- [ ] **Step 1:** Implement safe recognition of inline comments without treating `#` inside quoted strings as a comment.
- [ ] **Step 2:** Track top-level section, current parameter, port, preset, construction operation, validation block, artifact, and provenance context.
- [ ] **Step 3:** Encode field-specific classification rules and reasons using the approved four categories.
- [ ] **Step 4:** Generate `docs/component-spec-v1.2-template.annotated.yaml` from the untouched source.

### Task 2: Coverage and Structural Verification

**Files:**
- Modify: `tools/annotate_component_spec.py`
- Verify: `docs/component-spec-v1.2-template.annotated.yaml`

**Interfaces:**
- Consumes: source and annotated YAML.
- Produces: non-zero exit for missing/duplicate annotations, YAML parse failures, or structural differences.

- [ ] **Step 1:** Assert every source data line has exactly one output `@：` marker.
- [ ] **Step 2:** Assert source and output have the same physical line count.
- [ ] **Step 3:** Load both files with PyYAML and assert their parsed data structures are equal.
- [ ] **Step 4:** Print category counts and representative annotated lines for manual review.

### Task 3: Recommended Runtime Fields

**Files:**
- No repository file changes.

**Interfaces:**
- Consumes: the gaps identified across retrieval, generation, and assembly.
- Produces: a chat response containing suggested YAML fields with matching `@：` annotations.

- [ ] **Step 1:** Provide fields for resolved variant identity and artifact retrieval.
- [ ] **Step 2:** Provide fields for source-to-canonical transforms and geometry-anchored ports.
- [ ] **Step 3:** Provide executable mate behavior, generation readiness, and field-level evidence fields.
