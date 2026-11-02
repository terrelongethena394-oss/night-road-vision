"""ABI22 candidate: protect near-black pixels and lightly filter luminance.

Established Retinex and patch-similarity filtering; no learned enhancement
weights. This is a revision on known examples, not a new blind benchmark.
"""
import cv2
import numpy as np
from road_retinex_project import illumination
from road_local_enhance_v2 import smoothstep

PRESETS = {
    'guard_only': dict(tone=.40, max_gain=4.5, h=6., chroma_mix=.60, luma_mix=0.),
    'guard_light': dict(tone=.40, max_gain=4.5, h=10., chroma_mix=.60, luma_mix=.30),
    'guard_medium': dict(tone=.40, max_gain=4.5, h=10., chroma_mix=.60, luma_mix=.50),
}

def enhance(rgb, preset='guard_light'):
    assert rgb.shape == (240, 400, 3) and rgb.dtype == np.uint8
    p = PRESETS[preset] if isinstance(preset, str) else preset
    a = rgb.astype(np.float32)
    value = a.max(2) / 255
    raw_y = (54*a[:, :, 0]+183*a[:, :, 1]+19*a[:, :, 2])/256
    f = illumination(a)
    target = (f*(2-f))**p['tone']
    gain = np.divide(target, f, out=np.ones_like(f), where=f > 1e-8)
    gain = np.minimum(gain, p['max_gain'])
    alpha = float(np.clip((110-float(raw_y.mean()))/70, 0, 1))
    # Very dark pixels contain little reliable signal. Do not lift their
    # noise/codec blocks to the same degree as better-exposed surroundings.
    # Rational shoulder avoids the extra noise contrast of a steep smoothstep
    # around a fixed dark threshold. With constant base gain, its brightness
    # derivative stays below that base gain.
    confidence = raw_y/(raw_y+4.)
    gain = 1+(gain-1)*alpha*confidence*(1-smoothstep(.65, .98, value))
    lit = np.clip(a*gain[:, :, None], 0, 255)
    y = (lit[:, :, 0]+2*lit[:, :, 1]+lit[:, :, 2])*.25
    co = (lit[:, :, 0]-lit[:, :, 2])*.5
    cg = (-lit[:, :, 0]+2*lit[:, :, 1]-lit[:, :, 2])*.25
    planes = np.stack([y, co, cg], 2)
    pad = np.pad(planes, ((3, 3), (3, 3), (0, 0)), mode='reflect')
    numer = np.zeros_like(planes)
    den = np.zeros_like(y)
    for dy in range(7):
        for dx in range(7):
            shifted = pad[dy:dy+240, dx:dx+400]
            delta = shifted-planes
            distance = (delta[:, :, 0]**2*.25+delta[:, :, 1]**2+delta[:, :, 2]**2)/2.25
            distance = cv2.boxFilter(distance, cv2.CV_32F, (3, 3), normalize=True, borderType=cv2.BORDER_REFLECT_101)
            weight = np.exp(-np.maximum(distance-18., 0)/(p['h']**2))
            numer += shifted*weight[:, :, None]
            den += weight
    filtered = numer/den[:, :, None]
    dark = 1-smoothstep(.10, .65, value)
    y += (filtered[:, :, 0]-y)*(p['luma_mix']*dark)
    co += (filtered[:, :, 1]-co)*(p['chroma_mix']*dark)
    cg += (filtered[:, :, 2]-cg)*(p['chroma_mix']*dark)
    result = np.stack([y+co-cg, y+cg, y-co-cg], 2)
    out = np.floor(np.clip(result, 0, 255)+.5).astype(np.uint8)
    return out, dict(mean_in=float(raw_y.mean()), mean_out=float(((54*out[:, :, 0].astype(np.float32)+183*out[:, :, 1].astype(np.float32)+19*out[:, :, 2].astype(np.float32))/256).mean()), gain_max=float(gain.max()), alpha=alpha, luma_mix=p['luma_mix'], clipping_fraction=float(np.any(out >= 254, axis=2).mean()))
