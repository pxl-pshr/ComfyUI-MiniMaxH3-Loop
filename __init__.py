import torch

import comfy.patcher_extension
import comfy.utils
import nodes
from comfy_extras.nodes_audio import vae_decode_audio

# H3 video latents come in 17-frame clips of 5 latent frames (1, 4, 4, 4, 4 pixel frames).
# A 17k+5 frame video is 5k+2 latents: k clips plus a (1, 4) tail shaped like the first
# two latents, so the tail is filled with the start of the loop.
CLIP_LATENTS = 5
VIDEO_TAIL = 2
AUDIO_PER_CLIP = 17 * 40 / 24  # audio latents (40/s) per 17-frame clip (24 fps)


def audio_span(clips):
    return round(clips * AUDIO_PER_CLIP)


def wrap_pad(x, before, after, dim):
    # treat x as periodic along dim and extend it by `before` and `after` entries,
    # tiling as often as needed when the padding is longer than the loop
    n = x.shape[dim]
    if n == 0:
        raise ValueError("MiniMax H3 Loop needs a length of at least 22 frames (one 17-frame clip plus the 5-frame tail)")
    lead = -(-before // n)
    reps = lead + 1 + -(-after // n)
    return torch.cat([x] * reps, dim=dim).narrow(dim, lead * n - before, before + n + after)


def joint_weight(n, joint, like):
    # per-position weight of the second view, whose wrap point sits before position `joint`:
    # 0 at its own wrap point, 1 at the first view's wrap point (position 0), linear between
    t = torch.arange(n, dtype=like.dtype, device=like.device) + 0.5
    d_own = torch.minimum((t - joint) % n, (joint - t) % n)
    d_other = torch.minimum(t, n - t)
    return d_own / (d_own + d_other)


def loop_wrapper(executor, x, timestep, context, transformer_options, **kwargs):
    # circular padding: the model sees the loop with wrapped clips on both sides, so the
    # end-to-start join is denoised like any other clip boundary and the sequence edges
    # fall in context that is thrown away
    video, audio = x[0], x[1]
    n = video.shape[2] - VIDEO_TAIL
    clips = n // CLIP_LATENTS
    na = audio_span(clips)
    audio_tail = audio.shape[-1] - na
    pad = transformer_options["minimax_h3_loop_pad_clips"]
    pv = pad * CLIP_LATENTS
    pa = audio_span(pad)
    masks = (kwargs.get("denoise_mask"), kwargs.get("audio_denoise_mask"))
    # cond and uncond run as one batch, each a copy of the sampler's batch
    noise_swap = transformer_options["minimax_h3_loop_noise_swap"]
    noise_swap = noise_swap.repeat(video.shape[0] // noise_swap.shape[0], 1, 1, 1, 1)
    sigma = transformer_options["sigmas"].view(-1, 1, 1, 1, 1).to(video.dtype)

    def view(shift):
        # one pass with the loop rotated by `shift` whole clips; returns the loop's prediction unrotated
        sv, sa = shift * CLIP_LATENTS, audio_span(shift)
        args = dict(kwargs)
        payload = kwargs.get("minimax_payload")
        if payload and payload.get("keyframes"):
            # first/last frame and Add Guide anchors are pinned to timeline positions: move each one
            # to where its loop frame sits in this view (the loop end wraps onto the start)
            frames = clips * 17
            keyframes = [dict(kf, resolved_frame_index=pad * 17 + (kf["resolved_frame_index"] + shift * 17) % frames)
                         for kf in payload["keyframes"]]
            args["minimax_payload"] = dict(payload, keyframes=keyframes)
        # inpainting masks follow their streams through the rotation and padding
        if masks[0] is not None:
            args["denoise_mask"] = wrap_pad(masks[0][:, :, :n].roll(sv, dims=2), pv, pv + VIDEO_TAIL, 2)
        if masks[1] is not None:
            args["audio_denoise_mask"] = wrap_pad(masks[1][..., :na].roll(sa, dims=-1), pa, pa + audio_tail, -1)
        # the padding repeats the loop's latent including its starting noise; distilled models such as
        # FastH3 draw white specks where they see the same noise twice, so give the padding fresh noise
        swap = wrap_pad(noise_swap[:, :, :n].roll(sv, dims=2), pv, pv + VIDEO_TAIL, 2).to(video.dtype)
        swap[:, :, pv:pv + n] = 0
        if masks[0] is not None:
            swap = swap * args["denoise_mask"]
        padded = torch.addcmul(wrap_pad(video[:, :, :n].roll(sv, dims=2), pv, pv + VIDEO_TAIL, 2), sigma, swap)
        out = executor([padded,
                        wrap_pad(audio[..., :na].roll(sa, dims=-1), pa, pa + audio_tail, -1)],
                       timestep, context, transformer_options, **args)
        return out[0][:, :, pv:pv + n].roll(-sv, dims=2), out[1][..., pa:pa + na].roll(-sa, dims=-1)

    views = transformer_options["minimax_h3_loop_views"]
    if views == 2:
        # the Fun ControlNet encodes one unrotated control latent, which a rotated view would misalign
        for w in comfy.patcher_extension.get_all_wrappers(comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL, transformer_options):
            if type(getattr(w, "__self__", None)).__name__ == "MiniMaxH3FunControlPatch":
                raise ValueError("MiniMax H3 Loop views 2 can't be combined with the Fun ControlNet; set views to 1.")

    v, a = view(0)
    if views == 2 and clips > 1:
        # a fixed second view with its wrap point half a loop away: H3 garbles audio next to the
        # duplicated wrap context, so each audio position takes its prediction mostly from the view
        # where it is far from that view's wrap point. The picture stays on the first view: the two
        # views can settle on opposite directions of motion, and blending them reverses it mid-loop.
        half = clips // 2
        _, a2 = view(half)
        wa = joint_weight(na, na - audio_span(half), a)
        a = torch.lerp(a, a2, wa.view(1, 1, 1, -1))
    return [wrap_pad(v, 0, VIDEO_TAIL, 2), wrap_pad(a, 0, audio_tail, -1)]


def loop_sampler_wrapper(executor, guider, sigmas, extra_args, callback, noise, *args, **kwargs):
    # the sampler's video latent is sigma * noise + (1 - sigma) * clean, so adding
    # sigma * (fresh - noise) to the padding replaces its noise and keeps its content
    # with noise disabled (staged sampling) the latent's noise is unknown, so the padding keeps it
    shapes = guider.inner_model.latent_shapes
    video_noise = comfy.utils.unpack_latents(noise, shapes)[0] if shapes else noise
    if torch.count_nonzero(video_noise) == 0:
        swap = video_noise
    else:
        seed = ((extra_args.get("seed") or 0) + 1) % 2 ** 64
        generator = torch.Generator(device=video_noise.device).manual_seed(seed)
        swap = torch.randn(video_noise.shape, generator=generator, device=video_noise.device, dtype=video_noise.dtype) - video_noise
    extra_args["model_options"]["transformer_options"]["minimax_h3_loop_noise_swap"] = swap
    return executor(guider, sigmas, extra_args, callback, noise, *args, **kwargs)


class MiniMaxH3Loop:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "model": ("MODEL",),
            "pad_clips": ("INT", {"default": 1, "min": 1, "max": 8,
                                  "tooltip": "17-frame clips of wrapped context added on each side of the loop. Each clip adds sampling time."}),
        }, "optional": {
            "views": ("INT", {"default": 2, "min": 1, "max": 2,
                              "tooltip": "2 also samples the loop rotated by half and takes the audio around the loop point from it. Fixes garbled audio there; about 1.8x sampling time. Not usable with the Fun ControlNet."}),
        }}

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"
    CATEGORY = "model/patch/minimax"
    DESCRIPTION = "Generate a seamless loop by sampling the latent with its end wrapped around to its start. Set the latent length to 17k+5 frames (158, 209, 260, 311, 362); the loop is 17k frames. Decode with MiniMax H3 Loop Decode."

    def patch(self, model, pad_clips, views=2):
        # the Fun ControlNet sizes its control latent from the input it sees, so it has to
        # sit inside the loop padding: this patch must be applied first
        for w in model.get_all_wrappers(comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL):
            if type(getattr(w, "__self__", None)).__name__ == "MiniMaxH3FunControlPatch":
                raise ValueError("Apply MiniMax H3 Loop before Apply MiniMax H3 Fun ControlNet: chain model -> MiniMax H3 Loop -> Apply MiniMax H3 Fun ControlNet.")
        model = model.clone()
        model.model_options["transformer_options"]["minimax_h3_loop_pad_clips"] = pad_clips
        model.model_options["transformer_options"]["minimax_h3_loop_views"] = views
        model.add_wrapper_with_key(comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL, "minimax_h3_loop", loop_wrapper)
        model.add_wrapper_with_key(comfy.patcher_extension.WrappersMP.SAMPLER_SAMPLE, "minimax_h3_loop", loop_sampler_wrapper)
        return (model,)


class MiniMaxH3LoopDecode:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "samples": ("LATENT",),
            "vae": ("VAE",),
            "audio_vae": ("VAE",),
            "pad_clips": ("INT", {"default": 1, "min": 1, "max": 8,
                                  "tooltip": "17-frame clips of wrapped latent decoded on each side, so the decoder never starts or ends inside the loop."}),
        }}

    RETURN_TYPES = ("IMAGE", "AUDIO")
    FUNCTION = "decode"
    CATEGORY = "model/latent/minimax"
    DESCRIPTION = "Decode a MiniMax H3 Loop latent with wrapped context on both sides and return exactly one loop of frames and audio."

    def decode(self, samples, vae, audio_vae, pad_clips):
        video, audio = samples["samples"].unbind()
        n = video.shape[2] - VIDEO_TAIL
        clips = n // CLIP_LATENTS
        na = audio_span(clips)
        pv = pad_clips * CLIP_LATENTS
        pa = audio_span(pad_clips)

        images = vae.decode(wrap_pad(video[:, :, :n], pv, pv + VIDEO_TAIL, 2))
        images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
        images = images[17 * pad_clips:17 * (pad_clips + clips)]

        a = wrap_pad(audio[..., :na], pa, pa, -1)
        out = vae_decode_audio(audio_vae, {"samples": a})
        per_latent = out["waveform"].shape[-1] // a.shape[-1]
        out["waveform"] = out["waveform"][..., pa * per_latent:(pa + na) * per_latent]
        return (images, out)


