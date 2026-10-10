"""
icons.py
--------
Central repository for application icons.

Self-contained inline SVG rendering:
- Zero external CDN dependencies (eliminates unpkg downtime / adblocker / CORS blocks)
- Fully themeable via pure SVG attributes (stroke="{color}", fill="none")
- 100% reliable rendering across all platforms, OS, and network environments
"""

from __future__ import annotations

import re

# Pre-compiled, local SVG element definitions for all Lucide icons used in the app
_SVG_PATHS: dict[str, str] = {
    "alert-circle": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <line x1=\"12\" x2=\"12\" y1=\"8\" y2=\"12\" /> <line x1=\"12\" x2=\"12.01\" y1=\"16\" y2=\"16\" />",
    "alert-triangle": "<path d=\"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3\" /> <path d=\"M12 9v4\" /> <path d=\"M12 17h.01\" />",
    "award": "<path d=\"m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526\" /> <circle cx=\"12\" cy=\"8\" r=\"6\" />",
    "book": "<path d=\"M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20\" />",
    "book-open": "<path d=\"M12 7v14\" /> <path d=\"M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z\" />",
    "building": "<path d=\"M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z\" /> <path d=\"M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2\" /> <path d=\"M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2\" /> <path d=\"M10 6h4\" /> <path d=\"M10 10h4\" /> <path d=\"M10 14h4\" /> <path d=\"M10 18h4\" />",
    "building-2": "<path d=\"M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z\" /> <path d=\"M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2\" /> <path d=\"M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2\" /> <path d=\"M10 6h4\" /> <path d=\"M10 10h4\" /> <path d=\"M10 14h4\" /> <path d=\"M10 18h4\" />",
    "calendar": "<path d=\"M8 2v4\" /> <path d=\"M16 2v4\" /> <rect width=\"18\" height=\"18\" x=\"3\" y=\"4\" rx=\"2\" /> <path d=\"M3 10h18\" />",
    "chart-bar": "<path d=\"M3 3v16a2 2 0 0 0 2 2h16\" /> <path d=\"M7 16h8\" /> <path d=\"M7 11h12\" /> <path d=\"M7 6h3\" />",
    "chart-pie": "<path d=\"M21 12c.552 0 1.005-.449.95-.998a10 10 0 0 0-8.953-8.951c-.55-.055-.998.398-.998.95v8a1 1 0 0 0 1 1z\" /> <path d=\"M21.21 15.89A10 10 0 1 1 8 2.83\" />",
    "check": "<path d=\"M20 6 9 17l-5-5\" />",
    "check-circle": "<path d=\"M21.801 10A10 10 0 1 1 17 3.335\" /> <path d=\"m9 11 3 3L22 4\" />",
    "chevron-down": "<path d=\"m6 9 6 6 6-6\" />",
    "chevron-right": "<path d=\"m9 18 6-6-6-6\" />",
    "circle-alert": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <line x1=\"12\" x2=\"12\" y1=\"8\" y2=\"12\" /> <line x1=\"12\" x2=\"12.01\" y1=\"16\" y2=\"16\" />",
    "circle-check-big": "<path d=\"M21.801 10A10 10 0 1 1 17 3.335\" /> <path d=\"m9 11 3 3L22 4\" />",
    "circle-dot": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <circle cx=\"12\" cy=\"12\" r=\"1\" />",
    "circle-plus": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M8 12h8\" /> <path d=\"M12 8v8\" />",
    "clipboard-list": "<rect width=\"8\" height=\"4\" x=\"8\" y=\"2\" rx=\"1\" ry=\"1\" /> <path d=\"M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2\" /> <path d=\"M12 11h4\" /> <path d=\"M12 16h4\" /> <path d=\"M8 11h.01\" /> <path d=\"M8 16h.01\" />",
    "clock": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <polyline points=\"12 6 12 12 16 14\" />",
    "cpu": "<rect width=\"16\" height=\"16\" x=\"4\" y=\"4\" rx=\"2\" /> <rect width=\"6\" height=\"6\" x=\"9\" y=\"9\" rx=\"1\" /> <path d=\"M15 2v2\" /> <path d=\"M15 20v2\" /> <path d=\"M2 15h2\" /> <path d=\"M2 9h2\" /> <path d=\"M20 15h2\" /> <path d=\"M20 9h2\" /> <path d=\"M9 2v2\" /> <path d=\"M9 20v2\" />",
    "download": "<path d=\"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\" /> <polyline points=\"7 10 12 15 17 10\" /> <line x1=\"12\" x2=\"12\" y1=\"15\" y2=\"3\" />",
    "edit": "<path d=\"M12 20h9\" /> <path d=\"M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z\" />",
    "eye": "<path d=\"M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0\" /> <circle cx=\"12\" cy=\"12\" r=\"3\" />",
    "factory": "<path d=\"M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z\" /> <path d=\"M17 18h1\" /> <path d=\"M12 18h1\" /> <path d=\"M7 18h1\" />",
    "file-text": "<path d=\"M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z\" /> <path d=\"M14 2v4a2 2 0 0 0 2 2h4\" /> <path d=\"M10 9H8\" /> <path d=\"M16 13H8\" /> <path d=\"M16 17H8\" />",
    "flask-conical": "<path d=\"M10 2v7.527a2 2 0 0 1-.211.896L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45l-5.069-10.127A2 2 0 0 1 14 9.527V2\" /> <path d=\"M8.5 2h7\" /> <path d=\"M7 16h10\" />",
    "folder": "<path d=\"M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z\" />",
    "folder-open": "<path d=\"m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2\" />",
    "frown": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M16 16s-1.5-2-4-2-4 2-4 2\" /> <line x1=\"9\" x2=\"9.01\" y1=\"9\" y2=\"9\" /> <line x1=\"15\" x2=\"15.01\" y1=\"9\" y2=\"9\" />",
    "git-branch": "<line x1=\"6\" x2=\"6\" y1=\"3\" y2=\"15\" /> <circle cx=\"18\" cy=\"6\" r=\"3\" /> <circle cx=\"6\" cy=\"18\" r=\"3\" /> <path d=\"M18 9a9 9 0 0 1-9 9\" />",
    "git-merge": "<circle cx=\"18\" cy=\"18\" r=\"3\" /> <circle cx=\"6\" cy=\"6\" r=\"3\" /> <path d=\"M6 21V9a9 9 0 0 0 9 9\" />",
    "graduation-cap": "<path d=\"M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z\" /> <path d=\"M22 10v6\" /> <path d=\"M6 12.5V16a6 3 0 0 0 12 0v-3.5\" />",
    "hand": "<path d=\"M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2\" /> <path d=\"M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2\" /> <path d=\"M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8\" /> <path d=\"M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15\" />",
    "hand-wave": "<path d=\"M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2\" /> <path d=\"M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2\" /> <path d=\"M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8\" /> <path d=\"M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15\" />",
    "heart": "<path d=\"M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z\" />",
    "house": "<path d=\"M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8\" /> <path d=\"M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z\" />",
    "inbox": "<polyline points=\"22 12 16 12 14 15 10 15 8 12 2 12\" /> <path d=\"M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z\" />",
    "info": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M12 16v-4\" /> <path d=\"M12 8h.01\" />",
    "key": "<path d=\"m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4\" /> <path d=\"m21 2-9.6 9.6\" /> <circle cx=\"7.5\" cy=\"15.5\" r=\"5.5\" />",
    "layout-dashboard": "<rect width=\"7\" height=\"9\" x=\"3\" y=\"3\" rx=\"1\" /> <rect width=\"7\" height=\"5\" x=\"14\" y=\"3\" rx=\"1\" /> <rect width=\"7\" height=\"9\" x=\"14\" y=\"12\" rx=\"1\" /> <rect width=\"7\" height=\"5\" x=\"3\" y=\"16\" rx=\"1\" />",
    "lightbulb": "<path d=\"M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5\" /> <path d=\"M9 18h6\" /> <path d=\"M10 22h4\" />",
    "list": "<path d=\"M3 12h.01\" /> <path d=\"M3 18h.01\" /> <path d=\"M3 6h.01\" /> <path d=\"M8 12h13\" /> <path d=\"M8 18h13\" /> <path d=\"M8 6h13\" />",
    "list-checks": "<path d=\"m3 17 2 2 4-4\" /> <path d=\"m3 7 2 2 4-4\" /> <path d=\"M13 6h8\" /> <path d=\"M13 12h8\" /> <path d=\"M13 18h8\" />",
    "lock": "<rect width=\"18\" height=\"11\" x=\"3\" y=\"11\" rx=\"2\" ry=\"2\" /> <path d=\"M7 11V7a5 5 0 0 1 10 0v4\" />",
    "log-in": "<path d=\"M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4\" /> <polyline points=\"10 17 15 12 10 7\" /> <line x1=\"15\" x2=\"3\" y1=\"12\" y2=\"12\" />",
    "log-out": "<path d=\"M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4\" /> <polyline points=\"16 17 21 12 16 7\" /> <line x1=\"21\" x2=\"9\" y1=\"12\" y2=\"12\" />",
    "mail": "<rect width=\"20\" height=\"16\" x=\"2\" y=\"4\" rx=\"2\" /> <path d=\"m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7\" />",
    "map-pin": "<path d=\"M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0\" /> <circle cx=\"12\" cy=\"10\" r=\"3\" />",
    "meh": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <line x1=\"8\" x2=\"16\" y1=\"15\" y2=\"15\" /> <line x1=\"9\" x2=\"9.01\" y1=\"9\" y2=\"9\" /> <line x1=\"15\" x2=\"15.01\" y1=\"9\" y2=\"9\" />",
    "message-circle": "<path d=\"M7.9 20A9 9 0 1 0 4 16.1L2 22Z\" />",
    "microscope": "<path d=\"M6 18h8\" /> <path d=\"M3 22h18\" /> <path d=\"M14 22a7 7 0 1 0 0-14h-1\" /> <path d=\"M9 14h2\" /> <path d=\"M9 12a2 2 0 0 1-2-2V6h6v4a2 2 0 0 1-2 2Z\" /> <path d=\"M12 6V3a1 1 0 0 0-1-1H9a1 1 0 0 0-1 1v3\" />",
    "pen-line": "<path d=\"M12 20h9\" /> <path d=\"M16.376 3.622a1 1 0 0 1 3.002 3.002L7.368 18.635a2 2 0 0 1-.855.506l-2.872.838a.5.5 0 0 1-.62-.62l.838-2.872a2 2 0 0 1 .506-.854z\" />",
    "pie-chart": "<path d=\"M21 12c.552 0 1.005-.449.95-.998a10 10 0 0 0-8.953-8.951c-.55-.055-.998.398-.998.95v8a1 1 0 0 0 1 1z\" /> <path d=\"M21.21 15.89A10 10 0 1 1 8 2.83\" />",
    "plus-circle": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M8 12h8\" /> <path d=\"M12 8v8\" />",
    "presentation": "<path d=\"M2 3h20\" /> <path d=\"M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3\" /> <path d=\"m7 21 5-5 5 5\" />",
    "radar": "<path d=\"M19.07 4.93A10 10 0 0 0 6.99 3.34\" /> <path d=\"M4 6h.01\" /> <path d=\"M2.29 9.62A10 10 0 1 0 21.31 8.35\" /> <path d=\"M16.24 7.76A6 6 0 1 0 8.23 16.67\" /> <path d=\"M12 18h.01\" /> <path d=\"M17.99 11.66A6 6 0 0 1 15.77 16.67\" /> <circle cx=\"12\" cy=\"12\" r=\"2\" /> <path d=\"m13.41 10.59 5.66-5.66\" />",
    "refresh-cw": "<path d=\"M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8\" /> <path d=\"M21 3v5h-5\" /> <path d=\"M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16\" /> <path d=\"M8 16H3v5\" />",
    "rocket": "<path d=\"M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z\" /> <path d=\"m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z\" /> <path d=\"M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0\" /> <path d=\"M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5\" />",
    "search": "<circle cx=\"11\" cy=\"11\" r=\"8\" /> <path d=\"m21 21-4.3-4.3\" />",
    "send": "<path d=\"M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z\" /> <path d=\"m21.854 2.147-10.94 10.939\" />",
    "settings": "<path d=\"M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z\" /> <circle cx=\"12\" cy=\"12\" r=\"3\" />",
    "shield": "<path d=\"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z\" />",
    "shield-check": "<path d=\"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z\" /> <path d=\"m9 12 2 2 4-4\" />",
    "shuffle": "<path d=\"m18 14 4 4-4 4\" /> <path d=\"m18 2 4 4-4 4\" /> <path d=\"M2 18h1.973a4 4 0 0 0 3.3-1.7l5.454-8.6a4 4 0 0 1 3.3-1.7H22\" /> <path d=\"M2 6h1.972a4 4 0 0 1 3.6 2.2\" /> <path d=\"M22 18h-6.041a4 4 0 0 1-3.3-1.8l-.359-.45\" />",
    "siren": "<path d=\"M7 18v-6a5 5 0 1 1 10 0v6\" /> <path d=\"M5 21a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2z\" /> <path d=\"M21 12h1\" /> <path d=\"M18.5 4.5 18 5\" /> <path d=\"M2 12h1\" /> <path d=\"M12 2v1\" /> <path d=\"m4.929 4.929.707.707\" /> <path d=\"M12 12v6\" />",
    "slash": "<path d=\"M22 2 2 22\" />",
    "smile": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M8 14s1.5 2 4 2 4-2 4-2\" /> <line x1=\"9\" x2=\"9.01\" y1=\"9\" y2=\"9\" /> <line x1=\"15\" x2=\"15.01\" y1=\"9\" y2=\"9\" />",
    "sparkles": "<path d=\"M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z\" /> <path d=\"M20 3v4\" /> <path d=\"M22 5h-4\" /> <path d=\"M4 17v2\" /> <path d=\"M5 18H3\" />",
    "star": "<path d=\"M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z\" />",
    "table": "<path d=\"M12 3v18\" /> <rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M3 9h18\" /> <path d=\"M3 15h18\" />",
    # The audit trail's delete glyph. It was being requested by name with no entry
    # here, so `icon()` fell through to its deliberate "unknown icon" placeholder
    # and every deleted-account row rendered a warning circle instead of a bin.
    # The call site hid it because the name lived in a variable the checker could
    # not follow; naming the icon inline made it visible.
    "trash-2": "<path d=\"M3 6h18\" /> <path d=\"M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6\" /> <path d=\"M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2\" /> <line x1=\"10\" x2=\"10\" y1=\"11\" y2=\"17\" /> <line x1=\"14\" x2=\"14\" y1=\"11\" y2=\"17\" />",
    "target": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <circle cx=\"12\" cy=\"12\" r=\"6\" /> <circle cx=\"12\" cy=\"12\" r=\"2\" />",
    "thumbs-up": "<path d=\"M7 10v12\" /> <path d=\"M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z\" />",
    "trending-down": "<polyline points=\"22 17 13.5 8.5 8.5 13.5 2 7\" /> <polyline points=\"16 17 22 17 22 11\" />",
    "trending-up": "<polyline points=\"22 7 13.5 15.5 8.5 10.5 2 17\" /> <polyline points=\"16 7 22 7 22 13\" />",
    "triangle-alert": "<path d=\"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3\" /> <path d=\"M12 9v4\" /> <path d=\"M12 17h.01\" />",
    "user": "<path d=\"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2\" /> <circle cx=\"12\" cy=\"7\" r=\"4\" />",
    "user-cog": "<circle cx=\"18\" cy=\"15\" r=\"3\" /> <circle cx=\"9\" cy=\"7\" r=\"4\" /> <path d=\"M10 15H6a4 4 0 0 0-4 4v2\" /> <path d=\"m21.7 16.4-.9-.3\" /> <path d=\"m15.2 13.9-.9-.3\" /> <path d=\"m16.6 18.7.3-.9\" /> <path d=\"m19.1 12.2.3-.9\" /> <path d=\"m19.6 18.7-.4-1\" /> <path d=\"m16.8 12.3-.4-1\" /> <path d=\"m14.3 16.6 1-.4\" /> <path d=\"m20.7 13.8 1-.4\" />",
    "users": "<path d=\"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2\" /> <circle cx=\"9\" cy=\"7\" r=\"4\" /> <path d=\"M22 21v-2a4 4 0 0 0-3-3.87\" /> <path d=\"M16 3.13a4 4 0 0 1 0 7.75\" />",
    "wifi": "<path d=\"M12 20h.01\" /> <path d=\"M2 8.82a15 15 0 0 1 20 0\" /> <path d=\"M5 12.859a10 10 0 0 1 14 0\" /> <path d=\"M8.5 16.429a5 5 0 0 1 7 0\" />",
    "wrench": "<path d=\"M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z\" />",
    "x": "<path d=\"M18 6 6 18\" /> <path d=\"m6 6 12 12\" />",
    "zap": "<path d=\"M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z\" />",
}

