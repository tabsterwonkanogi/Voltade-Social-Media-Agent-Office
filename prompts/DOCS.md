# The Google Docs copies

The job descriptions also live as Google Docs, so they can be written in a
normal writing tool rather than a text editor.

Folder: https://drive.google.com/drive/folders/1JwcQB_Qcp5tVBH2LPE1urXHtboIx2cRA

| Agent | Doc |
|---|---|
| read me first | https://docs.google.com/document/d/1j-YJU5T4wzbv2CdPhooOtZs8xl79NJww4YpR9spGC60/edit |
| Michael | https://docs.google.com/document/d/1BdN_PKE-4ekXc_SoD_37ORPgzxi6k0pGOsBIfMVuKTM/edit |
| Jim | https://docs.google.com/document/d/1h3YlraiZiWH_zzSUnTrZMFpFlNdV04ykrIPFeJPehDM/edit |
| Pam | https://docs.google.com/document/d/1d4jO6NGVKikw79sBnFLZaGO0qvg7riYVPa3YCdP8Wu8/edit |
| Kelly | https://docs.google.com/document/d/1wbTb7XC2c2zLx-CCh_cXwANAh943lGImrD32udzJupw/edit |
| Angela | https://docs.google.com/document/d/1XFgAswPwxyWgcojhH6Qr8qIbxTZOR2u0zHpc0Ze0k2s/edit |

Dwight has no doc. He has no model call and no judgement to scope.

## Which one is real

The files in this folder are what the agents actually read. The Docs are a
writing surface.

That split is deliberate. A Doc is a live document: it is half-edited, it has
a sentence someone is still thinking about, it has a comment thread. None of
that should reach a running agent at 09:00. So edits come back on purpose,
not automatically.

## Pulling edits back

Ask Claude to pull the job descriptions from Docs. It reads each Doc, writes
the file, and shows you the diff before anything runs.

Then run the agent you changed and read what it produced. Scoping an agent is
a loop, not a document you write once:

    python -m scripts.run_pam "a brief"
