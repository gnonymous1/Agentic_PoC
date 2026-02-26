from langchain_core.tools import tool

@tool
def say_hello() -> None:
    """Prints 'Hello World' to the console."""
    print("Hello World")