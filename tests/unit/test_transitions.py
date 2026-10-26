"""O'tish effektlari: clock wipe (soat 3 dan, soat miliga teskari), zoom blur chegaraviy holatlari."""

import torch

from darsstudio.render import transitions

DEV = torch.device("cpu")


def test_clock_wipe_sweeps_counterclockwise_from_three() -> None:
    cw = transitions.ClockWipe((200, 100), (100, 50), DEV)
    a, b = torch.zeros(3, 100, 200), torch.ones(3, 100, 200)
    q = cw(a, b, 0.25)                       # chorak: soat 3 dan soat 12 gacha (yuqori o'ng chorak)
    assert q[0, 20, 160] == 1 and q[0, 80, 160] == 0 and q[0, 20, 40] == 0 and q[0, 80, 40] == 0
    h = cw(a, b, 0.5)                        # yarmi: yuqori yarim
    assert h[0, 20, 40] == 1 and h[0, 80, 40] == 0
    assert torch.equal(cw(a, b, 0.0), a) and torch.equal(cw(a, b, 1.0), b)
    covered = [float(cw.mask(w).mean()) for w in (0.1, 0.3, 0.6, 0.9)]
    assert covered == sorted(covered)       # monoton ochiladi


def test_zoom_identity_and_center_fixed() -> None:
    img = torch.rand(3, 60, 80)
    assert torch.equal(transitions.zoom(img, 1.0, 0.0, (40, 30)), img)
    grad = (torch.arange(80, dtype=torch.float32) / 79).view(1, 1, 80).expand(3, 60, 80).contiguous()
    z = transitions.zoom(grad, 2.0, 0.0, (39.5, 29.5))
    assert torch.allclose(z[:, :, 39:41], grad[:, :, 39:41], atol=0.01)   # markaz joyida qoladi
    assert z[0, 0, 79] < grad[0, 0, 79] and z[0, 0, 0] > grad[0, 0, 0]  # chetlar markazga tortiladi (kattalashish)


def test_zoom_blur_endpoints() -> None:
    a, b = torch.zeros(3, 40, 60), torch.ones(3, 40, 60)
    assert torch.allclose(transitions.zoom_blur(a, b, 0.0, (30, 20), (30, 20)), a)
    assert torch.allclose(transitions.zoom_blur(a, b, 1.0, (30, 20), (30, 20)), b)
    mids = [float(transitions.zoom_blur(a, b, w, (30, 20), (30, 20)).mean()) for w in (0.2, 0.5, 0.8)]
    assert mids == sorted(mids)
