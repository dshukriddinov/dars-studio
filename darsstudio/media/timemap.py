"""TimeMap (TZ 9.5, D-03): asl kadr indekslari <-> chiqish kadr indekslari. Hammasi butun son / Fraction.

keep_ranges: saqlanadigan asl kadr oraliqlari [start, end). Chiqishda ular ketma-ket yopishtiriladi.
"""

import bisect
from collections.abc import Iterable
from fractions import Fraction

AUDIO_RATE = 48000


class TimeMap:
    def __init__(self, keep_ranges: Iterable[tuple[int, int]], fps: Fraction, audio_rate: int = AUDIO_RATE) -> None:
        merged: list[list[int]] = []
        for s, e in sorted((int(s), int(e)) for s, e in keep_ranges):
            if s < 0 or e < s:
                raise ValueError(f"noto'g'ri oraliq [{s}, {e})")
            if s == e:
                continue
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        self.ranges: list[tuple[int, int]] = [(s, e) for s, e in merged]
        self.fps = Fraction(fps)
        self.audio_rate = audio_rate
        self._starts = [s for s, _ in self.ranges]
        self._out_starts: list[int] = []
        acc = 0
        for s, e in self.ranges:
            self._out_starts.append(acc)
            acc += e - s
        self.out_total = acc

    @classmethod
    def from_cuts(cls, total: int, cuts: Iterable[tuple[int, int]], fps: Fraction) -> "TimeMap":
        """total kadrdan cuts (olib tashlanadigan [s, e)) chiqarilgan TimeMap."""
        keep, pos = [], 0

        def clip(x: int) -> int:
            return min(max(0, x), total)

        for s, e in sorted((clip(s), clip(e)) for s, e in cuts):
            if e <= s:
                continue
            if s > pos:
                keep.append((pos, s))
            pos = max(pos, e)
        if pos < total:
            keep.append((pos, total))
        return cls(keep, fps)

    def src_to_out(self, f: int) -> int | None:
        """Asl kadr -> chiqish kadri; kesilgan bo'lsa None."""
        i = bisect.bisect_right(self._starts, f) - 1
        if i < 0:
            return None
        s, e = self.ranges[i]
        return self._out_starts[i] + (f - s) if f < e else None

    def out_to_src(self, g: int) -> int:
        if not 0 <= g < self.out_total:
            raise IndexError(f"chiqish kadri {g} [0, {self.out_total}) dan tashqarida")
        i = bisect.bisect_right(self._out_starts, g) - 1
        return self.ranges[i][0] + (g - self._out_starts[i])

    def map_span(self, s: int, e: int) -> list[tuple[int, int]]:
        """Asl [s, e) ning saqlangan qismlari chiqishda. Chiqish uzluksiz, shuning uchun qo'shnilar birlashtiriladi."""
        out: list[tuple[int, int]] = []
        for (rs, re), o in zip(self.ranges, self._out_starts, strict=True):
            a, b = max(s, rs), min(e, re)
            if a < b:
                span = (o + a - rs, o + b - rs)
                if out and out[-1][1] == span[0]:
                    out[-1] = (out[-1][0], span[1])
                else:
                    out.append(span)
        return out

    def audio_sample(self, f: int) -> int:
        """Kadr chegarasining audio namuna indeksi: round(f * rate / fps), Fraction bilan (TZ 8.1)."""
        return round(Fraction(f) * self.audio_rate / self.fps)

    def out_seconds(self, g: int) -> Fraction:
        return Fraction(g) / self.fps

    def audio_ranges(self) -> list[tuple[int, int]]:
        """Saqlanadigan oraliqlar audio namunalarida (kesish nuqtalari kadr chegarasida)."""
        return [(self.audio_sample(s), self.audio_sample(e)) for s, e in self.ranges]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TimeMap) and (self.ranges, self.fps) == (other.ranges, other.fps)

    def __repr__(self) -> str:
        return f"TimeMap({self.ranges}, fps={self.fps})"
