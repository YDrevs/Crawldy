# Brand source and social assets

Brand files that belong to the project but are **not served by the website** and are not used
by any component.

This is deliberately separate from [`frontend/public/brand/`](../frontend/public/brand/README.md),
which holds the web versions the `Brand.tsx` components render and which Next serves at
`/brand/…`. Anything placed there is publicly downloadable; a vector source and social banners
do not belong in the site's public payload.

| File | What it is |
|---|---|
| `crawldy_horizontal.svg` | Horizontal lockup, vector. |
| `crawldy_mark.eps` | The mark as a print/vector source. |
| `crawldy_avatar_light.png` | Square avatar on a light background, for profile images. |
| `crawldy_linkedin_banner.png` | LinkedIn banner. |
| `crawldy_linkedin_banner@2x.png` | The same banner at 2×. |
| `crawldy_linkedin_banner_1.png` | Second banner variant. |
| `crawldy_linkedin_banner@2x_1.png` | The second variant at 2×. |

Filenames are the designer's and are kept unchanged: `@2x` and `_1` carry which variant a file
is, and renaming them to the site's kebab-case convention would suggest these are web versions,
which they are not.

These files were held only in a downloads folder until
`CRAWLDY-REMEDIATION-REPORT-AND-MAXIMUM-SAFE-CLEANUP-01` moved them here. Each was verified
byte-for-byte by SHA-256 against its source; none duplicates anything already in the
repository.
