# AI Art Publisher

App for curating image series, generating AI captions, and publishing posts/stories to Instagram and Telegram. Currently single-user in code; multi-User support (invite-gated) is in design.

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

**User**:
An individual account, authenticated via Google sign-in. Owns their own Series/Images, isolated from other Users' data. Signup requires a valid Invite Code. Has a Free tier by default; Paid tier not yet designed.

**Invite Code**:
A single shared secret required to complete signup, set by the app owner. Revoking it (rotating or clearing the value) blocks all future signups immediately without affecting existing Users — the app owner's mitigation if the signup link leaks.

**Quota**:
A Free-tier User's monthly spending cap on AI generation, measured in the actual USD cost of their generations (not raw token count). Once a User's spend for the month reaches Quota, they can no longer generate using the app-provided Default AI Access, and must supply their own AI provider credentials to continue.

**Default AI Access**:
The app owner's own AI provider key, used automatically for Users who haven't configured their own provider credentials. Points at free-tier OpenRouter models so it costs the app owner nothing regardless of how many Users draw on it.

**Quick Capture**:
An Android entry point (PWA share-target) that creates a new Series directly from photos shared out of the phone's gallery/camera, without opening the desktop editor. Distinct from normal Series creation/editing, which stays on the full desktop-oriented UI.

## Example dialogue

> Dev: "Why does dragging an image into the tray feel different from clicking the skip button?"
> Domain expert: "They shouldn't — both mutate state that's autosaved instantly. Dragging into the tray changes Selection membership; clicking skip changes the Image to Skip status. Both used to need a manual 'Save' click for the Selection case only — that's the gap we're closing."