class MiniMaxH3LoopControlVideo:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "images": ("IMAGE", {"tooltip": "One or more whole cycles of a seamless loop (frame N+1 == frame 1, not included)."}),
            "fps": ("FLOAT", {"default": 25.0, "min": 1.0, "max": 240.0, "step": 1.0, "tooltip": "Frame rate of the input loop."}),
            "length": ("INT", {"default": 209, "min": 22, "max": 3600, "step": 17, "tooltip": "Same length as the H3 latent (17k+5)."}),
            "pad_clips": ("INT", {"default": 1, "min": 1, "max": 8, "tooltip": "Same pad_clips as MiniMax H3 Loop."}),
            "cycles": ("INT", {"default": 0, "min": 0, "max": 256, "tooltip": "How many times the input loop plays in the H3 loop. 0 picks the count closest to the input's own speed."}),
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "build"
    CATEGORY = "model/conditioning/minimax"
    DESCRIPTION = "Fit a seamless loop (e.g. a depth pass) to a MiniMax H3 Loop as the control video for Apply MiniMax H3 Fun ControlNet: repeat it a whole number of times over the loop at 24 fps and pad it like the latent."

    def build(self, images, fps, length, pad_clips, cycles):
        n = images.shape[0]
        loop = length + (5 - length) % 17 - 5  # H3 snaps lengths up to 17k+5
        if cycles == 0:
            cycles = max(1, round(loop * fps / (24 * n)))
        pad = 17 * pad_clips
        # the padded sequence H3 sees: pad frames of the loop's end, the loop, then pad + 5 frames of its start;
        # each output frame samples the input at its loop phase, blending neighbours between input frames
        i0, i1, w = [], [], []
        for t in range(-pad, loop + pad + 5):
            src = (t % loop) * cycles * n / loop
            base = int(src)
            i0.append(base % n)
            i1.append((base + 1) % n)
            w.append(src - base)
        w = torch.tensor(w, dtype=images.dtype, device=images.device).view(-1, 1, 1, 1)
        return (torch.lerp(images[i0], images[i1], w),)


