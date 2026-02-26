from langchain_core.tools import tool
from typing import Annotated, Dict, Any
import json
import requests
from bs4 import BeautifulSoup

@tool
def analyze_csv(filepath: Annotated[str, "Path to CSV file"]) -> str:
    """Analyzes a CSV file and provides summary statistics (mock pandas)."""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()

        if not lines:
            return "Empty file"

        header = lines[0].strip().split(',')
        row_count = len(lines) - 1

        return f"CSV Analysis:\nRows: {row_count}\nColumns: {len(header)}\nHeaders: {', '.join(header)}"
    except Exception as e:
        return f"Analysis failed: {str(e)}"

@tool
def web_scrape(url: Annotated[str, "URL to scrape"]) -> str:
    """Extracts text content from a webpage."""
    try:
        headers = {'User-Agent': 'AgentOS/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text()

        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)

        return text[:5000] + ("\n...[truncated]" if len(text) > 5000 else "")

    except Exception as e:
        return f"Scraping failed: {str(e)}"
