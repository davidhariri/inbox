import logging

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")

from inbox.server import create_server

mcp = create_server()

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
