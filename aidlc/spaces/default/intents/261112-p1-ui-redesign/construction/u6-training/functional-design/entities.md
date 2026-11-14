# Entities — u6-training

These entities serve the U6 rows (FR7.1–FR7.7, FR8.1) of `inception/units-generation/unit-of-work-story-map.md`, taken from `inception/requirements-analysis/requirements.md`. They sit inside the Lessons component of `inception/domain-design/components.md`. Lessons are read-only data that live in files. Nothing in this unit is stored in the database.

```yaml
entities:
  - name: LessonFile
    description: One file in lessons/ (YAML or JSON) holding one opening line. The file name without its extension is the lesson id.
    attributes:
      - { name: id, type: string, required: true, unique: true, constraints: "from the file name; ^[a-z0-9][a-z0-9-]{0,47}$" }
      - { name: name, type: string, required: true, max: 80 }
      - { name: aliases, type: list<string>, required: false, default: [] }
      - { name: eco, type: string, required: false, constraints: "^[A-E][0-9]{2}$; only when verified" }
      - { name: side, type: enum, required: true, allowed: [white, black], description: default side the learner practises }
      - { name: start, type: string, required: false, default: startpos, description: "startpos or a FEN" }
      - { name: moves, type: list<LessonMove>, required: true, min: 1, max: 60 }
      - { name: objectives, type: list<string>, required: false, default: [] }
    constraints:
      - every move must be legal in sequence from start
      - when a move gives both san and uci they must name the same move
    relationships:
      - { to: LessonMove, cardinality: "1..60", direction: owns }

  - name: LessonMove
    description: One ply of the taught line.
    attributes:
      - { name: san, type: string, required: true }
      - { name: uci, type: string, required: false, description: filled in by the loader when absent }
      - { name: note, type: string, required: true, max: 280 }
      - { name: alternatives, type: "list<{san, note}>", required: false, default: [], description: "other good moves, shown as text; never accepted as the line" }

  - name: LessonStep
    description: Derived by the loader for each ply; what the client needs to teach that move.
    attributes:
      - { name: ply, type: integer, required: true, min: 0 }
      - { name: side, type: enum, allowed: [white, black] }
      - { name: san, type: string }
      - { name: uci, type: string }
      - { name: note, type: string }
      - { name: fenBefore, type: string }
      - { name: fenAfter, type: string }
      - { name: legalBefore, type: list<string>, description: every legal UCI move in fenBefore }
      - { name: alternatives, type: "list<{san, note}>" }
    relationships:
      - { to: LessonFile, cardinality: "many..1", direction: derived-from }

  - name: LessonCatalog
    description: In-memory set of valid lessons plus the problems found while loading.
    attributes:
      - { name: lessons, type: "map<id, Lesson>" }
      - { name: problems, type: "list<{file, reason}>" }
      - { name: loadedAt, type: timestamp }
      - { name: dirStamp, type: string, description: "file names plus modification times, used to reload when the folder changes" }
```

## Summary

- **LessonFile:** what a person writes. **LessonMove** entries sit inside it.
- **LessonStep:** computed by the server, so the browser needs no chess engine for the taught line.
- **LessonCatalog:** the loaded set. Bad files land in `problems` and never break the good ones.
- Positions off the line in free play are computed on request (rules.md BR2.3) and are not stored anywhere.
