"""Bundled TypeScript / Ink frontend.

The build script copies ``ui-tui/dist/bundle.js`` into this package so the
launcher can locate it via ``importlib.resources``. The bundle itself is
not a Python module; this file exists only to make the directory a
package.
"""
