# Clinical Pathway Case Authoring Standard

**Version:** 2.0  
**Status:** operational authority  
**Scope:** complete AMC-style case construction only

## 1. Purpose

This standard governs how one complete clinical station case is selected, researched, authored, checked, reviewed, and locked.

The system must produce a coherent case from repository data and an explicit case command. It must not require the operator to duplicate information already stored in the curriculum, registries, or sources.

The authoring sequence is:

```text
Select one mapped case
→ inspect the curriculum and station contracts
→ verify current sources
→ build one clinical truth
→ write the visible station
→ write patient and examiner layers
→ write the full spoken station
→ add flexibility and recovery
→ run structural checks
→ obtain independent and human review
→ lock one exact content hash
```

## 2. Boundary

The Case Builder creates the clinical case only.

It does not create:

- ADHD-oriented Hints
- learner reasoning nodes
- visual task anchors
- reading or performance clocks
- learner progress controls
- website output
- clinical approval
- final release approval

Those jobs belong to separate components.

## 3. Authority order

Use the first applicable authority:

1. Current explicit user decision, unless it bypasses safety or falsely claims approval.
2. The operational repository and its locked decisions.
3. The selected curriculum entry and station grammar registry.
4. Current case-specific Australian clinical sources.
5. This standard and the machine schemas.

When authorities conflict:

```text
HOLD
→ name the exact conflict
→ identify the affected field or claim
→ do not blend the authorities
```

## 4. Repository-derived context

The repository contains the stable project context:

- four phases
- forty presentation patterns
- one hundred and sixty mapped case slots
- station grammars
- failure modes
- stable ID rules
- source policy
- visual anchors used downstream
- current case queue

The operator selects work with a short command:

```text
BUILD_CASE CP-P001-C001
```

The system derives the case context from the selected curriculum entry. It does not request re-entry of phase, pattern, slot, title, status, or other repository facts.

For a revision, the exact previous canonical case and unresolved findings must be supplied.

## 5. Automatic preflight

Before writing, the Case Builder must automatically determine and record:

- case identity
- phase
- pattern
- evolution slot
- classification
- case job
- confidence target
- primary station grammar
- exact task recipients
- likely failure mode
- meaningful variation
- current source needs
- forbidden assumptions

It must then check:

- the selected case exists in the curriculum
- the requested operation is authorised
- the station can fit two minutes of reading and eight minutes of performance
- current clinical sources can support the intended claims
- no existing case already trains the same job
- the case does not rely on unavailable resources
- the intended case does not expose the diagnosis in a diagnostic station

A genuine missing clinical fact, unresolved source conflict, or unsafe uncertainty returns HOLD.

## 6. Case selection

The case map is broad. Generation is narrow.

A case is justified only when it adds at least one distinct training job:

- a new station contract
- a new dangerous turn
- a different failure pattern
- a changed action threshold
- a different communication challenge
- a new interpretation or performance target

Changing only a name, age, or cosmetic setting is not a new case.

The four phases are:

1. Critical Emergency Dominance
2. High Complexity Pattern Mastery
3. Communication and Risk
4. Examination Performance

The phase chooses the capability. The station grammar chooses the encounter shape. The case is the vehicle.

## 7. Station grammar

Every case declares one primary grammar:

- consultation
- emergency
- physical examination
- investigation interpretation
- examiner presentation
- MSE or cognition
- counselling
- procedure or consent
- student teaching

A mixed station may contain secondary elements, but the primary grammar controls timing, task order, information release, and the full spoken run.

The disease does not choose the station shape. The assessment task does.

## 8. Visible station contract

The visible station must contain:

- condition or station number
- short neutral title
- doctor role and setting
- patient or encounter context
- information genuinely available before entry
- explicit action-based tasks
- necessary constraints
- reading and performance times

Tasks are labelled and itemised. Each task must have a clear action and recipient.

The visible station must not contain:

- hidden diagnosis in a diagnostic station
- dominant trap
- failure mode
- model answer
- clinical teaching
- critical errors
- source notes
- governance information

## 9. Complete clinical truth

Clinical truth is fixed before dialogue.

It contains:

- priority problem
- main danger
- first plausible explanation
- chronology
- relevant positives and negatives
- risk factors
- observations and examination findings
- investigation availability and results
- action threshold
- immediate and parallel actions
- management boundaries
- escalation and disposition
- safety net
- final close or handover
- current claims and source references

Every later layer must describe the same patient and the same clinical reality.

Do not invent a fact because a later script needs it.