# Semantic name -> Lucide slug. Add new names here, use i("name") everywhere else.
ICN = {
    "home": "house", "course": "book-open", "teaching": "presentation",
    "facilities": "building-2", "curriculum": "clipboard-list",
    "dashboard": "layout-dashboard", "search": "search", "target": "target",
    "star": "star", "users": "users", "user": "user", "user-cog": "user-cog",
    "settings": "settings", "logout": "log-out", "login": "log-in",
    "lock": "lock", "key": "key", "mail": "mail", "calendar": "calendar",
    "check": "check", "check-circle": "circle-check-big", "x": "x",
    "clock": "clock", "alert-triangle": "triangle-alert", "alert-circle": "circle-alert",
    "info": "info", "smile": "smile", "frown": "frown", "meh": "meh",
    "trending-up": "trending-up", "trending-down": "trending-down",
    "folder": "folder", "folder-open": "folder-open", "lightbulb": "lightbulb",
    "flask": "flask-conical", "rocket": "rocket", "refresh": "refresh-cw",
    "wrench": "wrench", "map-pin": "map-pin", "siren": "siren", "factory": "factory",
    "heart": "heart", "message": "message-circle", "sparkles": "sparkles",
    "award": "award", "file-text": "file-text", "list-checks": "list-checks",
    "clipboard-list": "clipboard-list",
    "chevron-right": "chevron-right", "chevron-down": "chevron-down",
    "graduation-cap": "graduation-cap",
    "bar-chart": "chart-bar", "pie-chart": "chart-pie", "radar": "radar",
    "shield-check": "shield-check", "wifi": "wifi", "send": "send",
    "inbox": "inbox", "edit": "pen-line", "plus-circle": "circle-plus",
    "thumbs-up": "thumbs-up", "download": "download", "eye": "eye",
    "book": "book", "microscope": "microscope", "building": "building-2",
    "shuffle": "shuffle", "circle-dot": "circle-dot", "hand-wave": "hand",
    "shield": "shield", "cpu": "cpu", "list": "list", "git-branch": "git-branch",
    "git-merge": "git-merge", "slash": "slash", "zap": "zap", "table": "table",
    "trash": "trash-2",
}


