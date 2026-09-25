"""``python -m Imervue.mcp_server`` entry point."""
from Imervue.mcp_server.server import run
from Imervue.system.pixel_limit import raise_pixel_limit

if __name__ == "__main__":
    raise_pixel_limit()   # a panorama past Pillow's server limit can be read too
    run()
