# Invent-SSH brand system

## Positioning
Invent-SSH turns SSH access into a clear, local-first Linux hardware inventory. Its personality is precise, confident and approachable: a practical infrastructure tool with a recognizable mascot, not a generic AI dashboard.

## Mascot
The custom penguin mark is drawn specifically for Invent-SSH using midnight navy, white and signal yellow. Use the standalone mark at app/icon size and the lockup for editorial or repository placements. Never replace it with a generic database stack or generic AI symbol.

## Palette
| Token | Hex | Purpose |
| --- | --- | --- |
| Midnight | #07172D | Primary canvas |
| Deep navy | #0B2342 | Surfaces and cards |
| Navy line | #183B63 | Dividers, borders and table rules |
| Signal yellow | #FFC629 | Primary actions and key highlights |
| Yellow hover | #E6A800 | Active/hover state |
| White | #F4F7FF | Primary text and mascot belly |
| Slate | #9DB6D7 | Supporting text |
| Success | #10B981 | Successful collection status only |
| Warning | #FFC629 | Warnings; always paired with a label |
| Error | #F87171 | Errors; always paired with a label |

Yellow is the primary action accent. Blue is the structural color. Green is reserved for success status, not for the overall product identity.

## Typography
- Display: Georgia/serif for a small number of editorial statements.
- Interface: native UI sans-serif (Avenir Next, Segoe UI, or system fallback).
- Data: platform monospace for technical identifiers only.
- Do not bundle fonts without redistribution rights.

## UI principles
1. One obvious next action; explain requirements before requesting credentials.
2. Use the viewport, resize cleanly, and keep dense content scrollable.
3. Prefer strong hierarchy, readable contrast and clear table headers over gradients, excessive cards or shadows.
4. Persistent actions have explicit labels and visible running/disabled states.
5. Missing or uncertain data must be marked honestly.
6. Never expose passwords or private-key content in logs; inventory exports are saved locally unless the user shares them.

## Reports
Excel and HTML use the same navy/yellow identity and terminology as the desktop application. Reports remain usable offline, printable, navigable, and safe for untrusted host metadata.