_SIZE_RE = re.compile(r"^\d{1,3}$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$|^rgba?\(\s*[\d.\s,%/]+\)$|^hsla?\(.*\)$|^currentColor$|^none$")
# Permissive for CSS declarations but structurally incapable of closing the
# attribute: no quote characters and no angle brackets can appear.
_STYLE_RE = re.compile(r"^[A-Za-z0-9_\-.%#(),/:; ]+$")
_RADIUS_RE = re.compile(r"^\d{1,3}(?:\.\d{1,2})?(?:px|em|rem|%|pt)?$")


def _safe_attr(value, pattern, fallback: str) -> str:
    """Returns `value` only if it matches `pattern`, else `fallback`.

    `icon()` interpolates `color`, `size` and `style` straight into an
    `unsafe_allow_html` SVG string. `color` and `style` reach it from
    user-influenced places — `sentiment_color()` and inline palette lookups
    fed by a DataFrame value — so a stray quote or `</style>` closed the
    attribute early and let arbitrary markup into the page. Anything that does
    not look like the thing it claims to be is replaced rather than escaped:
    a broken colour is not worth rendering.
    """
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if pattern.match(text) and '"' not in text and "'" not in text and "<" not in text:
        return text
    return fallback


def icon(slug: str, size: int = 18, color: str = "currentColor", style: str = "") -> str:
    """Renders pure inline SVG for any Lucide icon with complete themeability and zero network dependencies."""
    inner = _SVG_PATHS.get(slug) or _SVG_PATHS.get(ICN.get(slug, slug), "")
    if not inner:
        # Deliberately visible: an unknown icon name is a programming error, and
        # the old silent fallback made a wrong `i("some-typo")` look like a
        # working icon for as long as nobody compared it against the design.
        inner = ('<circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="12"/>'
                 '<line x1="12" y1="16" x2="12.01" y2="16"/>')

    size = _safe_attr(size, _SIZE_RE, "18")
    color = _safe_attr(color, _COLOR_RE, "currentColor")
    style_attr = f' style="{_safe_attr(style, _STYLE_RE, "")}"' if style else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" class="lc-ico"{style_attr}>{inner}</svg>'
    )


