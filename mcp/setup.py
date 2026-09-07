from setuptools import setup

setup(
    name="gmail-mcp",
    version="0.0.1",
    py_modules=["gmail_mcp_server"],
    install_requires=["gmail_parser"],
    entry_points={
        "console_scripts": ["gmail-mcp-server = gmail_mcp_server:main"]
    },
)