## 10. Patient layer

The patient or other role-player carries the lived story.

Define:

- identity
- opening line
- volunteered information
- information revealed only after a relevant question
- emotional tone
- ideas, concerns, and expectations
- questions
- resistance or refusal
- acceptance condition
- information that must not be volunteered

Patient speech must sound natural and use lay language. The patient must not teach or rescue the doctor.

## 11. Examiner layer

The examiner carries controlled findings and prompts.

Define:

- aim and assessed domains
- findings available automatically
- findings released only after a valid request
- unavailable information
- timing prompts
- examiner questions
- expected response content
- critical omissions
- end behaviour

The examiner supplies data, not the answer.

## 12. Full spoken station

Write the whole safe station from first word to final close or handover.

Use role-correct turns:

- doctor
- patient or role-player
- examiner
- observable doctor action
- handover

The full run must:

- complete every visible task
- follow the primary grammar
- use only facts from the clinical truth
- cross an action threshold at the correct point
- continue focused assessment safely when appropriate
- address patient questions and resistance
- reach the stated endpoint
- fit natural speech within the station time

A phrase bank, checklist, or summary is not a complete station.

## 13. Flexibility and recovery

Every meaningful new fact may require the doctor to:

```text
continue
switch
or escalate
```

Use at least three flexibility checkpoints when clinically applicable:

1. after the starting information
2. after pivotal clinical evidence
3. during the final interaction, challenge, interpretation, or counselling turn

Each checkpoint states:

- what changed
- what still fits
- what no longer fits
- what is now unsafe to miss
- whether the action threshold changed
- the required direction
- the rigid response to avoid

The recovery pathway states the common wrong start, the earliest recovery trigger, a natural recovery sentence, the updated action, and the safe re-entry point.

## 14. Clinical source governance

Draft generation may use web research only under the source policy.

For every clinical claim, record:

- claim ID
- exact claim
- risk level
- source ID
- source title and issuing body
- jurisdiction
- publication date or version
- source URL
- exact location
- access date
- archive state

Use current Australian guidance whenever available. AMC material controls examination mechanics, not current treatment.

High-risk or critical claims without adequate support return HOLD.

A draft source may be discovered but not yet archived. Before lock, Codex must archive the exact source, calculate its SHA-256, and update the source record. Human source and clinical review then cover the exact canonical hash.

## 15. Stable IDs and references

Use stable IDs for:

- stem nodes
- tasks
- facts
- findings
- actions
- decisions
- claims
- Gold Run turns
- flexibility checkpoints
- sources

Every reference must resolve. No dangling target is permitted.

## 16. Output order

The canonical case contains, in order:

1. method authority
2. authority summary
3. visible station card
4. complete clinical truth
5. patient layer
6. examiner layer
7. full Gold Run
8. flexibility and recovery
9. assessment guide
10. source governance
11. workflow and integrity

The Case Builder returns either:

- one canonical case JSON, or
- one precise HOLD report

It does not return commentary around the JSON.

## 17. Status and approval

Keep these separate:

- generation status
- structure audit
- source review
- clinical review
- timing test
- canonical lock state

The generator leaves human review fields unassigned.

A case can be locked only when:

- the schema passes
- stable IDs and cross-references pass
- source archives and hashes pass
- structure audit passes
- source review passes
- clinical review passes
- human timing test passes
- the lock record names the human locker
- every review covers the same authoring hash
- no blocking hold remains

A technical pass is not clinical approval.

## 18. Repair rule

When a defect is found:

```text
name the defect
→ identify the earliest faulty layer
→ repair that layer
→ propagate the change through dependent layers
→ recompute hashes
→ rerun the full audit
```

Do not patch only the final visible symptom of an upstream contradiction.

## 19. Forbidden drift

Never:

- invent missing clinical material
- claim a source was checked when it was not
- create human approval
- change clinical urgency to simplify language
- delay urgent action for completion of a history template
- expose hidden answers in the visible station
- use exam recall as clinical authority
- let the patient or examiner disclose the solution
- create learner Hints or website data in the Case Builder
- rely on chat memory as project authority

## 20. Import response

When permanent Knowledge is loaded, do not generate a case. Return:

```text
CASE AUTHORING ENGINE LOADED
Standard version: 2.0
Curriculum loaded: YES / NO
Station grammars loaded: YES / NO
Source policy loaded: YES / NO
Schemas loaded: YES / NO
Clinical generation performed: NO
Conflicts: NONE / exact list
Ready for BUILD_CASE: YES / NO
```
