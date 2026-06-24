# AI Art Publisher

Single-user app for curating image series, generating AI captions, and publishing posts/stories to Instagram and Telegram.

## Language

**Series**:
A named group of Images destined for one post. Has its own lifecycle status (`new`, `draft`, `approved`, `posted`, `partial_posted`, `skip`) separate from each Image's status.

**Image**:
A single uploaded asset belonging to a Series. Carries its own `status` independent of the Series' status.

**Selection**:
The set of Images within a Series that are included in the upcoming post, in story order. Represented in the DB as `Image.status == "queued"`; everywhere else (UI labels, JS variable names) called "selected" / "selection". Selection membership, order, and per-image Skip are saved to the server automatically as the user acts — there is no separate save step.
_Avoid_: Queue (use only when referring to the literal `queued` status value or the `/queue` endpoint)

**Skip**:
An Image explicitly excluded from the Selection and from automated picks; `Image.status == "skip"`. Distinct from simply not being selected (`pending`) — Skip is a sticky exclusion the user must deliberately undo (Unskip).

**Pending**:
An Image's default status: uploaded, not yet selected, not skipped, not posted.

**Posted**:
An Image's status once it has actually been sent in a post; immutable from the Selection's perspective (cannot be re-selected or skipped without first unmarking posted).

## Example dialogue

> Dev: "Why does dragging an image into the tray feel different from clicking the skip button?"
> Domain expert: "They shouldn't — both mutate state that's autosaved instantly. Dragging into the tray changes Selection membership; clicking skip changes the Image to Skip status. Both used to need a manual 'Save' click for the Selection case only — that's the gap we're closing."
