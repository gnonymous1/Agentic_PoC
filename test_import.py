import sys
print(f"Python: {sys.version}")
print(f"Executable: {sys.executable}")
print("Importing pydantic...")
import pydantic
print(f"Pydantic file: {pydantic.__file__}")
print(f"Pydantic version: {pydantic.VERSION}")

print("Importing chromadb...")
import chromadb
print("Chroma imported")
