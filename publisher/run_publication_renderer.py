#!/usr/bin/env python3
"""Entrypoint for the social publication renderer.

social-engine-daily.yml remains the workflow/orchestrator.
F1 graphic generation lives in publisher/f1_premium_renderer.py.
Real Media Pro remains handled by render_photos_only.py.
"""

import render_photos_only as renderer
import f1_premium_renderer as f1

f1.install()

if __name__ == "__main__":
    rc = renderer.main()
    if rc not in (None, 0):
        raise SystemExit(rc)
    f1.validate_f1_outputs()
    raise SystemExit(0)
