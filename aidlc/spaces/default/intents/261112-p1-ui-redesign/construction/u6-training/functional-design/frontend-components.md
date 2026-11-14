# Frontend Components — u6-training

These are the component contracts for the training screen. The behaviour is in `functional-spec.md` and the rules in `rules.md`. The modules are native ES modules under `static/js/training/`, with no build step.

## Hierarchy

```
static/js/training/
├── trainer-state.js   PURE reducer: reduce(state, event) → {state, effects}
├── arrow.js           PURE: arrowGeometry(fromSq, toSq, orientation) → {x1,y1,x2,y2} in board %; render helper
├── trainer.js         mountTrainer(element, {api, initialLessonId?}) → {destroy()}
└── lessons-api.js     list(), get(id), positionMove(fen, uci) — same {ok,data}|{ok:false,…} shape as U3's api.js
static/css/training.css
```

`static/js/app.js` (U3) gains:
- the `/learn` and `/learn/{id}` routes;
- the lobby "Learn an opening" button;
- `setHook("lessonsMount", (el) => mountTrainer(el, {api}))`.

## Trainer state (pure)

The state has these fields:
- `phase`: one of `choosing`, `walkthrough`, `practice`, `offLine`, `freePlay` or `complete`;
- `lesson`, `index` and `side`;
- `misses`, `hintShown` and `arrow`;
- `free`: `{fen, legalMoves, returnIndex}` or null;
- `message`.

| Event | Effect |
|---|---|
| `lessonLoaded(lesson)` | Go to walkthrough at index 0, with the side set to `lesson.side` |
| `next` / `back` / `restart` | Move the index; emit a `setBoard` effect |
| `startPractice(side?)` | Go to practice at index 0; when index 0 is the trainer's ply, emit `scheduleTrainer` |
| `learnerMove(uci)` | Correct: index + 1, `setBoard`, `announce`, then `scheduleTrainer` or `complete`. Off the line: go to `offLine`, misses + 1. |
| `rejectedTap(from, to)` | Message "That move isn't legal.", misses + 1 |
| `trainerMove` | Play `step.uci` for the trainer ply |
| `hint` | `hintShown` = true, which highlights `step.uci.slice(0,2)` |
| `keepPlaying` | Go to free play, with `free` set from the off-line move (filled by the `positionMove` effect) |
| `freeResult(data)` / `freeError(msg)` | Update `free`, or restore the last position and show the message |
| `backToLine` | Go to practice at `returnIndex`, keeping the misses |

When misses reach 3, `arrow` is set to `step.uci` and the message to "The move is <san>. <note>".

## Trainer view

- **Header:** the lesson name and ECO, and "Other lessons".
- **Side switch** (in practice): "Practise as White / Black", a two-option segmented control with radio semantics.
- **Board:** U2's `createBoard`, with `onMove` sent to the reducer and the new `onRejectedTap`. The arrow sits in an SVG layer above it, with `aria-hidden`; the same information is in the text message.
- **Controls:**
  - in the walkthrough: Back, Next and Restart, plus Practise;
  - in practice: Hint, plus "Keep playing freely" and "Back to the line" when off the line.
- **Scoresheet:** a `<table>` with the note for each move beside its row, in book italic.
- **Messages:** `role="status"`.

## U2 board addition

The new option is `onRejectedTap(from, to)`. It is called when a piece is selected and the person picks a square that is not one of its targets, other than another of their own movable pieces. That case still selects the new piece. When the option is absent, behaviour is exactly as before.

## Form validation

There are no free-text inputs. The lesson id comes from the list or the URL. The client checks it against `^[a-z0-9][a-z0-9-]{0,47}$` before calling the API.

## API integration points

| Action | Route |
|---|---|
| List lessons | `GET /api/lessons` → `[{id, name, aliases, eco, side, moves}]` |
| Load lesson | `GET /api/lessons/{id}` → `{id, name, aliases, eco, side, start, objectives, steps:[{ply, side, san, uci, note, fenBefore, fenAfter, legalBefore, alternatives}]}` |
| Free play move | `POST /api/position/move` `{fen, uci}` → `{fen, san, legalMoves, check, outcome}` |
