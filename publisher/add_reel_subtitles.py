#!/usr/bin/env python3
"""Legacy subtitle step intentionally disabled.

Real Media Pro rule: Reel exports must not contain burned subtitles.
The only on-screen text is the large hook/title created by the renderer.
This file remains as a harmless compatibility stub in case an old command calls it.
"""


def main() -> int:
    print("Subtitle burning disabled: no Reel files modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
