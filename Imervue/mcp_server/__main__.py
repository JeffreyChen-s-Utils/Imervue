"""``python -m Imervue.mcp_server`` entry point."""
from Imervue.mcp_server.server import run
from Imervue.system.pillow_setup import configure_pillow

if __name__ == "__main__":
    configure_pillow()   # a giant panorama and a file cut short can be read too
    run()
