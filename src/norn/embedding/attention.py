"""Typed facet-token self-attention and its explicit reverse derivative.

This module is an attention operator, not supervision. The retrieval training
owner supplies both query/memory gradients and records its actual exposure.
"""

import numpy as np

from norn.embedding.numerics import Array, softmax


def forward(h: Array, mask: Array, p: dict[str, Array]) -> tuple[Array, tuple[Array, ...]]:
    q, k, v = (h @ p[name] for name in ("aq", "ak", "av"))
    scale = h.shape[-1] ** -0.5
    scores = (q @ k.transpose(0, 2, 1)) * scale
    weights = softmax(np.where(mask[:, None, :] > 0, scores, -1e30))
    mixed = weights @ v
    result = np.tanh(h + mixed @ p["ao"])
    return result, (h, q, k, v, weights, mixed, result, mask)


def backward(
    g: Array, cache: tuple[Array, ...], p: dict[str, Array]
) -> tuple[Array, dict[str, Array]]:
    h, q, k, v, weights, mixed, result, mask = cache
    pre = g * (1 - result * result)

    def flat(x: Array) -> Array:
        return x.reshape(-1, x.shape[-1])

    grads = {"ao": flat(mixed).T @ flat(pre)}
    gm = pre @ p["ao"].T
    gv = weights.transpose(0, 2, 1) @ gm
    gw = gm @ v.transpose(0, 2, 1)
    gs = weights * (gw - np.sum(gw * weights, axis=-1, keepdims=True))
    gs *= mask[:, None, :]
    scale = h.shape[-1] ** -0.5
    gq, gk = (gs @ k) * scale, (gs.transpose(0, 2, 1) @ q) * scale
    gh = pre.copy()
    for name, value in (("aq", gq), ("ak", gk), ("av", gv)):
        grads[name] = flat(h).T @ flat(value)
        gh += value @ p[name].T
    return gh, grads