def icon_badge(slug: str, size: int = 22, bg: str = "rgba(59,130,246,.15)",
               color: str = "#2563eb", radius: str = "12px", box: int = 44) -> str:
    """A rounded, tinted square/circle containing a centered inline SVG icon."""
    return (
        f'<div style="width:{_safe_attr(box, _SIZE_RE, "44")}px;'
        f'height:{_safe_attr(box, _SIZE_RE, "44")}px;'
        f'border-radius:{_safe_attr(radius, _RADIUS_RE, "12px")};'
        f'background:{_safe_attr(bg, _COLOR_RE, "rgba(59,130,246,.15)")};'
        f'display:flex;align-items:center;justify-content:center;'
        f'flex-shrink:0;">{icon(slug, size, color)}</div>'
    )


def missing_icon_names() -> list[str]:
    """Every `ICN` alias whose target slug has no inlined path.

    Run this after adding to `ICN` to catch an alias that points at a slug
    nobody copied into `_SVG_PATHS` — otherwise the icon renders as the
    "unknown" glyph at runtime with nothing in the logs.
    """
    missing = []
    for alias, slug in ICN.items():
        if slug not in _SVG_PATHS and not alias.startswith("_"):
            missing.append(f"{alias} -> {slug}")
    return sorted(missing)


def i(name: str, size: int = 18, color: str = "currentColor", style: str = "") -> str:
    """Semantic icon lookup — the primary function called throughout the application."""
    return icon(ICN.get(name, name), size, color, style)


def sentiment_icon(sentiment: str) -> str:
    return {"Positive": "smile", "Negative": "frown", "Neutral": "meh"}.get(sentiment, "meh")


def sentiment_color(sentiment: str) -> str:
    """Colour for a sentiment glyph.

    These are non-text graphics, so WCAG 1.4.11 sets the floor at 3:1 against
    the surrounding surface, not the 4.5:1 that applies to text. On white all
    three here clear it: green `#059669` 3.77:1, gold `#d97706` 3.19:1, red
    `#dc2626` 4.83:1.

    The unknown-sentiment fallback used to be `#94a3b8`, the app's documented
    *decorative* grey, which only reaches 2.56:1 and so failed the floor for
    exactly the one case where nothing else had been decided. It is now
    `#64748b` (`--text-3`) — the same hue family one step darker, at 4.76:1.
    """
    return {"Positive": "#059669", "Negative": "#dc2626", "Neutral": "#d97706"}.get(sentiment, "#64748b")
