# Prompting guide for MiniMax H3 loops

How to write prompts for seamless loops with MiniMax H3 Loop. It's written so you can give the whole file to an LLM as instructions ("write me a loop prompt for X using this guide"), and it reads the same for people.

## The one rule

**The last frame has to flow straight back into the first.** The node makes the model join the end of the clip to its start, and the prompt has to describe something that can do that. Describe a **state that keeps going**, not a **sequence of events**.

Ask of every prompt: *if this clip played twice in a row, would the joint be invisible?*

## Prompt format

H3 takes a visual description in plain prose, optionally followed by labelled sound lines:

```
<visual description, 4-8 sentences>

overall_soundscape: <steady ambient sound, comma-separated>

non_diegetic_music: N/A
```

- Write the visual description as present-tense prose. No timestamps, no shot list.
- `overall_soundscape:` sets the generated audio. Describe a steady bed of sound.
- `non_diegetic_music: N/A` asks H3 not to add a score; it usually works but isn't guaranteed. Replace `N/A` with a description if you want music, but music phrases rarely loop cleanly.

## Structure of the visual description

Build it in this order:

1. **Camera:** `Locked-off static camera, no pan, no zoom.` (See [Camera movement](#camera-movement) for the exception.)
2. **Setting:** place, time of day, light. Keep it fixed.
3. **Main subject and its repeating action:** one clear subject doing one continuous or cyclic thing.
4. **Secondary motion:** slow ambient detail that never runs out (drifting particles, light shafts, swaying).
5. **Closing line (suggested):** `Continuous, smooth, unbroken motion throughout.` It reinforces steady motion; it isn't required for the loop to work.

## What loops well

Tested and clean:

- **Large, clear subjects with cyclic motion:** a jellyfish pulsing, an object rotating on its axis.

Expected to work well (same principle):

- Pulsing, breathing, rotating, orbiting, swaying, bobbing, slow drifting.
- Steady flows that look the same at every moment: a slow stream of particles, light moving along a surface, a constant glow.
- Stylised or abstract motion: geometric patterns cycling, light traces, holograms.

Useful words: *steady, constant, rhythmic, cyclic, continuous, slowly, evenly, in a slow orbit, on its axis, in a steady cycle.*

## What is harder

Tested and visibly harder:

- **Fine turbulent texture:** blowing sand, rain streaks, and by extension smoke, spray, splashing water, sparks. The large shapes loop, but the texture can change pattern at the loop point. Keep it secondary to a clear main subject, keep it subtle, or try several seeds.

## What does not loop

Avoid these. Each describes something that ends somewhere different from where it began:

- **Timelines:** `[0s-2s]` sections, shot lists, or "then", "begins", "starts to", "finally", "gradually", "transforms into", "by the end".
- **One-way changes:** a light switching on, something appearing, entering, leaving or being revealed, growth, melting, building, a sunrise, a weather change.
- **Single events:** an explosion, a jump, a hit, a spoken line. They happen once per loop and the cut gives them away.
- **Unlimited one-way travel:** a camera push, pan, dolly or orbit through a scene that doesn't repeat.
- **Speech and lyrics.** They can't wrap mid-sentence.

## Camera movement

Default to a locked-off camera. The exception is **travel through a repeating structure**: an endless corridor, tunnel, colonnade or grid of identical elements at even spacing. If the camera moves at a constant speed and the structure repeats exactly, one loop can carry the camera forward by exactly one section, and the end matches the start.

For travel prompts:

- Say **endless**, **identical** and **at exactly even intervals**.
- Say **perfectly constant speed**, **centered and level**, **no turns, no bobbing, no change in speed**.
- Hide the far end: *fades into dark haze / into black*.
- Say **nothing appears, opens or changes**.

This is the riskiest kind of loop (untested). Use a shorter length (158 or 209) and try several seeds.

## Sound

- A steady ambient bed loops invisibly: wind, rain, room tone, hum, drone, underwater ambience, distant city.
- Avoid one-off sounds (a voice line, an impact, a door) unless you want them to repeat every loop.
- Avoid music with a clear phrase or beat unless the loop length matches it. H3 won't line it up for you.

## Reference image

With a reference image connected to MiniMax H3 Reference to Video, refer to it as `<Picture 1>` (and `<Picture 2>`, and so on, for more):

```
Locked-off static camera, no pan, no zoom. The glowing creature from <Picture 1> floats in the center of frame, pulsing rhythmically...
```

Don't describe it as the first frame ("the video starts with..."). The loop has no first frame. Describe the subject and what it keeps doing.

## Length

Lengths must be 17k+5 frames. These keep the audio loop exact: **107** (4.25 s), **158** (6.4 s), **209** (8.5 s), **260** (10.6 s), **311** (12.75 s), **362** (14.9 s). Slow cyclic motion suits any of them; travel loops are easier when short.

## Checklist

Before using a prompt, check:

- [ ] Camera is locked-off, or travel through an explicitly repeating structure at constant speed.
- [ ] One main subject with one continuous or cyclic action.
- [ ] No timeline words, timestamps, or one-way changes.
- [ ] No single events in the picture or the sound.
- [ ] Light, weather and time of day are fixed.
- [ ] Optionally ends with `Continuous, smooth, unbroken motion throughout.`
- [ ] `overall_soundscape:` is a steady bed of sound; `non_diegetic_music: N/A` unless music is wanted.

## Rewriting a prompt that won't loop

Before:

```
A lantern flickers to life in a dark room, then slowly brightens as moths gather around it.
```

Problems: "flickers to life", "then", "slowly brightens" and "gather" are all one-way changes.

After:

```
Locked-off static camera, no pan, no zoom. A dark wooden room at night. A paper lantern hangs in the center of frame, glowing a steady warm orange with a soft, gentle flicker. A few small moths circle it in slow, continuous loops, their wings catching the light. Faint dust drifts through the glow. Continuous, smooth, unbroken motion throughout.

overall_soundscape: quiet room tone, a faint soft flutter of wings, a distant night breeze.

non_diegetic_music: N/A
```

## Examples

Jellyfish (tested, clean):

```
Locked-off static camera, no pan, no zoom. Deep blue ocean at night. A large glowing jellyfish pulses rhythmically in the center of frame, its bell contracting and relaxing in a steady cycle, long luminous tendrils trailing and swaying. Tiny specks of marine snow drift slowly upward through soft shafts of light. Continuous, smooth, unbroken motion throughout.

overall_soundscape: deep underwater ambience, a soft low hum, gentle muffled water movement.

non_diegetic_music: N/A
```

Rotating monolith (tested, clean loop point):

```
Locked-off static camera, no pan, no zoom. A dark, misty void. A tall black obsidian monolith stands in the center of frame, rotating slowly and steadily on its vertical axis. Thin lines of cyan light trace geometric patterns across its faces and flow upward in a constant stream. A soft halo of volumetric haze surrounds it, and fine particles of dust circle it in a slow orbit. Continuous, smooth, unbroken motion throughout.

overall_soundscape: a deep resonant drone, a faint electrical shimmer, a slow airy whoosh as the faces turn.

non_diegetic_music: N/A
```

Endless corridor (camera travel, untested):

```
Smooth first-person camera gliding forward at a slow, perfectly constant speed down an endless, perfectly symmetrical corridor. Identical arched doorways line both walls at exactly even intervals, repeating into the distance. Each section is lit by a single soft ceiling light, so the light pools repeat in a steady rhythm. The far end of the corridor fades into dark haze; no end is ever visible. The camera stays centered and level: no turns, no bobbing, no change in speed. Nothing appears, opens or changes. Continuous, smooth, unbroken forward motion throughout.

overall_soundscape: a low steady room tone, a soft continuous air hum, faint even reverb.

non_diegetic_music: N/A
```

Neon tunnel (camera travel, untested):

```
Smooth camera gliding forward at a slow, perfectly constant speed through an endless dark tunnel made of identical rectangular neon frames spaced at exactly even intervals. Each frame glows the same cool cyan, and the frames repeat into the distance, fading into black. Faint reflections of the frames shimmer on a glossy black floor. The camera stays centered and level: no turns, no change in speed. Nothing appears or changes. Continuous, smooth, unbroken forward motion throughout.

overall_soundscape: a deep steady electrical drone, a soft rhythmic hum as each frame passes.

non_diegetic_music: N/A
```

Neon rain on glass (turbulent texture; may pop at the loop point):

```
Locked-off static camera, no pan, no zoom. Night, a city seen through a rain-covered window, softly out of focus. Raindrops run down the glass in steady streams, merging and splitting, catching magenta and teal reflections from blurred neon signs beyond. The bokeh lights glow softly and steadily. Continuous, smooth, unbroken motion throughout.

overall_soundscape: steady rain pattering on glass, a distant low city hum, soft rolling water.

non_diegetic_music: N/A
```

Desert dune ridge (turbulent texture; may pop at the loop point):

```
Locked-off static camera, no pan, no zoom. Golden hour on a desert dune ridge. A constant wind lifts fine sand off the crest of the dune in a thin, flowing veil that streams across the frame from left to right. Long soft shadows stretch across rippled sand. Warm light, clear sky. Continuous, smooth, unbroken motion throughout.

overall_soundscape: steady wind across the sand, a soft hiss of blowing grains, distant open air.

non_diegetic_music: N/A
```

## Instructions for an LLM

If you are an LLM writing prompts with this guide:

- Output the prompt in the format above: visual description, a blank line, `overall_soundscape:`, a blank line, `non_diegetic_music:`. No title and no markdown fences unless asked.
- Follow the structure and checklist. Prefer subjects from "What loops well".
- If the user's idea has a one-way change or an event, turn it into a continuous state, and put one line before the prompt saying what you changed. Otherwise add no commentary.
- If the idea needs camera travel, use the repeating-structure approach and say it's the riskiest kind of loop.
- If a reference image is involved, refer to it as `<Picture 1>` and don't describe it as a first frame.
