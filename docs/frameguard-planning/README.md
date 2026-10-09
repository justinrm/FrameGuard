# FrameGuard v0.1 planning drafts

Status: **DRAFT — owner review required; no implementation authorized.** Prepared 2026-10-08 from the supplied MVP handoff and current upstream research. These documents are recommendations, not an approved specification or verification of a working product.

The intended outcome is a small Python-first, local/offline, single-video CLI that reports technical evidence without making creative judgments. The source media is read-only. JSON is authoritative; terminal and standalone HTML render the same normalized report. Cloud services, AI frameworks, editing, batch processing, and frame-pacing analysis remain excluded.

## Reading order and deliverables

[Planning review](planning-review.md) follows the requested thirteen-section response order and includes specification critique, open-source research, feasibility evidence, repository reconciliation, and approval decisions. [Architecture](architecture.md) defines proposed interfaces, data contracts, selection policies, timestamps, failure handling, and process safety. [Implementation roadmap](implementation-plan.md) is a milestone/task backlog with dependencies, tests, outputs, and gates. [Acceptance-test matrix](acceptance-tests.md) maps FR-01–FR-12, T01–T16, additional edge cases, fixtures, and release evidence. [Risk register](risk-register.md) covers realistic risks and mitigations. [First coding-session handoff](coding-session-handoff.md) is a bounded prompt for Milestone 0 and conditional Milestone 1.

The original supplied specification remains the baseline. Where these drafts propose changes, the review explicitly labels them required, recommended, or future-only. Decisions A1–A4 in the review must be settled before publishing support claims or implementing the affected contract. Milestone 0 may expose reasons to revise the drafts; such revisions require recorded owner agreement, not silent changes.

## Evidence boundary

The selected folder was empty and had no project-local Git repository when inspected. Read-only environment checks found Linux workspace Python 3.10.12, FFmpeg/FFprobe 4.4.2, and uv 0.12.13. This is not the user's macOS environment and does not establish compatibility with the proposed runtime. No product code, scaffold, Git initialization, dependencies, media fixtures, or release artifacts were created. No media-analysis experiment or product test was run in this planning session.

Documented FFmpeg capabilities and current upstream source were researched. EOF/timestamp behavior still needs experiments on pinned release binaries. Moving upstream `master`/`main` links are reference evidence, not a reproducibility pin; Milestone 0 must record release/build identifiers and source revisions where relevant.

## Approval and next action

Review the proposed contracts and approve or amend A1–A4. Then authorize **Milestone 0 only**, or explicitly authorize Milestone 0 followed by Milestone 1 if all its gates pass. The handoff includes stop conditions. License selection can remain pending during private engineering work but blocks public distribution.

## Planning verification

The seven drafts were checked for local-link resolution, balanced code fences, all thirteen requested review sections, FR-01–FR-12 and T01–T16 traceability, and twenty-one milestone tasks. An independent read-only reviewer identified three material draft issues: ambiguous return-code wording, potential loss of early decode errors when a diagnostic tail rotates, and missing explicit edit-list acceptance evidence. The drafts now require zero-exit/no-failure completion, sticky decode-error detection plus validated -xerror behavior, and a verified MOV/MP4 edit-list fixture. This is document review, not passed application tests, media experiments, installation evidence, or release validation.
