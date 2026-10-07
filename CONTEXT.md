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

**Collection**:
A named, User-owned grouping of Series that share a theme. Each member Series carries a number within the Collection, shown in its posts as the collection line. A Series belongs to at most one Collection, and only to a Collection of the same User.

**User**:
An individual account, authenticated via Google sign-in. Owns their own Collections/Series/Images, isolated from other Users' data. Signup requires a valid Invite Code. Has a Free tier by default; Paid tier not yet designed.

**Owner**:
The one User who runs this app instance. The AI provider and posting credentials the app holds are the Owner's, and the public landing page showcases the Owner's posts.
_Avoid_: app owner, superuser

**Admin**:
A User with elevated rights over the instance: managing app settings and other Users. Today the Owner is the only Admin; the two are still distinct — Owner is about whose credentials and content the instance carries, Admin is about what a User is allowed to do.

**Invite Code**:
A single shared secret required to complete signup, set by the Owner. Revoking it (rotating or clearing the value) blocks all future signups immediately without affecting existing Users — the Owner's mitigation if the signup link leaks.

**AI Request**:
One call to an AI provider made on a User's behalf: generating caption drafts, expanding a draft into a full caption, or an AI image fix. Every AI Request is recorded against the User who made it, whichever credentials it used, and the record outlives the Series it was made for.
_Avoid_: generation (ambiguous between one request and the caption variants it returns)

**Quota**:
A cap on how many AI requests a User may make through Default AI Access per day. The cap is one number for the whole instance, the same for every User, set by an Admin; setting it to zero switches Default AI Access off. Counts requests, not captions produced and not money: one request that returns three caption variants counts once, and a request that fails still counts. Requests made with the User's own AI credentials never count. Once a User reaches Quota they can no longer draw on Default AI Access until the next day, and must supply their own AI provider credentials to keep generating.
_Avoid_: spend cap, budget (Quota is not measured in USD)

**Default AI Access**:
An OpenRouter key held by the instance (supplied by the Owner) that any User without their own OpenRouter key draws on. Limited to free OpenRouter models, so it costs the Owner nothing regardless of how many Users draw on it. Separate from the Owner's personal AI credentials: the Owner, like every User, keeps their own keys, and no other User ever generates with them.

**Quick Capture**:
An Android entry point (PWA share-target) that creates a new Series directly from photos shared out of the phone's gallery/camera, without opening the desktop editor. Distinct from normal Series creation/editing, which stays on the full desktop-oriented UI.

## Example dialogue

> Dev: "Why does dragging an image into the tray feel different from clicking the skip button?"
> Domain expert: "They shouldn't — both mutate state that's autosaved instantly. Dragging into the tray changes Selection membership; clicking skip changes the Image to Skip status. Both used to need a manual 'Save' click for the Selection case only — that's the gap we're closing."
