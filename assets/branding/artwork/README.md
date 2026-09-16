# Artwork

## Approved splash and derived assets

Added September 16, 2026 at Ken's request.

| File | Dimensions | Purpose |
| --- | --- | --- |
| `bobtv-splash.png` | 1672 x 941 | Approved original splash, preserved byte-for-byte from ChatGPT. |
| `bobtv-logo.png` | 1774 x 887 | Transparent RGBA derivative: BobTV wordmark and golden sunrise arc. |
| `bobtv-icon.png` | 1254 x 1254 | Transparent RGBA derivative: compact golden sunrise arc. |
| `bobtv-background-dark-4k.png` | 3840 x 2160 | Dark Earth-and-stars background without branding or city labels. |

The dark background was requested by Ken after approval of the asset pack. It was edited from the approved splash with the built-in image-generation tool, removing the wordmark, golden logo arc, tagline and city labels, and reducing the sunrise and scene brightness. The tool returned 1672 x 941 pixels; the delivered PNG is a high-quality bicubic upscale to exactly 3840 x 2160, not native 4K generation. The approved splash and startup audio remain unchanged.

### Dark background prompt

> Edit the provided BobTV splash into a background-only image for the same TV app. REQUIRED OUTPUT exactly 3840 x 2160 pixels, 16:9 landscape PNG. Preserve the recognizable Earth-at-night composition: Atlantic centered, North America lower left and Europe lower right, curved Earth horizon around the middle/lower half, stars in space above. Completely remove BobTV lettering, the golden logo arc and its top glint, the tagline, Athens GA and London text, all lettering/labels, and the two exaggerated city starburst highlights. Seamlessly fill removed branding with natural dark starfield. Make the entire scene substantially darker, quieter, understated: deep midnight navy/near-black space, fewer and much dimmer stars, very faint Milky Way, soft restrained blue atmospheric rim, dim scattered warm city lights without starbursts. Reduce the horizon sunrise to a subtle low amber glow, no blazing white sun or strong lens flare. Keep clouds and coastlines discernible but subdued, ample calm dark negative space above Earth for app UI overlays. No logo, no symbol, no text, no labels, no border. High quality full-bleed 4K background. Save the requested output at exactly 3840x2160.

The splash preserves the Earth at night, sunrise, ivory Bob/cool-blue TV wordmark, tagline, and finalized Athens GA and London highlights/labels. Its native dimensions are retained without resampling or cropping.

Source: Ken's [Omarchy OS Overview conversation](https://chatgpt.com/c/6aa9e90e-800c-83e9-b08f-7c4fe259b3eb), final generated image titled **BobTV: Sunrise Over Earth**, following “Move Athens GA up 1/4 of an inch. Above the light.” and immediately preceding “Looks great. If I save this file what should I save it as?” Image message: `bacca8d1-e591-4876-9467-c463f31b3c0a`; original file: `file_00000000cb5c822f97c329d6cb52db83`.

Splash SHA-256: `f8cf093d682a13ca0641921d3f5efe43ee46c9d25c2c70d57116462b36f20f2f`.

Creator/source: original artwork generated in ChatGPT for Ken; transparent derivatives created with the built-in image-generation editor from that approved splash. The derivatives are AI-generated adaptations, not original layered source files or exact pixel extractions. The approved splash remains the visual source of truth. All three PNGs were decoded successfully; both derivatives have actual alpha transparency and were visually checked on navy and light-gray backgrounds. The ivory wordmark is intended primarily for dark backgrounds.

Usage: uploaded to this private BobTV repository under Ken's explicit authorization for BobTV branding. No additional third-party license or exclusivity claim is made here.

Pair these visuals with the existing `../sound/bobtv-startup-sunrise-v1` assets and their cue sheet. This artwork commit does not modify sound assets or integrate the images into the live application.

## Derivative prompts

Both edits used `bobtv-splash.png` as their sole input and the built-in image-generation tool.

### Logo

> Use case: background-extraction. Edit target: the attached approved BobTV artwork. Create one transparent PNG logo derivative by isolating ONLY the central BobTV wordmark and golden sunrise arc above it. Preserve precisely the letter shapes, proportions, spacing and colors: bold warm ivory 'Bob', slender cool blue 'TV', subtle warm flare in the o, golden arch with a light at top center. Remove Earth, stars, all background, labels and tagline. Do not redesign or add elements. Center the extracted logo with a small even transparent margin. Actual alpha transparency, not a checkerboard painted into the image. Deliver one standalone logo image, no presentation sheet. Preserve the approved source separately unchanged.

### Icon

> Use case: background-extraction. Input is approved BobTV splash artwork; preserve original separately. Produce a standalone compact app icon derivative containing ONLY the golden sunrise arc positioned above the wordmark in the reference. Preserve that graceful arch shape, tapered ends, gold-to-amber color and small bright warm sun glint at its apex. Remove the entire wordmark, text, Earth and all stars/background. Do not invent extra forms, letters, horizon, circle or tile. Center arc on a square transparent PNG canvas with generous balanced transparent padding suitable for an app icon. Actual alpha transparency, no painted checkerboard or dark rectangle. Clean smooth edges and restrained small glow, no scattered speckle artifacts.

See [branding handoff](../README.md) for naming and collaboration notes.
