# Changelog

## 1.0.1

- The padding's fresh noise is drawn on the CPU like the sampler's own noise, so a seed gives the same result on every device.
- The views 2 / Fun ControlNet check runs once per sampling run instead of on every model call, and both ControlNet checks use the patch class instead of its name.
- MiniMax H3 Loop lists 107 among the exact-audio lengths.
- README: prompting and settings guidance moved up into a "Getting a clean loop" section right after Install.
- pyproject.toml: `requires-comfyui >=0.42.0`, documentation link to the README, template leftovers removed.

## 1.0.0

First release.

- **MiniMax H3 Loop**: samples the latent with its end wrapped around to its start (circular padding, `pad_clips`), so the loop point is denoised like any other part of the video. The padding gets fresh noise, which stops distilled models such as FastH3 from drawing white specks near the loop point. `views` 2 (default) also samples a half-rotated view and takes the audio around the loop point from it, which keeps the sound clean there. Moves first/last frame and Add Guide anchors and denoise masks with the padding.
- **MiniMax H3 Loop Decode**: decodes with wrapped context on both sides and returns exactly one loop of frames and audio.
- **MiniMax H3 Loop Control Video**: fits a seamless control loop (for example a depth pass) to the H3 loop for Apply MiniMax H3 Fun ControlNet.
- **Loop Interpolate**: FILM or RIFE 4.9 interpolation across the whole loop, including last to first frame, through ComfyUI-Frame-Interpolation.
- Example workflows: 25 steps without LoRA, turbo 8-step LoRA, FastH3-Omni, and Fun ControlNet.
- PROMPTING.md: prompting guide that also works as instructions for an LLM.