# interpolators from ComfyUI-Frame-Interpolation: (node name, checkpoint, extra args)
INTERPOLATORS = {
    "FILM": ("FILM VFI", "film_net_fp32.pt", {}),
    "RIFE 4.9": ("RIFE VFI", "rife49.pth", {"fast_mode": True, "ensemble": True}),
}


class LoopInterpolate:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "images": ("IMAGE",),
            "method": (list(INTERPOLATORS),),
            "multiplier": ("INT", {"default": 2, "min": 2, "max": 8}),
            "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 240.0, "step": 1.0}),
        }}

    RETURN_TYPES = ("IMAGE", "FLOAT")
    RETURN_NAMES = ("IMAGE", "fps")
    FUNCTION = "interpolate"
    CATEGORY = "image/animation"
    DESCRIPTION = "Frame-interpolate a looping clip, including the frames between the last frame and the first, so it stays seamless. Needs ComfyUI-Frame-Interpolation."

    def interpolate(self, images, method, multiplier, fps):
        node_name, ckpt, extra = INTERPOLATORS[method]
        if node_name not in nodes.NODE_CLASS_MAPPINGS:
            raise RuntimeError("Loop Interpolate needs ComfyUI-Frame-Interpolation installed")
        # close the loop with frame 0, interpolate, then drop the duplicate frame 0 at the end
        frames = torch.cat((images, images[:1]), dim=0)
        out = nodes.NODE_CLASS_MAPPINGS[node_name]().vfi(ckpt, frames, multiplier=multiplier, **extra)[0]
        return (out[:-1], fps * multiplier)


NODE_CLASS_MAPPINGS = {
    "MiniMaxH3Loop": MiniMaxH3Loop,
    "MiniMaxH3LoopDecode": MiniMaxH3LoopDecode,
    "MiniMaxH3LoopControlVideo": MiniMaxH3LoopControlVideo,
    "LoopInterpolate": LoopInterpolate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3Loop": "MiniMax H3 Loop",
    "MiniMaxH3LoopDecode": "MiniMax H3 Loop Decode",
    "MiniMaxH3LoopControlVideo": "MiniMax H3 Loop Control Video",
    "LoopInterpolate": "Loop Interpolate",
}
