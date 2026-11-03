"""Automatic time over Wi-Fi: the pinned string-literal edits in demo (docs/modules/autotime.md).

Stock already syncs the clock (AUTOSYNCTIME, networktime_adjust_thd 0x4d92bc). As in q2-pod
(RTC_WRITE, `hwclock -wu`) the RTC is kept as UTC; the boot read is changed to match. Two NUL-padded
literals are overwritten in place with text of the same slot length, after checking the stock bytes.
No code word changes.
"""

# (address, stock slot bytes, new slot bytes, what); a slot runs to the next string, so len(old) == len(new)
EDITS = (
    (0x756f7c, b'hwclock -s\0\0', b'hwclock -su\0', 'toolsGetRtcTime (boot): read the RTC as UTC'),
    (0x756fa4, b'hwclock -w\0\0', b'hwclock -wu\0', 'toolsSetRtcTime: write the RTC as UTC (q2-pod RTC_WRITE)'),
)
# neighbours that must stay as they are: the next literal of each slot
NEIGHBOURS = (
    (0x756f88, b'date -s "%d-%d-%d %d:%d:%d"\0'), (0x756fb0, b'/sys/devices/platform/md_i2c_gpio.5'),
)


def apply(patched, fileoff):
    """Check every stock slot and its next literal in the bytearray `patched`, then write the new text."""
    for a, old, new, what in EDITS:
        assert len(old) == len(new), what
        o = fileoff(patched, a)
        if bytes(patched[o:o + len(old)]) != old:
            raise ValueError(f'{a:#x} ({what}): {bytes(patched[o:o + len(old)])!r} != pinned {old!r}')
    for a, text in NEIGHBOURS:
        o = fileoff(patched, a)
        if bytes(patched[o:o + len(text)]) != text:
            raise ValueError(f'{a:#x}: neighbouring literal {bytes(patched[o:o + len(text)])!r} != pinned {text!r}')
    for a, old, new, what in EDITS:
        o = fileoff(patched, a)
        patched[o:o + len(new)] = new
